from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

COMPLETE_TASK = {"DONE", "RESOLVED"}
RUNNABLE_TASK = {"READY", "ACTIVE"}
BLOCKED_TASK = {"BLOCKED_DEP"}
EXTERNAL_TASK = {"BLOCKED_EVIDENCE"}
IGNORED_TASK = {"SUPERSEDED", "CANCELLED"}
def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists mission_objectives(
          id text primary key,
          parent_id text,
          title text not null,
          weight real not null default 1,
          definition_of_done text not null default '',
          status_override text not null default 'AUTO',
          sort_order integer not null default 100,
          created_at text not null,
          updated_at text not null
        );
        create table if not exists mission_links(
          objective_id text not null,
          milestone_id text,
          task_id text,
          gate_type text not null default 'required',
          primary key(objective_id,milestone_id,task_id,gate_type)
        );
        create index if not exists mission_parent_idx
          on mission_objectives(parent_id,sort_order,id);
        """
    )
    conn.commit()
def _sync_milestones(
    conn: sqlite3.Connection,
    payload: dict,
    stamp: str,
) -> int:
    if not _table_exists(conn, "milestones"):
        return 0
    columns = {
        str(row[1])
        for row in conn.execute("pragma table_info(milestones)")
    }
    if not {"id", "status"}.issubset(columns):
        return 0

    items = list(payload.get("milestones", []))
    for index, item in enumerate(items, start=1):
        milestone_id = str(item["id"])
        existing = conn.execute(
            "select status from milestones where id=?",
            (milestone_id,),
        ).fetchone()
        values = {
            "title": str(item.get("title", milestone_id)),
            "sort_order": int(item.get("sort_order", index * 10)),
            "definition_of_done": str(item.get("definition_of_done", "")),
            "updated_at": stamp,
        }
        if existing:
            updates = [
                (name, value)
                for name, value in values.items()
                if name in columns
            ]
            if updates:
                assignments = ",".join(f"{name}=?" for name, _ in updates)
                conn.execute(
                    f"update milestones set {assignments} where id=?",
                    (*[value for _name, value in updates], milestone_id),
                )
            continue

        insert_values = {
            "id": milestone_id,
            "status": str(item.get("status", "PLANNED")),
            "created_at": stamp,
            **values,
        }
        selected = [
            (name, value)
            for name, value in insert_values.items()
            if name in columns
        ]
        names = ",".join(name for name, _ in selected)
        marks = ",".join("?" for _ in selected)
        conn.execute(
            f"insert into milestones({names}) values({marks})",
            tuple(value for _name, value in selected),
        )
    return len(items)


def load_config(conn: sqlite3.Connection, config_path: Path) -> dict:
    ensure_schema(conn)
    payload = json.loads(Path(config_path).read_text())
    mission_id = str(payload["mission_id"])
    stamp = now()
    root = conn.execute(
        "select 1 from mission_objectives where id=?",
        (mission_id,),
    ).fetchone()
    if root is None:
        conn.execute(
            """insert into mission_objectives(
                 id,parent_id,title,weight,definition_of_done,status_override,
                 sort_order,created_at,updated_at
               ) values(?,?,?,?,?,'AUTO',0,?,?)""",
            (
                mission_id,
                None,
                str(payload.get("title", mission_id)),
                1.0,
                "All required child objectives are complete.",
                stamp,
                stamp,
            ),
        )
    for index, item in enumerate(payload.get("objectives", []), start=1):
        conn.execute(
            """insert into mission_objectives(
                 id,parent_id,title,weight,definition_of_done,status_override,
                 sort_order,created_at,updated_at
               ) values(?,?,?,?,?,'AUTO',?,?,?)
               on conflict(id) do update set
                 parent_id=excluded.parent_id,
                 title=excluded.title,
                 weight=excluded.weight,
                 definition_of_done=excluded.definition_of_done,
                 sort_order=excluded.sort_order,
                 updated_at=excluded.updated_at""",
            (
                str(item["id"]),
                str(item.get("parent_id") or mission_id),
                str(item["title"]),
                float(item.get("weight", 1)),
                str(item.get("definition_of_done", "")),
                int(item.get("sort_order", index * 10)),
                stamp,
                stamp,
            ),
        )
    milestone_count = _sync_milestones(conn, payload, stamp)
    conn.execute(
        "delete from mission_links where objective_id in "
        "(select id from mission_objectives)"
    )
    for link in payload.get("links", []):
        conn.execute(
            """insert or ignore into mission_links(
                 objective_id,milestone_id,task_id,gate_type
               ) values(?,?,?,?)""",
            (
                str(link["objective_id"]),
                link.get("milestone_id"),
                link.get("task_id"),
                str(link.get("gate_type", "required")),
            ),
        )
    conn.commit()
    return {
        "mission_id": mission_id,
        "objectives": len(payload.get("objectives", [])) + 1,
        "milestones": milestone_count,
        "links": len(payload.get("links", [])),
    }


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "select 1 from sqlite_master where type='table' and name=?",
        (name,),
    ).fetchone() is not None
def _link_states(conn: sqlite3.Connection, objective_id: str) -> list[str]:
    states: list[str] = []
    for row in conn.execute(
        """select milestone_id,task_id,gate_type
             from mission_links where objective_id=?
             order by gate_type,milestone_id,task_id""",
        (objective_id,),
    ):
        milestone_id, task_id = row[0], row[1]
        if task_id and _table_exists(conn, "tasks"):
            task = conn.execute(
                "select status from tasks where id=?", (task_id,)
            ).fetchone()
            states.append(_task_state(str(task[0])) if task else "UNCOVERED")
        elif milestone_id and _table_exists(conn, "milestones"):
            milestone = conn.execute(
                "select status from milestones where id=?", (milestone_id,)
            ).fetchone()
            states.append(_milestone_state(str(milestone[0])) if milestone else "UNCOVERED")
        else:
            states.append("UNCOVERED")
    return states


def _task_state(status: str) -> str:
    if status in COMPLETE_TASK:
        return "COMPLETE"
    if status in RUNNABLE_TASK:
        return "IN_PROGRESS"
    if status in EXTERNAL_TASK:
        return "WAITING_EXTERNAL"
    if status in BLOCKED_TASK:
        return "BLOCKED"
    if status in IGNORED_TASK:
        return "UNCOVERED"
    return "UNCOVERED"
def _milestone_state(status: str) -> str:
    if status in {"DONE", "COMPLETE", "RESOLVED"}:
        return "COMPLETE"
    if status in {"ACTIVE", "READY", "IN_PROGRESS"}:
        return "IN_PROGRESS"
    if status in {"BLOCKED_EVIDENCE", "WAITING_EXTERNAL"}:
        return "WAITING_EXTERNAL"
    if status in {"BLOCKED", "BLOCKED_DEP"}:
        return "BLOCKED"
    return "UNCOVERED"


def _combine(states: list[str]) -> str:
    if not states:
        return "UNCOVERED"
    if all(state == "COMPLETE" for state in states):
        return "COMPLETE"
    if any(state in {"IN_PROGRESS", "COMPLETE"} for state in states):
        return "IN_PROGRESS"
    if all(state == "WAITING_EXTERNAL" for state in states):
        return "WAITING_EXTERNAL"
    if any(state == "BLOCKED" for state in states):
        return "BLOCKED"
    if any(state == "WAITING_EXTERNAL" for state in states):
        return "WAITING_EXTERNAL"
    return "UNCOVERED"


@dataclass(frozen=True)
class ObjectiveStatus:
    id: str
    title: str
    state: str
    progress_percent: float
    definition_of_done: str
    children: tuple["ObjectiveStatus", ...]
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "state": self.state,
            "progress_percent": round(self.progress_percent, 2),
            "definition_of_done": self.definition_of_done,
            "children": [child.to_dict() for child in self.children],
        }


def objective_status(conn: sqlite3.Connection, objective_id: str) -> ObjectiveStatus:
    ensure_schema(conn)
    row = conn.execute(
        """select id,title,definition_of_done,status_override
             from mission_objectives where id=?""",
        (objective_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"unknown objective: {objective_id}")
    children = [
        objective_status(conn, str(child[0]))
        for child in conn.execute(
            """select id from mission_objectives
               where parent_id=? order by sort_order,id""",
            (objective_id,),
        )
    ]
    if children:
        weighted_total = 0.0
        weighted_done = 0.0
        child_states = []
        for child in children:
            weight_row = conn.execute(
                "select weight from mission_objectives where id=?",
                (child.id,),
            ).fetchone()
            weight = float(weight_row[0] if weight_row else 1.0)
            weighted_total += weight
            weighted_done += weight * child.progress_percent / 100.0
            child_states.append(child.state)
        state = _combine(child_states)
        progress = 0.0 if weighted_total <= 0 else weighted_done / weighted_total * 100.0
    else:
        link_states = _link_states(conn, objective_id)
        state = _combine(link_states)
        if not link_states:
            progress = 0.0
        else:
            completed = sum(1 for item in link_states if item == "COMPLETE")
            partial = sum(1 for item in link_states if item == "IN_PROGRESS")
            progress = (completed + partial * 0.5) / len(link_states) * 100.0
    override = str(row[3] or "AUTO")
    if override != "AUTO":
        state = override
        progress = 100.0 if override == "COMPLETE" else progress
    return ObjectiveStatus(
        id=str(row[0]),
        title=str(row[1]),
        state=state,
        progress_percent=progress,
        definition_of_done=str(row[2] or ""),
        children=tuple(children),
    )
def mission_roots(conn: sqlite3.Connection) -> list[str]:
    ensure_schema(conn)
    return [
        str(row[0])
        for row in conn.execute(
            """select id from mission_objectives
               where parent_id is null order by sort_order,id"""
        )
    ]


def mission_status(conn: sqlite3.Connection) -> dict:
    roots = mission_roots(conn)
    payload = [objective_status(conn, root).to_dict() for root in roots]
    leaves = list(_flatten_leaves(payload))
    counts: dict[str, int] = {}
    for leaf in leaves:
        counts[leaf["state"]] = counts.get(leaf["state"], 0) + 1
    return {
        "missions": payload,
        "leaf_counts": counts,
        "uncovered": [leaf for leaf in leaves if leaf["state"] == "UNCOVERED"],
    }


def _flatten_leaves(nodes: list[dict]):
    for node in nodes:
        children = node.get("children", [])
        if children:
            yield from _flatten_leaves(children)
        else:
            yield node


def tree_lines(node: dict, depth: int = 0) -> list[str]:
    prefix = "  " * depth
    line = (
        f"{prefix}{node['id']} [{node['state']}] "
        f"{node['progress_percent']:.2f}% - {node['title']}"
    )
    lines = [line]
    for child in node.get("children", []):
        lines.extend(tree_lines(child, depth + 1))
    return lines
