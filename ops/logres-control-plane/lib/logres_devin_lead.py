from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def _ensure_runtime(conn) -> None:
    conn.execute(
        """create table if not exists devin_lead_runtime(
             singleton integer primary key check(singleton=1),
             instance_id text not null,
             lease_until_epoch real not null,
             renewed_at_epoch real not null
           )"""
    )


def load_lead_policy(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("lead policy must be an object")
    models = data.get("models", {})
    if bool(models.get("allow_paid_default", False)):
        raise ValueError("paid models may not be enabled by default")
    return data


def acquire_leader(conn, *, instance_id: str, now: float, ttl_seconds: int) -> bool:
    _ensure_runtime(conn)
    conn.execute("begin immediate")
    try:
        row = conn.execute(
            "select instance_id,lease_until_epoch from devin_lead_runtime where singleton=1"
        ).fetchone()
        if row and float(row[1]) > now and str(row[0]) != instance_id:
            conn.rollback()
            return False
        conn.execute(
            """insert into devin_lead_runtime(singleton,instance_id,lease_until_epoch,renewed_at_epoch)
               values(1,?,?,?)
               on conflict(singleton) do update set
                 instance_id=excluded.instance_id,
                 lease_until_epoch=excluded.lease_until_epoch,
                 renewed_at_epoch=excluded.renewed_at_epoch""",
            (instance_id, now + max(1, int(ttl_seconds)), now),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise


def renew_leader(conn, *, instance_id: str, now: float, ttl_seconds: int) -> bool:
    _ensure_runtime(conn)
    cur = conn.execute(
        """update devin_lead_runtime
             set lease_until_epoch=?, renewed_at_epoch=?
           where singleton=1 and instance_id=? and lease_until_epoch>?""",
        (now + max(1, int(ttl_seconds)), now, instance_id, now),
    )
    conn.commit()
    return cur.rowcount == 1


def read_pause(root: Path) -> dict:
    path = Path(root) / "control" / "devin-lead.pause"
    if not path.is_file():
        return {"paused": False, "reason": "", "path": str(path)}
    try:
        reason = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        reason = f"pause file unreadable: {exc}"
    return {"paused": True, "reason": reason or "operator pause", "path": str(path)}


def write_heartbeat(root: Path, payload: dict) -> None:
    path = Path(root) / "control" / "devin-lead-heartbeat.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    tmp = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def default_policy() -> dict:
    return {
        "cycle_seconds": 60,
        "leader_ttl_seconds": 180,
        "heartbeat_seconds": 30,
        "task_generation_cap_per_cycle": 3,
        "assignment_cap_per_cycle": 4,
        "predicate_cooldown_seconds": 900,
        "infrastructure_work_ratio_max": 0.35,
        "stale_worker_seconds": 900,
        "models": {"preferred": "swe-2-max", "allow_paid_default": False},
    }


def _table_rows(conn, table: str) -> list[dict]:
    try:
        return [dict(row) for row in conn.execute(f"select * from {table}").fetchall()]
    except Exception:
        return []


def _load_json_file(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def collect_planning_snapshot(conn, root: Path, policy: dict) -> dict:
    root = Path(root)
    return {
        "tasks": _table_rows(conn, "tasks"),
        "leases": _table_rows(conn, "brain_task_leases"),
        "dependencies": _table_rows(conn, "task_dependencies"),
        "scopes": _table_rows(conn, "task_scopes"),
        "metadata": _table_rows(conn, "task_metadata"),
        "integration_queue": _table_rows(conn, "integration_queue"),
        "regressions": _table_rows(conn, "regressions"),
        "capacity": _load_json_file(root / "control" / "capacity-state.json"),
        "swarm": _load_json_file(root / "control" / "swarm-state.json"),
        "policy": policy,
    }


def score_ready_task(task: dict, snapshot: dict, policy: dict) -> tuple:
    priority = int(task.get("priority", 9) if task.get("priority") is not None else 9)
    lane = str(task.get("lane") or "").lower()
    title = str(task.get("title") or "").lower()
    note = str(task.get("note") or "").lower()
    visible_game = lane in {"game", "release", "android", "presentation"} or any(
        token in title for token in ("battle", "field", "onboarding", "android", "playable", "visual", "game")
    )
    critical = "critical" in note or "critical" in title
    infra = lane in {"control-plane", "infra", "devops", "security"}
    explicit_unblock = "unblock" in title or "unblock" in note or "blocker" in note
    class_rank = 0 if (visible_game or critical) else (1 if (infra and explicit_unblock) else 2 if not infra else 3)
    return (class_rank, priority, str(task.get("id") or ""))


def select_frontier(snapshot: dict, policy: dict) -> list[dict]:
    candidates = [
        dict(task)
        for task in snapshot.get("tasks", [])
        if str(task.get("status") or "") == "READY" and not task.get("owner")
    ]
    candidates.sort(key=lambda item: score_ready_task(item, snapshot, policy))
    capacity = snapshot.get("capacity", {}) if isinstance(snapshot.get("capacity"), dict) else {}
    plan = capacity.get("plan", {}) if isinstance(capacity.get("plan"), dict) else {}
    signals = capacity.get("signals", {}) if isinstance(capacity.get("signals"), dict) else {}
    verifier = signals.get("verifier", {}) if isinstance(signals.get("verifier"), dict) else {}
    pressure = str(plan.get("pressure") or "normal")
    logical = max(1, int(plan.get("logical_workers") or policy.get("assignment_cap_per_cycle", 4) or 4))
    limit = min(int(policy.get("assignment_cap_per_cycle", 4) or 4), logical)
    backlog = int(verifier.get("backlog") or 0)
    if pressure == "high" or backlog >= 8:
        limit = min(limit, 1)
    elif pressure in {"medium", "elevated"} or backlog >= 4:
        limit = min(limit, 2)
    return candidates[: max(0, limit)]
