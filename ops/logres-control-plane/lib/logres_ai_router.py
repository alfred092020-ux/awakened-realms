from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from logres_ai_runner import automatic_api_allowed, budget_state
from logres_route_policy import RouteDecision, classify_evidence_event
from logres_route_store import (
    RouteJob,
    RouteSpec,
    append_decision,
    claim_route,
    transition_route,
)

DEFAULT_QUESTION = (
    "Using only this artifact and its stated provenance, extract material Logres "
    "behavior, contradictions, unresolved predicates, and the highest-value "
    "deterministic next search. Do not promote later/current JP evidence to "
    "Global 2017 truth."
)
MAX_ZERO_COST_AI_FAILURES = 2


@dataclass(frozen=True)
class CycleResult:
    processed: int
    api_calls: int
    cache_hits: int
    created_research_tasks: int


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch_dict(conn: sqlite3.Connection, sql: str, params=()) -> dict | None:
    cursor = conn.execute(sql, params)
    row = cursor.fetchone()
    if row is None:
        return None
    return {column[0]: row[index] for index, column in enumerate(cursor.description)}


def _event_context(conn: sqlite3.Connection, event_id: int):
    event = _fetch_dict(conn, "select * from brain_events where id=?", (event_id,))
    if event is None:
        raise KeyError(f"brain event not found: {event_id}")
    task = None
    metadata = None
    if event.get("task_id"):
        task = _fetch_dict(
            conn,
            "select * from tasks where id=?",
            (event["task_id"],),
        )
        metadata = _fetch_dict(
            conn,
            "select * from task_metadata where task_id=?",
            (event["task_id"],),
        )
    return event, task or {}, metadata or {}


