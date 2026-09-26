"""Deterministic elastic capacity planner for the Logres autonomous studio."""
from __future__ import annotations

import copy
import json
import math
import os
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path

DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[1] / "config" / "capacity_policy.json"


def default_policy() -> dict:
    return json.loads(DEFAULT_POLICY_PATH.read_text(encoding="utf-8"))


def load_policy(path: Path | None = None) -> dict:
    source = Path(path or DEFAULT_POLICY_PATH)
    return json.loads(source.read_text(encoding="utf-8"))


def _f(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _i(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _pressure_band(host: dict, policy: dict) -> str:
    p = policy["pressure"]
    high = (
        _f(host.get("cpu_psi_avg10")) >= _f(p["cpu_psi_high"])
        or _f(host.get("memory_psi_avg10")) >= _f(p["memory_psi_high"])
        or _f(host.get("io_psi_avg10")) >= _f(p["io_psi_high"])
        or _f(host.get("mem_available_ratio"), 1.0) <= _f(p["mem_available_high"])
        or _f(host.get("load_per_cpu")) >= _f(p["load_per_cpu_high"])
    )
    if high:
        return "high"
    elevated = (
        _f(host.get("cpu_psi_avg10")) >= _f(p["cpu_psi_warn"])
        or _f(host.get("memory_psi_avg10")) >= _f(p["memory_psi_warn"])
        or _f(host.get("io_psi_avg10")) >= _f(p["io_psi_warn"])
        or _f(host.get("mem_available_ratio"), 1.0) <= _f(p["mem_available_warn"])
        or _f(host.get("load_per_cpu")) >= _f(p["load_per_cpu_warn"])
    )
    return "elevated" if elevated else "low"


def _devin_cap(signals: dict, policy: dict) -> tuple[int, list[str]]:
    q = policy["quota"]
    d = signals.get("devin") or {}
    reasons: list[str] = []
    session_limit = max(0, _i(d.get("cloud_session_limit"), q["unknown_devin_cap"]))
    cap = min(_i(policy["lane_caps"]["devin_cloud"]), session_limit)
    if not bool(d.get("quota_known", False)):
        cap = min(cap, _i(q["unknown_devin_cap"]))
        reasons.append("devin_quota_unknown")
        return cap, reasons
    daily = _f(d.get("daily_remaining_ratio"), 0.0)
    weekly = _f(d.get("weekly_remaining_ratio"), 0.0)
    remaining = min(daily, weekly)
    if remaining <= _f(q["critical_remaining_ratio"]):
        reasons.append("devin_quota_critical")
        return 0, reasons
    if remaining <= _f(q["low_remaining_ratio"]):
        reasons.append("devin_quota_low")
        return min(cap, _i(q["low_quota_cap"])), reasons
    return cap, reasons


def _department_allocations(total: int, weights: dict, demand: dict, critical: str | None) -> dict:
    names = list(weights)
    if total <= 0:
        return {name: 0 for name in names}
    scores = {name: max(0.0, _f(weights.get(name))) + 0.02 * max(0, _i(demand.get(name))) for name in names}
    if critical in scores:
        scores[critical] += 0.18
    if total >= len(names):
        base = {name: 1 for name in names}
        remaining = total - len(names)
    else:
        base = {name: 0 for name in names}
        remaining = total
    denom = sum(scores.values()) or 1.0
    raw = {name: remaining * scores[name] / denom for name in names}
    floors = {name: int(math.floor(raw[name])) for name in names}
    for name in names:
        base[name] += floors[name]
    left = total - sum(base.values())
    order = sorted(names, key=lambda name: (-(raw[name] - floors[name]), -scores[name], name))
    for name in order[:left]:
        base[name] += 1
    return base


def plan_capacity(signals: dict, policy: dict | None = None) -> dict:
    policy = copy.deepcopy(policy or default_policy())
    logical_cfg = policy["logical_workers"]
    heavy_cfg = policy["heavy_local_workers"]
    tuning = policy["tuning"]
    verifier_cfg = policy["verifier"]
    reasons: list[str] = []

    logical = _i(logical_cfg["target"])
    heavy = _i(heavy_cfg["target"])
    pressure = _pressure_band(signals.get("host") or {}, policy)
    if pressure == "high":
        logical -= 4
        heavy = _i(heavy_cfg["min"])
        reasons.append("host_pressure_high")
    elif pressure == "elevated":
        logical -= 2
        heavy = max(_i(heavy_cfg["min"]), heavy - 1)
        reasons.append("host_pressure_elevated")

    verifier = signals.get("verifier") or {}
    backlog = _i(verifier.get("backlog"))
    latency = _f(verifier.get("latency_seconds"))
    verifier_cap = min(2, _i(policy["lane_caps"]["verifier"]))
    verifier_saturated = backlog >= _i(verifier_cfg["backlog_high"]) or latency >= _f(verifier_cfg["latency_high_seconds"])
    verifier_warn = backlog >= _i(verifier_cfg["backlog_warn"]) or latency >= _f(verifier_cfg["latency_warn_seconds"])
    if verifier_saturated:
        logical -= 2
        heavy = max(_i(heavy_cfg["min"]), heavy - 1)
        verifier_cap = _i(policy["lane_caps"]["verifier"])
        reasons.append("verifier_saturated")
    elif verifier_warn:
        logical -= 1
        verifier_cap = min(_i(policy["lane_caps"]["verifier"]), 3)
        reasons.append("verifier_pressure")

    recent = signals.get("recent") or {}
    failure_ratio = _f(recent.get("failure_ratio"))
    samples = _i(recent.get("terminal_samples"))
    if samples >= _i(tuning["failure_min_samples"]) and failure_ratio >= _f(tuning["failure_ratio_scale_down"]):
        logical -= _i(tuning["scale_down_step"])
        reasons.append("recent_failure_rate")

    queue = signals.get("queue") or {}
    healthy_factory = pressure == "low" and not verifier_warn and failure_ratio < _f(tuning["failure_ratio_scale_down"])
    if (
        healthy_factory
        and _f(queue.get("oldest_ready_age_seconds")) >= _f(tuning["queue_age_scale_up_seconds"])
        and _i(queue.get("independent_ready")) > 0
        and _i(recent.get("integrations_last_hour")) > 0
    ):
        logical += _i(tuning["scale_up_step"])
        reasons.append("independent_queue_scale_up")

    logical = max(_i(logical_cfg["min"]), min(_i(logical_cfg["max"]), logical))
    heavy = max(_i(heavy_cfg["min"]), min(_i(heavy_cfg["max"]), heavy))

    devin_cap, quota_reasons = _devin_cap(signals, policy)
    reasons.extend(quota_reasons)
    availability = signals.get("availability") or {}
    lane_caps = {
        "local": min(_i(policy["lane_caps"]["local"]), heavy),
        "devin_cloud": devin_cap,
        "chatgpt": _i(policy["lane_caps"]["chatgpt"]) if availability.get("chatgpt", True) else 0,
        "copilot": _i(policy["lane_caps"]["copilot"]) if availability.get("copilot", False) else 0,
        "research": _i(policy["lane_caps"]["research"]) if availability.get("research", True) else 0,
        "verifier": verifier_cap,
    }
    departments = _department_allocations(
        logical,
        policy["departments"],
        signals.get("department_demand") or {},
        signals.get("critical_department"),
    )
    on_demand = bool((signals.get("devin") or {}).get("on_demand_authorized", policy["quota"]["allow_on_demand_default"]))
    return {
        "logical_workers": logical,
        "heavy_local_workers": heavy,
        "pressure": pressure,
        "lane_caps": lane_caps,
        "departments": departments,
        "spending": {
            "on_demand_authorized": on_demand,
            "allow_paid_fallback": False,
        },
        "reasons": reasons,
    }


def build_runtime_overlays(base_autoflow: dict, base_devin: dict, plan: dict) -> tuple[dict, dict]:
    autoflow = copy.deepcopy(base_autoflow)
    devin = copy.deepcopy(base_devin)
    swarm = autoflow.setdefault("swarm", {})
    swarm["max_workers"] = _i(plan["logical_workers"])
    swarm["research_workers"] = min(_i(swarm.get("research_workers", 0)), _i(plan["lane_caps"]["research"]))
    swarm["implementation_dispatch_per_tick"] = min(
        max(1, _i(swarm.get("implementation_dispatch_per_tick", 1))),
        max(1, _i(plan["lane_caps"]["devin_cloud"])),
    )
    # Never enable an engine whose current authorization/budget is zero.
    if _i(autoflow.get("copilot", {}).get("max_active", 0)) > 0:
        autoflow["copilot"]["max_active"] = min(
            _i(autoflow["copilot"]["max_active"]), _i(plan["lane_caps"]["copilot"])
        )
    if _i(autoflow.get("openai", {}).get("max_active_hard", 0)) > 0:
        autoflow["openai"]["max_active_hard"] = min(
            _i(autoflow["openai"]["max_active_hard"]), _i(plan["lane_caps"]["chatgpt"])
        )
    router = devin.setdefault("router", {})
    router["allow_paid"] = False
    router["max_active"] = _i(plan["lane_caps"]["devin_cloud"])
    router["workers"] = _i(plan["lane_caps"]["devin_cloud"])
    router["dispatch_per_tick"] = min(3, max(0, _i(plan["lane_caps"]["devin_cloud"])))
    return autoflow, devin


def _psi_avg10(name: str) -> float | None:
    try:
        for line in Path(f"/proc/pressure/{name}").read_text().splitlines():
            if line.startswith("some "):
                for part in line.split():
                    if part.startswith("avg10="):
                        return float(part.split("=", 1)[1])
    except OSError:
        return None
    return None


def _memory_available_ratio() -> float | None:
    try:
        values = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, _, rest = line.partition(":")
            if key in {"MemTotal", "MemAvailable"}:
                values[key] = int(rest.strip().split()[0])
        if values.get("MemTotal"):
            return values.get("MemAvailable", 0) / values["MemTotal"]
    except OSError:
        pass
    return None


def _quota_state(path: Path | None = None) -> dict:
    path = Path(path or os.environ.get("LOGRES_DEVIN_QUOTA_STATE", "/home/ubuntu/logres/control/devin-quota.json"))
    data = {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            data.update(raw)
    except (OSError, json.JSONDecodeError):
        pass
    for env, key in (
        ("LOGRES_DEVIN_DAILY_REMAINING_RATIO", "daily_remaining_ratio"),
        ("LOGRES_DEVIN_WEEKLY_REMAINING_RATIO", "weekly_remaining_ratio"),
        ("LOGRES_DEVIN_CLOUD_SESSION_LIMIT", "cloud_session_limit"),
    ):
        if os.environ.get(env) is not None:
            try:
                data[key] = float(os.environ[env]) if "RATIO" in env else int(os.environ[env])
            except ValueError:
                pass
    data["quota_known"] = all(k in data for k in ("daily_remaining_ratio", "weekly_remaining_ratio"))
    data.setdefault("cloud_session_limit", 2)
    data.setdefault("free_variants", 0)
    data.setdefault("on_demand_authorized", False)
    return data


def _department_for_lane(lane: str) -> str:
    text = str(lane or "").lower()
    if "security" in text: return "Security"
    if "research" in text or "reverse" in text or "evidence" in text: return "Research"
    if "qa" in text or "test" in text or "verify" in text: return "QA"
    if "art" in text or "ui" in text or "visual" in text: return "Art"
    if "design" in text: return "Design"
    if "release" in text or "devops" in text or "deploy" in text: return "Release"
    return "Engineering"


def collect_signals(conn: sqlite3.Connection, *, quota_path: Path | None = None) -> dict:
    cpus = max(1, os.cpu_count() or 1)
    try:
        load = os.getloadavg()[0] / cpus
    except OSError:
        load = 0.0
    host = {
        "cpu_psi_avg10": _psi_avg10("cpu"),
        "memory_psi_avg10": _psi_avg10("memory"),
        "io_psi_avg10": _psi_avg10("io"),
        "mem_available_ratio": _memory_available_ratio(),
        "load_per_cpu": load,
    }
    backlog = conn.execute(
        "select count(*) from integration_queue where status not in ('INTEGRATED','SUPERSEDED')"
    ).fetchone()[0]
    latencies = []
    for q, i in conn.execute(
        "select queued_at,integrated_at from integration_queue where status='INTEGRATED' and integrated_at is not null order by integrated_at desc limit 20"
    ):
        try:
            qts = time.mktime(time.strptime(q, "%Y-%m-%d %H:%M:%S"))
            its = time.mktime(time.strptime(i, "%Y-%m-%d %H:%M:%S"))
            if its >= qts: latencies.append(its-qts)
        except (TypeError, ValueError):
            pass
    verifier = {"backlog": backlog, "latency_seconds": (sum(latencies)/len(latencies) if latencies else 0.0)}
    rows = conn.execute(
        "select t.id,t.lane,coalesce(m.concurrency_key,'') from tasks t left join task_metadata m on m.task_id=t.id where t.status='READY'"
    ).fetchall()
    keys = set()
    departments = {}
    for task_id, lane, key in rows:
        keys.add(str(key) if key else f"task:{task_id}")
        dep = _department_for_lane(lane)
        departments[dep] = departments.get(dep, 0) + 1
    oldest = conn.execute(
        "select coalesce(max(0,strftime('%s','now')-strftime('%s',min(updated_at))),0) from tasks where status='READY'"
    ).fetchone()[0]
    states = [r[0] for r in conn.execute(
        "select state from swarm_jobs where state in ('DONE','FAILED') order by id desc limit 20"
    )]
    failures = sum(1 for state in states if state == "FAILED")
    integrated_hour = conn.execute(
        "select count(*) from integration_queue where status='INTEGRATED' and integrated_at>=datetime('now','-1 hour')"
    ).fetchone()[0]
    active = conn.execute(
        "select count(*) from brain_task_leases where lease_until_epoch>strftime('%s','now') and chat_id<>'lead'"
    ).fetchone()[0]
    return {
        "host": host,
        "verifier": verifier,
        "queue": {"ready": len(rows), "independent_ready": len(keys), "oldest_ready_age_seconds": _f(oldest)},
        "recent": {"failure_ratio": (failures/len(states) if states else 0.0), "terminal_samples": len(states), "integrations_last_hour": _i(integrated_hour)},
        "active": {"logical": _i(active)},
        "devin": _quota_state(quota_path),
        "availability": {"copilot": False, "chatgpt": True, "research": True},
        "department_demand": departments,
        "critical_department": max(departments, key=departments.get) if departments else "Engineering",
    }



def execute_swarm_tick(root: Path, plan: dict, *, runner=subprocess.run) -> dict:
    root = Path(root)
    autoflow_path = root / "control/autoflow.json"
    devin_path = root / "config/devin_workers.json"
    swarm_bin = root / "bin/logres-swarm"
    base_autoflow = json.loads(autoflow_path.read_text(encoding="utf-8"))
    base_devin = json.loads(devin_path.read_text(encoding="utf-8"))
    autoflow, devin = build_runtime_overlays(base_autoflow, base_devin, plan)
    scratch_root = root / "scratch"
    scratch_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="capacity-", dir=scratch_root) as td:
        tmp = Path(td)
        auto_overlay = tmp / "autoflow.json"
        devin_overlay = tmp / "devin_workers.json"
        auto_overlay.write_text(json.dumps(autoflow, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        devin_overlay.write_text(json.dumps(devin, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        env = os.environ.copy()
        env["LOGRES_AUTOFLOW_CONFIG"] = str(auto_overlay)
        env["LOGRES_DEVIN_WORKER_CONFIG"] = str(devin_overlay)
        result = runner(
            [
                "/usr/bin/flock",
                "-n",
                "-E",
                "0",
                "/tmp/logres-swarm.cron.lock",
                str(swarm_bin),
                "tick",
            ],
            text=True,
            capture_output=True,
            check=False,
            timeout=300,
            env=env,
        )
        return {
            "returncode": int(result.returncode),
            "stdout": str(result.stdout or ""),
            "stderr": str(result.stderr or ""),
        }
