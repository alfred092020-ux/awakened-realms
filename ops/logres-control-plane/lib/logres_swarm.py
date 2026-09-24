from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from logres_optimizer import rank_task_ids


TERMINAL_JOB_STATES = {"DONE", "BLOCKED", "FAILED", "SUPERSEDED"}
RESEARCH_WORK_TYPES = {"research", "evidence", "analysis"}
IMPLEMENTATION_WORK_TYPES = {"implementation", "regression", "code"}


@dataclass(frozen=True)
class SwarmCapacity:
    max_workers: int
    active_leases: int
    active_research: int
    active_copilot: int
    free_slots: int


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """create table if not exists swarm_jobs(
             id integer primary key autoincrement,
             task_id text not null,
             worker_id text not null,
             engine text not null,
             state text not null,
             pid integer,
             artifact_path text,
             last_error text,
             started_at text not null default (datetime('now')),
             updated_at text not null default (datetime('now')),
             finished_at text
           )"""
    )
    conn.execute(
        "create index if not exists idx_swarm_jobs_state on swarm_jobs(state)"
    )
    conn.execute(
        "create unique index if not exists idx_swarm_jobs_live_task "
        "on swarm_jobs(task_id) where state in ('STARTING','RUNNING')"
    )
    conn.commit()


def pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def reconcile_jobs(conn: sqlite3.Connection) -> list[int]:
    ensure_schema(conn)
    stale: list[int] = []
    for row in conn.execute(
        "select id,pid,state from swarm_jobs where state in ('STARTING','RUNNING')"
    ):
        if not pid_alive(row[1]):
            conn.execute(
                """update swarm_jobs
                      set state='FAILED',
                          last_error=coalesce(last_error,'worker process exited'),
                          updated_at=datetime('now'),
                          finished_at=datetime('now')
                    where id=?""",
                (row[0],),
            )
            stale.append(int(row[0]))
    conn.commit()
    return stale


def swarm_capacity(conn: sqlite3.Connection, config: dict) -> SwarmCapacity:
    ensure_schema(conn)
    now = time.time()
    max_workers = int(config.get("swarm", {}).get("max_workers", 6) or 6)
    active_leases = int(
        conn.execute(
            "select count(*) from brain_task_leases "
            "where lease_until_epoch>? and chat_id<>'lead'",
            (now,),
        ).fetchone()[0]
    )
    active_research = int(
        conn.execute(
            "select count(*) from swarm_jobs "
            "where engine='research' and state in ('STARTING','RUNNING')"
        ).fetchone()[0]
    )
    try:
        active_copilot = int(
            conn.execute(
                "select count(*) from copilot_jobs "
                "where state in ('ISSUE_CREATED','ASSIGNED','PR_READY','VERIFYING')"
            ).fetchone()[0]
        )
    except sqlite3.OperationalError:
        active_copilot = 0
    free_slots = max(0, max_workers - active_leases - active_copilot)
    return SwarmCapacity(
        max_workers=max_workers,
        active_leases=active_leases,
        active_research=active_research,
        active_copilot=active_copilot,
        free_slots=free_slots,
    )


def ready_tasks(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """select t.id,t.priority,t.title,t.lane,t.status,
                  coalesce(m.work_type,'implementation') work_type,
                  coalesce(m.expected_minutes,60) expected_minutes,
                  coalesce(m.concurrency_key,'') concurrency_key,
                  coalesce(m.evidence_policy,'') evidence_policy
             from tasks t
             left join task_metadata m on m.task_id=t.id
            where t.status='READY'
            order by t.priority asc,
                     coalesce(m.expected_minutes,60) asc,
                     t.id asc"""
    ).fetchall()
    return [dict(r) for r in rows]


def classify_engine(task: dict) -> str:
    work_type = str(task.get("work_type") or "").lower()
    if work_type in RESEARCH_WORK_TYPES:
        return "research"
    if work_type in IMPLEMENTATION_WORK_TYPES:
        return "copilot"
    return "manual"


