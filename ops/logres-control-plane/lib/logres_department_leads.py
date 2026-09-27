from __future__ import annotations

import json
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any, Mapping

import logres_studio_org as studio

TERMINAL = {"DONE", "RESOLVED", "SUPERSEDED", "CANCELLED", "INTEGRATED"}
PROFILE_FIELDS = {
    "queue_view", "metrics", "decomposition_policy", "review_responsibilities",
    "escalation_rules", "allowed_scope_prefixes",
}


def validate_profiles(raw: Mapping[str, Any], policy: Mapping[str, Any]) -> dict[str, dict]:
    profiles = raw.get("profiles") if isinstance(raw, Mapping) else None
    if int(raw.get("schema") or 0) != 1 or not isinstance(profiles, Mapping):
        raise ValueError("department lead profiles must use schema 1")
    expected = set(studio.REQUIRED_DEPARTMENTS)
    missing = expected - set(profiles)
    if missing:
        raise ValueError(f"missing department lead profile: {sorted(missing)}")
    extras = set(profiles) - expected
    if extras:
        raise ValueError(f"unknown department lead profile: {sorted(extras)}")
    clean: dict[str, dict] = {}
    for name in studio.REQUIRED_DEPARTMENTS:
        source = profiles[name]
        if not isinstance(source, Mapping):
            raise ValueError(f"invalid department lead profile: {name}")
        absent = PROFILE_FIELDS - set(source)
        if absent:
            raise ValueError(f"invalid department lead profile {name}: missing={sorted(absent)}")
        profile = dict(source)
        profile["department"] = name
        profile["charter"] = str(policy["departments"][name]["charter"])
        for key in PROFILE_FIELDS:
            if not profile.get(key):
                raise ValueError(f"empty department lead field {name}:{key}")
        decomposition = profile["decomposition_policy"]
        max_tasks = int(decomposition.get("max_tasks_per_cycle", decomposition.get("max_generated_per_cycle", 0)))
        if not 1 <= max_tasks <= 8:
            raise ValueError(f"invalid decomposition cap for {name}")
        profile["specialist_roles"] = list(profile.get("specialist_roles") or policy["departments"][name]["engines"])
        clean[name] = profile
    return clean


