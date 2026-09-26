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
            "devin_lead",
            (str(b / "logres-devin-lead"), "run"),
            20,
            31536000,
            True,
            "devin_lead",
        ),
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


BATON_PATH_ENV = "LOGRES_CHATGPT_BATON_PATH"
BATON_STALE_ENV = "LOGRES_CHATGPT_BATON_STALE_SECONDS"
FAILOVER_STATE_ENV = "LOGRES_DEVIN_FAILOVER_STATE"
FAILOVER_COOLDOWN_ENV = "LOGRES_DEVIN_FAILOVER_COOLDOWN_SECONDS"
BATON_RUN_STATES = frozenset({"RUNNING", "CONTINUE_REQUESTED"})
BATON_SUPPRESS_STATES = frozenset({"PAUSED", "WAITING_USER", "DONE"})
BATON_STATES = BATON_RUN_STATES | BATON_SUPPRESS_STATES
DEFAULT_BATON_STALE_SECONDS = 120.0
DEFAULT_FAILOVER_COOLDOWN_SECONDS = 600.0
STAGE2_REQUIRED_TASKS = (
    "DEVIN-OS-ISOLATION-001",
    "DEVIN-SWARM-ROUTER-001",
)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return float(default)


def baton_path(root: Path) -> Path:
    return Path(
        os.environ.get(
            BATON_PATH_ENV,
            str(Path(root) / "control" / "chatgpt-coordinator-baton.json"),
        )
    )


def failover_state_path(root: Path) -> Path:
    return Path(
        os.environ.get(
            FAILOVER_STATE_ENV,
            str(Path(root) / "control" / "chatgpt-devin-failover.json"),
        )
    )


def handback_path(root: Path) -> Path:
    return Path(root) / "control" / "chatgpt-devin-handback.json"


def write_baton(
    root: Path,
    *,
    run_state: str,
    objective: str | None = None,
    task: str | None = None,
    note: str = "",
    generation: int | None = None,
    new_generation: bool = False,
    now_epoch: float | None = None,
) -> dict:
    """Durable atomic coordinator-baton write under control/.

    The baton carries a fencing generation, the coordinator run state, a
    timestamp, and the current objective/task/note. A heartbeat is the same
    write without a generation bump; a fresh heartbeat or a bumped
    generation is what tells the Devin failover to hand coordination back.
    """
    state = str(run_state or "").strip().upper()
    if state not in BATON_STATES:
        raise ValueError(f"invalid baton run_state: {run_state!r}")
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    path = baton_path(root)
    previous = load_state(path)
    if generation is not None:
        gen = int(generation)
    elif new_generation:
        gen = int(previous.get("generation") or 0) + 1
    else:
        gen = int(previous.get("generation") or 0) or 1
    baton = {
        "generation": gen,
        "run_state": state,
        "updated_epoch": now_epoch,
        "updated_at": utc_now(),
        "objective": str(objective if objective is not None else previous.get("objective") or ""),
        "task": str(task if task is not None else previous.get("task") or ""),
        "note": str(note or ""),
    }
    atomic_json(path, baton)
    return baton


def live_brain_leases(root: Path, now_epoch: float) -> list[dict]:
    """Read-only snapshot of live Brain leases.

    Failover must never steal or duplicate live leases, so this is strictly
    a read-only observer: it never writes to brain_task_leases.
    """
    db = Path(root) / "control" / "control.sqlite"
    if not db.exists():
        return []
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=1)
        try:
            rows = conn.execute(
                "select chat_id,task_id,branch,lease_until_epoch "
                "from brain_task_leases where lease_until_epoch>? "
                "order by chat_id,task_id",
                (float(now_epoch),),
            ).fetchall()
        finally:
            conn.close()
    except (sqlite3.Error, OSError, ValueError):
        return []
    return [
        {
            "chat_id": str(row[0]),
            "task_id": str(row[1]),
            "branch": str(row[2] or ""),
            "lease_until_epoch": float(row[3] or 0.0),
        }
        for row in rows
    ]


