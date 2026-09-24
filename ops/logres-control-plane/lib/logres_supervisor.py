from __future__ import annotations

import fcntl
import json
import os
import signal
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class ScheduledJob:
    name: str
    argv: tuple[str, ...]
    interval_seconds: int
    timeout_seconds: int


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _locked(lock: str, *argv: str) -> tuple[str, ...]:
    # Return success when another scheduler already owns the same single-flight
    # lock. This lets legacy cron remain as a harmless bootstrap/fallback.
    return ("/usr/bin/flock", "-n", "-E", "0", lock, *argv)


def default_jobs(root: Path) -> tuple[ScheduledJob, ...]:
    b = root / "bin"
    return (
        ScheduledJob(
            "autonomy",
            _locked(
                "/tmp/logres-autonomy.cron.lock",
                str(b / "logres-autonomy"),
                "cycle",
            ),
            60,
            240,
        ),
        ScheduledJob(
            "swarm",
            _locked(
                "/tmp/logres-swarm.cron.lock",
                str(b / "logres-swarm"),
                "tick",
            ),
            60,
            120,
        ),
        ScheduledJob(
            "autopilot",
            _locked(
                "/tmp/logres-autopilot-watch.lock",
                str(b / "logres-autopilot-watch"),
            ),
            300,
            180,
        ),
        ScheduledJob("lead_snapshot", (str(b / "logres-lead-snapshot"),), 300, 180),
        ScheduledJob("health_snapshot", (str(b / "logres-health-snapshot"),), 600, 120),
        ScheduledJob("control_backup", (str(b / "logres-control-backup"),), 600, 180),
        ScheduledJob("evidence_refresh", (str(b / "logres-evidence-refresh"),), 900, 600),
        ScheduledJob(
            "preview_reaper",
            _locked(
                "/tmp/logres-preview-reaper.lock",
                str(b / "logres-preview-reaper"),
                "--apply",
                "--age-hours",
                "2",
            ),
            600,
            120,
        ),
        ScheduledJob("maintenance", (str(b / "logres-maintain"),), 3600, 1200),
    )


def load_state(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temp, path)


def pid_alive(pid: int | None) -> bool:
    if not pid or int(pid) <= 0:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def supervisor_health(
    heartbeat_path: Path,
    *,
    now_epoch: float | None = None,
    max_age_seconds: int = 900,
) -> dict:
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    state = load_state(heartbeat_path)
    pid = int(state.get("pid") or 0)
    updated = float(state.get("updated_epoch") or 0)
    age = max(0.0, now_epoch - updated) if updated else 1e18
    alive = pid_alive(pid)
    healthy = alive and age <= max_age_seconds
    return {
        "healthy": healthy,
        "pid": pid or None,
        "alive": alive,
        "age_seconds": round(age, 3) if age < 1e17 else None,
        "updated_at": state.get("updated_at"),
        "started_at": state.get("started_at"),
        "last_runs": state.get("last_runs") or {},
    }


def due(job: ScheduledJob, state: dict, now_epoch: float) -> bool:
    last = ((state.get("last_runs") or {}).get(job.name) or {}).get("finished_epoch")
    if last is None:
        return True
    return now_epoch - float(last) >= job.interval_seconds


def actionable_integration_backlog(root: Path) -> int:
    db = root / "control" / "control.sqlite"
    if not db.exists():
        return 0
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=1)
        try:
            row = conn.execute(
                "select count(*) from integration_queue "
                "where status='READY_FOR_PREFLIGHT'"
            ).fetchone()
            return int(row[0] if row else 0)
        finally:
            conn.close()
    except (sqlite3.Error, OSError, ValueError):
        return 0


def should_run_job(
    job: ScheduledJob,
    state: dict,
    now_epoch: float,
    *,
    integration_backlog: int,
) -> bool:
    if due(job, state, now_epoch):
        return True
    if job.name != "autonomy" or integration_backlog <= 0:
        return False
    last = ((state.get("last_runs") or {}).get(job.name) or {}).get("finished_epoch")
    if last is None:
        return True
    # The supervisor itself ticks every 20s. Ten seconds prevents an external
    # tick storm from bypassing the normal single-flight/autonomy cadence while
    # still allowing the next supervisor tick to react to newly queued work.
    return now_epoch - float(last) >= 10.0


