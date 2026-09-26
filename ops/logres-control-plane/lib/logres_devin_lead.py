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
    preferred = str(models.get("preferred") or "swe-2-max")
    if preferred not in {"swe-2-max", "swe-2-medium", "swe-2-high"}:
        raise ValueError("preferred model must be a free SWE-2 variant")
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
        "milestones": _table_rows(conn, "milestones"),
        "goal_snapshots": _table_rows(conn, "goal_snapshots"),
        "capacity": _load_json_file(root / "control" / "capacity-state.json"),
        "swarm": _load_json_file(root / "control" / "swarm-state.json"),
        "policy": policy,
    }


def score_ready_task(task: dict, snapshot: dict, policy: dict) -> tuple:
    priority = int(task.get("priority", 9) if task.get("priority") is not None else 9)
    lane = str(task.get("lane") or "").lower()
    title = str(task.get("title") or "").lower()
    note = str(task.get("note") or "").lower()
    infra = lane in {"control-plane", "infra", "devops", "security"}
    visible_game = (not infra) and (
        lane in {"game", "release", "android", "presentation"}
        or any(token in title for token in ("battle", "field", "onboarding", "android", "playable", "visual", "game", "quest"))
    )
    critical = "critical" in note or "critical" in title
    explicit_unblock = "unblock" in title or "unblock" in note or "blocker" in note or critical
    if visible_game:
        class_rank = 0
    elif infra and explicit_unblock:
        class_rank = 1
    elif not infra:
        class_rank = 2
    else:
        class_rank = 3
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
    limit = max(0, limit)
    if not limit:
        return []
    infra_lanes = {"control-plane", "infra", "devops", "security"}
    noninfra_exists = any(str(item.get("lane") or "").lower() not in infra_lanes for item in candidates)
    ratio = max(0.0, min(1.0, float(policy.get("infrastructure_work_ratio_max", 0.35) or 0.0)))
    infra_limit = int(limit * ratio)
    if not noninfra_exists and any(score_ready_task(item, snapshot, policy)[0] == 1 for item in candidates):
        infra_limit = max(1, infra_limit)
    selected: list[dict] = []
    infra_count = 0
    for item in candidates:
        is_infra = str(item.get("lane") or "").lower() in infra_lanes
        if is_infra:
            if score_ready_task(item, snapshot, policy)[0] != 1 or infra_count >= infra_limit:
                continue
            infra_count += 1
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected


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
        key = str(proposal.get("concurrency_key") or "").strip()
        if key:
            existing = conn.execute(
                """select t.id from tasks t join task_metadata m on m.task_id=t.id
                     where m.concurrency_key=? and t.id<>?
                       and upper(coalesce(t.status,'')) not in ('DONE','RESOLVED','SUPERSEDED','CANCELLED')
                     limit 1""",
                (key, task_id),
            ).fetchone()
            if existing:
                return False, f"existing unresolved task owns concurrency key: {existing[0]}"
        title = str(proposal.get("title") or "").strip().lower()
        lane = str(proposal.get("lane") or "").strip().lower()
        if title and lane:
            existing = conn.execute(
                """select id from tasks where lower(title)=? and lower(lane)=? and id<>?
                       and upper(coalesce(status,'')) not in ('DONE','RESOLVED','SUPERSEDED','CANCELLED')
                     limit 1""",
                (title, lane, task_id),
            ).fetchone()
            if existing:
                return False, f"existing semantically equivalent task: {existing[0]}"
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
            for ordinal, criterion in enumerate(proposal.get("acceptance", []), start=1):
                conn.execute("insert into task_acceptance(task_id,ordinal,criterion) values(?,?,?)", (task_id, ordinal, str(criterion)))
        except Exception:
            pass
        try:
            for scope in proposal.get("scopes", []):
                conn.execute("insert into task_scopes(task_id,path_prefix) values(?,?)", (task_id, str(scope)))
        except Exception:
            pass
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


