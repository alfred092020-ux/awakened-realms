from __future__ import annotations

import fcntl
import json
import os
import signal
import sqlite3
import subprocess
import tempfile
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
    background: bool = False
    background_group: str | None = None


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
            True,
            "autonomy",
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
            True,
            "maintenance",
        ),
        ScheduledJob(
            "lead_snapshot",
            (str(b / "logres-lead-snapshot"),),
            300,
            180,
            True,
            "maintenance",
        ),
        ScheduledJob("code_index", (str(b / "logres-code-index"),), 300, 180),
        ScheduledJob("sync_health", (str(b / "logres-sync-health"), "--quiet"), 300, 180),
        ScheduledJob(
            "health_snapshot",
            (str(b / "logres-health-snapshot"),),
            600,
            120,
            True,
            "maintenance",
        ),
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
        ScheduledJob(
            "governor_propose",
            _locked(
                "/tmp/logres-governor-propose.lock",
                str(b / "logres-governor"),
                "propose",
                "--apply",
                "--shadow-only",
            ),
            900,
            180,
            True,
            "governor",
        ),
        ScheduledJob(
            "shadow_experiment",
            _locked(
                "/tmp/logres-shadow-experiment.lock",
                str(b / "logres-experiment-executor"),
                "next",
            ),
            900,
            180,
            True,
            "governor",
        ),
        ScheduledJob(
            "chaos_cert",
            _locked(
                "/tmp/logres-chaos-cert.lock",
                str(b / "logres-chaos-cert"),
                "run",
                "--shadow",
                "--quiet",
            ),
            21600,
            300,
            True,
            "governor",
        ),
        ScheduledJob(
            "maintenance",
            (str(b / "logres-maintain"),),
            3600,
            1200,
            True,
            "maintenance",
        ),
    )


def load_state(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


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


def direct_child_pids(
    pid: int,
    *,
    proc_root: Path = Path("/proc"),
) -> tuple[int, ...]:
    if pid <= 0:
        return ()
    children = []
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            lines = (entry / "status").read_text().splitlines()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        parent = None
        for line in lines:
            if line.startswith("PPid:"):
                try:
                    parent = int(line.split()[1])
                except (IndexError, ValueError):
                    parent = None
                break
        if parent == pid:
            children.append(int(entry.name))
    return tuple(sorted(children))


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
    last_run = (state.get("last_runs") or {}).get(job.name) or {}
    if last_run.get("running"):
        return False
    last = last_run.get("finished_epoch")
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


def actionable_worker_backlog(root: Path) -> int:
    db = root / "control" / "control.sqlite"
    if not db.exists():
        return 0
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=1)
        try:
            row = conn.execute(
                "select count(*) from tasks where status='READY'"
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
    worker_backlog: int = 0,
) -> bool:
    last_run = (state.get("last_runs") or {}).get(job.name) or {}
    if last_run.get("running"):
        return False
    if due(job, state, now_epoch):
        return True
    early_wake = (
        (job.name == "autonomy" and integration_backlog > 0)
        or (job.name == "swarm" and worker_backlog > 0)
    )
    if not early_wake:
        return False
    last = last_run.get("finished_epoch")
    if last is None:
        return True
    # The supervisor itself ticks every 20s. Ten seconds prevents an external
    # tick storm from bypassing single-flight cadence while still allowing the
    # next supervisor tick to react to newly actionable work.
    return now_epoch - float(last) >= 10.0


def background_lane_busy(
    job: ScheduledJob,
    jobs: tuple[ScheduledJob, ...],
    state: dict,
) -> bool:
    if not job.background:
        return False
    group = job.background_group or job.name
    for peer in jobs:
        if peer.name == job.name or not peer.background:
            continue
        if (peer.background_group or peer.name) != group:
            continue
        peer_state = (state.get("last_runs") or {}).get(peer.name) or {}
        if peer_state.get("running"):
            return True
    return False


def append_log(root: Path, job: str, text: str) -> None:
    logs = root / "logs" / "supervisor"
    logs.mkdir(parents=True, exist_ok=True)
    path = logs / f"{job}.log"
    with path.open("a", errors="replace") as handle:
        handle.write(text)
        if text and not text.endswith("\n"):
            handle.write("\n")


