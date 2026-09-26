from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
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


def proposal_fingerprint(proposal: dict) -> str:
    material = {
        "lane": proposal.get("lane"),
        "title": proposal.get("title"),
        "work_type": proposal.get("work_type"),
        "concurrency_key": proposal.get("concurrency_key"),
        "acceptance": sorted(str(x) for x in proposal.get("acceptance", [])),
        "dependencies": sorted(str(x) for x in proposal.get("dependencies", [])),
        "scopes": sorted(str(x) for x in proposal.get("scopes", [])),
    }
    raw = json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _ensure_proposal_schema(conn) -> None:
    conn.execute(
        """create table if not exists devin_lead_proposals(
             fingerprint text primary key,
             task_id text not null,
             concurrency_key text,
             created_epoch real not null,
             cycle_id text
           )"""
    )


def _would_cycle(conn, task_id: str, dependencies: list[str]) -> bool:
    graph: dict[str, list[str]] = {}
    try:
        for row in conn.execute("select task_id,depends_on from task_dependencies"):
            graph.setdefault(str(row[0]), []).append(str(row[1]))
    except Exception:
        pass
    graph[task_id] = [str(x) for x in dependencies]
    def reaches(start: str, target: str, seen: set[str]) -> bool:
        if start == target:
            return True
        if start in seen:
            return False
        seen.add(start)
        return any(reaches(nxt, target, seen) for nxt in graph.get(start, []))
    return any(reaches(dep, task_id, set()) for dep in graph[task_id])


def validate_proposal(conn, proposal: dict, snapshot: dict, policy: dict, *, now: float | None = None) -> tuple[bool, str]:
    _ensure_proposal_schema(conn)
    task_id = str(proposal.get("id") or "").strip()
    if not task_id or not proposal.get("title") or not proposal.get("lane"):
        return False, "proposal missing bounded identity/title/lane"
    dependencies = [str(x) for x in proposal.get("dependencies", [])]
    if _would_cycle(conn, task_id, dependencies):
        return False, "dependency cycle rejected"
    fingerprint = proposal_fingerprint(proposal)
    if now is not None:
        cooldown = int(policy.get("predicate_cooldown_seconds", 0) or 0)
        key = str(proposal.get("concurrency_key") or "")
        row = conn.execute(
            "select max(created_epoch) from devin_lead_proposals where concurrency_key=?",
            (key,),
        ).fetchone()
        if key and row and row[0] is not None and float(row[0]) + cooldown > now:
            return False, "predicate cooldown active"
    row = conn.execute("select task_id from devin_lead_proposals where fingerprint=?", (fingerprint,)).fetchone()
    if row:
        return False, f"duplicate semantic proposal already mapped to {row[0]}"
    try:
        if conn.execute("select 1 from tasks where id=?", (task_id,)).fetchone():
            return False, "duplicate task id"
    except Exception:
        pass
    return True, "ok"


def create_bounded_task(conn, proposal: dict, *, policy: dict | None = None, now: float | None = None, cycle_id: str | None = None) -> str | None:
    policy = policy or default_policy()
    now = time.time() if now is None else float(now)
    _ensure_proposal_schema(conn)
    if cycle_id:
        used = conn.execute("select count(*) from devin_lead_proposals where cycle_id=?", (cycle_id,)).fetchone()[0]
        if int(used) >= int(policy.get("task_generation_cap_per_cycle", 3) or 3):
            return None
    ok, _reason = validate_proposal(conn, proposal, {}, policy, now=now if cycle_id else None)
    if not ok:
        return None
    task_id = str(proposal["id"])
    try:
        conn.execute(
            "insert into tasks(id,priority,lane,title,status,branch,owner,note,updated_at) values(?,?,?,?,?,?,?,?,datetime('now'))",
            (task_id, int(proposal.get("priority", 5)), str(proposal["lane"]), str(proposal["title"]), "READY", None, None, "generated by Devin Lead"),
        )
        for dep in proposal.get("dependencies", []):
            conn.execute("insert into task_dependencies(task_id,depends_on,kind,rationale) values(?,?,?,?)", (task_id, str(dep), "hard", "Lead decomposition"))
        try:
            conn.execute(
                "insert or replace into task_metadata(task_id,milestone,work_type,concurrency_key,expected_minutes,evidence_policy,created_at,updated_at) values(?,?,?,?,?,?,datetime('now'),datetime('now'))",
                (task_id, proposal.get("milestone"), proposal.get("work_type", "implementation"), proposal.get("concurrency_key"), int(proposal.get("expected_minutes", 60)), proposal.get("evidence_policy", "evidence-first")),
            )
        except Exception:
            pass
        fingerprint = proposal_fingerprint(proposal)
        conn.execute("insert into devin_lead_proposals values(?,?,?,?,?)", (fingerprint, task_id, proposal.get("concurrency_key"), now, cycle_id))
        conn.commit()
        return task_id
    except Exception:
        conn.rollback()
        raise


def route_task(task: dict, snapshot: dict, policy: dict) -> dict:
    lane = str(task.get("lane") or "").lower()
    work_type = str(task.get("work_type") or "implementation").lower()
    title = str(task.get("title") or "").lower()
    note = str(task.get("note") or "").lower()
    infrastructure = lane in {"control-plane", "infra", "devops", "security"}
    measurable_unblock = "unblock" in title or "blocker" in note or "critical" in note
    if infrastructure and not measurable_unblock:
        return {"task_id": task.get("id"), "action": "defer", "reason": "noncritical infrastructure budget", "paid": False}
    if work_type == "research" or lane == "research":
        return {"task_id": task.get("id"), "action": "dispatch", "engine": "research", "paid": False}
    devin_cap = int(snapshot.get("capacity", {}).get("plan", {}).get("lane_caps", {}).get("devin_cloud", 1) or 0)
    if devin_cap > 0:
        return {"task_id": task.get("id"), "action": "dispatch", "engine": "devin", "model": str(policy.get("models", {}).get("preferred") or "swe-2-max"), "paid": False}
    return {"task_id": task.get("id"), "action": "defer", "reason": "no free implementation capacity", "paid": False}


def dispatch_plan(root: Path, routes: list[dict], *, execute: bool) -> dict:
    actionable = [r for r in routes if r.get("action") == "dispatch"]
    if not execute:
        return {"executed": False, "routes": routes, "dispatchable": len(actionable)}
    if not actionable:
        return {"executed": True, "routes": routes, "dispatchable": 0, "returncode": 0}
    proc = subprocess.run([str(Path(root) / "bin" / "logres-capacity"), "tick", "--execute"], text=True, capture_output=True, check=False)
    return {"executed": True, "routes": routes, "dispatchable": len(actionable), "returncode": proc.returncode, "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-4000:]}