def dispatch_plan(root: Path, routes: list[dict], *, execute: bool, runner=subprocess.run) -> dict:
    actionable = [r for r in routes if r.get("action") == "dispatch"]
    if not execute:
        return {"executed": False, "routes": routes, "dispatchable": len(actionable)}
    if not actionable:
        return {"executed": True, "routes": routes, "dispatchable": 0, "returncode": 0}
    argv = [str(Path(root) / "bin" / "logres-capacity"), "tick", "--execute"]
    try:
        proc = runner(argv, text=True, capture_output=True, check=False, timeout=180)
        return {"executed": True, "routes": routes, "dispatchable": len(actionable), "returncode": int(proc.returncode), "stdout": (proc.stdout or "")[-4000:], "stderr": (proc.stderr or "")[-4000:]}
    except subprocess.TimeoutExpired:
        return {"executed": True, "routes": routes, "dispatchable": len(actionable), "returncode": 124, "stdout": "", "stderr": "capacity/swarm tick timed out"}
    except OSError as exc:
        return {"executed": True, "routes": routes, "dispatchable": len(actionable), "returncode": 127, "stdout": "", "stderr": f"{type(exc).__name__}: {exc}"}


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
    active_tasks = [t for t in snapshot.get("tasks", []) if str(t.get("status")) == "ACTIVE"]
    capacity = snapshot.get("capacity", {}) if isinstance(snapshot.get("capacity"), dict) else {}
    plan = capacity.get("plan", {}) if isinstance(capacity.get("plan"), dict) else {}
    signals = capacity.get("signals", {}) if isinstance(capacity.get("signals"), dict) else {}
    verifier = signals.get("verifier", {}) if isinstance(signals.get("verifier"), dict) else {}
    host = signals.get("host", {}) if isinstance(signals.get("host"), dict) else {}

    latencies: list[float] = []
    try:
        rows = conn.execute("select task_id,ts_epoch,status from task_state_history order by task_id,ts_epoch").fetchall()
        starts: dict[str, float] = {}
        finishes: dict[str, float] = {}
        for row in rows:
            task_id = str(row[0]); ts = float(row[1]); status = str(row[2] or "").upper()
            if status in {"READY", "ACTIVE"}:
                starts.setdefault(task_id, ts)
            if status == "DONE":
                finishes[task_id] = max(ts, finishes.get(task_id, ts))
        latencies = [max(0.0, finishes[t] - starts[t]) for t in finishes if t in starts and finishes[t] >= starts[t]]
    except Exception:
        latencies = []

    verification_passed = int(verifier.get("passed", 0) or 0)
    verification_failed = int(verifier.get("failed", verifier.get("backlog", 0)) or 0)
    try:
        statuses = [str(row[0] or "").upper() for row in conn.execute("select status from verification order by ran_at desc limit 50").fetchall()]
        if statuses:
            verification_passed = sum(1 for status in statuses if status == "PASS")
            verification_failed = sum(1 for status in statuses if status not in {"PASS", "SKIP", "CACHED"})
    except Exception:
        pass

    active_workers = len(active_tasks)
    try:
        active_workers = int(conn.execute("select count(*) from swarm_jobs where upper(state) in ('RUNNING','STARTING','QUEUED','ACTIVE')").fetchone()[0])
    except Exception:
        pass

    open_regressions = [
        row for row in snapshot.get("regressions", [])
        if str(row.get("status") or row.get("state") or "OPEN").upper() not in {"DONE", "RESOLVED", "SUPERSEDED", "CLOSED"}
    ]
    return {
        "completed_latencies_seconds": latencies,
        "rework_count": len(open_regressions),
        "completed_count": len(latencies),
        "ready_queue_age_seconds": float(signals.get("queue", {}).get("oldest_ready_age_seconds", 0.0) or 0.0) if isinstance(signals.get("queue"), dict) else 0.0,
        "verification_passed": verification_passed,
        "verification_failed": verification_failed,
        "active_workers": active_workers,
        "logical_capacity": int(plan.get("logical_workers", max(1, active_workers)) or max(1, active_workers)),
        "resource_contention": max(float(host.get("cpu_psi_avg10", 0) or 0), float(host.get("memory_psi_avg10", 0) or 0), float(host.get("io_psi_avg10", 0) or 0)),
        "ready_count": len(ready),
    }



def decompose_unmet_milestones(
    root: Path,
    snapshot: dict,
    policy: dict,
    *,
    execute: bool,
    runner=subprocess.run,
) -> list[dict]:
    root = Path(root)
    active = [
        dict(row)
        for row in snapshot.get("milestones", [])
        if str(row.get("status") or "").upper() not in {"DONE", "CERTIFIED", "CANCELLED"}
    ]
    active.sort(key=lambda row: (int(row.get("sort_order") or 100), str(row.get("id") or "")))
    limit = max(0, int(policy.get("task_generation_cap_per_cycle", 3) or 3))
    selected = active[:limit]
    binary = root / "bin" / "logres-goal-executor"
    results: list[dict] = []
    for milestone in selected:
        milestone_id = str(milestone.get("id") or "").strip()
        if not milestone_id:
            continue
        argv = [str(binary), milestone_id, "--json"]
        if execute:
            argv.insert(2, "--apply")
        if not execute:
            results.append({"milestone_id": milestone_id, "status": "planned", "argv": argv})
            continue
        if not binary.is_file():
            results.append({"milestone_id": milestone_id, "status": "blocked", "reason": "goal_executor_missing"})
            continue
        try:
            proc = runner(argv, text=True, capture_output=True, check=False, timeout=90)
        except (OSError, subprocess.TimeoutExpired) as exc:
            results.append({"milestone_id": milestone_id, "status": "blocked", "reason": f"{type(exc).__name__}: {exc}"})
            continue
        try:
            payload = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError:
            payload = {}
        results.append({
            "milestone_id": milestone_id,
            "status": str(payload.get("status") or ("error" if proc.returncode else "noop")).lower(),
            "task_id": payload.get("task_id"),
            "returncode": int(proc.returncode),
            "stderr": (proc.stderr or "")[-1200:],
        })
    return results