def _meta(event: dict) -> dict:
    try:
        return json.loads(event.get("meta_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}


def _question_sha(question: str) -> str:
    return hashlib.sha256(question.encode("utf-8")).hexdigest()


def _route_dedupe(artifact_sha: str, question: str) -> str:
    return f"ai:{artifact_sha}:{_question_sha(question)}"


def _cached_ai_result(
    conn: sqlite3.Connection,
    artifact_sha: str,
    question: str,
):
    return conn.execute(
        """select id,model,result_json from ai_runs
             where artifact_sha=? and question=? and status='PASS'
             order by id desc limit 1""",
        (artifact_sha, question),
    ).fetchone()
def _task_priority(task: dict) -> int:
    try:
        return int(task.get("priority", 1))
    except (TypeError, ValueError):
        return 1


def _insert_research_task(
    conn: sqlite3.Connection,
    *,
    parent_task_id: str | None,
    parent_route_id: int,
    resolution_type: str,
    result: dict,
    priority: int,
) -> tuple[str, bool]:
    suffix = hashlib.sha256(
        f"{parent_route_id}:{resolution_type}".encode("utf-8")
    ).hexdigest()[:10]
    parent_label = parent_task_id or "UNSCOPED"
    task_id = f"AUTO-RE-{parent_label}-{suffix}"
    existed = conn.execute(
        "select 1 from tasks where id=?",
        (task_id,),
    ).fetchone() is not None

    if not existed:
        now = _now()
        title = f"Resolve {resolution_type}: {parent_label}"
        note = "Autoflow research child from AI evidence routing."
        conn.execute(
            """insert into tasks(
                 id,priority,lane,title,status,branch,owner,note,updated_at
               ) values(?,?,?,?,?,?,?,?,?)""",
            (
                task_id,
                priority,
                "research",
                title,
                "READY",
                None,
                None,
                note,
                now,
            ),
        )
        conn.execute(
            """insert into task_metadata(
                 task_id,milestone,work_type,concurrency_key,expected_minutes,
                 evidence_policy,created_at,updated_at
               ) values(?,?,?,?,?,?,?,?)""",
            (
                task_id,
                "autoflow",
                "research",
                f"research:{parent_label}",
                30,
                "Global evidence required",
                now,
                now,
            ),
        )
        acceptance = (
            result.get("recommended_next_search")
            or "; ".join(result.get("unresolved") or [])
            or f"Resolve {resolution_type} with deterministic evidence."
        )
        conn.execute(
            "insert into task_acceptance(task_id,ordinal,criterion) values(?,?,?)",
            (task_id, 1, acceptance),
        )
        if parent_task_id:
            conn.execute(
                """insert into task_dependencies(task_id,depends_on,kind,rationale)
                   values(?,?,?,?)""",
                (
                    task_id,
                    parent_task_id,
                    "evidence",
                    f"Autoflow child for {resolution_type}",
                ),
            )

    child_route = claim_route(
        conn,
        RouteSpec(
            dedupe_key=f"research:{parent_route_id}:{resolution_type}",
            route_kind="RESEARCH",
            task_id=task_id,
            parent_route_id=parent_route_id,
            resolution_type=resolution_type,
        ),
    )
    if child_route.state == "NEW":
        transition_route(conn, child_route.id, "NEW", "ROUTED")
    conn.commit()
    return task_id, not existed


def route_ai_result(
    conn: sqlite3.Connection,
    route_job_id: int,
    result: dict,
    task_row: dict | None,
    metadata_row: dict | None,
    provenance: str,
) -> RouteDecision:
    task_row = task_row or {}
    metadata_row = metadata_row or {}
    task_id = task_row.get("id")
    priority = _task_priority(task_row)
    confidence = result.get("confidence", "UNRESOLVED")
    contradictions = result.get("contradictions") or []

    terminal_statuses = {"DONE","RESOLVED","SUPERSEDED","CANCELLED"}
    task_status = str(task_row.get("status") or "")
    task_note = str(task_row.get("note") or "").lower()
    external_action_markers = (
        "real-device proof",
        "device proof",
        "no adb device",
        "physical device",
        "awaiting real-device",
        "hardware-dependent",
    )

    if contradictions and (
        not task_id
        or task_status in terminal_statuses
        or (
            task_status == "BLOCKED_EVIDENCE"
            and any(marker in task_note for marker in external_action_markers)
        )
    ):
        reason = (
            "contradiction retained for review without creating research work: "
            + ("unscoped evidence" if not task_id else f"parent status={task_status}")
        )
        append_decision(
            conn,
            route_job_id,
            "EVIDENCE_CONFLICT_ADVISORY",
            reason,
            task_id=task_id,
        )
        return RouteDecision(
            "REVIEW_REQUIRED",
            reason,
        )

    if contradictions:
        child_task_id, _ = _insert_research_task(
            conn,
            parent_task_id=task_id,
            parent_route_id=route_job_id,
            resolution_type="EVIDENCE_CONFLICT",
            result=result,
            priority=priority,
        )
        append_decision(
            conn,
            route_job_id,
            "EVIDENCE_CONFLICT",
            "AI analysis reported contradictions requiring deterministic review",
            task_id=task_id,
        )
        return RouteDecision(
            "EVIDENCE_CONFLICT",
            "contradictory evidence requires review",
            child_task_id,
        )

    if confidence in {"UNRESOLVED", "VERSION SENSITIVE"} and (
        not task_id or task_status in terminal_statuses
    ):
        reason = (
            f"{confidence} retained for review without research child: "
            + ("unscoped evidence" if not task_id else f"parent status={task_status}")
        )
        append_decision(
            conn,
            route_job_id,
            "FOCUSED_RESEARCH_SKIPPED",
            reason,
            task_id=task_id,
        )
        return RouteDecision("REVIEW_REQUIRED", reason)

    if confidence in {"UNRESOLVED", "VERSION SENSITIVE"}:
        resolution = (
            "TARGET_VERSION_CROSSCHECK"
            if confidence == "VERSION SENSITIVE"
            else "UNRESOLVED"
        )
        child_task_id, _ = _insert_research_task(
            conn,
            parent_task_id=task_id,
            parent_route_id=route_job_id,
            resolution_type=resolution,
            result=result,
            priority=priority,
        )
        append_decision(
            conn,
            route_job_id,
            "FOCUSED_RESEARCH",
            f"{confidence} requires deterministic follow-up",
            task_id=task_id,
        )
        return RouteDecision(
            "FOCUSED_RESEARCH",
            f"{confidence} requires deterministic follow-up",
            child_task_id,
        )
    policy = str(metadata_row.get("evidence_policy") or "")
    provenance_lower = provenance.lower()
    if "current_jp" in provenance_lower or "later_jp" in provenance_lower:
        append_decision(
            conn,
            route_job_id,
            "REVIEW_REQUIRED",
            "later/current JP provenance cannot establish Global 2017 truth",
            task_id=task_id,
        )
        return RouteDecision(
            "REVIEW_REQUIRED",
            "target-version provenance required",
        )

    if (
        confidence == "SUPPORTED INFERENCE"
        and "allow-supported-inference" not in policy.lower()
    ):
        append_decision(
            conn,
            route_job_id,
            "REVIEW_REQUIRED",
            "task evidence policy does not permit inference-backed implementation",
            task_id=task_id,
        )
        return RouteDecision(
            "REVIEW_REQUIRED",
            "strict evidence policy blocks inferred implementation",
        )

    append_decision(
        conn,
        route_job_id,
        "EVIDENCE_PACKET_REVIEW",
        "AI result is eligible for deterministic evidence-packet review",
        task_id=task_id,
    )
    return RouteDecision(
        "EVIDENCE_PACKET_REVIEW",
        "deterministic evidence review required before implementation",
    )
def _zero_cost_ai_retryable(
    conn: sqlite3.Connection,
    job: RouteJob,
) -> bool:
    if (
        job.route_kind != "AI"
        or job.state != "FAILED_BOUNDED"
        or job.attempt_count >= MAX_ZERO_COST_AI_FAILURES
    ):
        return False
    usage = int(
        conn.execute(
            "select count(*) from api_usage where route_job_id=?",
            (job.id,),
        ).fetchone()[0]
    )
    return usage == 0


def route_event(
    conn: sqlite3.Connection,
    source_event_id: int,
    config: dict,
    dry_run: bool,
    ai_runner,
) -> RouteJob:
    event, task, metadata = _event_context(conn, source_event_id)

    task_status = str(task.get("status") or "")
    task_note = str(task.get("note") or "").lower()
    terminal_statuses = {"DONE","RESOLVED","SUPERSEDED","CANCELLED"}
    external_action_markers = (
        "real-device proof",
        "device proof",
        "no adb device",
        "physical device",
        "awaiting real-device",
        "hardware-dependent",
    )
    skip_reason = None
    if task and task_status in terminal_statuses:
        skip_reason = f"parent task is terminal ({task_status})"
    elif (
        task
        and task_status == "BLOCKED_EVIDENCE"
        and any(marker in task_note for marker in external_action_markers)
    ):
        skip_reason = "parent task is waiting on external hardware/device proof"

    if skip_reason:
        job = claim_route(
            conn,
            RouteSpec(
                dedupe_key=f"event:{source_event_id}:TASK_STATE_SKIP",
                route_kind="DETERMINISTIC",
                source_event_id=source_event_id,
                task_id=event.get("task_id"),
                artifact_sha=event.get("artifact_sha256"),
            ),
        )
        if job.state == "NEW":
            job = transition_route(conn, job.id, "NEW", "SKIPPED_DETERMINISTIC")
            append_decision(
                conn,
                job.id,
                "SKIP_TASK_STATE",
                skip_reason,
                source_event_id=source_event_id,
                task_id=event.get("task_id"),
            )
        return job

    decision = classify_evidence_event(event, task, metadata, config)

    if decision.route != "AI":
        job = claim_route(
            conn,
            RouteSpec(
                dedupe_key=f"event:{source_event_id}:{decision.route}",
                route_kind="DETERMINISTIC",
                source_event_id=source_event_id,
                task_id=event.get("task_id"),
                artifact_sha=event.get("artifact_sha256"),
            ),
        )
        if job.state == "NEW":
            job = transition_route(
                conn,
                job.id,
                "NEW",
                "SKIPPED_DETERMINISTIC",
            )
            append_decision(
                conn,
                job.id,
                "SKIP_DETERMINISTIC",
                decision.reason,
                source_event_id=source_event_id,
                task_id=event.get("task_id"),
            )
        return job

    artifact_sha = str(event["artifact_sha256"])
    question = DEFAULT_QUESTION
    question_sha = _question_sha(question)
    meta = _meta(event)
    provenance = str(meta.get("provenance", "UNRESOLVED"))
    job = claim_route(
        conn,
        RouteSpec(
            dedupe_key=_route_dedupe(artifact_sha, question),
            route_kind="AI",
            source_event_id=source_event_id,
            task_id=event.get("task_id"),
            artifact_sha=artifact_sha,
            question_sha=question_sha,
            meta={"provenance": provenance, "question": question},
        ),
    )
    if _zero_cost_ai_retryable(conn, job):
        legacy_failure_count = max(1, int(job.attempt_count or 0))
        job = transition_route(
            conn,
            job.id,
            "FAILED_BOUNDED",
            "NEW",
            attempt_count=legacy_failure_count,
            last_error=None,
        )
        append_decision(
            conn,
            job.id,
            "AI_ZERO_COST_RETRY",
            (
                "retrying transient AI failure because no API usage was "
                f"recorded ({legacy_failure_count}/{MAX_ZERO_COST_AI_FAILURES})"
            ),
            source_event_id=source_event_id,
            task_id=event.get("task_id"),
        )
    if job.state != "NEW":
        return job

    cached = _cached_ai_result(conn, artifact_sha, question)
    if cached is not None:
        job = transition_route(conn, job.id, "NEW", "DUPLICATE_CACHE")
        append_decision(
            conn,
            job.id,
            "DUPLICATE_CACHE",
            "artifact/question analysis already exists",
            source_event_id=source_event_id,
            task_id=event.get("task_id"),
        )
        return job

    routing = config.get("routing", {})
    if dry_run or not bool(routing.get("ai_dispatch_enabled", False)):
        append_decision(
            conn,
            job.id,
            "PLAN_AI",
            "AI dispatch disabled or dry-run",
            source_event_id=source_event_id,
            task_id=event.get("task_id"),
        )
        return job

    openai_config = config.get("openai", {})
    auto_model = openai_config.get("auto_model")
    rates = openai_config.get("model_rates_per_million", {})
    if not auto_model or auto_model not in rates:
        append_decision(
            conn,
            job.id,
            "BUDGET_UNKNOWN",
            "automatic model is unset or has no configured rate",
            source_event_id=source_event_id,
            task_id=event.get("task_id"),
        )
        return job

    state = budget_state(
        conn,
        config,
        priority=_task_priority(task),
        model=auto_model,
    )
    if not automatic_api_allowed(state, _task_priority(task)):
        append_decision(
            conn,
            job.id,
            f"BUDGET_{state}",
            f"automatic API spend blocked by budget state {state}",
            source_event_id=source_event_id,
            task_id=event.get("task_id"),
        )
        return job
    artifact_path = Path(str(event["artifact_path"]))
    if not artifact_path.is_file():
        append_decision(
            conn,
            job.id,
            "ARTIFACT_MISSING",
            f"artifact path not found: {artifact_path}",
            source_event_id=source_event_id,
            task_id=event.get("task_id"),
        )
        return job
    actual_sha = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    if actual_sha != artifact_sha:
        append_decision(
            conn,
            job.id,
            "ARTIFACT_SHA_MISMATCH",
            "artifact SHA does not match Brain event",
            source_event_id=source_event_id,
            task_id=event.get("task_id"),
        )
        return job

    job = transition_route(conn, job.id, "NEW", "ROUTED")
    job = transition_route(conn, job.id, "ROUTED", "AI_RUNNING")
    try:
        output = ai_runner.run(
            artifact_path=str(artifact_path),
            artifact_sha=artifact_sha,
            question=question,
            task_id=event.get("task_id"),
            route_job_id=job.id,
            config=config,
            auto_model=auto_model,
        )
    except Exception as exc:
        job = transition_route(
            conn,
            job.id,
            "AI_RUNNING",
            "FAILED_BOUNDED",
            last_error=str(exc),
            attempt_count=int(job.attempt_count or 0) + 1,
        )
        append_decision(
            conn,
            job.id,
            "AI_FAILED",
            str(exc),
            source_event_id=source_event_id,
            task_id=event.get("task_id"),
        )
        raise

    job = transition_route(conn, job.id, "AI_RUNNING", "AI_VALIDATED")
    route_ai_result(
        conn,
        job.id,
        output["result"],
        task,
        metadata,
        provenance=provenance,
    )
    job = transition_route(conn, job.id, "AI_VALIDATED", "BRAIN_POSTED")
    job = transition_route(conn, job.id, "BRAIN_POSTED", "COMPLETE")
    return job


class SubprocessAIRunner:
    def __init__(self, executable: str = "/home/ubuntu/logres/bin/logres-ai"):
        self.executable = executable

    def run(self, **kwargs) -> dict:
        cmd = [
            self.executable,
            kwargs["artifact_path"],
            "--question",
            kwargs["question"],
            "--route-job-id",
            str(kwargs["route_job_id"]),
            "--post-brain",
        ]
        if kwargs.get("task_id"):
            cmd += ["--task", str(kwargs["task_id"])]
        env = os.environ.copy()
        if kwargs.get("auto_model"):
            env["LOGRES_AI_MODEL"] = str(kwargs["auto_model"])
        completed = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        summary = json.loads(completed.stdout)
        result_path = Path(summary["result_path"])
        stored = json.loads(result_path.read_text())
        return stored


class NullBrainRunner:
    def post(self, *args, **kwargs):
        return None


class SubprocessBrainRunner:
    def __init__(
        self,
        executable: str = "/home/ubuntu/logres/bin/logres-brain",
        runner=subprocess.run,
    ):
        self.executable = executable
        self.runner = runner

    def post(
        self,
        *,
        event_type: str,
        task_id: str | None,
        subject: str,
        body: str,
        dedupe_key: str,
        priority: str = "HIGH",
    ):
        cmd = [
            self.executable,
            "post",
            "ai",
            "ALL",
            event_type,
            priority,
            subject,
            "--body",
            body,
        ]
        if task_id:
            cmd += ["--task", task_id]
        if dedupe_key:
            cmd += ["--dedupe", dedupe_key]
        return self.runner(cmd, check=True)


def run_ai_cycle(
    conn: sqlite3.Connection,
    ai_runner,
    brain_runner,
    config: dict,
    limit: int = 10,
    since_event_id: int = 0,
    dry_run: bool = False,
) -> CycleResult:
    rows = conn.execute(
        """select id from brain_events
             where id>? and event_type in ('EVIDENCE','DISCOVERY')
               and artifact_path is not null and artifact_sha256 is not null
             order by id asc limit ?""",
        (since_event_id, limit),
    ).fetchall()
    before_tasks = conn.execute(
        "select count(*) from tasks where note='Autoflow research child from AI evidence routing.'"
    ).fetchone()[0]
    before_calls = getattr(ai_runner, "calls", None)
    cache_hits = 0
    for row in rows:
        event_id = row[0]
        job = route_event(
            conn,
            source_event_id=event_id,
            config=config,
            dry_run=dry_run,
            ai_runner=ai_runner,
        )
        if job.state == "DUPLICATE_CACHE":
            cache_hits += 1

        conflict = conn.execute(
            """select reason,task_id from route_decisions
                 where route_job_id=? and decision='EVIDENCE_CONFLICT'
                 order by id desc limit 1""",
            (job.id,),
        ).fetchone()
        already_posted = conn.execute(
            """select 1 from route_decisions
                 where route_job_id=? and decision='BRAIN_CONFLICT_POSTED'
                 limit 1""",
            (job.id,),
        ).fetchone()
        if conflict is not None and already_posted is None:
            reason, task_id = conflict
            brain_runner.post(
                event_type="EVIDENCE_CONFLICT",
                task_id=task_id,
                subject=f"AI evidence conflict for {task_id or 'unscoped'}",
                body=reason,
                dedupe_key=f"ai-router-conflict:{job.id}",
                priority="HIGH",
            )
            append_decision(
                conn,
                job.id,
                "BRAIN_CONFLICT_POSTED",
                "posted deduplicated EVIDENCE_CONFLICT to Brain",
                task_id=task_id,
            )

    after_tasks = conn.execute(
        "select count(*) from tasks where note='Autoflow research child from AI evidence routing.'"
    ).fetchone()[0]
    after_calls = getattr(ai_runner, "calls", None)
    api_calls = 0
    if before_calls is not None and after_calls is not None:
        api_calls = max(0, int(after_calls) - int(before_calls))
    return CycleResult(
        processed=len(rows),
        api_calls=api_calls,
        cache_hits=cache_hits,
        created_research_tasks=max(0, after_tasks - before_tasks),
    )
