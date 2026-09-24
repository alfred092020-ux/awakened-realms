from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


COMPLETE = {"DONE", "RESOLVED"}
IGNORED = {"SUPERSEDED", "CANCELLED"}
RUNNABLE = {"READY", "ACTIVE"}


@dataclass(frozen=True)
class GoalPlan:
    milestone_id: str
    title: str
    definition_of_done: str
    state: str
    progress_percent: float
    total_minutes: float
    completed_minutes: float
    counts: dict
    next_actions: tuple[dict, ...]
    external_blockers: tuple[dict, ...]
    dependency_blockers: tuple[dict, ...]
    fingerprint: str

    def to_dict(self) -> dict:
        value = asdict(self)
        value["next_actions"] = list(self.next_actions)
        value["external_blockers"] = list(self.external_blockers)
        value["dependency_blockers"] = list(self.dependency_blockers)
        return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """create table if not exists goal_snapshots(
             milestone_id text primary key,
             fingerprint text not null,
             state text not null,
             payload_json text not null,
             updated_at text not null
           )"""
    )
    conn.commit()


def active_milestones(conn: sqlite3.Connection) -> list[str]:
    try:
        rows = conn.execute(
            "select id from milestones where status='ACTIVE' order by sort_order,id"
        )
    except sqlite3.OperationalError:
        return []
    return [str(row[0]) for row in rows]


def _task_rows(conn: sqlite3.Connection, milestone_id: str) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """select t.id,t.priority,t.title,t.status,t.note,
                      coalesce(m.expected_minutes,30) expected_minutes,
                      coalesce(l.progress,0) lease_progress
                 from tasks t
                 join task_metadata m on m.task_id=t.id
                 left join brain_task_leases l on l.task_id=t.id
                where m.milestone=?
                order by t.priority,t.id""",
            (milestone_id,),
        )
    )


def _dependency_detail(conn: sqlite3.Connection, task_id: str) -> list[dict]:
    rows = conn.execute(
        """select d.depends_on,d.kind,d.rationale,coalesce(t.status,'MISSING')
             from task_dependencies d
             left join tasks t on t.id=d.depends_on
            where d.task_id=?
            order by d.kind,d.depends_on""",
        (task_id,),
    )
    return [
        {
            "task_id": str(row[0]),
            "kind": str(row[1]),
            "rationale": str(row[2] or ""),
            "status": str(row[3]),
        }
        for row in rows
        if str(row[3]) not in COMPLETE | IGNORED
    ]