def launch_background_job(
    root: Path,
    job: ScheduledJob,
    *,
    popen=subprocess.Popen,
    now_epoch: float | None = None,
) -> dict:
    started = time.time() if now_epoch is None else float(now_epoch)
    logs = root / "logs" / "supervisor"
    logs.mkdir(parents=True, exist_ok=True)
    path = logs / f"{job.name}.log"
    with path.open("ab", buffering=0) as handle:
        handle.write(
            (
                f"=== {utc_now()} background launch "
                f"timeout={job.timeout_seconds}s ===\n"
            ).encode()
        )
        proc = popen(
            list(job.argv),
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
            env=os.environ.copy(),
        )
    return {
        "argv": list(job.argv),
        "pid": int(proc.pid),
        "running": True,
        "rc": None,
        "error": None,
        "started_epoch": started,
        "started_at": utc_now(),
        "finished_epoch": None,
        "finished_at": None,
        "duration_seconds": 0.0,
        "timeout_seconds": int(job.timeout_seconds),
        "terminate_sent_epoch": None,
        "kill_sent_epoch": None,
    }


def _finish_background_run(
    root: Path,
    job: ScheduledJob,
    run_state: dict,
    *,
    now_epoch: float,
    rc: int | None,
    error: str | None = None,
) -> dict:
    updated = dict(run_state)
    started = float(updated.get("started_epoch") or now_epoch)
    updated.update(
        {
            "running": False,
            "rc": rc,
            "error": error,
            "finished_epoch": now_epoch,
            "finished_at": utc_now(),
            "duration_seconds": round(max(0.0, now_epoch - started), 3),
        }
    )
    append_log(
        root,
        job.name,
        (
            f"=== {utc_now()} background complete rc={rc} "
            f"duration={updated['duration_seconds']:.1f}s"
            + (f" error={error}" if error else "")
        ),
    )
    return updated


def refresh_background_run(
    root: Path,
    job: ScheduledJob,
    run_state: dict,
    *,
    now_epoch: float | None = None,
    waitpid_fn=os.waitpid,
    killpg_fn=os.killpg,
    pid_alive_fn=pid_alive,
) -> dict:
    if not run_state.get("running"):
        return dict(run_state)

    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    pid = int(run_state.get("pid") or 0)
    if pid <= 0:
        return _finish_background_run(
            root,
            job,
            run_state,
            now_epoch=now_epoch,
            rc=127,
            error="background job lost its pid",
        )

    try:
        waited_pid, status = waitpid_fn(pid, os.WNOHANG)
    except ChildProcessError:
        if pid_alive_fn(pid):
            waited_pid = 0
            status = 0
        else:
            return _finish_background_run(
                root,
                job,
                run_state,
                now_epoch=now_epoch,
                rc=None,
                error="background completion status unavailable after supervisor restart",
            )

    if waited_pid == pid:
        try:
            rc = os.waitstatus_to_exitcode(status)
        except ValueError:
            rc = 127
        return _finish_background_run(
            root,
            job,
            run_state,
            now_epoch=now_epoch,
            rc=int(rc),
        )

    updated = dict(run_state)
    started = float(updated.get("started_epoch") or now_epoch)
    timeout_seconds = int(
        updated.get("timeout_seconds") or job.timeout_seconds
    )
    elapsed = max(0.0, now_epoch - started)
    if elapsed <= timeout_seconds:
        return updated

    terminate_sent = updated.get("terminate_sent_epoch")
    if terminate_sent is None:
        try:
            killpg_fn(pid, signal.SIGTERM)
        except ProcessLookupError:
            return _finish_background_run(
                root,
                job,
                updated,
                now_epoch=now_epoch,
                rc=None,
                error="background job exited during timeout handling",
            )
        updated["terminate_sent_epoch"] = now_epoch
        updated["error"] = f"timeout after {timeout_seconds}s; SIGTERM sent"
        append_log(
            root,
            job.name,
            f"=== {utc_now()} timeout SIGTERM pid={pid} ===",
        )
        return updated

    if (
        updated.get("kill_sent_epoch") is None
        and now_epoch - float(terminate_sent) >= 10.0
    ):
        try:
            killpg_fn(pid, signal.SIGKILL)
        except ProcessLookupError:
            return _finish_background_run(
                root,
                job,
                updated,
                now_epoch=now_epoch,
                rc=None,
                error="background job exited after timeout SIGTERM",
            )
        updated["kill_sent_epoch"] = now_epoch
        updated["error"] = (
            f"timeout after {timeout_seconds}s; SIGTERM then SIGKILL sent"
        )
        append_log(
            root,
            job.name,
            f"=== {utc_now()} timeout SIGKILL pid={pid} ===",
        )
    return updated


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
    popen=subprocess.Popen,
    waitpid_fn=os.waitpid,
    killpg_fn=os.killpg,
    pid_alive_fn=pid_alive,
    now_epoch: float | None = None,
    integration_backlog: int | None = None,
    worker_backlog: int | None = None,
) -> dict:
    jobs = default_jobs(root) if jobs is None else jobs
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    if integration_backlog is None:
        integration_backlog = actionable_integration_backlog(root)
    if worker_backlog is None:
        worker_backlog = actionable_worker_backlog(root)
    state = load_state(heartbeat_path)
    state.setdefault("started_at", utc_now())
    state["pid"] = os.getpid()
    state.setdefault("last_runs", {})
    state["updated_epoch"] = now_epoch
    state["updated_at"] = utc_now()

    for job in jobs:
        if not job.background:
            continue
        previous = state["last_runs"].get(job.name) or {}
        if not previous.get("running"):
            continue
        state["last_runs"][job.name] = refresh_background_run(
            root,
            job,
            previous,
            now_epoch=now_epoch,
            waitpid_fn=waitpid_fn,
            killpg_fn=killpg_fn,
            pid_alive_fn=pid_alive_fn,
        )
    atomic_json(heartbeat_path, state)

    ran = []
    for job in jobs:
        if not should_run_job(
            job,
            state,
            now_epoch,
            integration_backlog=integration_backlog,
            worker_backlog=worker_backlog,
        ):
            continue
        if job.background and background_lane_busy(job, jobs, state):
            continue
        if job.background:
            result = launch_background_job(
                root,
                job,
                popen=popen,
                now_epoch=now_epoch,
            )
        else:
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