def select_research_tasks(
    conn: sqlite3.Connection,
    limit: int,
    *,
    skip_task_ids: set[str] | None = None,
) -> list[dict]:
    skip_task_ids = skip_task_ids or set()
    selected: list[dict] = []
    keys: set[str] = set()
    claimed = [
        tuple(row)
        for row in conn.execute("select task_id,path_prefix from claims")
    ]
    selected_scopes: list[tuple[str, str]] = []

    task_map = {task["id"]: task for task in ready_tasks(conn)}
    ranked_ids = rank_task_ids(
        conn,
        limit=max(16, max(1, limit) * 4),
        work_type_filter=RESEARCH_WORK_TYPES,
    )
    for task_id in ranked_ids:
        task = task_map.get(task_id)
        if task is None:
            continue
        if task["id"] in skip_task_ids or classify_engine(task) != "research":
            continue
        key = task.get("concurrency_key") or task.get("lane") or ""
        if key and key in keys:
            continue
        scopes = [
            row[0]
            for row in conn.execute(
                "select path_prefix from task_scopes where task_id=? order by path_prefix",
                (task["id"],),
            )
        ]
        conflict = False
        for scope in scopes:
            a = scope.rstrip("/") + "/"
            for owner_task, prior in claimed + selected_scopes:
                if owner_task == task["id"]:
                    continue
                b = prior.rstrip("/") + "/"
                if a.startswith(b) or b.startswith(a):
                    conflict = True
                    break
            if conflict:
                break
        if conflict:
            continue
        selected.append(task)
        if key:
            keys.add(key)
        selected_scopes.extend((task["id"], scope) for scope in scopes)
        if len(selected) >= max(0, limit):
            break
    return selected


def prior_failures(conn: sqlite3.Connection, task_id: str) -> int:
    ensure_schema(conn)
    return int(
        conn.execute(
            """select count(*) from swarm_jobs
                where task_id=? and state='FAILED'
                  and artifact_path is not null""",
            (task_id,),
        ).fetchone()[0]
    )


def worker_ids(config: dict) -> list[str]:
    count = int(config.get("swarm", {}).get("research_workers", 2) or 2)
    return [f"auto-research-{i}" for i in range(1, max(1, count) + 1)]


def available_worker_ids(conn: sqlite3.Connection, config: dict) -> list[str]:
    now = time.time()
    busy = {
        row[0]
        for row in conn.execute(
            "select chat_id from brain_task_leases where lease_until_epoch>?",
            (now,),
        )
    }
    return [worker for worker in worker_ids(config) if worker not in busy]


def register_worker(root: Path, worker_id: str) -> None:
    subprocess.run(
        [str(root / "bin/logres-brain"), "join", worker_id, "--name", worker_id],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def acquire_task(root: Path, worker_id: str, task_id: str) -> str | None:
    proc = subprocess.run(
        [
            str(root / "bin/logres-coordinator"),
            "acquire",
            worker_id,
            "--task",
            task_id,
            "--minutes",
            "120",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode:
        return None
    match = re.search(r"ACQUIRED task=\S+ branch=(\S+)", proc.stdout)
    return match.group(1) if match else None


def create_job(
    conn: sqlite3.Connection,
    task_id: str,
    worker_id: str,
    engine: str,
) -> int:
    ensure_schema(conn)
    cur = conn.execute(
        """insert into swarm_jobs(task_id,worker_id,engine,state)
           values(?,?,?,'STARTING')""",
        (task_id, worker_id, engine),
    )
    conn.commit()
    return int(cur.lastrowid)


def mark_job_running(conn: sqlite3.Connection, job_id: int, pid: int) -> None:
    conn.execute(
        """update swarm_jobs set state='RUNNING',pid=?,updated_at=datetime('now')
           where id=?""",
        (pid, job_id),
    )
    conn.commit()


def status_dict(conn: sqlite3.Connection, config: dict) -> dict:
    cap = swarm_capacity(conn, config)
    jobs = [
        dict(row)
        for row in conn.execute(
            "select * from swarm_jobs order by id desc limit 20"
        )
    ]
    return {
        "enabled": bool(config.get("swarm", {}).get("enabled", False)),
        "capacity": {
            "max_workers": cap.max_workers,
            "active_leases": cap.active_leases,
            "active_research": cap.active_research,
            "active_copilot": cap.active_copilot,
            "free_slots": cap.free_slots,
        },
        "ready": [
            {
                "task_id": task["id"],
                "engine": classify_engine(task),
                "priority": task["priority"],
                "work_type": task["work_type"],
            }
            for task in ready_tasks(conn)
        ],
        "jobs": jobs,
    }


def load_config(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
