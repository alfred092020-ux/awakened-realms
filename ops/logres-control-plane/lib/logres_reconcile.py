from __future__ import annotations

import json
import sqlite3
import subprocess
from dataclasses import dataclass

from logres_ai_common import brain_post_dedupe_key
from logres_ai_runner import budget_state
from logres_copilot import CopilotJobRecord
from logres_copilot_router import reconcile_copilot_job
from logres_route_store import (
    TERMINAL_STATES,
    RouteJob,
    append_decision,
    ensure_route_schema,
    transition_route,
)


@dataclass(frozen=True)
class RouteRecoveryResult:
    route_job_id: int
    state: str
    task_id: str | None
    route_kind: str
    issue_number: int | None = None
    candidate_sha: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class BackpressureState:
    copilot_paused: bool
    ai_research_paused: bool
    ready_for_integration: int
    verification_backlog: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class RouteStatus:
    cursor: int
    lag: int
    active: int
    failed: int
    ai_active: int
    cache_hits: int
    budget: str
    copilot_active: int
    copilot_queued: int
    copilot_prs: int
    backpressure: BackpressureState


def _job_from_row(row) -> RouteJob:
    return RouteJob(
        id=int(row["id"]),
        dedupe_key=row["dedupe_key"],
        source_event_id=row["source_event_id"],
        task_id=row["task_id"],
        route_kind=row["route_kind"],
        state=row["state"],
        attempt_count=int(row["attempt_count"] or 0),
        artifact_sha=row["artifact_sha"],
        question_sha=row["question_sha"],
        base_sha=row["base_sha"],
        external_ref=row["external_ref"],
        parent_route_id=row["parent_route_id"],
        resolution_type=row["resolution_type"],
        last_error=row["last_error"],
        meta_json=row["meta_json"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _copilot_job_from_row(row) -> CopilotJobRecord:
    return CopilotJobRecord(
        id=int(row["id"]),
        route_job_id=int(row["route_job_id"]),
        task_id=row["task_id"],
        issue_number=row["issue_number"],
        pr_number=row["pr_number"],
        branch=row["branch"],
        base_sha=row["base_sha"],
        candidate_sha=row["candidate_sha"],
        state=row["state"],
        last_error=row["last_error"],
    )


def backpressure(conn: sqlite3.Connection, config: dict) -> BackpressureState:
    ensure_route_schema(conn)
    thresholds = config.get("backpressure", {})
    ready_limit = int(thresholds.get("ready_for_integration", 4))
    verify_limit = int(thresholds.get("verification_backlog", 3))

    ready = int(
        conn.execute(
            "select count(*) from integration_queue where status='READY_FOR_INTEGRATION'"
        ).fetchone()[0]
    )
    verifying = int(
        conn.execute(
            "select count(*) from route_jobs where state='VERIFYING'"
        ).fetchone()[0]
    )

    reasons: list[str] = []
    if ready > ready_limit:
        reasons.append(f"integration-ready backlog {ready}/{ready_limit}")
    if verifying > verify_limit:
        reasons.append(f"verification backlog {verifying}/{verify_limit}")

    return BackpressureState(
        copilot_paused=bool(reasons),
        ai_research_paused=False,
        ready_for_integration=ready,
        verification_backlog=verifying,
        reasons=tuple(reasons),
    )


def _task_status(conn: sqlite3.Connection, task_id: str | None) -> str | None:
    if not task_id:
        return None
    row = conn.execute("select status from tasks where id=?", (task_id,)).fetchone()
    return None if row is None else str(row[0])


def _close_superseded(
    conn: sqlite3.Connection,
    route: RouteJob,
) -> RouteRecoveryResult | None:
    status = _task_status(conn, route.task_id)
    if status not in {"SUPERSEDED", "CANCELLED"}:
        return None
    if route.state in TERMINAL_STATES:
        return RouteRecoveryResult(
            route.id, route.state, route.task_id, route.route_kind,
            reason=f"task already {status}",
        )

    if route.state in {"ACTIVE", "PR_READY"}:
        transition_route(conn, route.id, route.state, "SUPERSEDED")
    else:
        conn.execute(
            "update route_jobs set state='SUPERSEDED',updated_at=datetime('now') where id=?",
            (route.id,),
        )
        conn.commit()

    conn.execute(
        """update copilot_jobs
              set state='SUPERSEDED',updated_at=datetime('now')
            where route_job_id=? and state not in
                  ('QUEUED','SUPERSEDED','SCOPE_VIOLATION','FAILED_BOUNDED')""",
        (route.id,),
    )
    conn.commit()
    append_decision(
        conn,
        route.id,
        "ROUTE_SUPERSEDED",
        f"parent task state is {status}; no external work resumed",
        task_id=route.task_id,
    )
    return RouteRecoveryResult(
        route.id,
        "SUPERSEDED",
        route.task_id,
        route.route_kind,
        reason=f"task {status.lower()}",
    )


def _recover_ai(
    conn: sqlite3.Connection,
    route: RouteJob,
    ai_cache,
) -> RouteRecoveryResult | None:
    if route.state not in {"AI_RUNNING", "AI_VALIDATED", "BRAIN_POSTED"}:
        return None

    if route.state == "BRAIN_POSTED":
        return RouteRecoveryResult(
            route.id,
            "BRAIN_POSTED",
            route.task_id,
            route.route_kind,
            reason="Brain post already durable",
        )

    record = ai_cache.recover(conn, route)
    if record is None:
        return None

    if route.state == "AI_RUNNING":
        route = transition_route(conn, route.id, "AI_RUNNING", "AI_VALIDATED")
        append_decision(
            conn,
            route.id,
            "AI_CACHE_RECOVERED",
            "completed ai_runs result recovered after crash",
            task_id=route.task_id,
        )

    ai_cache.ensure_brain_post(route, record)
    route = transition_route(conn, route.id, "AI_VALIDATED", "BRAIN_POSTED")
    append_decision(
        conn,
        route.id,
        "BRAIN_POST_RECOVERED",
        "cached AI result posted/reconciled without another API call",
        task_id=route.task_id,
    )
    return RouteRecoveryResult(
        route.id,
        "BRAIN_POSTED",
        route.task_id,
        route.route_kind,
        reason="cached AI result recovered",
    )


def _safe_copilot_branch(task_id: str) -> str:
    import re

    slug = re.sub(r"[^a-z0-9._-]+", "-", task_id.lower()).strip("-") or "task"
    return f"copilot/{slug}"


def _recover_copilot_assignment(
    conn: sqlite3.Connection,
    route: RouteJob,
    github,
) -> RouteRecoveryResult | None:
    if route.state != "ASSIGNING" or not route.task_id:
        return None

    existing = conn.execute(
        "select * from copilot_jobs where route_job_id=?",
        (route.id,),
    ).fetchone()
    if existing is not None:
        job = _copilot_job_from_row(existing)
        return RouteRecoveryResult(
            route.id,
            job.state,
            route.task_id,
            route.route_kind,
            issue_number=job.issue_number,
            candidate_sha=job.candidate_sha,
            reason="existing Copilot job already durable",
        )

    search = getattr(github, "search_issue", None)
    if search is None:
        return None
    issue = search(route.task_id)
    if not issue:
        return None

    issue_number = int(issue["number"])
    branch = _safe_copilot_branch(route.task_id)
    now = "2026-09-24T00:00:00Z"
    conn.execute(
        """insert into copilot_jobs(
             route_job_id,task_id,issue_number,pr_number,branch,base_sha,
             candidate_sha,state,last_error,created_at,updated_at
           ) values(?,?,?,?,?,?,?,?,?,?,?)""",
        (
            route.id,
            route.task_id,
            issue_number,
            None,
            branch,
            route.base_sha or "",
            None,
            "ACTIVE",
            None,
            now,
            now,
        ),
    )
    conn.execute(
        "update route_jobs set external_ref=?,updated_at=datetime('now') where id=?",
        (f"issue:{issue_number}", route.id),
    )
    conn.commit()
    transition_route(conn, route.id, "ASSIGNING", "ACTIVE")
    append_decision(
        conn,
        route.id,
        "COPILOT_ISSUE_ADOPTED",
        f"adopted pre-existing GitHub issue #{issue_number} after crash",
        task_id=route.task_id,
    )
    return RouteRecoveryResult(
        route.id,
        "ACTIVE",
        route.task_id,
        route.route_kind,
        issue_number=issue_number,
        reason="existing issue adopted",
    )


def reconcile_routes(
    conn: sqlite3.Connection,
    ai_cache,
    github,
    command_runner,
    config: dict,
    current_integration_sha: str,
) -> list[RouteRecoveryResult]:
    ensure_route_schema(conn)
    rows = conn.execute(
        """select * from route_jobs
             where state not in (
               'COMPLETE','SKIPPED_DETERMINISTIC','DUPLICATE_CACHE',
               'FAILED_BOUNDED','SUPERSEDED','SCOPE_VIOLATION','QUEUED'
             )
             order by id"""
    ).fetchall()
    results: list[RouteRecoveryResult] = []

    for row in rows:
        route = _job_from_row(row)

        closed = _close_superseded(conn, route)
        if closed is not None:
            results.append(closed)
            continue

        if route.route_kind == "AI":
            recovered = _recover_ai(conn, route, ai_cache)
            if recovered is not None:
                results.append(recovered)
            continue

        if route.route_kind == "COPILOT":
            assignment = _recover_copilot_assignment(conn, route, github)
            if assignment is not None:
                results.append(assignment)
                continue

            job_row = conn.execute(
                "select * from copilot_jobs where route_job_id=?",
                (route.id,),
            ).fetchone()
            if job_row is None:
                continue
            job = _copilot_job_from_row(job_row)
            if job.state not in {"ACTIVE", "PR_READY"}:
                continue
            reconciled = reconcile_copilot_job(
                job,
                gh_runner=github,
                command_runner=command_runner,
                current_integration_sha=current_integration_sha,
                conn=conn,
            )
            results.append(
                RouteRecoveryResult(
                    route_job_id=reconciled.route_job_id,
                    state=reconciled.state,
                    task_id=reconciled.task_id,
                    route_kind="COPILOT",
                    issue_number=job.issue_number,
                    candidate_sha=reconciled.candidate_sha,
                    reason="Copilot external state reconciled",
                )
            )

    return results


def route_cursor(conn: sqlite3.Connection) -> int:
    ensure_route_schema(conn)
    pending = conn.execute(
        """select min(source_event_id) from route_jobs
             where state='NEW' and source_event_id is not null"""
    ).fetchone()[0]
    if pending is not None:
        return max(0, int(pending) - 1)
    return int(
        conn.execute(
            "select coalesce(max(source_event_id),0) from route_jobs "
            "where source_event_id is not null"
        ).fetchone()[0]
        or 0
    )


def route_status(conn: sqlite3.Connection, config: dict) -> RouteStatus:
    ensure_route_schema(conn)
    cursor = route_cursor(conn)
    lag = int(
        conn.execute(
            """select count(*) from brain_events
                where id>? and event_type in ('EVIDENCE','DISCOVERY')
                  and artifact_path is not null and artifact_sha256 is not null""",
            (cursor,),
        ).fetchone()[0]
    )
    terminals = sorted(TERMINAL_STATES)
    placeholders = ",".join("?" for _ in terminals)
    active = int(
        conn.execute(
            f"select count(*) from route_jobs where state not in ({placeholders})",
            terminals,
        ).fetchone()[0]
    )
    failed = int(
        conn.execute(
            "select count(*) from route_jobs where state='FAILED_BOUNDED'"
        ).fetchone()[0]
    )
    ai_active = int(
        conn.execute(
            "select count(*) from route_jobs where route_kind='AI' and state='AI_RUNNING'"
        ).fetchone()[0]
    )
    cache_hits = int(
        conn.execute(
            "select count(*) from route_jobs where route_kind='AI' and state='DUPLICATE_CACHE'"
        ).fetchone()[0]
    )

    routing = config.get("routing", {})
    openai_config = config.get("openai", {})
    auto_model = openai_config.get("auto_model")
    if not routing.get("ai_dispatch_enabled", False):
        budget = "DISABLED"
    elif not auto_model:
        budget = "UNKNOWN"
    else:
        budget = budget_state(conn, config, priority=1, model=str(auto_model))

    copilot_active = int(
        conn.execute(
            """select count(*) from copilot_jobs
                 where state in ('ASSIGNING','ACTIVE','PR_READY','VERIFYING')"""
        ).fetchone()[0]
    )
    copilot_queued = int(
        conn.execute(
            "select count(*) from copilot_jobs where state='QUEUED'"
        ).fetchone()[0]
    )
    copilot_prs = int(
        conn.execute(
            "select count(*) from copilot_jobs where pr_number is not null"
        ).fetchone()[0]
    )

    return RouteStatus(
        cursor=cursor,
        lag=lag,
        active=active,
        failed=failed,
        ai_active=ai_active,
        cache_hits=cache_hits,
        budget=budget,
        copilot_active=copilot_active,
        copilot_queued=copilot_queued,
        copilot_prs=copilot_prs,
        backpressure=backpressure(conn, config),
    )


def format_routes_status(status: RouteStatus) -> str:
    pressure = status.backpressure
    copilot_state = "PAUSED" if pressure.copilot_paused else "OPEN"
    ai_state = "PAUSED" if pressure.ai_research_paused else "OPEN"
    return "\n".join(
        [
            (
                f"ROUTER cursor={status.cursor} lag={status.lag} "
                f"active={status.active} failed={status.failed}"
            ),
            (
                f"OPENAI active={status.ai_active} cache_hits={status.cache_hits} "
                f"budget={status.budget}"
            ),
            (
                f"COPILOT active={status.copilot_active} queued={status.copilot_queued} "
                f"prs={status.copilot_prs}"
            ),
            f"BACKPRESSURE copilot={copilot_state} ai={ai_state}",
        ]
    )


class SQLiteAICache:
    def __init__(
        self,
        brain_executable: str = "/home/ubuntu/logres/bin/logres-brain",
        runner=subprocess.run,
    ):
        self.brain_executable = brain_executable
        self.runner = runner
        self.openai_calls = 0

    def recover(self, conn: sqlite3.Connection, route: RouteJob) -> dict | None:
        if not route.artifact_sha:
            return None
        try:
            meta = json.loads(route.meta_json or "{}")
        except json.JSONDecodeError:
            meta = {}
        question = str(meta.get("question") or "")
        if not question:
            return None
        row = conn.execute(
            """select id,model,result_json from ai_runs
                 where artifact_sha=? and question=? and status='PASS'
                 order by id desc limit 1""",
            (route.artifact_sha, question),
        ).fetchone()
        if row is None or not row[2]:
            return None
        return {
            "ai_run_id": int(row[0]),
            "model": row[1],
            "result": json.loads(row[2]),
        }

    def ensure_brain_post(self, route: RouteJob, record: dict) -> None:
        result = record.get("result") or {}
        confidence = str(result.get("confidence") or "UNRESOLVED")
        body = json.dumps(result, separators=(",", ":"), ensure_ascii=False)
        if len(body) > 7600:
            body = body[:7600] + "..."
        try:
            meta = json.loads(route.meta_json or "{}")
        except json.JSONDecodeError:
            meta = {}
        question = str(meta.get("question") or "")
        dedupe = (
            brain_post_dedupe_key(route.artifact_sha or "", question)
            if route.artifact_sha and question
            else f"ai-recover:{route.id}"
        )
        cmd = [
            self.brain_executable,
            "post",
            "ai",
            "ALL",
            "EVIDENCE",
            "NORMAL",
            f"Recovered AI analysis [{confidence}]",
            "--body",
            body,
            "--dedupe",
            dedupe,
        ]
        if route.task_id:
            cmd += ["--task", route.task_id]
        self.runner(
            cmd,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
