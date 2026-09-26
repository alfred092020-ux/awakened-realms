from __future__ import annotations

import hashlib
import json
import os
import statistics
import subprocess
import tempfile
import time
from datetime import datetime, timezone
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


def inspect_owned_work(conn, snapshot: dict, policy: dict) -> list[dict]:
    now = time.time()
    stale_after = int(policy.get("stale_worker_seconds", 900) or 900)
    observations: list[dict] = []
    leases = snapshot.get("leases") or _table_rows(conn, "brain_task_leases")
    recovery_by_task = {
        str(row.get("task_id")): row for row in _table_rows(conn, "task_recovery")
    }
    for lease in leases:
        task_id = str(lease.get("task_id") or "")
        until = float(lease.get("lease_until_epoch") or 0)
        renewed = lease.get("renewed_at_epoch")
        age = max(0.0, now - float(renewed)) if renewed not in (None, "") else max(0.0, now - until + stale_after)
        state = "stale" if until and until <= now else "active"
        recovery = recovery_by_task.get(task_id, {})
        observations.append(
            {
                "task_id": task_id,
                "state": state,
                "age_seconds": age,
                "owner": lease.get("chat_id"),
                "branch": lease.get("branch"),
                "recovery_path": recovery.get("manifest_path") or recovery.get("recovery_path"),
            }
        )
    for row in snapshot.get("regressions", []):
        state = str(row.get("state") or row.get("status") or "").lower()
        if "fail" in state or "quarant" in state:
            observations.append(
                {
                    "task_id": row.get("task_id"),
                    "state": "verification_failed",
                    "candidate_sha": row.get("candidate_sha") or row.get("sha"),
                    "failure_class": row.get("failure_class") or state,
                }
            )
    return observations


def plan_recoveries(conn, observations: list[dict], policy: dict) -> list[dict]:
    plans: list[dict] = []
    stale_after = int(policy.get("stale_worker_seconds", 900) or 900)
    for obs in observations:
        state = str(obs.get("state") or "")
        if state == "stale" and float(obs.get("age_seconds") or 0) >= stale_after:
            plans.append(
                {
                    "task_id": obs.get("task_id"),
                    "action": "recover",
                    "branch": obs.get("branch"),
                    "recovery_path": obs.get("recovery_path"),
                    "preserve_evidence": True,
                    "target_status": "READY",
                }
            )
        elif state == "verification_failed":
            task_id = str(obs.get("task_id") or "UNKNOWN")
            sha = str(obs.get("candidate_sha") or "")
            plans.append(
                {
                    "task_id": task_id,
                    "action": "repair",
                    "failed_candidate_sha": sha,
                    "repair_task_id": f"REG-{task_id}-{(sha[:8] or 'FAILED').upper()}",
                    "requires_distinct_candidate_sha": True,
                    "preserve_evidence": True,
                }
            )
    return plans