def reload_if_idle(
    root: Path,
    executable: Path,
    heartbeat_path: Path,
    *,
    expected_pid: int | None = None,
    max_age_seconds: int = 900,
    wait_seconds: float = 15.0,
    child_pids_fn=direct_child_pids,
    kill_fn=os.kill,
    alive_fn=pid_alive,
    sleep_fn=time.sleep,
    ensure_fn=None,
) -> dict:
    health = supervisor_health(
        heartbeat_path,
        max_age_seconds=max_age_seconds,
    )
    current_pid = int(health.get("pid") or 0)
    if expected_pid and current_pid and current_pid != int(expected_pid):
        return {
            "reload": "already-replaced",
            **health,
            "old_pid": int(expected_pid),
            "new_pid": current_pid,
        }

    if not health.get("alive"):
        ensure = ensure_fn or ensure_running
        replacement = ensure(
            root,
            executable,
            heartbeat_path,
            max_age_seconds=max_age_seconds,
        )
        return {
            "reload": "started",
            **replacement,
            "old_pid": current_pid or None,
            "new_pid": replacement.get("pid"),
        }

    children = child_pids_fn(current_pid)
    if children:
        return {
            "reload": "deferred",
            **health,
            "old_pid": current_pid,
            "children": list(children),
        }

    try:
        kill_fn(current_pid, signal.SIGTERM)
    except ProcessLookupError:
        pass

    deadline = time.monotonic() + max(0.0, float(wait_seconds))
    while alive_fn(current_pid) and time.monotonic() < deadline:
        sleep_fn(0.1)

    if alive_fn(current_pid):
        return {
            "reload": "failed",
            **health,
            "healthy": False,
            "old_pid": current_pid,
            "reason": "supervisor did not exit after SIGTERM",
        }

    ensure = ensure_fn or ensure_running
    replacement = ensure(
        root,
        executable,
        heartbeat_path,
        max_age_seconds=max_age_seconds,
    )
    return {
        "reload": "reloaded",
        **replacement,
        "old_pid": current_pid,
        "new_pid": replacement.get("pid"),
    }


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