def plan_milestone(conn: sqlite3.Connection, milestone_id: str) -> GoalPlan:
    ensure_schema(conn)
    milestone = conn.execute(
        """select id,title,definition_of_done
             from milestones where id=?""",
        (milestone_id,),
    ).fetchone()
    if milestone is None:
        raise ValueError(f"unknown milestone: {milestone_id}")

    rows = _task_rows(conn, milestone_id)
    considered = [row for row in rows if str(row["status"]) not in IGNORED]
    total = sum(float(row["expected_minutes"] or 0) for row in considered)
    completed = 0.0
    next_actions = []
    external = []
    dependency = []
    counts: dict[str, int] = {}

    for row in considered:
        status = str(row["status"])
        counts[status] = counts.get(status, 0) + 1
        minutes = float(row["expected_minutes"] or 0)
        if status in COMPLETE:
            completed += minutes
        elif status == "ACTIVE":
            progress = max(0.0, min(100.0, float(row["lease_progress"] or 0)))
            completed += minutes * progress / 100.0

        item = {
            "task_id": str(row["id"]),
            "priority": int(row["priority"] or 0),
            "title": str(row["title"]),
            "status": status,
            "expected_minutes": int(row["expected_minutes"] or 0),
        }
        if status in RUNNABLE:
            next_actions.append(item)
        elif status == "BLOCKED_EVIDENCE":
            external.append(
                {
                    **item,
                    "note": str(row["note"] or ""),
                    "dependencies": _dependency_detail(conn, str(row["id"])),
                }
            )
        elif status == "BLOCKED_DEP":
            dependency.append(
                {
                    **item,
                    "dependencies": _dependency_detail(conn, str(row["id"])),
                }
            )

    incomplete = [
        row for row in considered if str(row["status"]) not in COMPLETE
    ]
    if not considered:
        state = "EMPTY"
    elif not incomplete:
        state = "COMPLETE"
    elif next_actions:
        state = "RUNNABLE"
    elif all(str(row["status"]) == "BLOCKED_EVIDENCE" for row in incomplete):
        state = "WAITING_EXTERNAL"
    else:
        state = "BLOCKED_DEP"

    progress = 100.0 if total <= 0 and not incomplete else (
        0.0 if total <= 0 else min(100.0, completed / total * 100.0)
    )
    next_actions.sort(
        key=lambda item: (
            item["priority"],
            0 if item["status"] == "ACTIVE" else 1,
            item["expected_minutes"],
            item["task_id"],
        )
    )
    external.sort(key=lambda item: (item["priority"], item["task_id"]))
    dependency.sort(key=lambda item: (item["priority"], item["task_id"]))

    fingerprint_payload = {
        "milestone_id": milestone_id,
        "state": state,
        "tasks": [
            [str(row["id"]), str(row["status"]), int(row["lease_progress"] or 0)]
            for row in considered
        ],
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            fingerprint_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    return GoalPlan(
        milestone_id=milestone_id,
        title=str(milestone["title"]),
        definition_of_done=str(milestone["definition_of_done"] or ""),
        state=state,
        progress_percent=round(progress, 2),
        total_minutes=round(total, 2),
        completed_minutes=round(completed, 2),
        counts=counts,
        next_actions=tuple(next_actions[:12]),
        external_blockers=tuple(external),
        dependency_blockers=tuple(dependency),
        fingerprint=fingerprint,
    )


def watch_milestone(
    conn: sqlite3.Connection,
    milestone_id: str,
    *,
    apply: bool = False,
) -> dict:
    plan = plan_milestone(conn, milestone_id)
    previous = conn.execute(
        """select fingerprint,state,payload_json,updated_at
             from goal_snapshots where milestone_id=?""",
        (milestone_id,),
    ).fetchone()
    changed = previous is None or str(previous["fingerprint"]) != plan.fingerprint
    result = {
        "changed": changed,
        "previous_state": str(previous["state"]) if previous else None,
        "plan": plan.to_dict(),
    }
    if apply and changed:
        payload = json.dumps(plan.to_dict(), sort_keys=True)
        conn.execute(
            """insert into goal_snapshots(
                 milestone_id,fingerprint,state,payload_json,updated_at
               ) values(?,?,?,?,?)
               on conflict(milestone_id) do update set
                 fingerprint=excluded.fingerprint,
                 state=excluded.state,
                 payload_json=excluded.payload_json,
                 updated_at=excluded.updated_at""",
            (
                milestone_id,
                plan.fingerprint,
                plan.state,
                payload,
                _now(),
            ),
        )
        conn.commit()
    return result


def portfolio(conn: sqlite3.Connection) -> dict:
    milestones = active_milestones(conn)
    plans = [plan_milestone(conn, item).to_dict() for item in milestones]
    states: dict[str, int] = {}
    for plan in plans:
        states[plan["state"]] = states.get(plan["state"], 0) + 1
    return {
        "active_milestones": plans,
        "states": states,
        "policy": {
            "manufacture_missing_work": False,
            "evidence_ceiling": (
                "WAITING_EXTERNAL means stop recursive research and wait for "
                "genuinely new evidence or external/manual capability."
            ),
            "scheduler": (
                "Goal watchdog describes objective state; task optimizer remains "
                "authoritative for runnable-task ordering."
            ),
        },
    }
