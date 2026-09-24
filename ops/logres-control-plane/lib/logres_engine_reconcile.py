from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from logres_route_store import VALID_TRANSITIONS

TERMINAL_TASK = {"SUPERSEDED", "CANCELLED", "BLOCKED_EVIDENCE"}
COPILOT_LIVE = {"ASSIGNING", "ACTIVE", "PR_READY", "VERIFYING", "QUEUED"}
ROUTE_LIVE = {"ASSIGNING", "ROUTED", "ACTIVE", "PR_READY", "VERIFYING", "QUEUED"}
SWARM_LIVE = {"STARTING", "RUNNING"}
INTEGRATION_RESOLVED = {"INTEGRATED", "SUPERSEDED"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def in_states(states):
    return ",".join("'" + state + "'" for state in sorted(states))


def _table_exists(conn, table):
    row = conn.execute(
        "select 1 from sqlite_master where type='table' and name=?",
        (table,),
    ).fetchone()
    return row is not None


def _candidate_resolved(conn, task_id, candidate_sha):
    if not candidate_sha or not _table_exists(conn, "integration_queue"):
        return False
    placeholders = ",".join("?" for _ in INTEGRATION_RESOLVED)
    row = conn.execute(
        f"""select 1
              from integration_queue
             where task_id=? and sha=?
               and status in ({placeholders})
             limit 1""",
        (task_id, candidate_sha, *sorted(INTEGRATION_RESOLVED)),
    ).fetchone()
    return row is not None


def _task_resolved(conn, task_id):
    if not _table_exists(conn, "integration_queue"):
        return False
    placeholders = ",".join("?" for _ in INTEGRATION_RESOLVED)
    row = conn.execute(
        f"""select 1
              from integration_queue
             where task_id=?
               and status in ({placeholders})
             limit 1""",
        (task_id, *sorted(INTEGRATION_RESOLVED)),
    ).fetchone()
    return row is not None


def _terminal_reason(conn, task_id, task_status, candidate_sha=None):
    if task_status == "MISSING":
        return "task_missing"
    if task_status in TERMINAL_TASK:
        return "task_" + task_status.lower()
    if task_status != "DONE":
        return None

    if candidate_sha:
        if _candidate_resolved(conn, task_id, candidate_sha):
            return "candidate_resolved"
        return None

    if _task_resolved(conn, task_id):
        return "task_integration_resolved"
    return None


def _copilot_by_route(conn):
    if not _table_exists(conn, "copilot_jobs"):
        return {}
    rows = conn.execute(
        f"""select route_job_id,task_id,state,candidate_sha
              from copilot_jobs
             where route_job_id is not null
               and state in ({in_states(COPILOT_LIVE)})"""
    ).fetchall()
    return {
        int(row[0]): {
            "task_id": row[1],
            "state": row[2],
            "candidate_sha": row[3],
        }
        for row in rows
    }


def plan(conn):
    actions = []

    for row in conn.execute(
        f"""select c.id,c.task_id,c.state,t.status,c.branch,c.candidate_sha
              from copilot_jobs c
              left join tasks t on t.id=c.task_id
             where c.state in ({in_states(COPILOT_LIVE)})"""
    ):
        task_status = row[3] or "MISSING"
        reason = _terminal_reason(
            conn,
            row[1],
            task_status,
            row[5],
        )
        if reason:
            actions.append(
                {
                    "engine": "copilot",
                    "id": row[0],
                    "task_id": row[1],
                    "from_state": row[2],
                    "to_state": "SUPERSEDED",
                    "reason": reason,
                    "branch": row[4],
                    "candidate_sha": row[5],
                }
            )

    copilot_by_route = _copilot_by_route(conn)
    for row in conn.execute(
        f"""select r.id,r.task_id,r.state,t.status,r.external_ref,r.last_error
              from route_jobs r
              left join tasks t on t.id=r.task_id
             where r.state in ({in_states(ROUTE_LIVE)})"""
    ):
        task_status = row[3] or "MISSING"
        child = copilot_by_route.get(int(row[0]))
        candidate_sha = child["candidate_sha"] if child else None

        reason = _terminal_reason(
            conn,
            row[1],
            task_status,
            candidate_sha,
        )
        if reason:
            actions.append(
                {
                    "engine": "route",
                    "id": row[0],
                    "task_id": row[1],
                    "from_state": row[2],
                    "to_state": "SUPERSEDED",
                    "reason": reason,
                    "external_ref": row[4],
                    "last_error": row[5],
                }
            )

    for row in conn.execute(
        """select s.id,s.task_id,s.state,t.status,s.pid,s.artifact_path,s.last_error
             from swarm_jobs s
             left join tasks t on t.id=s.task_id
            where s.state in ('STARTING','RUNNING')"""
    ):
        task_status = row[3] or "MISSING"
        if task_status in TERMINAL_TASK or task_status in {"DONE", "MISSING"}:
            actions.append(
                {
                    "engine": "swarm",
                    "id": row[0],
                    "task_id": row[1],
                    "from_state": row[2],
                    "to_state": "SUPERSEDED",
                    "reason": "task_" + task_status.lower(),
                    "pid": row[4],
                    "artifact_path": row[5],
                    "last_error": row[6],
                }
            )

    for row in conn.execute(
        """select l.task_id,l.chat_id,l.branch,t.status,l.lease_until_epoch
             from brain_task_leases l
             left join tasks t on t.id=l.task_id"""
    ):
        task_status = row[3] or "MISSING"
        if task_status in TERMINAL_TASK or task_status in {"DONE", "MISSING"}:
            actions.append(
                {
                    "engine": "lease",
                    "id": row[0],
                    "task_id": row[0],
                    "from_state": "LEASED",
                    "to_state": "RELEASED",
                    "reason": "task_" + task_status.lower(),
                    "chat_id": row[1],
                    "branch": row[2],
                    "lease_until_epoch": row[4],
                }
            )

    return sorted(actions, key=lambda item: (item["engine"], str(item["id"])))


def apply(conn):
    actions = plan(conn)
    stamp = now()

    for action in actions:
        if action["engine"] == "copilot":
            conn.execute(
                """update copilot_jobs
                      set state='SUPERSEDED',updated_at=?
                    where id=? and state=?""",
                (stamp, action["id"], action["from_state"]),
            )
        elif action["engine"] == "route":
            allowed = VALID_TRANSITIONS.get(action["from_state"], set())
            if "SUPERSEDED" not in allowed:
                raise RuntimeError(
                    "route state lacks legal terminal transition: "
                    + action["from_state"]
                )
            conn.execute(
                """update route_jobs
                      set state='SUPERSEDED',updated_at=?
                    where id=? and state=?""",
                (stamp, action["id"], action["from_state"]),
            )
        elif action["engine"] == "swarm":
            conn.execute(
                """update swarm_jobs
                      set state='SUPERSEDED',
                          updated_at=?,
                          finished_at=coalesce(finished_at,?)
                    where id=? and state=?""",
                (
                    stamp,
                    stamp,
                    action["id"],
                    action["from_state"],
                ),
            )
        else:
            conn.execute(
                "delete from brain_task_leases where task_id=?",
                (action["task_id"],),
            )

    conn.commit()
    return actions