def append_log(root: Path, job: str, text: str) -> None:
    logs = root / "logs" / "supervisor"
    logs.mkdir(parents=True, exist_ok=True)
    path = logs / f"{job}.log"
    with path.open("a", errors="replace") as handle:
        handle.write(text)
        if text and not text.endswith("\n"):
            handle.write("\n")


def run_job(
    root: Path,
    job: ScheduledJob,
    *,
    runner=subprocess.run,
) -> dict:
    started = time.time()
    try:
        result = runner(
            list(job.argv),
            text=True,
            capture_output=True,
            check=False,
            timeout=job.timeout_seconds,
            env=os.environ.copy(),
        )
        rc = int(result.returncode)
        output = ((result.stdout or "") + ("\n" + result.stderr if result.stderr else ""))
        error = None
    except subprocess.TimeoutExpired as exc:
        rc = 124
        output = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        error = f"timeout after {job.timeout_seconds}s"
    except OSError as exc:
        rc = 127
        output = ""
        error = f"{type(exc).__name__}: {exc}"

    duration = time.time() - started
    append_log(
        root,
        job.name,
        (
            f"=== {utc_now()} rc={rc} duration={duration:.1f}s ===\n"
            + output[-12000:]
            + (f"\nERROR: {error}" if error else "")
        ),
    )
    return {
        "argv": list(job.argv),
        "rc": rc,
        "error": error,
        "duration_seconds": round(duration, 3),
        "finished_epoch": time.time(),
        "finished_at": utc_now(),
    }


def tick(
    root: Path,
    heartbeat_path: Path,
    *,
    jobs: tuple[ScheduledJob, ...] | None = None,
    runner=subprocess.run,
    now_epoch: float | None = None,
    integration_backlog: int | None = None,
) -> dict:
    jobs = default_jobs(root) if jobs is None else jobs
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    if integration_backlog is None:
        integration_backlog = actionable_integration_backlog(root)
    state = load_state(heartbeat_path)
    state.setdefault("started_at", utc_now())
    state["pid"] = os.getpid()
    state.setdefault("last_runs", {})
    state["updated_epoch"] = now_epoch
    state["updated_at"] = utc_now()
    atomic_json(heartbeat_path, state)

    ran = []
    for job in jobs:
        if not should_run_job(
            job,
            state,
            now_epoch,
            integration_backlog=integration_backlog,
        ):
            continue
        result = run_job(root, job, runner=runner)
        state["last_runs"][job.name] = result
        state["updated_epoch"] = time.time()
        state["updated_at"] = utc_now()
        atomic_json(heartbeat_path, state)
        ran.append(job.name)
    return {"ran": ran, "state": state}


def run_forever(
    root: Path,
    heartbeat_path: Path,
    lock_path: Path,
    *,
    sleep_seconds: int = 20,
) -> int:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 0

    stop = False

    def _stop(_signum, _frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    while not stop:
        tick(root, heartbeat_path)
        for _ in range(max(1, int(sleep_seconds))):
            if stop:
                break
            time.sleep(1)
    return 0


def ensure_running(
    root: Path,
    executable: Path,
    heartbeat_path: Path,
    *,
    max_age_seconds: int = 900,
    popen=subprocess.Popen,
) -> dict:
    health = supervisor_health(
        heartbeat_path,
        max_age_seconds=max_age_seconds,
    )
    if health["healthy"]:
        return {"started": False, **health}

    if health["alive"]:
        # A live process holding the supervisor lock may be inside a bounded
        # long-running maintenance command. Do not manufacture a duplicate.
        return {"started": False, **health, "reason": "live supervisor heartbeat stale"}

    log = root / "logs" / "supervisor.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("ab", buffering=0) as handle:
        proc = popen(
            [str(executable), "run"],
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    return {
        "started": True,
        "healthy": True,
        "pid": int(proc.pid),
        "alive": True,
        "age_seconds": 0.0,
        "updated_at": None,
        "started_at": utc_now(),
        "last_runs": {},
    }