def failover_stage2_status(root: Path) -> dict:
    """Report whether stage-2 Devin swarm delegation is unlocked.

    Stage 2 may only delegate new implementation work through the guarded
    Devin swarm engine once BOTH DEVIN-OS-ISOLATION-001 and
    DEVIN-SWARM-ROUTER-001 are integrated. Until then the failover must not
    launch unrestricted unattended implementation.
    """
    db = Path(root) / "control" / "control.sqlite"
    satisfied: set[str] = set()
    if db.exists():
        try:
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=1)
            try:
                for task_id in STAGE2_REQUIRED_TASKS:
                    row = conn.execute(
                        "select 1 from integration_queue "
                        "where task_id=? and status='INTEGRATED' limit 1",
                        (task_id,),
                    ).fetchone()
                    if row:
                        satisfied.add(task_id)
            finally:
                conn.close()
        except (sqlite3.Error, OSError, ValueError):
            satisfied = set()
    missing = [t for t in STAGE2_REQUIRED_TASKS if t not in satisfied]
    return {
        "unlocked": not missing,
        "satisfied": sorted(satisfied),
        "missing": missing,
        "required": list(STAGE2_REQUIRED_TASKS),
    }


def evaluate_failover(
    root: Path,
    *,
    now_epoch: float | None = None,
    stale_seconds: float | None = None,
    cooldown_seconds: float | None = None,
) -> dict:
    """Decide the deterministic failover action for the current baton.

    Actions: no-baton, suppressed, fresh, dedupe, cooldown, handback,
    launch. Only a stale RUNNING/CONTINUE_REQUESTED baton may launch, and a
    fenced generation may launch at most one continuation pass.
    """
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    if stale_seconds is None:
        stale_seconds = _env_float(BATON_STALE_ENV, DEFAULT_BATON_STALE_SECONDS)
    if cooldown_seconds is None:
        cooldown_seconds = _env_float(
            FAILOVER_COOLDOWN_ENV, DEFAULT_FAILOVER_COOLDOWN_SECONDS
        )
    stale_seconds = max(1.0, float(stale_seconds))
    cooldown_seconds = max(0.0, float(cooldown_seconds))

    baton = load_state(baton_path(root))
    failover = load_state(failover_state_path(root))
    run_state = str(baton.get("run_state") or "").upper()
    generation = int(baton.get("generation") or 0)
    updated = float(baton.get("updated_epoch") or 0.0)
    age = (
        max(0.0, now_epoch - updated)
        if updated > 0
        else float("inf")
    )
    fresh = age < stale_seconds
    active = failover.get("active") or {}
    last_launch = failover.get("last_launch") or {}
    result = {
        "run_state": run_state or None,
        "generation": generation or None,
        "age_seconds": round(age, 3) if age < 1e17 else None,
        "stale_seconds": stale_seconds,
        "cooldown_seconds": cooldown_seconds,
        "fresh": fresh,
        "active_generation": active.get("generation"),
    }
    if not baton:
        return {**result, "action": "no-baton"}

    chatgpt_back = (
        fresh
        or generation != int(active.get("generation") or 0)
        or run_state in BATON_SUPPRESS_STATES
    )
    if active and chatgpt_back:
        return {**result, "action": "handback"}
    if run_state in BATON_SUPPRESS_STATES:
        return {**result, "action": "suppressed"}
    if run_state not in BATON_RUN_STATES:
        return {**result, "action": "unknown-state"}
    if not fresh:
        if last_launch and int(last_launch.get("generation") or 0) == generation:
            return {**result, "action": "dedupe"}
        launched_epoch = float(last_launch.get("epoch") or 0.0)
        cooldown_age = now_epoch - launched_epoch
        if launched_epoch > 0 and cooldown_age < cooldown_seconds:
            return {
                **result,
                "action": "cooldown",
                "cooldown_remaining_seconds": round(
                    cooldown_seconds - cooldown_age, 3
                ),
            }
        return {**result, "action": "launch"}
    return {**result, "action": "fresh"}