def record_lead_event(
    conn,
    *,
    event_type: str,
    subject: str,
    body: str,
    task_id: str | None,
    dedupe_key: str,
) -> int:
    now = time.time()
    ts = datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds")
    priority = 0 if event_type == "BLOCKER" else 1 if event_type in {"ASSIGNMENT", "TASK_RECLAIMED", "REGRESSION"} else 5
    payload = (
        now,
        ts,
        "devin-lead",
        "ALL",
        event_type,
        priority,
        task_id,
        subject[:240],
        body[:8000],
        None,
        None,
        dedupe_key,
        "{}",
    )
    try:
        cur = conn.execute(
            """insert into brain_events
               (ts_epoch,ts,sender,recipient,event_type,priority,task_id,subject,body,
                artifact_path,artifact_sha256,dedupe_key,meta_json)
               values(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            payload,
        )
        conn.commit()
        return int(cur.lastrowid)
    except Exception as exc:
        if "unique" in str(exc).lower() or "dedupe" in str(exc).lower():
            row = conn.execute("select id from brain_events where dedupe_key=?", (dedupe_key,)).fetchone()
            if row:
                return int(row[0])
        raise


def compute_lead_metrics(conn, snapshot: dict) -> dict:
    src = snapshot.get("metrics_input", {}) if isinstance(snapshot, dict) else {}
    latencies = [float(x) for x in src.get("completed_latencies_seconds", []) if x is not None]
    completed = max(0, int(src.get("completed_count", len(latencies)) or 0))
    rework = max(0, int(src.get("rework_count", 0) or 0))
    passed = max(0, int(src.get("verification_passed", 0) or 0))
    failed = max(0, int(src.get("verification_failed", 0) or 0))
    active = max(0, int(src.get("active_workers", 0) or 0))
    logical = max(0, int(src.get("logical_capacity", 0) or 0))
    verification_total = passed + failed
    return {
        "median_task_latency_seconds": float(statistics.median(latencies)) if latencies else 0.0,
        "rework_rate": round(rework / max(1, completed + rework), 6),
        "queue_age_seconds": float(src.get("ready_queue_age_seconds", 0.0) or 0.0),
        "verification_pass_rate": round(passed / max(1, verification_total), 6),
        "worker_utilization": round(active / max(1, logical), 6) if logical else 0.0,
        "resource_contention": float(src.get("resource_contention", 0.0) or 0.0),
        "critical_path_completions": int(src.get("critical_path_completions", 0) or 0),
    }


def _connect_root(root: Path):
    import sqlite3
    db = Path(root) / "control" / "control.sqlite"
    conn = sqlite3.connect(db, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma busy_timeout=30000")
    return conn


def _policy_for_root(root: Path) -> dict:
    path = Path(root) / "config" / "devin_lead.json"
    if not path.is_file():
        return default_policy()
    loaded = load_lead_policy(path)
    merged = default_policy()
    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def _metrics_input(conn, snapshot: dict) -> dict:
    ready = [t for t in snapshot.get("tasks", []) if str(t.get("status")) == "READY"]
    active = [t for t in snapshot.get("tasks", []) if str(t.get("status")) == "ACTIVE"]
    capacity = snapshot.get("capacity", {}) if isinstance(snapshot.get("capacity"), dict) else {}
    plan = capacity.get("plan", {}) if isinstance(capacity.get("plan"), dict) else {}
    signals = capacity.get("signals", {}) if isinstance(capacity.get("signals"), dict) else {}
    verifier = signals.get("verifier", {}) if isinstance(signals.get("verifier"), dict) else {}
    host = signals.get("host", {}) if isinstance(signals.get("host"), dict) else {}
    return {
        "completed_latencies_seconds": [],
        "rework_count": len(snapshot.get("regressions", [])),
        "completed_count": 0,
        "ready_queue_age_seconds": float(signals.get("queue", {}).get("oldest_ready_age_seconds", 0.0) or 0.0) if isinstance(signals.get("queue"), dict) else 0.0,
        "verification_passed": int(verifier.get("passed", 0) or 0),
        "verification_failed": int(verifier.get("failed", verifier.get("backlog", 0)) or 0),
        "active_workers": len(active),
        "logical_capacity": int(plan.get("logical_workers", max(1, len(active))) or max(1, len(active))),
        "resource_contention": max(float(host.get("cpu_psi_avg10", 0) or 0), float(host.get("memory_psi_avg10", 0) or 0), float(host.get("io_psi_avg10", 0) or 0)),
        "ready_count": len(ready),
    }


def status_payload(root: Path) -> dict:
    root = Path(root)
    heartbeat = _load_json_file(root / "control" / "devin-lead-heartbeat.json")
    return {
        "heartbeat": heartbeat,
        "pause": read_pause(root),
        "healthy": bool(heartbeat) and not bool(heartbeat.get("error")),
    }


def lead_tick(
    root: Path,
    *,
    execute: bool = True,
    instance_id: str | None = None,
    now_fn=time.time,
) -> dict:
    root = Path(root)
    policy = _policy_for_root(root)
    instance_id = instance_id or f"{os.uname().nodename}:{os.getpid()}"
    conn = _connect_root(root)
    now = float(now_fn())
    try:
        leader_acquired = True
        if execute:
            leader_acquired = acquire_leader(
                conn,
                instance_id=instance_id,
                now=now,
                ttl_seconds=int(policy.get("leader_ttl_seconds", 180) or 180),
            )
            if not leader_acquired:
                return {
                    "instance_id": instance_id,
                    "leader": False,
                    "executed": False,
                    "blocked": "leader_busy",
                }
        snapshot = collect_planning_snapshot(conn, root, policy)
        frontier = select_frontier(snapshot, policy)
        snapshot["metrics_input"] = _metrics_input(conn, snapshot)
        metrics = compute_lead_metrics(conn, snapshot)
        pause = read_pause(root)
        base = {
            "instance_id": instance_id,
            "leader": leader_acquired,
            "paused": bool(pause.get("paused")),
            "pause_reason": pause.get("reason", ""),
            "frontier": frontier,
            "metrics": metrics,
            "executed": False,
        }
        if not execute:
            return {**base, "routes": [route_task(task, snapshot, policy) for task in frontier]}
        if pause.get("paused"):
            payload = {**base, "last_decision": "paused: observe only", "ts_epoch": now}
            write_heartbeat(root, payload)
            return payload

        observations = inspect_owned_work(conn, snapshot, policy)
        recoveries = plan_recoveries(conn, observations, policy)
        for item in recoveries:
            record_lead_event(
                conn,
                event_type="TASK_RECLAIMED" if item.get("action") == "recover" else "REGRESSION",
                subject=f"Lead {item.get('action')}: {item.get('task_id')}",
                body=json.dumps(item, sort_keys=True),
                task_id=item.get("task_id"),
                dedupe_key=f"devin-lead:{item.get('action')}:{item.get('task_id')}:{item.get('failed_candidate_sha','')}",
            )
        routes = [route_task(task, snapshot, policy) for task in frontier]
        dispatch = dispatch_plan(root, routes, execute=True)
        decision = "game-first frontier dispatched" if dispatch.get("dispatchable", 0) else "observed; no safe dispatchable frontier"
        record_lead_event(
            conn,
            event_type="DECISION",
            subject="Devin Lead planning cycle",
            body=json.dumps({"frontier": [x.get("id") for x in frontier], "routes": routes, "metrics": metrics}, sort_keys=True),
            task_id=None,
            dedupe_key=f"devin-lead:cycle:{int(now // max(1, int(policy.get('cycle_seconds', 60) or 60)))}",
        )
        payload = {
            **base,
            "executed": True,
            "routes": routes,
            "dispatch": dispatch,
            "recoveries": recoveries,
            "last_decision": decision,
            "ts_epoch": now,
        }
        write_heartbeat(root, payload)
        return payload
    finally:
        conn.close()


def run_forever(
    root: Path,
    *,
    interval_seconds: int,
    instance_id: str | None = None,
    max_cycles: int | None = None,
    now_fn=time.time,
    sleep_fn=time.sleep,
) -> int:
    root = Path(root)
    policy = _policy_for_root(root)
    instance_id = instance_id or f"{os.uname().nodename}:{os.getpid()}"
    conn = _connect_root(root)
    try:
        if not acquire_leader(
            conn,
            instance_id=instance_id,
            now=float(now_fn()),
            ttl_seconds=int(policy.get("leader_ttl_seconds", 180) or 180),
        ):
            return 2
    finally:
        conn.close()
    cycles = 0
    while max_cycles is None or cycles < max_cycles:
        try:
            result = lead_tick(root, execute=True, instance_id=instance_id, now_fn=now_fn)
            if result.get("blocked") == "leader_busy":
                return 2
        except Exception as exc:
            write_heartbeat(
                root,
                {
                    "instance_id": instance_id,
                    "healthy": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "ts_epoch": float(now_fn()),
                },
            )
        cycles += 1
        if max_cycles is not None and cycles >= max_cycles:
            break
        sleep_fn(max(0, interval_seconds))
    return 0
