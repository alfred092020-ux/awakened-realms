from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import logres_governor as governor

OBJECTIVE_METRICS = {
    "median_task_latency_seconds", "rework_rate", "queue_age_seconds",
    "verification_pass_rate", "worker_utilization", "resource_contention",
    "critical_path_completions",
}
AUTHORITY = "ADVISORY_LEAD_EVOLUTION_NO_DIRECT_SAFETY_SPEND_MERGE_DEPLOY"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_policy(path: Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if int(data.get("version") or 0) != 1 or not isinstance(data.get("domains"), dict):
        raise ValueError("invalid lead evolution policy")
    return data


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    create table if not exists devin_lead_policy_versions(
      version integer primary key,
      created_at text not null,
      source_experiment_id integer not null,
      policy_json text not null,
      shadow_pass integer not null,
      independent_attestation text not null,
      status text not null
    );
    create table if not exists devin_lead_policy_state(
      singleton integer primary key check(singleton=1),
      active_version integer not null
    );
    """)
    conn.commit()


def _finite(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be an objective metric value")
    if not math.isfinite(number):
        raise ValueError(f"{label} must be an objective metric value")
    return number


def _domain(policy: Mapping[str, Any], name: str) -> dict[str, Any]:
    domains = policy.get("domains") if isinstance(policy, Mapping) else None
    if not isinstance(domains, Mapping) or name not in domains:
        raise ValueError("lead evolution domain is not allowlisted")
    row = domains[name]
    if not isinstance(row, Mapping):
        raise ValueError("lead evolution domain is malformed")
    return dict(row)


def emit_experiment(conn: sqlite3.Connection, policy: Mapping[str, Any], decision: Mapping[str, Any]) -> dict[str, Any]:
    domain_name = str(decision.get("domain") or "").strip()
    domain = _domain(policy, domain_name)
    metric = str(decision.get("metric_name") or "").strip()
    if metric not in OBJECTIVE_METRICS or metric != str(domain.get("metric") or ""):
        raise ValueError("decision must use the allowlisted objective metric for its domain")
    before = _finite(decision.get("before_value"), "before_value")
    after = _finite(decision.get("after_value"), "after_value")
    direction = str(domain.get("direction") or "")
    if direction not in {"higher", "lower"}:
        raise ValueError("invalid domain direction")
    delta = max(abs(after - before), max(abs(before), 1.0) * 0.05)
    target = after + delta if direction == "higher" else after - delta
    rollback = before - delta if direction == "higher" else before + delta
    scopes = [str(x) for x in domain.get("scopes", [])]
    if not scopes:
        raise ValueError("domain has no bounded scopes")
    acceptance = [
        f"Measure {metric} objectively before and after the bounded Lead policy change.",
        "Shadow evaluation must pass before canonical promotion.",
        "Independent verification is mandatory; no self-attestation.",
        "No safety, spending, credential, protected-branch, merge, deploy, or paid-model authority may change.",
    ]
    contract = {
        "version": 1,
        "domain": f"lead_{domain_name}",
        "title": f"Bounded Devin Lead {domain_name.replace('_', ' ')} experiment",
        "lane": "control-plane",
        "priority": 1,
        "expected_minutes": 60,
        "measurement_key": metric,
        "scopes": scopes,
        "acceptance": acceptance,
        "depends": [],
        "depends_integrated": ["DEVIN-AUTONOMOUS-LEAD-001", "DEVIN-GOVERNED-EVOLUTION-001"],
    }
    source = {
        "decision_id": str(decision.get("decision_id") or ""),
        "decision_summary": str(decision.get("summary") or ""),
        "objective_before": before,
        "objective_after": after,
        "shadow_evaluated": bool(decision.get("shadow_evaluated", False)),
        "independent_verification": dict(decision.get("independent_verification") or {}),
        "evolution_contract": contract,
        "authority": AUTHORITY,
    }
    proposal = governor.ExperimentProposal(
        source_kind=f"DEVIN_LEAD_{domain_name.upper()}",
        hypothesis=f"A bounded Lead {domain_name} change can improve {metric} without weakening guardrails.",
        metric_name=metric,
        direction=direction,
        baseline_value=before,
        success_target=target,
        rollback_threshold=rollback,
        rollback_condition="Reject on objective regression, failed shadow evaluation, failed independent verification, or any guardrail breach.",
        max_scope="Only the explicit evolution_contract scopes; no policy authority outside the allowlisted Lead domain.",
        proposed_action=f"Evaluate one bounded {domain_name} Lead policy change in shadow mode.",
        source=source,
    )
    row = governor.persist_proposals(conn, [proposal])[0]
    return {**row, "experiment_id": int(row["id"])}


def _attestation_fields(raw: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in str(raw or "").split(";"):
        key, _, value = part.partition("=")
        if key.strip() and value.strip():
            fields[key.strip().lower()] = value.strip()
    return fields


def _attestation_pass(policy: Mapping[str, Any], raw: str) -> bool:
    fields = _attestation_fields(raw)
    reviewer = fields.get("reviewer", "").strip()
    forbidden = {str(x).strip().casefold() for x in policy.get("forbidden_attestation_reviewers", [])}
    return bool(reviewer) and reviewer.casefold() not in forbidden and fields.get("verdict", "").upper() == "PASS"


def _assert_candidate_safe(policy: Mapping[str, Any], candidate: Mapping[str, Any]) -> None:
    allowed = set(policy.get("domains", {}).keys())
    protected = [str(x).lower() for x in policy.get("protected_key_fragments", [])]
    if not candidate or any(str(k) not in allowed for k in candidate):
        raise ValueError("candidate modifies protected or non-evolvable Lead policy")
    def walk(value: Any, path: str = "") -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                p = f"{path}.{key}" if path else str(key)
                low = p.lower()
                if any(token in low for token in protected):
                    raise ValueError("candidate modifies protected Lead policy constraint")
                walk(child, p)
        elif isinstance(value, list):
            for i, child in enumerate(value):
                walk(child, f"{path}[{i}]")
    walk(candidate)


def _require_keep_experiment(conn: sqlite3.Connection, experiment_id: int) -> sqlite3.Row:
    row = conn.execute("select * from governor_experiments where id=?", (int(experiment_id),)).fetchone()
    if row is None or str(row["status"]) != "EVALUATED" or str(row["recommendation"]) != "KEEP":
        raise ValueError("canonical promotion requires an EVALUATED+KEEP governor experiment")
    return row


def promote_policy(conn: sqlite3.Connection, policy: Mapping[str, Any], candidate: Mapping[str, Any], *, source_experiment_id: int, shadow_pass: bool, independent_attestation: str) -> dict[str, Any]:
    ensure_schema(conn)
    _assert_candidate_safe(policy, candidate)
    _require_keep_experiment(conn, source_experiment_id)
    if not shadow_pass:
        raise ValueError("shadow evaluation must pass before canonical promotion")
    if not _attestation_pass(policy, independent_attestation):
        raise ValueError("independent verification PASS attestation is required")
    row = conn.execute("select coalesce(max(version),0) from devin_lead_policy_versions").fetchone()
    version = int(row[0] if row else 0) + 1
    conn.execute("update devin_lead_policy_versions set status='VERIFIED' where status='ACTIVE_VERIFIED'")
    conn.execute("insert into devin_lead_policy_versions(version,created_at,source_experiment_id,policy_json,shadow_pass,independent_attestation,status) values(?,?,?,?,?,?,?)",
                 (version, _now(), int(source_experiment_id), json.dumps(dict(candidate), sort_keys=True), 1, str(independent_attestation), "ACTIVE_VERIFIED"))
    conn.execute("insert into devin_lead_policy_state(singleton,active_version) values(1,?) on conflict(singleton) do update set active_version=excluded.active_version", (version,))
    conn.commit()
    return {"version": version, "status": "ACTIVE_VERIFIED", "authority": AUTHORITY}


def rollback_if_regressed(conn: sqlite3.Connection, policy: Mapping[str, Any], metrics: Mapping[str, Any]) -> dict[str, Any]:
    ensure_schema(conn)
    state = conn.execute("select active_version from devin_lead_policy_state where singleton=1").fetchone()
    if state is None:
        return {"rolled_back": False, "reason": "no active verified policy"}
    active = int(state[0])
    thresholds = policy.get("rollback", {}) if isinstance(policy, Mapping) else {}
    verification = _finite(metrics.get("verification_pass_rate", 1.0), "verification_pass_rate")
    rework = _finite(metrics.get("rework_rate", 0.0), "rework_rate")
    breached = verification < float(thresholds.get("verification_pass_rate_min", 0.0)) or rework > float(thresholds.get("rework_rate_max", 1.0))
    if not breached:
        return {"rolled_back": False, "active_version": active}
    prior = conn.execute("select version from devin_lead_policy_versions where version<? and status in ('VERIFIED','ACTIVE_VERIFIED') order by version desc limit 1", (active,)).fetchone()
    if prior is None:
        return {"rolled_back": False, "active_version": active, "reason": "no prior verified policy"}
    previous = int(prior[0])
    conn.execute("update devin_lead_policy_versions set status='ROLLED_BACK' where version=?", (active,))
    conn.execute("update devin_lead_policy_versions set status='ACTIVE_VERIFIED' where version=?", (previous,))
    conn.execute("update devin_lead_policy_state set active_version=? where singleton=1", (previous,))
    conn.commit()
    return {"rolled_back": True, "from_version": active, "active_version": previous, "reason": "objective regression threshold breached"}
