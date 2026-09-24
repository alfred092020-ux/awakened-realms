from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SATISFIED_TASK_STATES = {"DONE", "RESOLVED", "INTEGRATED"}
TERMINAL_TASK_STATES = SATISFIED_TASK_STATES | {"SUPERSEDED", "CANCELLED"}


@dataclass(frozen=True)
class ResourceState:
    cpus: int
    load1: float
    memory_available_gib: float
    disk_free_gib: float

    @property
    def load_per_cpu(self) -> float:
        return self.load1 / max(1, self.cpus)


@dataclass(frozen=True)
class AutonomyDecision:
    allowed: bool
    reasons: tuple[str, ...]
    batch_limit: int


@dataclass(frozen=True)
class DoctorStability:
    ok: bool
    recovered: bool
    attempts: int


def doctor_stability(
    first_returncode: int,
    retry_returncode: int | None = None,
) -> DoctorStability:
    if first_returncode == 0:
        return DoctorStability(ok=True, recovered=False, attempts=1)
    if retry_returncode is None:
        return DoctorStability(ok=False, recovered=False, attempts=1)
    if retry_returncode == 0:
        return DoctorStability(ok=True, recovered=True, attempts=2)
    return DoctorStability(ok=False, recovered=False, attempts=2)


def load_config(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text())


MANAGED_RUNTIME_PATH_PARTS = (
    "/home/ubuntu/logres/bin",
    "/home/ubuntu/.local/bin",
    "/home/ubuntu/bin",
    "/usr/local/sbin",
    "/usr/local/bin",
    "/usr/sbin",
    "/usr/bin",
    "/sbin",
    "/bin",
    "/snap/bin",
)
MANAGED_RUNTIME_PATH = ":".join(MANAGED_RUNTIME_PATH_PARTS)


def normalized_runtime_path(existing: str = "") -> str:
    parts = list(MANAGED_RUNTIME_PATH_PARTS)
    for item in existing.split(":"):
        item = item.strip()
        if item and item not in parts:
            parts.append(item)
    return ":".join(parts)


def normalize_runtime_environment(
    environment: dict[str, str] | None = None,
) -> dict[str, str]:
    target = os.environ if environment is None else environment
    target["PATH"] = normalized_runtime_path(target.get("PATH", ""))
    return target


MANAGED_CRON_ENV = f"PATH={MANAGED_RUNTIME_PATH} "
AUTONOMY_CRON_MARKER = "# LOGRES_AUTONOMY_V3"
AUTONOMY_CRON_LINE = (
    "* * * * * "
    + MANAGED_CRON_ENV
    + "flock -n /tmp/logres-autonomy.cron.lock "
    "nice -n 10 ionice -c3 /home/ubuntu/logres/bin/logres-autonomy cycle "
    ">>/home/ubuntu/logres/logs/autonomy-cron.log 2>&1 "
    + AUTONOMY_CRON_MARKER
)


def _proc_ppid(proc_dir: Path) -> int | None:
    try:
        for line in (proc_dir / "status").read_text(errors="replace").splitlines():
            if line.startswith("PPid:"):
                return int(line.split(":", 1)[1].strip())
    except (OSError, ValueError):
        return None
    return None


def process_ancestry_contains_marker(
    marker: str,
    *,
    start_pid: int | None = None,
    proc_root: Path = Path("/proc"),
    max_depth: int = 6,
) -> bool:
    pid = os.getppid() if start_pid is None else int(start_pid)
    seen: set[int] = set()
    for _ in range(max(1, int(max_depth))):
        if pid <= 1 or pid in seen:
            return False
        seen.add(pid)
        proc_dir = proc_root / str(pid)
        try:
            command = (
                (proc_dir / "cmdline")
                .read_bytes()
                .replace(b"\0", b" ")
                .decode(errors="replace")
            )
        except OSError:
            return False
        if marker in command:
            return True
        parent = _proc_ppid(proc_dir)
        if parent is None or parent == pid:
            return False
        pid = parent
    return False


