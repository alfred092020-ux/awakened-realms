from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from logres_copilot_router import ACTIVE_COPILOT_STATES
from logres_optimizer import rank_task_ids


TERMINAL_JOB_STATES = {"DONE", "BLOCKED", "FAILED", "SUPERSEDED"}
RESEARCH_WORK_TYPES = {"research", "evidence", "analysis"}
IMPLEMENTATION_WORK_TYPES = {"implementation", "regression", "code"}


@dataclass(frozen=True)
class SwarmCapacity:
    max_workers: int
    active_leases: int
    active_research: int
    active_patch: int
    active_devin: int
    active_copilot: int
    free_slots: int


def isolation_certificate_gate(
    certificate: dict, integration_sha: str, runtime_deployment: dict
) -> tuple[bool, str | None]:
    if not bool((certificate or {}).get("production_ready", False)):
        return False, "isolation_not_certified"
    current_sha = str(integration_sha or "").strip()
    certificate_sha = str((certificate or {}).get("integration_sha") or "").strip()
    if not current_sha or not certificate_sha or certificate_sha != current_sha:
        return False, "isolation_certificate_stale"
    runtime_sha = str((runtime_deployment or {}).get("integration_sha") or "").strip()
    if not runtime_sha or runtime_sha != current_sha:
        return False, "isolation_runtime_stale"
    return True, None


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """create table if not exists swarm_jobs(
             id integer primary key autoincrement,
             task_id text not null,
             worker_id text not null,
             engine text not null,
             state text not null,
             pid integer,
             branch text,
             model text,
             session_id text,
             verification text,
             artifact_path text,
             last_error text,
             started_at text not null default (datetime('now')),
             updated_at text not null default (datetime('now')),
             finished_at text
           )"""
    )
    existing = {
        str(row[1])
        for row in conn.execute("pragma table_info(swarm_jobs)").fetchall()
    }
    for name, ddl in (
        ("branch", "text"),
        ("model", "text"),
        ("session_id", "text"),
        ("verification", "text"),
    ):
        if name not in existing:
            conn.execute(f"alter table swarm_jobs add column {name} {ddl}")
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


def active_copilot_task_ids(conn: sqlite3.Connection) -> set[str]:
    states = tuple(sorted(ACTIVE_COPILOT_STATES))
    placeholders = ",".join("?" for _ in states)
    try:
        rows = conn.execute(
            f"select distinct task_id from copilot_jobs "
            f"where state in ({placeholders})",
            states,
        ).fetchall()
    except sqlite3.OperationalError:
        return set()
    return {str(row[0]) for row in rows if row[0]}


def active_copilot_job_count(conn: sqlite3.Connection) -> int:
    states = tuple(sorted(ACTIVE_COPILOT_STATES))
    placeholders = ",".join("?" for _ in states)
    try:
        return int(
            conn.execute(
                f"select count(*) from copilot_jobs "
                f"where state in ({placeholders})",
                states,
            ).fetchone()[0]
        )
    except sqlite3.OperationalError:
        return 0


def active_swarm_task_ids(conn: sqlite3.Connection) -> set[str]:
    ensure_schema(conn)
    return {
        str(row[0])
        for row in conn.execute(
            "select distinct task_id from swarm_jobs "
            "where state in ('STARTING','RUNNING')"
        )
        if row[0]
    }


def active_swarm_engine_count(conn: sqlite3.Connection, engine: str) -> int:
    ensure_schema(conn)
    return int(
        conn.execute(
            "select count(*) from swarm_jobs "
            "where engine=? and state in ('STARTING','RUNNING')",
            (engine,),
        ).fetchone()[0]
    )


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
    active_research = active_swarm_engine_count(conn, "research")
    active_patch = active_swarm_engine_count(conn, "openai-patch")
    active_devin = active_swarm_engine_count(conn, "devin")
    active_copilot = active_copilot_job_count(conn)
    # Research and OpenAI patch workers both hold Brain leases, so they are
    # already represented in active_leases. Copilot jobs are external and do
    # not necessarily hold a Brain lease, so only Copilot is added separately.
    free_slots = max(0, max_workers - active_leases - active_copilot)
    return SwarmCapacity(
        max_workers=max_workers,
        active_leases=active_leases,
        active_research=active_research,
        active_patch=active_patch,
        active_devin=active_devin,
        active_copilot=active_copilot,
        free_slots=free_slots,
    )


def ready_tasks(conn: sqlite3.Connection) -> list[dict]:
    owned = active_copilot_task_ids(conn) | active_swarm_task_ids(conn)
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
    return [
        dict(row)
        for row in rows
        if str(row["id"]) not in owned
    ]