def failover_snapshot(
    root: Path,
    baton: dict,
    *,
    now_epoch: float | None = None,
) -> dict:
    """Fresh local status/Brain snapshot for the co-lead review.

    Read-only: captures backlog, live leases, and stage gating so the
    bounded Devin review reasons over current control state without any
    repository mutation.
    """
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    return {
        "captured_at": utc_now(),
        "baton": dict(baton),
        "backlog": {
            "integration_ready_for_preflight": actionable_integration_backlog(
                Path(root)
            ),
            "worker_ready_tasks": actionable_worker_backlog(Path(root)),
        },
        "live_brain_leases": live_brain_leases(Path(root), now_epoch),
        "stage2": failover_stage2_status(Path(root)),
        "lanes": {
            "autonomy": "eligible",
            "swarm": "eligible",
            "merge_preflight": "eligible",
        },
    }


def build_failover_prompt(
    *,
    baton: dict,
    snapshot: dict,
    stage: str,
    export_path: Path,
) -> str:
    return f"""You are the bounded Logres Devin co-lead running a STAGE-1
failover continuation review while the ChatGPT coordinator baton is stale.

BATON (generation {baton.get('generation')}, run_state={baton.get('run_state')}):
- objective: {baton.get('objective') or '(none)'}
- task: {baton.get('task') or '(none)'}
- note: {baton.get('note') or '(none)'}

FRESH STATUS/BRAIN SNAPSHOT (read-only, captured at failover time):
{json.dumps(snapshot, indent=2, sort_keys=True)}

HARD RULES:
- This is a reasoning-only continuation review ({stage}). Do NOT mutate the
  repository, do NOT commit, do NOT acquire or release Brain leases, and do
  NOT launch workers.
- Stage 1 keeps existing supervisor autonomy, swarm, and eligible
  merge-preflight lanes moving; it must not launch unrestricted unattended
  implementation work.
- Stage 2 implementation delegation is allowed only through the guarded
  Devin swarm engine after DEVIN-OS-ISOLATION-001 and
  DEVIN-SWARM-ROUTER-001 are both integrated.
- Review the snapshot and write a concise continuation assessment —
  current state, what is still safe to keep moving, what must wait for the
  ChatGPT coordinator, and recommended next actions — as your final
  answer. The harness exports it to {export_path}.
"""


def launch_failover_continuation(
    root: Path,
    baton: dict,
    *,
    now_epoch: float | None = None,
    popen=subprocess.Popen,
    runner=subprocess.run,
    devin_bin: str | None = None,
) -> dict:
    """Launch one bounded, fenced Devin co-lead continuation pass.

    Stage 1 launches a single reasoning-only Devin review from a fresh
    local status/Brain snapshot. It acquires no Brain leases and mutates no
    repository state. When stage 2 is unlocked the same pass may also
    delegate new implementation work through the guarded swarm engine.
    """
    root = Path(root)
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    generation = int(baton.get("generation") or 0)
    stage2 = failover_stage2_status(root)
    stage = "stage2" if stage2["unlocked"] else "stage1"
    snapshot = failover_snapshot(root, baton, now_epoch=now_epoch)

    control = root / "control"
    prompt_path = control / f"devin-failover-review-gen{generation}.md"
    export_path = control / f"devin-failover-review-gen{generation}.json"
    snapshot_path = control / f"devin-failover-snapshot-gen{generation}.json"
    atomic_json(snapshot_path, snapshot)
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(
        build_failover_prompt(
            baton=baton,
            snapshot=snapshot,
            stage=stage,
            export_path=export_path,
        ),
        encoding="utf-8",
    )

    devin = str(
        devin_bin or os.environ.get("LOGRES_DEVIN_BIN", "devin")
    )
    argv = [
        devin,
        "-p",
        "--model",
        str(os.environ.get("LOGRES_DEVIN_FAILOVER_MODEL", "swe-2-max")),
        "--permission-mode",
        "smart",
        "--prompt-file",
        str(prompt_path),
        "--export",
        str(export_path),
    ]
    log_path = root / "logs" / "supervisor" / "devin-failover.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab", buffering=0) as handle:
        handle.write(
            (
                f"=== {utc_now()} failover launch generation={generation} "
                f"stage={stage} ===\n"
            ).encode()
        )
        proc = popen(
            argv,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )

    record = {
        "generation": generation,
        "stage": stage,
        "stage2": stage2,
        "pid": int(proc.pid),
        "argv": argv,
        "prompt_path": str(prompt_path),
        "export_path": str(export_path),
        "snapshot_path": str(snapshot_path),
        "log_path": str(log_path),
        "launched_epoch": now_epoch,
        "launched_at": utc_now(),
    }

    if stage2["unlocked"]:
        swarm_bin = root / "bin" / "logres-swarm"
        if swarm_bin.is_file():
            swarm_argv = [str(swarm_bin), "tick"]
            try:
                proc_run = runner(
                    swarm_argv,
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=300,
                    env=os.environ.copy(),
                )
                record["delegation"] = {
                    "argv": swarm_argv,
                    "rc": int(proc_run.returncode),
                    "engine": "guarded-devin-swarm",
                }
            except (OSError, subprocess.TimeoutExpired) as exc:
                record["delegation"] = {
                    "argv": swarm_argv,
                    "error": f"{type(exc).__name__}: {exc}",
                    "engine": "guarded-devin-swarm",
                }
        else:
            record["delegation"] = {
                "skipped": "guarded swarm engine binary unavailable",
                "engine": "guarded-devin-swarm",
            }
    return record