def supervisor_heartbeat_healthy(
    heartbeat_path: Path,
    *,
    now_epoch: float | None = None,
    max_age_seconds: float = 120.0,
    pid_alive_fn=None,
) -> bool:
    try:
        state = json.loads(heartbeat_path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(state, dict):
        return False
    try:
        pid = int(state.get("pid") or 0)
        updated = float(state.get("updated_epoch") or 0)
    except (TypeError, ValueError):
        return False
    if pid <= 0 or updated <= 0:
        return False
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    if now_epoch - updated > max_age_seconds:
        return False
    if now_epoch < updated - 5:
        return False
    if pid_alive_fn is None:
        def pid_alive_fn(candidate: int) -> bool:
            try:
                os.kill(candidate, 0)
                return True
            except ProcessLookupError:
                return False
            except PermissionError:
                return True
    try:
        return bool(pid_alive_fn(pid))
    except OSError:
        return False


def legacy_cron_should_defer(
    heartbeat_path: Path,
    *,
    start_pid: int | None = None,
    proc_root: Path = Path("/proc"),
    now_epoch: float | None = None,
    pid_alive_fn=None,
) -> bool:
    if not process_ancestry_contains_marker(
        "LOGRES_AUTONOMY_V3",
        start_pid=start_pid,
        proc_root=proc_root,
    ):
        return False
    return supervisor_heartbeat_healthy(
        heartbeat_path,
        now_epoch=now_epoch,
        pid_alive_fn=pid_alive_fn,
    )


SWARM_CRON_MARKER = "# LOGRES_SWARM_V1"
SWARM_CRON_LINE = (
    "* * * * * "
    + MANAGED_CRON_ENV
    + "flock -n /tmp/logres-swarm.cron.lock "
    "nice -n 10 ionice -c3 /home/ubuntu/logres/bin/logres-swarm tick "
    ">>/home/ubuntu/logres/logs/swarm-cron.log 2>&1 "
    + SWARM_CRON_MARKER
)
PREVIEW_REAPER_CRON_MARKER = "# LOGRES_PREVIEW_REAPER_V1"
PREVIEW_REAPER_CRON_LINE = (
    "*/10 * * * * "
    + MANAGED_CRON_ENV
    + "flock -n /tmp/logres-preview-reaper.lock "
    "nice -n 15 ionice -c3 /home/ubuntu/logres/bin/logres-preview-reaper "
    "--apply --age-hours 2 >>/home/ubuntu/logres/logs/preview-reaper.log 2>&1 "
    + PREVIEW_REAPER_CRON_MARKER
)


def rewrite_crontab(existing: str, *, install: bool = True) -> str:
    kept: list[str] = []
    for raw in existing.splitlines():
        line = raw.rstrip()
        if not line:
            kept.append("")
            continue
        if (
            AUTONOMY_CRON_MARKER in line
            or SWARM_CRON_MARKER in line
            or PREVIEW_REAPER_CRON_MARKER in line
        ):
            continue
        # Autonomy v3 owns integration preflight cadence. Remove the old
        # standalone producer to avoid duplicate full-E2E work and races.
        if "logres-merge-preflight run" in line:
            continue
        kept.append(line)

    while kept and kept[-1] == "":
        kept.pop()
    if install:
        kept.append(AUTONOMY_CRON_LINE)
        kept.append(SWARM_CRON_LINE)
        kept.append(PREVIEW_REAPER_CRON_LINE)
    return "\n".join(kept) + ("\n" if kept else "")


def load_state(path: Path) -> dict:
    if not path.is_file():
        return {
            "consecutive_failures": 0,
            "tripped": False,
            "last_failure": None,
            "last_success": None,
            "last_applied_preflight": None,
        }
    try:
        state = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        state = {}
    return {
        "consecutive_failures": int(state.get("consecutive_failures", 0) or 0),
        "tripped": bool(state.get("tripped", False)),
        "last_failure": state.get("last_failure"),
        "last_success": state.get("last_success"),
        "last_applied_preflight": state.get("last_applied_preflight"),
    }


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def record_failure(path: Path, message: str, threshold: int) -> dict:
    state = load_state(path)
    state["consecutive_failures"] += 1
    state["last_failure"] = message
    if state["consecutive_failures"] >= max(1, threshold):
        state["tripped"] = True
    save_state(path, state)
    return state


def record_success(path: Path, *, preflight_id: int | None = None) -> dict:
    state = load_state(path)
    state["consecutive_failures"] = 0
    state["tripped"] = False
    state["last_failure"] = None
    state["last_success"] = "success"
    if preflight_id is not None:
        state["last_applied_preflight"] = int(preflight_id)
    save_state(path, state)
    return state


def reset_circuit(path: Path) -> dict:
    state = load_state(path)
    state["consecutive_failures"] = 0
    state["tripped"] = False
    state["last_failure"] = None
    save_state(path, state)
    return state


def resource_state() -> ResourceState:
    cpus = os.cpu_count() or 1
    load1 = os.getloadavg()[0]
    mem_available = 0
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            mem_available = int(line.split()[1]) * 1024
            break
    stat = os.statvfs("/")
    disk_free = stat.f_bavail * stat.f_frsize
    return ResourceState(
        cpus=cpus,
        load1=load1,
        memory_available_gib=mem_available / 1024**3,
        disk_free_gib=disk_free / 1024**3,
    )


def dynamic_batch_limit(
    config: dict,
    resources: ResourceState,
    ready_count: int,
) -> int:
    auto = config.get("autonomy", {})
    maximum = max(1, int(auto.get("max_preflight_batch", 4) or 4))
    if ready_count <= 0:
        return 0

    min_mem = float(auto.get("min_free_memory_gib", 12.0) or 12.0)
    min_disk = float(auto.get("min_free_disk_gib", 30.0) or 30.0)
    max_load = float(auto.get("max_load_per_cpu", 1.25) or 1.25)

    if (
        resources.memory_available_gib < min_mem
        or resources.disk_free_gib < min_disk
        or resources.load_per_cpu > max_load
    ):
        return 1

    # Use more of the machine when it is obviously underloaded.
    if (
        resources.memory_available_gib >= max(32.0, min_mem * 2)
        and resources.disk_free_gib >= max(60.0, min_disk * 2)
        and resources.load_per_cpu <= min(0.5, max_load / 2)
    ):
        return min(maximum, ready_count)

    return min(maximum, ready_count, 2)


def _hard_dependencies_satisfied(conn: sqlite3.Connection, task_id: str) -> bool:
    rows = conn.execute(
        """select d.depends_on,t.status
             from task_dependencies d
             left join tasks t on t.id=d.depends_on
            where d.task_id=? and d.kind='hard'""",
        (task_id,),
    ).fetchall()
    return all((row[1] or "MISSING") in SATISFIED_TASK_STATES for row in rows)


def _downstream_count(conn: sqlite3.Connection, task_id: str) -> int:
    seen: set[str] = set()
    frontier = [task_id]
    while frontier:
        current = frontier.pop()
        for row in conn.execute(
            "select task_id from task_dependencies where depends_on=?",
            (current,),
        ):
            child = row[0]
            if child not in seen:
                seen.add(child)
                frontier.append(child)
    return len(seen)


def _critical_path_minutes(
    conn: sqlite3.Connection,
    task_id: str,
    memo: dict[str, int] | None = None,
    visiting: set[str] | None = None,
) -> int:
    memo = {} if memo is None else memo
    visiting = set() if visiting is None else visiting
    if task_id in memo:
        return memo[task_id]
    if task_id in visiting:
        return 0

    visiting.add(task_id)
    row = conn.execute(
        """select t.status,coalesce(m.expected_minutes,60)
             from tasks t
             left join task_metadata m on m.task_id=t.id
            where t.id=?""",
        (task_id,),
    ).fetchone()
    if row is None:
        visiting.discard(task_id)
        return 0

    own = 0 if row[0] in SATISFIED_TASK_STATES else int(row[1] or 60)
    children = [
        child[0]
        for child in conn.execute(
            """select d.task_id
                 from task_dependencies d
                 left join tasks t on t.id=d.task_id
                where d.depends_on=? and d.kind='hard'
                  and coalesce(t.status,'MISSING')
                      not in ('DONE','RESOLVED','INTEGRATED')""",
            (task_id,),
        )
    ]
    downstream = max(
        (
            _critical_path_minutes(conn, child, memo=memo, visiting=visiting)
            for child in children
        ),
        default=0,
    )
    visiting.discard(task_id)
    memo[task_id] = own + downstream
    return memo[task_id]


def rank_ready_tasks(conn: sqlite3.Connection, limit: int = 8) -> list[str]:
    rows = []
    memo: dict[str, int] = {}
    for row in conn.execute(
        """select t.id,t.priority,t.lane,
                  coalesce(m.expected_minutes,60) expected_minutes,
                  coalesce(m.work_type,'implementation') work_type
             from tasks t
             left join task_metadata m on m.task_id=t.id
            where t.status='READY'"""
    ):
        task_id = row[0]
        if not _hard_dependencies_satisfied(conn, task_id):
            continue
        priority = int(row[1] if row[1] is not None else 99)
        expected = int(row[3] or 60)
        downstream = _downstream_count(conn, task_id)
        critical = _critical_path_minutes(conn, task_id, memo=memo)
        regression_bonus = -5000 if str(row[4]) == "regression" else 0
        rank = (
            priority * 10000
            + regression_bonus
            - critical * 8
            - downstream * 100
            + expected
        )
        rows.append((rank, task_id))
    rows.sort(key=lambda item: (item[0], item[1]))
    return [task for _, task in rows[: max(1, limit)]]


def actionable_open_regressions(conn: sqlite3.Connection) -> int:
    try:
        return int(
            conn.execute(
                """select count(*) from regressions
                    where status in ('OPEN','ACTIVE','VERIFYING')"""
            ).fetchone()[0]
        )
    except sqlite3.OperationalError:
        return 0


def integration_backlog(conn: sqlite3.Connection) -> int:
    try:
        return int(
            conn.execute(
                """select count(*) from integration_queue
                    where status in (
                      'READY_FOR_PREFLIGHT',
                      'READY_FOR_INTEGRATION'
                    )"""
            ).fetchone()[0]
        )
    except sqlite3.OperationalError:
        return 0


def autonomy_decision(
    config: dict,
    state: dict,
    resources: ResourceState,
    *,
    doctor_ok: bool,
    route_failures: int,
    open_regressions: int,
    ready_count: int,
) -> AutonomyDecision:
    auto = config.get("autonomy", {})
    reasons: list[str] = []

    if not bool(auto.get("enabled", False)):
        reasons.append("autonomy disabled")
    if state.get("tripped"):
        reasons.append("circuit breaker tripped")
    if not doctor_ok:
        reasons.append("doctor is not clean")
    if route_failures:
        reasons.append(f"route failures={route_failures}")
    # An open regression often owns the repair candidate currently waiting for
    # integration. Exact-SHA full-E2E preflight is the hard safety gate, so
    # regressions are telemetry by default rather than an integration deadlock.
    if open_regressions and bool(auto.get("block_on_open_regressions", False)):
        reasons.append(f"open regressions={open_regressions}")

    min_mem = float(auto.get("min_free_memory_gib", 12.0) or 12.0)
    min_disk = float(auto.get("min_free_disk_gib", 30.0) or 30.0)
    max_load = float(auto.get("max_load_per_cpu", 1.25) or 1.25)
    if resources.memory_available_gib < min_mem:
        reasons.append(
            f"memory {resources.memory_available_gib:.1f}GiB < {min_mem:.1f}GiB"
        )
    if resources.disk_free_gib < min_disk:
        reasons.append(
            f"disk {resources.disk_free_gib:.1f}GiB < {min_disk:.1f}GiB"
        )
    if resources.load_per_cpu > max_load:
        reasons.append(
            f"load/cpu {resources.load_per_cpu:.2f} > {max_load:.2f}"
        )

    return AutonomyDecision(
        allowed=not reasons,
        reasons=tuple(reasons),
        batch_limit=dynamic_batch_limit(config, resources, ready_count),
    )


def autonomy_apply_authorized(
    config: dict,
    environment: dict[str, str],
    preflight_id: int,
) -> bool:
    auto = config.get("autonomy", {})
    return bool(
        auto.get("enabled", False)
        and auto.get("auto_apply_preflight_enabled", False)
        and environment.get("LOGRES_AUTONOMY_APPLY") == "1"
        and environment.get("LOGRES_AUTONOMY_PREFLIGHT_ID") == str(preflight_id)
    )


def parse_route_failures(text: str) -> int:
    for token in text.replace("\n", " ").split():
        if token.startswith("failed="):
            try:
                return int(token.split("=", 1)[1])
            except ValueError:
                return 1
    return 0


def latest_verified_preflight(
    conn: sqlite3.Connection,
    current_base_sha: str,
):
    try:
        return conn.execute(
            """select *
                 from integration_preflights
                where status='VERIFIED' and base_sha=?
                order by created_epoch desc,id desc
                limit 1""",
            (current_base_sha,),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
