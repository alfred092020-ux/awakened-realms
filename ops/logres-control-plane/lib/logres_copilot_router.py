from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass

from logres_copilot import (
    DEFAULT_REPO,
    INTEGRATION_BRANCH,
    CopilotPacket,
    PolicyError,
    build_assignment,
    build_issue_body,
)
from logres_route_store import RouteSpec, claim_route, ensure_route_schema, transition_route


SATISFIED = {"DONE", "RESOLVED", "INTEGRATED"}
ALLOWED_WORK_TYPES = {"implementation", "test", "refactor", "tooling", "review"}
ACTIVE_COPILOT_STATES = {"ASSIGNING", "ACTIVE", "PR_READY", "VERIFYING"}


@dataclass(frozen=True)
class Eligibility:
    allowed: bool
    reason: str


@dataclass(frozen=True)
class CopilotJobRecord:
    id: int
    route_job_id: int
    task_id: str
    issue_number: int | None
    pr_number: int | None
    branch: str | None
    base_sha: str
    candidate_sha: str | None
    state: str
    last_error: str | None


@dataclass(frozen=True)
class DispatchResult:
    route_job_id: int
    job: CopilotJobRecord
    branch: str


def _normalize_prefix(value: str) -> str:
    return value.rstrip("/") + "/"
def _scopes_overlap(a: str, b: str) -> bool:
    left = _normalize_prefix(a)
    right = _normalize_prefix(b)
    return left.startswith(right) or right.startswith(left)


def _job_from_row(row) -> CopilotJobRecord:
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


def _fetch_job(conn: sqlite3.Connection, route_job_id: int) -> CopilotJobRecord | None:
    row = conn.execute(
        "select * from copilot_jobs where route_job_id=?",
        (route_job_id,),
    ).fetchone()
    return None if row is None else _job_from_row(row)


def _hard_deps_ok(conn: sqlite3.Connection, task_id: str) -> bool:
    rows = conn.execute(
        """select d.depends_on,t.status
             from task_dependencies d
             left join tasks t on t.id=d.depends_on
            where d.task_id=? and d.kind='hard'""",
        (task_id,),
    ).fetchall()
    return all((row["status"] or "MISSING") in SATISFIED for row in rows)


def _task_scopes(conn: sqlite3.Connection, task_id: str) -> tuple[str, ...]:
    return tuple(
        row[0]
        for row in conn.execute(
            "select path_prefix from task_scopes where task_id=? order by path_prefix",
            (task_id,),
        )
    )
def copilot_eligibility(
    conn: sqlite3.Connection,
    task_id: str,
    integration_sha: str,
    config: dict,
) -> Eligibility:
    del integration_sha
    ensure_route_schema(conn)
    task = conn.execute(
        """select t.*,m.work_type,m.concurrency_key,m.evidence_policy
             from tasks t
             left join task_metadata m on m.task_id=t.id
            where t.id=?""",
        (task_id,),
    ).fetchone()
    if task is None:
        return Eligibility(False, "task not found")
    if task["status"] != "READY":
        return Eligibility(False, f"status is {task['status']}, expected READY")

    work_type = task["work_type"] or "implementation"
    if work_type not in ALLOWED_WORK_TYPES:
        return Eligibility(False, f"work_type {work_type!r} is not Copilot eligible")

    acceptance_count = conn.execute(
        "select count(*) from task_acceptance where task_id=?",
        (task_id,),
    ).fetchone()[0]
    if acceptance_count == 0:
        return Eligibility(False, "acceptance criteria are required")

    scopes = _task_scopes(conn, task_id)
    if not scopes:
        return Eligibility(False, "file scope is required")

    if not _hard_deps_ok(conn, task_id):
        return Eligibility(False, "hard dependency is not satisfied")

    active_lease = conn.execute(
        "select 1 from brain_task_leases where task_id=? and lease_until_epoch>? limit 1",
        (task_id, time.time()),
    ).fetchone()
    if active_lease is not None:
        return Eligibility(False, "task already has an active lease")
    concurrency_key = task["concurrency_key"] or task["lane"]
    if concurrency_key:
        conflicting_key = conn.execute(
            """select 1
                 from brain_task_leases l
                 join tasks t on t.id=l.task_id
                 left join task_metadata m on m.task_id=t.id
                where l.task_id<>?
                  and l.lease_until_epoch>?
                  and coalesce(m.concurrency_key,t.lane)=?
                limit 1""",
            (task_id, time.time(), concurrency_key),
        ).fetchone()
        if conflicting_key is not None:
            return Eligibility(False, "active concurrency-key overlap")

    claims = conn.execute(
        "select task_id,path_prefix from claims where task_id<>?",
        (task_id,),
    ).fetchall()
    for scope in scopes:
        for claim in claims:
            if _scopes_overlap(scope, claim["path_prefix"]):
                return Eligibility(
                    False,
                    f"active scope overlap with {claim['task_id']}:{claim['path_prefix']}",
                )

    max_active = int(config.get("copilot", {}).get("max_active", 2))
    active_jobs = conn.execute(
        "select count(*) from copilot_jobs where state in ('ASSIGNING','ACTIVE','PR_READY','VERIFYING')"
    ).fetchone()[0]
    if active_jobs >= max_active:
        return Eligibility(False, f"Copilot capacity full ({active_jobs}/{max_active})")

    return Eligibility(True, "eligible")