def classify_engine(task: dict) -> str:
    work_type = str(task.get("work_type") or "").lower()
    if work_type in RESEARCH_WORK_TYPES:
        return "research"
    if work_type in IMPLEMENTATION_WORK_TYPES:
        return "copilot"
    return "manual"


def _select_tasks(
    conn: sqlite3.Connection,
    limit: int,
    *,
    work_types: set[str],
    engine: str,
    skip_task_ids: set[str] | None = None,
    require_scopes: bool = False,
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
        work_type_filter=work_types,
    )
    for task_id in ranked_ids:
        task = task_map.get(task_id)
        if task is None or task["id"] in skip_task_ids:
            continue
        work_type = str(task.get("work_type") or "").lower()
        if work_type not in work_types:
            continue
        key = task.get("concurrency_key") or task.get("lane") or ""
        if key and key in keys:
            continue
        scopes = [
            str(row[0])
            for row in conn.execute(
                "select path_prefix from task_scopes where task_id=? order by path_prefix",
                (task["id"],),
            )
        ]
        if require_scopes and not scopes:
            continue
        conflict = False
        for scope in scopes:
            a = scope.rstrip("/") + "/"
            for owner_task, prior in claimed + selected_scopes:
                if owner_task == task["id"]:
                    continue
                b = str(prior).rstrip("/") + "/"
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


def select_research_tasks(
    conn: sqlite3.Connection,
    limit: int,
    *,
    skip_task_ids: set[str] | None = None,
) -> list[dict]:
    return _select_tasks(
        conn,
        limit,
        work_types=RESEARCH_WORK_TYPES,
        engine="research",
        skip_task_ids=skip_task_ids,
    )


def select_implementation_tasks(
    conn: sqlite3.Connection,
    limit: int,
    *,
    skip_task_ids: set[str] | None = None,
) -> list[dict]:
    return _select_tasks(
        conn,
        limit,
        work_types=IMPLEMENTATION_WORK_TYPES,
        engine="openai-patch",
        skip_task_ids=skip_task_ids,
        require_scopes=True,
    )

def prior_failures(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    engine: str | None = None,
) -> int:
    ensure_schema(conn)
    sql = """select count(*) from swarm_jobs
               where task_id=? and state='FAILED'
                 and artifact_path is not null"""
    params: list[str] = [task_id]
    if engine:
        sql += " and engine=?"
        params.append(engine)
    return int(conn.execute(sql, tuple(params)).fetchone()[0])


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


def patch_worker_ids(config: dict) -> list[str]:
    impl = config.get("implementation", {})
    count = int(impl.get("workers", 1) or 1)
    return [f"auto-patch-{i}" for i in range(1, max(1, count) + 1)]


def available_patch_worker_ids(
    conn: sqlite3.Connection,
    config: dict,
) -> list[str]:
    now = time.time()
    busy = {
        str(row[0])
        for row in conn.execute(
            "select chat_id from brain_task_leases where lease_until_epoch>?",
            (now,),
        )
    }
    return [worker for worker in patch_worker_ids(config) if worker not in busy]


def devin_worker_ids(config: dict) -> list[str]:
    router = config.get("router", {}) if isinstance(config, dict) else {}
    count = int(router.get("workers", 2) or 2)
    return [f"auto-devin-{i}" for i in range(1, max(1, count) + 1)]


def available_devin_worker_ids(
    conn: sqlite3.Connection,
    config: dict,
) -> list[str]:
    now = time.time()
    busy = {
        str(row[0])
        for row in conn.execute(
            "select chat_id from brain_task_leases where lease_until_epoch>?",
            (now,),
        )
    }
    return [worker for worker in devin_worker_ids(config) if worker not in busy]


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
    *,
    branch: str | None = None,
    model: str | None = None,
    verification: str | None = None,
) -> int:
    ensure_schema(conn)
    cur = conn.execute(
        """insert into swarm_jobs(
             task_id,worker_id,engine,state,branch,model,verification
           ) values(?,?,?,'STARTING',?,?,?)""",
        (task_id, worker_id, engine, branch, model, verification),
    )
    conn.commit()
    return int(cur.lastrowid)


def mark_job_running(
    conn: sqlite3.Connection,
    job_id: int,
    pid: int,
    *,
    session_id: str | None = None,
) -> None:
    conn.execute(
        """update swarm_jobs
              set state='RUNNING',pid=?,session_id=coalesce(?,session_id),
                  updated_at=datetime('now')
            where id=?""",
        (pid, session_id, job_id),
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
            "active_patch": cap.active_patch,
            "active_devin": cap.active_devin,
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