def pause_lead(root: Path, reason: str, *, now_fn=time.time) -> dict:
    root = Path(root)
    path = root / "control" / "devin-lead.pause"
    path.parent.mkdir(parents=True, exist_ok=True)
    reason = reason.strip() or "operator pause"
    path.write_text(reason + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
    event_id = None
    try:
        conn = _connect_root(root)
        try:
            event_id = record_lead_event(conn, event_type="DECISION", subject="Devin Lead paused", body=reason, task_id=None, dedupe_key=f"devin-lead:pause:{int(float(now_fn())*1000)}")
        finally:
            conn.close()
    except Exception:
        event_id = None
    return {"paused": True, "reason": reason, "event_id": event_id}


def resume_lead(root: Path, *, now_fn=time.time) -> dict:
    root = Path(root)
    path = root / "control" / "devin-lead.pause"
    path.unlink(missing_ok=True)
    event_id = None
    try:
        conn = _connect_root(root)
        try:
            event_id = record_lead_event(conn, event_type="DECISION", subject="Devin Lead resumed", body="operator resumed autonomous planning", task_id=None, dedupe_key=f"devin-lead:resume:{int(float(now_fn())*1000)}")
        finally:
            conn.close()
    except Exception:
        event_id = None
    return {"paused": False, "event_id": event_id}

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
            leader_acquired = acquire_leader(conn, instance_id=instance_id, now=now, ttl_seconds=int(policy.get("leader_ttl_seconds", 180) or 180))
            if not leader_acquired:
                return {"instance_id": instance_id, "leader": False, "executed": False, "blocked": "leader_busy"}

        snapshot = collect_planning_snapshot(conn, root, policy)
        pause = read_pause(root)
        if pause.get("paused"):
            frontier = select_frontier(snapshot, policy)
            snapshot["metrics_input"] = _metrics_input(conn, snapshot)
            metrics = compute_lead_metrics(conn, snapshot)
            payload = {
                "instance_id": instance_id, "leader": leader_acquired, "paused": True,
                "pause_reason": pause.get("reason", ""), "frontier": frontier,
                "metrics": metrics, "decomposition": [], "executed": False,
                "routes": [], "last_decision": "paused: observe only", "ts_epoch": now,
            }
            if execute:
                write_heartbeat(root, payload)
            return payload

        decomposition = decompose_unmet_milestones(root, snapshot, policy, execute=execute)
        if execute and any(item.get("task_id") for item in decomposition):
            snapshot = collect_planning_snapshot(conn, root, policy)
        frontier = select_frontier(snapshot, policy)
        snapshot["metrics_input"] = _metrics_input(conn, snapshot)
        metrics = compute_lead_metrics(conn, snapshot)
        routes = [route_task(task, snapshot, policy) for task in frontier]
        base = {
            "instance_id": instance_id, "leader": leader_acquired, "paused": False,
            "pause_reason": "", "frontier": frontier, "metrics": metrics,
            "decomposition": decomposition, "executed": False,
        }
        if not execute:
            return {**base, "routes": routes}

        observations = inspect_owned_work(conn, snapshot, policy)
        recoveries = plan_recoveries(conn, observations, policy)
        for item in recoveries:
            record_lead_event(
                conn,
                event_type="TASK_RECLAIMED" if item.get("action") == "recover" else "REGRESSION",
                subject=f"Lead {item.get('action')}: {item.get('task_id')}",
                body=json.dumps(item, sort_keys=True), task_id=item.get("task_id"),
                dedupe_key=f"devin-lead:{item.get('action')}:{item.get('task_id')}:{item.get('failed_candidate_sha','')}",
            )

        dispatch = dispatch_plan(root, routes, execute=True)
        if int(dispatch.get("returncode", 0) or 0) != 0:
            error = f"dispatch failed rc={dispatch.get('returncode')}: {dispatch.get('stderr','')[-800:]}"
            record_lead_event(conn, event_type="BLOCKER", subject="Devin Lead dispatch failed", body=error, task_id=None, dedupe_key=f"devin-lead:dispatch-fail:{int(now // max(1, int(policy.get('cycle_seconds',60) or 60)))}")
            payload = {**base, "routes": routes, "dispatch": dispatch, "recoveries": recoveries, "dispatch_failed": True, "error": error, "last_decision": "fail-closed dispatch failure", "ts_epoch": now}
            write_heartbeat(root, payload)
            return payload

        decision = "game-first frontier dispatched" if dispatch.get("dispatchable", 0) else "observed; no safe dispatchable frontier"
        record_lead_event(
            conn, event_type="DECISION", subject="Devin Lead planning cycle",
            body=json.dumps({"frontier": [x.get("id") for x in frontier], "routes": routes, "metrics": metrics, "decomposition": decomposition}, sort_keys=True),
            task_id=None, dedupe_key=f"devin-lead:cycle:{int(now // max(1, int(policy.get('cycle_seconds', 60) or 60)))}",
        )
        payload = {**base, "executed": True, "routes": routes, "dispatch": dispatch, "recoveries": recoveries, "last_decision": decision, "ts_epoch": now}
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