def _safe_branch(task_id: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", task_id.lower()).strip("-") or "task"
    return f"copilot/{slug}"
def _evidence_summary(conn: sqlite3.Connection, task_id: str, evidence_policy: str) -> str:
    rows = conn.execute(
        """select subject,body,artifact_path,artifact_sha256
             from brain_events
            where task_id=? and event_type in ('EVIDENCE','DISCOVERY')
            order by id desc limit 3""",
        (task_id,),
    ).fetchall()
    parts = [f"Evidence policy: {evidence_policy or 'not specified'}"]
    for row in rows:
        artifact = ""
        if row["artifact_path"]:
            artifact = f" artifact={row['artifact_path']}"
            if row["artifact_sha256"]:
                artifact += f" sha256={row['artifact_sha256']}"
        parts.append(f"{row['subject']}: {row['body']}{artifact}")
    return "\n".join(parts)


def _build_packet(conn: sqlite3.Connection, task_id: str, integration_sha: str) -> CopilotPacket:
    task = conn.execute(
        """select t.title,m.evidence_policy
             from tasks t left join task_metadata m on m.task_id=t.id
            where t.id=?""",
        (task_id,),
    ).fetchone()
    scopes = _task_scopes(conn, task_id)
    acceptance = tuple(
        row[0]
        for row in conn.execute(
            "select criterion from task_acceptance where task_id=? order by ordinal",
            (task_id,),
        )
    )
    return CopilotPacket(
        task_id=task_id,
        title=task["title"] or task_id,
        base_sha=integration_sha,
        evidence_summary=_evidence_summary(
            conn,
            task_id,
            task["evidence_policy"] or "",
        ),
        allowed_files=scopes,
        forbidden_files=(
            "main",
            "direct commits or merges to feat/logres-reconstruction",
            "files outside the allowed scopes above",
        ),
        acceptance=acceptance,
        tests=("npm test", "npm run build"),
    )
def _dedupe_key(conn: sqlite3.Connection, task_id: str, integration_sha: str) -> str:
    row = conn.execute(
        "select updated_at from tasks where id=?",
        (task_id,),
    ).fetchone()
    revision = row[0] if row else "missing"
    return f"copilot:{task_id}:{revision}:{integration_sha}"


def dispatch_task(
    conn: sqlite3.Connection,
    task_id: str,
    integration_sha: str,
    config: dict,
    gh_runner,
) -> DispatchResult:
    ensure_route_schema(conn)
    if not bool(config.get("routing", {}).get("copilot_dispatch_enabled", False)):
        raise PolicyError("automatic Copilot dispatch is disabled")

    eligibility = copilot_eligibility(conn, task_id, integration_sha, config)
    if not eligibility.allowed:
        raise PolicyError(f"task {task_id} is not Copilot eligible: {eligibility.reason}")

    route = claim_route(
        conn,
        RouteSpec(
            dedupe_key=_dedupe_key(conn, task_id, integration_sha),
            route_kind="COPILOT",
            task_id=task_id,
            base_sha=integration_sha,
        ),
    )
    existing_job = _fetch_job(conn, route.id)
    if existing_job is not None:
        return DispatchResult(route.id, existing_job, existing_job.branch or _safe_branch(task_id))

    if route.state != "NEW":
        raise PolicyError(
            f"route {route.id} exists in {route.state} without a Copilot job record"
        )

    transition_route(conn, route.id, "NEW", "ROUTED")
    transition_route(conn, route.id, "ROUTED", "ASSIGNING")

    packet = _build_packet(conn, task_id, integration_sha)
    issue_number = gh_runner.create_issue(
        DEFAULT_REPO,
        f"[Copilot] {task_id}: {packet.title}",
        build_issue_body(packet),
    )
    branch = _safe_branch(task_id)
    now = "2026-09-23T00:00:00Z"
    cursor = conn.execute(
        """insert into copilot_jobs(
             route_job_id,task_id,issue_number,pr_number,branch,base_sha,
             candidate_sha,state,last_error,created_at,updated_at
           ) values(?,?,?,?,?,?,?,?,?,?,?)""",
        (
            route.id,
            task_id,
            issue_number,
            None,
            branch,
            integration_sha,
            None,
            "ASSIGNING",
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

    payload = build_assignment(packet, INTEGRATION_BRANCH)
    gh_runner.assign_copilot(DEFAULT_REPO, issue_number, payload)

    conn.execute(
        "update copilot_jobs set state='ACTIVE',updated_at=datetime('now') where route_job_id=?",
        (route.id,),
    )
    conn.commit()
    transition_route(conn, route.id, "ASSIGNING", "ACTIVE")

    job = _fetch_job(conn, route.id)
    if job is None:
        raise RuntimeError(f"Copilot job disappeared for route {route.id}")
    return DispatchResult(route.id, job, branch)