def failover_tick(
    root: Path,
    *,
    now_epoch: float | None = None,
    stale_seconds: float | None = None,
    cooldown_seconds: float | None = None,
    popen=subprocess.Popen,
    runner=subprocess.run,
    devin_bin: str | None = None,
) -> dict:
    """Apply the deterministic ChatGPT-stale Devin failover policy once."""
    root = Path(root)
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    decision = evaluate_failover(
        root,
        now_epoch=now_epoch,
        stale_seconds=stale_seconds,
        cooldown_seconds=cooldown_seconds,
    )
    action = decision["action"]
    state_file = failover_state_path(root)
    failover = load_state(state_file)

    if action == "launch":
        baton = load_state(baton_path(root))
        launch = launch_failover_continuation(
            root,
            baton,
            now_epoch=now_epoch,
            popen=popen,
            runner=runner,
            devin_bin=devin_bin,
        )
        failover["last_launch"] = {
            "generation": launch["generation"],
            "epoch": now_epoch,
            "stage": launch["stage"],
            "pid": launch["pid"],
        }
        failover["active"] = {
            "generation": launch["generation"],
            "epoch": now_epoch,
            "stage": launch["stage"],
            "pid": launch["pid"],
        }
        history = list(failover.get("history") or [])
        history.append(launch)
        failover["history"] = history[-20:]
        atomic_json(state_file, failover)
        return {**decision, "launch": launch}

    if action == "handback":
        active = failover.get("active") or {}
        summary = {
            "handed_back_at": utc_now(),
            "handed_back_epoch": now_epoch,
            "generation": active.get("generation"),
            "baton": load_state(baton_path(root)),
            "note": (
                "ChatGPT coordinator baton is fresh again; no new Devin "
                "failover actions will be launched. Valid failover workers "
                "already running may finish."
            ),
        }
        atomic_json(handback_path(root), summary)
        failover["active"] = None
        failover["last_handback"] = summary
        atomic_json(state_file, failover)
        return {**decision, "handback": summary}

    return decision


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
    baton_stale_seconds: float | None = None,
    failover_cooldown_seconds: float | None = None,
    failover_enabled: bool = True,
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

    if failover_enabled:
        try:
            failover = failover_tick(
                root,
                now_epoch=now_epoch,
                stale_seconds=baton_stale_seconds,
                cooldown_seconds=failover_cooldown_seconds,
                popen=popen,
                runner=runner,
            )
        except Exception as exc:
            failover = {
                "action": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }
        state["devin_failover"] = failover
        atomic_json(heartbeat_path, state)
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