def load_profiles(path: str | Path, policy: Mapping[str, Any]) -> dict[str, dict]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_profiles(raw, policy)


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    create table if not exists department_lead_cycles(
      id integer primary key autoincrement, created_epoch real not null,
      source text not null, allocation_json text not null, standup_json text not null);
    create table if not exists department_lead_task_log(
      task_id text primary key, department text not null, cycle_id text not null,
      provenance_json text not null, created_epoch real not null);
    """)
    conn.commit()

def _rows(conn: sqlite3.Connection, table: str) -> list[dict]:
    try:
        return [dict(row) for row in conn.execute(f"select * from {table}")]
    except sqlite3.OperationalError:
        return []


def _metadata(conn: sqlite3.Connection) -> dict[str, dict]:
    return {str(row["task_id"]): row for row in _rows(conn, "task_metadata")}


def _merged_task(task: Mapping[str, Any], metadata: Mapping[str, dict]) -> dict:
    out = dict(task)
    out.update({k: v for k, v in metadata.get(str(task.get("id")), {}).items() if v is not None})
    return out


def department_snapshot(
    conn: sqlite3.Connection,
    department: str,
    policy: Mapping[str, Any],
    profiles: Mapping[str, dict],
) -> dict:
    if department not in profiles:
        raise ValueError(f"unknown department: {department}")
    metadata = _metadata(conn)
    all_tasks = [_merged_task(row, metadata) for row in _rows(conn, "tasks")]
    owned = [t for t in all_tasks if studio.classify_task(t, policy)["department"] == department]
    queue = [t for t in owned if str(t.get("status") or "").upper() not in TERMINAL]
    queue.sort(key=lambda t: (int(9 if t.get("priority") is None else t.get("priority")), str(t.get("id") or "")))
    statuses = [str(t.get("status") or "").upper() for t in owned]
    blockers = [t for t in queue if str(t.get("status") or "").upper().startswith("BLOCKED")]
    task_ids = {str(t.get("id")) for t in owned}
    regressions = [r for r in _rows(conn, "regressions")
                   if str(r.get("task_id") or "") in task_ids and str(r.get("status") or "").upper() == "OPEN"]
    running = [j for j in _rows(conn, "swarm_jobs")
               if str(j.get("task_id") or "") in task_ids and str(j.get("state") or "").upper() in {"STARTING", "RUNNING"}]
    profile = profiles[department]
    return {
        "source": "brain",
        "department": department,
        "charter": profile["charter"],
        "queue_view": profile["queue_view"],
        "queue": queue,
        "decomposition_policy": profile["decomposition_policy"],
        "review_responsibilities": profile["review_responsibilities"],
        "escalation_rules": profile["escalation_rules"],
        "metrics": {
            "queue_depth": len(queue),
            "active_workers": len(running),
            "done": statuses.count("DONE") + statuses.count("INTEGRATED"),
            "blocked": sum(1 for s in statuses if s.startswith("BLOCKED")),
            "open_regressions": len(regressions),
        },
        "blockers": blockers,
        "risks": regressions,
    }


def _scope_allowed(scope: str, allowed: list[str]) -> bool:
    scope = str(scope).rstrip("/")
    return any(scope == prefix.rstrip("/") or scope.startswith(prefix.rstrip("/") + "/") for prefix in allowed)

def _work_order_ok(conn: sqlite3.Connection, work_order_id: str,
                   source: str, target: str) -> bool:
    try:
        row = conn.execute(
            "select source_department,target_department,status from studio_work_orders where id=?",
            (work_order_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    if row is None:
        return False
    return str(row[0]) == source and str(row[1]) == target and str(row[2]) == "OPEN"


def build_task_command(
    proposal: Mapping[str, Any],
    department: str,
    policy: Mapping[str, Any],
    profiles: Mapping[str, dict],
    *,
    coordinator_bin: str = "/home/ubuntu/logres/bin/logres-coordinator",
    requested_department: str | None = None,
    work_order_id: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[str]:
    if department not in profiles:
        raise ValueError("unknown source department")
    target = requested_department or department
    if target not in profiles:
        raise ValueError("unknown target department")
    if target != department:
        if not work_order_id or conn is None or not _work_order_ok(conn, work_order_id, department, target):
            raise ValueError("cross-department task requires explicit work order")
    classified = studio.classify_task(dict(proposal), policy)["department"]
    if classified != target:
        raise ValueError(f"proposal outside department charter: classified={classified} target={target}")
    scopes = [str(x) for x in proposal.get("scopes", [])]
    acceptance = [str(x) for x in proposal.get("acceptance", [])]
    if not scopes or not acceptance:
        raise ValueError("department task requires scopes and acceptance")
    allowed = [str(x) for x in profiles[target]["allowed_scope_prefixes"]]
    for scope in scopes:
        if not _scope_allowed(scope, allowed):
            raise ValueError(f"scope outside department scope: {scope}")
    priority = int(proposal.get("priority", 5))
    minutes = int(proposal.get("expected_minutes", 60))
    if not 0 <= priority <= 9 or not 5 <= minutes <= 240:
        raise ValueError("invalid bounded task priority or duration")
    evidence = {
        "source": "department_lead",
        "department": target,
        "source_department": department,
        "work_order_id": work_order_id,
        "provenance": dict(proposal.get("provenance") or {}),
        "brain_ownership_required": True,
        "independent_verification_required": independent_review_route(dict(proposal), policy)["required"],
        "direct_merge_deploy_authority": False,
        "protected_branch_authority": False,
        "paid_model_authority": False,
    }
    task_id = str(proposal.get("id") or "").strip()
    title = str(proposal.get("title") or "").strip()
    lane = str(proposal.get("lane") or "").strip()
    if not task_id or not title or not lane:
        raise ValueError("department task requires id, title and lane")
    argv = [coordinator_bin, "add-task", task_id, str(priority), lane, title,
            "--work-type", str(proposal.get("work_type") or "implementation"),
            "--concurrency-key", str(proposal.get("concurrency_key") or f"department:{target}"),
            "--minutes", str(minutes), "--evidence-policy", json.dumps(evidence, sort_keys=True)]
    if proposal.get("milestone"):
        argv += ["--milestone", str(proposal["milestone"])]
    for item in acceptance:
        argv += ["--accept", item]
    for scope in scopes:
        argv += ["--scope", scope]
    for dep in proposal.get("dependencies", []):
        argv += ["--depends", str(dep)]
    return argv


def elastic_worker_plan(*, queue_depth: int, active_workers: int, desired_workers: int) -> dict:
    queue_depth = max(0, int(queue_depth))
    active_workers = max(0, int(active_workers))
    desired_workers = max(0, int(desired_workers))
    target = min(queue_depth, desired_workers)
    return {
        "target_workers": target,
        "spawn": max(0, target - active_workers),
        "release": max(0, active_workers - target),
        "active_workers": active_workers,
        "queue_depth": queue_depth,
    }


def _health_score(row: Mapping[str, Any] | None) -> float:
    row = row or {}
    pass_rate = max(0.0, min(1.0, float(row.get("verification_pass_rate", 1.0))))
    rework = max(0.0, min(1.0, float(row.get("rework_rate", 0.0))))
    return pass_rate - rework

def executive_allocate(
    tasks: list[dict],
    policy: Mapping[str, Any],
    profiles: Mapping[str, dict],
    *,
    verifier_capacity: int,
    resource_pressure: str,
    health: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, dict]:
    queues = {name: [] for name in profiles}
    for task in tasks:
        if str(task.get("status") or "").upper() in TERMINAL:
            continue
        department = studio.classify_task(task, policy)["department"]
        queues[department].append(task)
    ranked = []
    for name, queue in queues.items():
        critical = sum(1 for t in queue if int(9 if t.get("priority") is None else t.get("priority")) == 0)
        score = critical * 10000 + len(queue) * 100 + _health_score((health or {}).get(name))
        ranked.append((score, name, critical))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    remaining = max(0, int(verifier_capacity))
    result: dict[str, dict] = {}
    for _, name, critical in ranked:
        queue = queues[name]
        budget = int(policy["departments"][name]["concurrency_budget"])
        desired = min(len(queue), budget, remaining)
        if str(resource_pressure).lower() in {"high", "critical"} and not critical:
            desired = min(desired, 1)
        remaining -= desired
        result[name] = {
            "queue_depth": len(queue), "critical": critical,
            "desired_workers": max(0, desired), "active": desired > 0,
            "specialist_roles": list(profiles[name]["specialist_roles"]),
            "health_score": round(_health_score((health or {}).get(name)), 4),
        }
    return result

def independent_review_route(task: Mapping[str, Any], policy: Mapping[str, Any]) -> dict:
    text = " ".join(str(task.get(k) or "").lower() for k in ("lane", "title", "work_type", "note"))
    reviews: list[str] = []
    reasons: list[str] = []
    if any(token in text for token in ("design", "quest contract", "systems")):
        reviews.extend(["qa_test"]); reasons.append("design_sensitive")
    if any(token in text for token in ("security", "sandbox", "privilege", "credential", "integrity")):
        reviews.extend(["security_integrity", "qa_test"]); reasons.append("security_sensitive")
    if any(token in text for token in ("release", "apk", "deploy", "production")):
        reviews.extend(["qa_test", "security_integrity"]); reasons.append("release_critical")
    if any(token in text for token in ("historical", "global fidelity", "original evidence", "version sensitive")):
        reviews.extend(["qa_test", "knowledge_documentation"]); reasons.append("historical_fidelity")
    unique = []
    for name in reviews:
        if name in policy["departments"] and name not in unique:
            unique.append(name)
    return {"required": bool(unique), "review_departments": unique, "reasons": reasons}


def _progress_counts(tasks: list[dict]) -> dict:
    statuses = [str(t.get("status") or "").upper() for t in tasks]
    return {
        "done": sum(1 for s in statuses if s in TERMINAL),
        "active": statuses.count("ACTIVE"),
        "ready": statuses.count("READY"),
        "blocked": sum(1 for s in statuses if s.startswith("BLOCKED")),
    }


def studio_standup(
    conn: sqlite3.Connection,
    policy: Mapping[str, Any],
    profiles: Mapping[str, dict],
    *,
    verifier_capacity: int,
    resource_pressure: str,
) -> dict:
    metadata = _metadata(conn)
    tasks = [_merged_task(row, metadata) for row in _rows(conn, "tasks")]
    departments = {}
    blockers = []
    risks = []
    for name in profiles:
        snap = department_snapshot(conn, name, policy, profiles)
        owned = [t for t in tasks if studio.classify_task(t, policy)["department"] == name]
        snap["progress"] = _progress_counts(owned)
        departments[name] = snap
        blockers.extend({"department": name, "task_id": t.get("id"), "note": t.get("note", "")} for t in snap["blockers"])
        risks.extend({"department": name, "task_id": r.get("task_id"), "kind": r.get("kind"), "summary": r.get("summary")} for r in snap["risks"])
    allocation = executive_allocate(
        tasks, policy, profiles, verifier_capacity=verifier_capacity,
        resource_pressure=resource_pressure, health={},
    )
    actionable = [t for t in tasks if str(t.get("status") or "").upper() in {"READY", "ACTIVE"}]
    actionable.sort(key=lambda t: (int(9 if t.get("priority") is None else t.get("priority")), str(t.get("id") or "")))
    next_actions = [
        {"task_id": t.get("id"), "department": studio.classify_task(t, policy)["department"],
         "status": t.get("status"), "title": t.get("title")}
        for t in actionable[:10]
    ]
    return {
        "source": "brain", "created_epoch": time.time(),
        "departments": departments, "allocation": allocation,
        "blockers": blockers, "risks": risks, "next_actions": next_actions,
        "resource_pressure": str(resource_pressure),
        "verifier_capacity": max(0, int(verifier_capacity)),
        "authority": "BRAIN_TASKS_ONLY_NO_DIRECT_MERGE_DEPLOY_CREDENTIAL_SPEND",
    }


def run_worker_cycle(
    root: str | Path,
    report: Mapping[str, Any],
    *,
    execute: bool,
    runner=subprocess.run,
) -> dict:
    departments = report.get("departments") if isinstance(report, Mapping) else {}
    allocation = report.get("allocation") if isinstance(report, Mapping) else {}
    departments = departments if isinstance(departments, Mapping) else {}
    allocation = allocation if isinstance(allocation, Mapping) else {}
    actions = {}
    total_spawn = 0
    total_release = 0
    for name, target in allocation.items():
        snapshot = departments.get(name, {}) if isinstance(departments.get(name, {}), Mapping) else {}
        metrics = snapshot.get("metrics", {}) if isinstance(snapshot, Mapping) else {}
        plan = elastic_worker_plan(
            queue_depth=int(metrics.get("queue_depth", 0) or 0),
            active_workers=int(metrics.get("active_workers", 0) or 0),
            desired_workers=int((target or {}).get("desired_workers", 0) or 0),
        )
        actions[str(name)] = plan
        total_spawn += plan["spawn"]
        total_release += plan["release"]
    result = {
        "executed": False, "spawn": total_spawn, "release": total_release,
        "departments": actions,
        "authority": "GOVERNED_CAPACITY_ONLY_NO_DIRECT_PROCESS_OR_SPEND_AUTHORITY",
    }
    if not execute or total_spawn + total_release == 0:
        return result
    argv = [str(Path(root) / "bin" / "logres-capacity"), "tick", "--execute"]
    try:
        proc = runner(argv, text=True, capture_output=True, check=False, timeout=180)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {**result, "executed": True, "returncode": 124 if isinstance(exc, subprocess.TimeoutExpired) else 127, "error": str(exc)}
    return {
        **result, "executed": True, "returncode": int(proc.returncode),
        "stdout": str(proc.stdout or "")[-2000:], "stderr": str(proc.stderr or "")[-2000:],
    }
