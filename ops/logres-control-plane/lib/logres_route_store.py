from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class RouteSpec:
    dedupe_key: str
    route_kind: str
    source_event_id: int | None = None
    task_id: str | None = None
    artifact_sha: str | None = None
    question_sha: str | None = None
    base_sha: str | None = None
    parent_route_id: int | None = None
    resolution_type: str | None = None
    meta: dict | None = None


@dataclass(frozen=True)
class RouteJob:
    id: int
    dedupe_key: str
    source_event_id: int | None
    task_id: str | None
    route_kind: str
    state: str
    attempt_count: int
    artifact_sha: str | None
    question_sha: str | None
    base_sha: str | None
    external_ref: str | None
    parent_route_id: int | None
    resolution_type: str | None
    last_error: str | None
    meta_json: str
    created_at: str
    updated_at: str


class StateConflict(RuntimeError):
    pass


VALID_TRANSITIONS = {
    "NEW": {"ROUTED", "SKIPPED_DETERMINISTIC", "DUPLICATE_CACHE"},
    "ROUTED": {"AI_RUNNING", "ASSIGNING", "FAILED_BOUNDED"},
    "AI_RUNNING": {"AI_VALIDATED", "FAILED_BOUNDED"},
    "AI_VALIDATED": {"BRAIN_POSTED", "FAILED_BOUNDED"},
    "BRAIN_POSTED": {"COMPLETE"},
    "ASSIGNING": {"ACTIVE", "FAILED_BOUNDED"},
    "ACTIVE": {"PR_READY", "SUPERSEDED", "BLOCKED_EVIDENCE", "FAILED_BOUNDED"},
    "PR_READY": {"VERIFYING", "SCOPE_VIOLATION", "SUPERSEDED"},
    "VERIFYING": {"QUEUED", "FAILED_BOUNDED", "SCOPE_VIOLATION"},
    # Exact-cache recovery may reopen an AI bounded failure after the model
    # result is durably present. Zero-cost transient AI failures may also be
    # requeued by the router under a strict bounded-attempt policy.
    "FAILED_BOUNDED": {"NEW", "AI_VALIDATED"},
    # Preserve the live immutable-candidate guard when a queued PR head moves.
    "QUEUED": {"SUPERSEDED"},
}


TERMINAL_STATES = {
    "COMPLETE",
    "SKIPPED_DETERMINISTIC",
    "DUPLICATE_CACHE",
    "FAILED_BOUNDED",
    "SUPERSEDED",
    "BLOCKED_EVIDENCE",
    "SCOPE_VIOLATION",
    "QUEUED",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _begin_immediate(
    conn: sqlite3.Connection,
    *,
    attempts: int = 6,
    initial_delay_seconds: float = 0.02,
) -> None:
    """Acquire the SQLite writer lock with bounded retry.

    Autonomous workers intentionally share one WAL database. A short-lived
    SQLITE_BUSY/locked condition is infrastructure contention, not a routing
    failure. Retry only those transient lock errors; preserve all other
    OperationalError behavior unchanged.
    """
    delay = max(0.0, float(initial_delay_seconds))
    for attempt in range(max(1, int(attempts))):
        try:
            conn.execute("begin immediate")
            return
        except sqlite3.OperationalError as exc:
            detail = str(exc).lower()
            transient = (
                "database is locked" in detail
                or "database is busy" in detail
                or "database table is locked" in detail
            )
            if not transient or attempt + 1 >= attempts:
                raise
            if conn.in_transaction:
                conn.rollback()
            time.sleep(delay)
            delay = min(0.32, max(0.02, delay * 2.0))


def ensure_route_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists route_jobs (
          id integer primary key autoincrement,
          dedupe_key text unique not null,
          source_event_id integer,
          task_id text,
          route_kind text not null,
          state text not null,
          attempt_count integer not null default 0,
          artifact_sha text,
          question_sha text,
          base_sha text,
          external_ref text,
          parent_route_id integer,
          resolution_type text,
          last_error text,
          meta_json text not null default '{}',
          created_at text not null,
          updated_at text not null
        );
        create index if not exists route_jobs_state_idx
          on route_jobs(state, route_kind);
        create index if not exists route_jobs_parent_idx
          on route_jobs(parent_route_id, resolution_type, state);
        create table if not exists route_decisions (
          id integer primary key autoincrement,
          route_job_id integer not null,
          source_event_id integer,
          task_id text,
          decision text not null,
          reason text not null,
          meta_json text not null default '{}',
          created_at text not null
        );
        create table if not exists copilot_jobs (
          id integer primary key autoincrement,
          route_job_id integer unique not null,
          task_id text not null,
          issue_number integer,
          pr_number integer,
          branch text,
          base_sha text not null,
          candidate_sha text,
          state text not null,
          last_error text,
          created_at text not null,
          updated_at text not null
        );
        create table if not exists api_usage (
          id integer primary key autoincrement,
          route_job_id integer,
          ai_run_id integer,
          task_id text,
          artifact_sha text,
          model text not null,
          input_tokens integer not null default 0,
          cached_input_tokens integer not null default 0,
          output_tokens integer not null default 0,
          reasoning_tokens integer not null default 0,
          estimated_cost_usd real,
          status text not null,
          created_at text not null
        );
        """
    )
    conn.commit()
def _row_to_job(row) -> RouteJob:
    return RouteJob(
        id=row[0],
        dedupe_key=row[1],
        source_event_id=row[2],
        task_id=row[3],
        route_kind=row[4],
        state=row[5],
        attempt_count=row[6],
        artifact_sha=row[7],
        question_sha=row[8],
        base_sha=row[9],
        external_ref=row[10],
        parent_route_id=row[11],
        resolution_type=row[12],
        last_error=row[13],
        meta_json=row[14],
        created_at=row[15],
        updated_at=row[16],
    )


def _fetch_job(conn: sqlite3.Connection, route_id: int) -> RouteJob:
    row = conn.execute(
        """select id,dedupe_key,source_event_id,task_id,route_kind,state,attempt_count,
                  artifact_sha,question_sha,base_sha,external_ref,parent_route_id,
                  resolution_type,last_error,meta_json,created_at,updated_at
             from route_jobs where id=?""",
        (route_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"route job not found: {route_id}")
    return _row_to_job(row)


def claim_route(conn: sqlite3.Connection, spec: RouteSpec) -> RouteJob:
    ensure_route_schema(conn)
    now = _now()
    meta_json = json.dumps(spec.meta or {}, sort_keys=True, separators=(",", ":"))
    _begin_immediate(conn)
    try:
        conn.execute(
            """insert or ignore into route_jobs(
                 dedupe_key,source_event_id,task_id,route_kind,state,artifact_sha,
                 question_sha,base_sha,parent_route_id,resolution_type,meta_json,
                 created_at,updated_at
               ) values(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                spec.dedupe_key,
                spec.source_event_id,
                spec.task_id,
                spec.route_kind,
                "NEW",
                spec.artifact_sha,
                spec.question_sha,
                spec.base_sha,
                spec.parent_route_id,
                spec.resolution_type,
                meta_json,
                now,
                now,
            ),
        )
        row = conn.execute(
            """select id,dedupe_key,source_event_id,task_id,route_kind,state,attempt_count,
                      artifact_sha,question_sha,base_sha,external_ref,parent_route_id,
                      resolution_type,last_error,meta_json,created_at,updated_at
                 from route_jobs where dedupe_key=?""",
            (spec.dedupe_key,),
        ).fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return _row_to_job(row)
