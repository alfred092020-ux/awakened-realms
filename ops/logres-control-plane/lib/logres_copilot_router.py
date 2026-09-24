from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass

from logres_copilot import (
    DEFAULT_REPO,
    INTEGRATION_BRANCH,
    CopilotJobRecord,
    CopilotPacket,
    PolicyError,
    SubprocessCommandRunner,
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

    pressure = config.get("backpressure", {})
    ready_limit = int(pressure.get("ready_for_integration", 4))
    verify_limit = int(pressure.get("verification_backlog", 3))
    ready_backlog = int(
        conn.execute(
            "select count(*) from integration_queue where status='READY_FOR_INTEGRATION'"
        ).fetchone()[0]
    )
    verify_backlog = int(
        conn.execute(
            "select count(*) from route_jobs where state='VERIFYING'"
        ).fetchone()[0]
    )
    if ready_backlog > ready_limit or verify_backlog > verify_limit:
        return Eligibility(
            False,
            (
                "backpressure active "
                f"integration_ready={ready_backlog}/{ready_limit} "
                f"verifying={verify_backlog}/{verify_limit}"
            ),
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

    task_row = conn.execute(
        """select coalesce(m.work_type,'implementation') work_type
             from tasks t left join task_metadata m on m.task_id=t.id
            where t.id=?""",
        (task_id,),
    ).fetchone()
    work_type = str(task_row["work_type"]) if task_row is not None else "implementation"
    mode = str(config.get("routing", {}).get("copilot_mode", "report_only"))
    if mode == "report_only" and work_type != "review":
        raise PolicyError(
            f"Copilot mode report_only blocks work_type {work_type!r}"
        )
    if mode not in {"report_only", "bounded_implementation"}:
        raise PolicyError(f"unknown Copilot mode: {mode!r}")

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


@dataclass(frozen=True)
class ReconcileResult:
    state: str
    task_id: str
    branch: str
    candidate_sha: str | None
    route_job_id: int
    revalidation_required: bool = False


def _set_copilot_job_state(
    conn: sqlite3.Connection,
    route_job_id: int,
    state: str,
    *,
    last_error: str | None = None,
) -> None:
    conn.execute(
        """update copilot_jobs
              set state=?,last_error=?,updated_at=datetime('now')
            where route_job_id=?""",
        (state, last_error, route_job_id),
    )
    conn.commit()


def _matching_pr(job: CopilotJobRecord, gh_runner) -> dict | None:
    list_prs = getattr(gh_runner, "list_prs", None)
    if list_prs is None:
        return None
    candidates = []
    for pr in list_prs(DEFAULT_REPO):
        if pr.get("baseRefName") != INTEGRATION_BRANCH:
            continue
        if pr.get("isDraft") is not True:
            continue
        changed_files = pr.get("changedFiles")
        if changed_files is not None:
            try:
                if int(changed_files) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
        candidates.append(pr)
    if not candidates:
        return None

    branch_matches = [
        pr for pr in candidates
        if job.branch and pr.get("headRefName") == job.branch
    ]
    if len(branch_matches) == 1:
        return branch_matches[0]

    issue_token = f"#{job.issue_number}" if job.issue_number is not None else None
    issue_matches = [
        pr for pr in candidates
        if issue_token and issue_token in str(pr.get("body") or "")
    ]
    if len(issue_matches) == 1:
        return issue_matches[0]

    task_matches = [
        pr for pr in candidates
        if job.task_id.lower() in (
            str(pr.get("title") or "") + "\n" + str(pr.get("body") or "")
        ).lower()
    ]
    if len(task_matches) == 1:
        return task_matches[0]
    return None


def _insert_pr_ready_job(
    conn: sqlite3.Connection,
    *,
    old_job: CopilotJobRecord,
    pr: dict,
    current_integration_sha: str,
) -> CopilotJobRecord:
    branch = str(pr.get("headRefName") or "")
    candidate_sha = str(pr.get("headRefOid") or "")
    if not branch.startswith("copilot/"):
        raise PolicyError(f"Copilot PR branch is not isolated: {branch!r}")
    if len(candidate_sha) != 40:
        raise PolicyError(f"Copilot PR candidate SHA is invalid: {candidate_sha!r}")

    if old_job.state == "ACTIVE":
        transition_route(conn, old_job.route_job_id, "ACTIVE", "PR_READY")
        conn.execute(
            """update copilot_jobs
                  set pr_number=?,branch=?,candidate_sha=?,state='PR_READY',
                      updated_at=datetime('now')
                where route_job_id=?""",
            (
                int(pr["number"]),
                branch,
                candidate_sha,
                old_job.route_job_id,
            ),
        )
        conn.commit()
        adopted = _fetch_job(conn, old_job.route_job_id)
        if adopted is None:
            raise RuntimeError("adopted Copilot job disappeared")
        return adopted

    if old_job.state in {"PR_READY", "QUEUED"} and old_job.candidate_sha == candidate_sha:
        conn.execute(
            """update copilot_jobs
                  set pr_number=?,branch=?,updated_at=datetime('now')
                where route_job_id=?""",
            (int(pr["number"]), branch, old_job.route_job_id),
        )
        conn.commit()
        adopted = _fetch_job(conn, old_job.route_job_id)
        if adopted is None:
            raise RuntimeError("Copilot job disappeared after PR refresh")
        return adopted

    if old_job.state not in {"PR_READY", "QUEUED"}:
        return old_job

    transition_route(conn, old_job.route_job_id, old_job.state, "SUPERSEDED")
    _set_copilot_job_state(conn, old_job.route_job_id, "SUPERSEDED")
    conn.execute(
        """update integration_queue
              set status='SUPERSEDED',updated_at=datetime('now'),
                  note='Superseded by a newer verified Copilot PR candidate.'
            where task_id=? and sha=?
              and status not in ('INTEGRATED','SUPERSEDED')""",
        (old_job.task_id, old_job.candidate_sha),
    )
    conn.commit()

    replacement = claim_route(
        conn,
        RouteSpec(
            dedupe_key=f"copilot-candidate:{old_job.task_id}:{candidate_sha}",
            route_kind="COPILOT",
            task_id=old_job.task_id,
            base_sha=current_integration_sha,
        ),
    )
    existing = _fetch_job(conn, replacement.id)
    if existing is not None:
        return existing

    if replacement.state == "NEW":
        transition_route(conn, replacement.id, "NEW", "ROUTED")
        transition_route(conn, replacement.id, "ROUTED", "ASSIGNING")
        transition_route(conn, replacement.id, "ASSIGNING", "ACTIVE")
        transition_route(conn, replacement.id, "ACTIVE", "PR_READY")

    conn.execute(
        """insert into copilot_jobs(
             route_job_id,task_id,issue_number,pr_number,branch,base_sha,
             candidate_sha,state,last_error,created_at,updated_at
           ) values(?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))""",
        (
            replacement.id,
            old_job.task_id,
            old_job.issue_number,
            int(pr["number"]),
            branch,
            current_integration_sha,
            candidate_sha,
            "PR_READY",
            None,
        ),
    )
    conn.commit()
    adopted = _fetch_job(conn, replacement.id)
    if adopted is None:
        raise RuntimeError("replacement Copilot job disappeared")
    return adopted


def reconcile_copilot_job(
    job: CopilotJobRecord,
    gh_runner,
    command_runner,
    current_integration_sha: str,
    conn: sqlite3.Connection,
) -> ReconcileResult:
    ensure_route_schema(conn)

    matched_pr = _matching_pr(job, gh_runner)
    if matched_pr is not None:
        job = _insert_pr_ready_job(
            conn,
            old_job=job,
            pr=matched_pr,
            current_integration_sha=current_integration_sha,
        )

    branch = job.branch or _safe_branch(job.task_id)

    if job.state == "QUEUED":
        if job.candidate_sha is None:
            raise PolicyError(f"Copilot job {job.id} has no immutable candidate SHA")
        prepare_ref = getattr(command_runner, "prepare_ref", None)
        verify_ref = prepare_ref(branch) if prepare_ref is not None else branch
        resolve_sha = getattr(command_runner, "resolve_sha", None)
        actual_sha = resolve_sha(verify_ref) if resolve_sha is not None else job.candidate_sha
        if actual_sha != job.candidate_sha:
            transition_route(conn, job.route_job_id, "QUEUED", "SUPERSEDED")
            _set_copilot_job_state(
                conn,
                job.route_job_id,
                "SUPERSEDED",
                last_error=(
                    f"queued branch moved: expected {job.candidate_sha}, got {actual_sha}"
                ),
            )
            conn.execute(
                """update integration_queue
                      set status='SUPERSEDED',updated_at=datetime('now'),
                          note='Queued Copilot candidate superseded after remote branch moved.'
                    where task_id=? and sha=?
                      and status not in ('INTEGRATED','SUPERSEDED')""",
                (job.task_id, job.candidate_sha),
            )
            conn.commit()
            return ReconcileResult(
                state="SUPERSEDED",
                task_id=job.task_id,
                route_job_id=job.route_job_id,
                branch=branch,
                candidate_sha=job.candidate_sha,
            )
        conn.execute(
            "update tasks set branch=?,updated_at=datetime('now') where id=?",
            (branch, job.task_id),
        )
        conn.commit()
        return ReconcileResult(
            state="QUEUED",
            task_id=job.task_id,
            route_job_id=job.route_job_id,
            branch=branch,
            candidate_sha=job.candidate_sha,
            revalidation_required=False,
        )

    if job.state != "PR_READY":
        return ReconcileResult(
            state=job.state,
            task_id=job.task_id,
            route_job_id=job.route_job_id,
            branch=branch,
            candidate_sha=job.candidate_sha,
            revalidation_required=False,
        )

    if job.candidate_sha is None:
        raise PolicyError(f"Copilot job {job.id} has no immutable candidate SHA")

    # A candidate may have been authored from an older integration base.
    # Scope/fast verification can still run on its immutable SHA; the shared
    # merge preflight is what validates the composed result on the current
    # canonical base. Do not strand the route in VERIFYING merely because
    # canonical advanced while Copilot was working.
    revalidation_required = job.base_sha != current_integration_sha

    verify_ref = branch
    prepare_ref = getattr(command_runner, "prepare_ref", None)
    if prepare_ref is not None:
        verify_ref = prepare_ref(branch)

    resolve_sha = getattr(command_runner, "resolve_sha", None)
    if resolve_sha is not None:
        actual_sha = resolve_sha(verify_ref)
        if actual_sha != job.candidate_sha:
            transition_route(conn, job.route_job_id, "PR_READY", "SUPERSEDED")
            _set_copilot_job_state(
                conn,
                job.route_job_id,
                "SUPERSEDED",
                last_error=(
                    f"prepared ref moved: expected {job.candidate_sha}, got {actual_sha}"
                ),
            )
            return ReconcileResult(
                state="SUPERSEDED",
                task_id=job.task_id,
                route_job_id=job.route_job_id,
                branch=verify_ref,
                candidate_sha=job.candidate_sha,
            )

    if command_runner.scope_check(job.task_id, verify_ref) != 0:
        transition_route(conn, job.route_job_id, "PR_READY", "SCOPE_VIOLATION")
        _set_copilot_job_state(
            conn,
            job.route_job_id,
            "SCOPE_VIOLATION",
            last_error="scope check failed",
        )
        command_runner.post_scope_conflict(job.task_id, verify_ref, job.candidate_sha)
        return ReconcileResult(
            state="SCOPE_VIOLATION",
            task_id=job.task_id,
            route_job_id=job.route_job_id,
            branch=branch,
            candidate_sha=job.candidate_sha,
        )

    transition_route(conn, job.route_job_id, "PR_READY", "VERIFYING")
    _set_copilot_job_state(conn, job.route_job_id, "VERIFYING")

    if command_runner.fast_gate(verify_ref) != 0:
        transition_route(conn, job.route_job_id, "VERIFYING", "FAILED_BOUNDED")
        _set_copilot_job_state(
            conn,
            job.route_job_id,
            "FAILED_BOUNDED",
            last_error="fast gate failed",
        )
        command_runner.capture_regression(job.task_id, verify_ref, job.candidate_sha)
        return ReconcileResult(
            state="FAILED_BOUNDED",
            task_id=job.task_id,
            route_job_id=job.route_job_id,
            branch=branch,
            candidate_sha=job.candidate_sha,
        )

    conn.execute(
        """update tasks
              set status='DONE',branch=?,owner='copilot',
                  note='Copilot candidate passed scope and fast verification; Lead integration remains required',
                  updated_at=datetime('now')
            where id=?""",
        (job.branch or _safe_branch(job.task_id), job.task_id),
    )
    conn.commit()

    rc = command_runner.coordinator_reconcile(
        conn,
        job.task_id,
        branch,
        job.candidate_sha,
    )
    if rc != 0:
        transition_route(conn, job.route_job_id, "VERIFYING", "FAILED_BOUNDED")
        _set_copilot_job_state(
            conn,
            job.route_job_id,
            "FAILED_BOUNDED",
            last_error="coordinator reconcile failed",
        )
        return ReconcileResult(
            state="FAILED_BOUNDED",
            task_id=job.task_id,
            route_job_id=job.route_job_id,
            branch=branch,
            candidate_sha=job.candidate_sha,
        )

    queued = conn.execute(
        "select 1 from integration_queue where task_id=? and sha=? limit 1",
        (job.task_id, job.candidate_sha),
    ).fetchone()
    if queued is None:
        raise RuntimeError(
            f"coordinator did not queue immutable candidate {job.task_id}@{job.candidate_sha}"
        )

    transition_route(conn, job.route_job_id, "VERIFYING", "QUEUED")
    _set_copilot_job_state(conn, job.route_job_id, "QUEUED")
    return ReconcileResult(
        state="QUEUED",
        task_id=job.task_id,
        route_job_id=job.route_job_id,
        branch=job.branch or _safe_branch(job.task_id),
        candidate_sha=job.candidate_sha,
        revalidation_required=revalidation_required,
    )


def active_copilot_jobs(conn: sqlite3.Connection) -> list[CopilotJobRecord]:
    return [
        _job_from_row(row)
        for row in conn.execute(
            """select cj.* from copilot_jobs cj
                 where cj.state in ('ACTIVE','PR_READY')
                    or (
                      cj.state='QUEUED'
                      and not exists (
                        select 1 from integration_queue iq
                         where iq.task_id=cj.task_id
                           and iq.sha=cj.candidate_sha
                           and iq.status='INTEGRATED'
                      )
                    )
                 order by cj.id"""
        )
    ]
