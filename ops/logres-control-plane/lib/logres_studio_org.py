from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import time
from pathlib import Path

REQUIRED_DEPARTMENTS = (
    "executive_production", "game_design", "gameplay_engineering", "art_ui_ux", "qa_test",
    "security_integrity", "reverse_engineering_research", "devops_build_release",
    "performance_telemetry", "knowledge_documentation",
)
TERMINAL = {"DONE", "RESOLVED", "SUPERSEDED", "CANCELLED"}


def load_policy(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("departments"), dict):
        raise ValueError("studio policy must define departments")
    missing = set(REQUIRED_DEPARTMENTS) - set(data["departments"])
    if missing:
        raise ValueError(f"studio policy missing departments: {sorted(missing)}")
    required = {"charter","objectives","task_types","owned_artifacts","required_evidence","quality_gates","concurrency_budget","engines"}
    for name, dept in data["departments"].items():
        absent = required - set(dept)
        if absent or int(dept.get("concurrency_budget", 0)) < 1:
            raise ValueError(f"invalid department {name}: missing={sorted(absent)}")
    guardrails = set(data.get("guardrails") or [])
    expected = {"brain_ownership","independent_verification","protected_branches","spending_policy","cross_department_gates"}
    if not expected <= guardrails:
        raise ValueError("studio policy weakens required governance")
    return data


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    create table if not exists studio_work_orders(
      id text primary key, source_department text not null, target_department text not null,
      subject text not null, acceptance_json text not null, provenance_json text not null,
      status text not null, created_epoch real not null, updated_epoch real not null);
    create table if not exists studio_decisions(
      id text primary key, department text not null, subject text not null,
      payload_json text not null, created_epoch real not null);
    create table if not exists studio_outcomes(
      id integer primary key autoincrement, department text not null, task_id text,
      outcome text not null, metrics_json text not null, created_epoch real not null);
    """)
    conn.commit()


def _tokens(task: dict) -> str:
    return " ".join(str(task.get(k) or "").lower() for k in ("lane","title","work_type","note"))


def classify_task(task: dict, policy: dict) -> dict:
    text = _tokens(task)
    rules = (
        ("security_integrity", ("security","isolation","privilege","integrity","credential")),
        ("reverse_engineering_research", ("research","reverse","evidence","protocol","native","ghidra")),
        ("qa_test", ("qa","test","regression","verify","device","e2e")),
        ("performance_telemetry", ("performance","telemetry","metric","benchmark")),
        ("art_ui_ux", ("art","ui","ux","visual","presentation","asset")),
        ("knowledge_documentation", ("knowledge","documentation","memory","handoff","docs")),
        ("devops_build_release", ("devops","build","release","control-plane","deploy","ci")),
        ("game_design", ("design","quest","content plan","spec")),
        ("gameplay_engineering", ("battle","field","gameplay","implementation","npc","inventory","progression")),
    )
    department = "executive_production"
    for name, keywords in rules:
        if any(k in text for k in keywords):
            department = name
            break
    dept = policy["departments"][department]
    return {"department": department, "engines": list(dept["engines"]), "quality_gates": list(dept["quality_gates"])}


def plan_departments(tasks: list[dict], policy: dict, *, verifier_capacity: int, resource_pressure: str) -> dict:
    queues = {name: [] for name in policy["departments"]}
    for task in tasks:
        if str(task.get("status") or "").upper() in TERMINAL:
            continue
        queues[classify_task(task, policy)["department"]].append(task)
    remaining = max(0, int(verifier_capacity))
    result = {}
    ordered = sorted(queues, key=lambda n: (0 if n == "executive_production" else 1, n))
    for name in ordered:
        queue = queues[name]
        budget = int(policy["departments"][name]["concurrency_budget"])
        critical = sum(1 for t in queue if int(t.get("priority", 9) or 9) == 0)
        desired = min(budget, len(queue), max(0, remaining))
        if str(resource_pressure).lower() in {"high","critical"} and not critical:
            desired = min(desired, 1)
        remaining -= desired
        result[name] = {"queue_depth": len(queue), "critical": critical, "desired_workers": max(0, desired), "active": desired > 0, "engines": list(policy["departments"][name]["engines"])}
    return result


def _stable_id(prefix: str, material: dict) -> str:
    raw = json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    return f"{prefix}-{hashlib.sha256(raw).hexdigest()[:16]}"


def create_work_order(conn: sqlite3.Connection, *, source_department: str, target_department: str, subject: str, acceptance: list[str], provenance: dict, policy: dict) -> str:
    if source_department not in policy["departments"] or target_department not in policy["departments"]:
        raise ValueError("unknown studio department")
    if not subject.strip() or not acceptance:
        raise ValueError("work order requires subject and acceptance criteria")
    ensure_schema(conn)
    material = {"source":source_department,"target":target_department,"subject":subject,"acceptance":acceptance,"provenance":provenance}
    work_id = _stable_id("WO", material)
    now = time.time()
    conn.execute("insert or ignore into studio_work_orders values(?,?,?,?,?,?,?,?,?)", (work_id,source_department,target_department,subject,json.dumps(acceptance,sort_keys=True),json.dumps(provenance,sort_keys=True),"OPEN",now,now))
    conn.commit()
    return work_id


def record_decision(conn: sqlite3.Connection, department: str, subject: str, payload: dict) -> str:
    ensure_schema(conn)
    material = {"department":department,"subject":subject,"payload":payload}
    decision_id = _stable_id("SD", material)
    conn.execute("insert or ignore into studio_decisions values(?,?,?,?,?)", (decision_id,department,subject,json.dumps(payload,sort_keys=True),time.time()))
    conn.commit()
    return decision_id


def department_health(*, completed: int, verification_passed: int, verification_failed: int, rework: int, queue_age_seconds: float, blocker_age_seconds: float, regressions: int, resource_cost: float, critical_path_completions: int) -> dict:
    completed = max(0, int(completed)); passed = max(0, int(verification_passed)); failed = max(0, int(verification_failed)); rework = max(0, int(rework)); regressions = max(0, int(regressions))
    return {
        "throughput": completed,
        "verification_pass_rate": round(passed / max(1, passed + failed), 6),
        "rework_rate": round(rework / max(1, completed + rework), 6),
        "queue_age_seconds": max(0.0, float(queue_age_seconds)),
        "blocker_age_seconds": max(0.0, float(blocker_age_seconds)),
        "regression_rate": round(regressions / max(1, completed + regressions), 6),
        "resource_cost": max(0.0, float(resource_cost)),
        "critical_path_contribution": max(0, int(critical_path_completions)),
    }


def executive_priority(tasks: list[dict], milestones: list[dict], policy: dict) -> list[dict]:
    milestone_rank = {str(m.get("id")): int(m.get("sort_order", 999) or 999) for m in milestones}
    def score(task: dict):
        classified = classify_task(task, policy)
        critical = 0 if int(task.get("priority", 9) or 9) == 0 else 1
        return (critical, milestone_rank.get(str(task.get("milestone") or ""), 999), 0 if classified["department"] != "executive_production" else 1, str(task.get("id") or ""))
    return sorted((dict(t) for t in tasks if str(t.get("status") or "").upper() not in TERMINAL), key=score)