def transition_route(
    conn: sqlite3.Connection,
    route_id: int,
    expected: str,
    new: str,
    **fields,
) -> RouteJob:
    if new not in VALID_TRANSITIONS.get(expected, set()):
        raise StateConflict(f"invalid route transition: {expected} -> {new}")
    allowed = {
        "source_event_id",
        "task_id",
        "artifact_sha",
        "question_sha",
        "base_sha",
        "external_ref",
        "parent_route_id",
        "resolution_type",
        "last_error",
        "meta_json",
        "attempt_count",
    }
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"unsupported route fields: {sorted(unknown)}")
    assignments = ["state=?", "updated_at=?"]
    values: list[object] = [new, _now()]
    for name, value in fields.items():
        assignments.append(f"{name}=?")
        values.append(value)
    values.extend([route_id, expected])
    _begin_immediate(conn)
    try:
        cursor = conn.execute(
            f"update route_jobs set {','.join(assignments)} where id=? and state=?",
            values,
        )
        if cursor.rowcount != 1:
            conn.rollback()
            raise StateConflict(
                f"route {route_id} was not in expected state {expected}"
            )
        conn.commit()
    except StateConflict:
        raise
    except Exception:
        conn.rollback()
        raise
    return _fetch_job(conn, route_id)


def append_decision(
    conn: sqlite3.Connection,
    route_job_id: int,
    decision: str,
    reason: str,
    source_event_id: int | None = None,
    task_id: str | None = None,
    meta: dict | None = None,
) -> int:
    cursor = conn.execute(
        """insert into route_decisions(
             route_job_id,source_event_id,task_id,decision,reason,meta_json,created_at
           ) values(?,?,?,?,?,?,?)""",
        (
            route_job_id,
            source_event_id,
            task_id,
            decision,
            reason,
            json.dumps(meta or {}, sort_keys=True, separators=(",", ":")),
            _now(),
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)
def find_active_child(
    conn: sqlite3.Connection,
    parent_route_id: int,
    resolution_type: str,
) -> RouteJob | None:
    terminal = sorted(TERMINAL_STATES)
    placeholders = ",".join("?" for _ in terminal)
    row = conn.execute(
        f"""select id,dedupe_key,source_event_id,task_id,route_kind,state,attempt_count,
                   artifact_sha,question_sha,base_sha,external_ref,parent_route_id,
                   resolution_type,last_error,meta_json,created_at,updated_at
              from route_jobs
             where parent_route_id=? and resolution_type=?
               and state not in ({placeholders})
             order by id desc limit 1""",
        (parent_route_id, resolution_type, *terminal),
    ).fetchone()
    return None if row is None else _row_to_job(row)
