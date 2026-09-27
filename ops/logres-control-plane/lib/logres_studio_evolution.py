from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

REQUIRED_OUTCOMES = (
    "throughput", "verification_pass_rate", "rework_rate", "queue_depth",
    "queue_age_seconds", "blocker_count", "blocker_age_seconds",
    "regressions", "resource_pressure", "critical_path_completions",
)
EVOLVABLE_DOMAINS = {"routing", "concurrency", "decomposition", "review_scheduling", "specialization"}
AUTHORITY = "ADVISORY_STUDIO_EVOLUTION_NO_DIRECT_INTEGRATION_SPEND_CREDENTIAL_OR_PROTECTED_BRANCH_AUTHORITY"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_policy(path: Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    domains = data.get("evolvable_domains")
    if int(data.get("version") or 0) != 1 or not isinstance(domains, dict):
        raise ValueError("invalid studio evolution policy")
    if set(domains) != EVOLVABLE_DOMAINS or bool(data.get("direct_integration_authority", True)):
        raise ValueError("studio evolution policy expands protected authority")
    return data


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    create table if not exists studio_evolution_proposals(
      id integer primary key autoincrement,
      fingerprint text not null unique,
      created_at text not null,
      department text not null,
      domain text not null,
      metric_name text not null,
      direction text not null,
      baseline_value real not null,
      target_value real not null,
      rollback_threshold real not null,
      patch_json text not null,
      contract_json text not null,
      evidence_json text not null,
      shadow_json text,
      status text not null
    );
    create table if not exists studio_policy_versions(
      version integer primary key,
      created_at text not null,
      source_proposal_id integer,
      policy_json text not null,
      evidence_json text not null,
      independent_attestation text not null,
      status text not null
    );
    create table if not exists studio_evolution_state(
      singleton integer primary key check(singleton=1),
      active_version integer not null,
      last_decision_id integer,
      last_rollback_from integer,
      last_rollback_at text
    );
    create table if not exists studio_evolution_decisions(
      id integer primary key autoincrement,
      created_at text not null,
      proposal_id integer,
      phase text not null,
      verdict text not null,
      details_json text not null
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


def _brain_event(conn: sqlite3.Connection, event_type: str, subject: str, body: str, meta: Mapping[str, Any]) -> None:
    conn.execute(
        """insert into brain_events(ts_epoch,ts,sender,recipient,event_type,priority,task_id,subject,body,dedupe_key,meta_json)
           values(?,?,?,?,?,?,?,?,?,?,?)""",
        (time.time(), _now(), "studio-evolution", "ALL", event_type, 1,
         "AUTONOMOUS-STUDIO-CLOSED-LOOP-001", subject, body,
         hashlib.sha256((event_type+subject+json.dumps(dict(meta),sort_keys=True)).encode()).hexdigest(),
         json.dumps(dict(meta), sort_keys=True)),
    )


def _decision(conn: sqlite3.Connection, proposal_id: int | None, phase: str, verdict: str, details: Mapping[str, Any]) -> int:
    cur = conn.execute(
        "insert into studio_evolution_decisions(created_at,proposal_id,phase,verdict,details_json) values(?,?,?,?,?)",
        (_now(), proposal_id, phase, verdict, json.dumps(dict(details), sort_keys=True)),
    )
    decision_id = int(cur.lastrowid)
    try:
        conn.execute("update studio_evolution_state set last_decision_id=? where singleton=1", (decision_id,))
    except sqlite3.OperationalError:
        pass
    return decision_id


def validate_patch(policy: Mapping[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(patch, Mapping) or len(patch) != 1:
        raise ValueError("policy patch must contain exactly one bounded evolvable domain")
    domain = str(next(iter(patch)))
    if domain not in EVOLVABLE_DOMAINS or domain not in policy.get("evolvable_domains", {}):
        raise ValueError(f"policy domain not evolvable: {domain}")
    values = patch[domain]
    if not isinstance(values, Mapping) or not values:
        raise ValueError("policy patch must contain bounded field values")
    protected = [str(x).casefold() for x in policy.get("protected_key_fragments", [])]
    spec = policy["evolvable_domains"][domain]
    bounds = spec.get("bounds", {})
    for key, value in values.items():
        low_key = str(key).casefold()
        if any(token in low_key for token in protected):
            raise ValueError("policy patch touches protected authority")
        if key not in bounds:
            raise ValueError(f"policy field outside bounded contract: {domain}.{key}")
        number = _finite(value, f"{domain}.{key}")
        lo, hi = bounds[key]
        if number < float(lo) or number > float(hi):
            raise ValueError(f"policy field outside bounded contract: {domain}.{key}")
    return {domain: dict(values)}


def _empty_policy_state() -> dict[str, Any]:
    return {"departments": {}}


def validate_policy_state(policy: Mapping[str, Any], state: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(state, Mapping) or set(state) != {"departments"}:
        raise ValueError("persisted policy outside bounded contract")
    departments = state.get("departments")
    if not isinstance(departments, Mapping):
        raise ValueError("persisted policy departments must be a mapping")
    normalized: dict[str, Any] = {"departments": {}}
    for department, overlays in departments.items():
        name = str(department).strip()
        if not name or not isinstance(overlays, Mapping):
            raise ValueError("persisted policy department is invalid")
        normalized_overlays: dict[str, Any] = {}
        for domain, values in overlays.items():
            checked = validate_patch(policy, {str(domain): values})
            normalized_overlays.update(checked)
        normalized["departments"][name] = normalized_overlays
    return normalized


def _validate_outcome(outcome: Mapping[str, Any]) -> dict[str, Any]:
    if not str(outcome.get("department") or "").strip() or not str(outcome.get("window") or "").strip():
        raise ValueError("missing measured outcome identity")
    result = {"department": str(outcome["department"]), "window": str(outcome["window"])}
    for key in REQUIRED_OUTCOMES:
        if key not in outcome:
            raise ValueError(f"missing measured outcome: {key}")
        result[key] = _finite(outcome[key], key)
    return result


def _triggered(spec: Mapping[str, Any], evidence: Mapping[str, Any]) -> bool:
    trigger = spec.get("trigger") or {}
    metric = str(trigger.get("metric") or "")
    if metric not in evidence:
        return False
    value = float(evidence[metric])
    threshold = float(trigger.get("threshold", 0.0))
    op = str(trigger.get("operator") or "")
    matched = (op == "lt" and value < threshold) or (op == "lte" and value <= threshold) or (op == "gt" and value > threshold) or (op == "gte" and value >= threshold)
    if "resource_pressure_max" in trigger and float(evidence["resource_pressure"]) > float(trigger["resource_pressure_max"]):
        return False
    return matched


def propose_improvement(conn: sqlite3.Connection, policy: Mapping[str, Any], outcome: Mapping[str, Any]) -> dict[str, Any]:
    ensure_schema(conn)
    evidence = _validate_outcome(outcome)
    domains = policy["evolvable_domains"]
    domain = next((name for name in policy.get("domain_priority", []) if name in domains and _triggered(domains[name], evidence)), "routing")
    spec = domains[domain]
    metric = str(spec["metric"])
    direction = str(spec["direction"])
    if direction not in {"higher", "lower"}:
        raise ValueError("invalid studio evolution metric direction")
    baseline = _finite(evidence[metric], metric)
    delta = max(abs(baseline) * 0.05, 0.01)
    target = baseline + delta if direction == "higher" else max(0.0, baseline - delta)
    rollback = max(0.0, baseline - delta) if direction == "higher" else baseline + delta
    patch = validate_patch(policy, {domain: dict(spec["candidate"])})
    contract = {
        "version": 1,
        "department": evidence["department"],
        "domain": domain,
        "metric_name": metric,
        "direction": direction,
        "allowed_fields": sorted(spec["bounds"]),
        "bounds": spec["bounds"],
        "patch": patch,
        "requires_shadow_evaluation": True,
        "requires_independent_verification": True,
        "direct_integration_authority": False,
        "protected_authorities": ["safety", "spending", "credentials", "protected_branches", "merge", "deploy", "independent_verification"],
        "authority": AUTHORITY,
    }
    material = {"department": evidence["department"], "window": evidence["window"], "contract": contract, "evidence": evidence}
    fingerprint = hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()
    row = conn.execute("select id from studio_evolution_proposals where fingerprint=?", (fingerprint,)).fetchone()
    if row is None:
        cur = conn.execute(
            """insert into studio_evolution_proposals(
               fingerprint,created_at,department,domain,metric_name,direction,baseline_value,target_value,
               rollback_threshold,patch_json,contract_json,evidence_json,status)
               values(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fingerprint, _now(), evidence["department"], domain, metric, direction, baseline, target, rollback,
             json.dumps(patch,sort_keys=True), json.dumps(contract,sort_keys=True), json.dumps(evidence,sort_keys=True), "PROPOSED"),
        )
        proposal_id = int(cur.lastrowid)
        decision_id = _decision(conn, proposal_id, "PROPOSAL", "PROPOSED", {"contract": contract, "evidence": evidence})
        _brain_event(conn, "DECISION", "Bounded studio improvement proposed", f"proposal={proposal_id} department={evidence['department']} domain={domain}", {"proposal_id":proposal_id,"decision_id":decision_id,"contract":contract,"evidence":evidence})
        conn.commit()
    else:
        proposal_id = int(row[0])
    return {"proposal_id": proposal_id, "status": "PROPOSED", "baseline_value": baseline, "target_value": target, "rollback_threshold": rollback, "direction": direction, "patch": patch, "contract": contract, "evidence": evidence, "authority": AUTHORITY}


def _proposal(conn: sqlite3.Connection, proposal_id: int) -> sqlite3.Row:
    row = conn.execute("select * from studio_evolution_proposals where id=?", (int(proposal_id),)).fetchone()
    if row is None:
        raise ValueError("unknown studio evolution proposal")
    return row


def record_shadow_result(conn: sqlite3.Connection, policy: Mapping[str, Any], proposal_id: int, shadow_metrics: Mapping[str, Any]) -> dict[str, Any]:
    row = _proposal(conn, proposal_id)
    metric = str(row["metric_name"])
    if metric not in shadow_metrics:
        raise ValueError("shadow evaluation missing objective metric")
    observed = _finite(shadow_metrics[metric], metric)
    baseline = float(row["baseline_value"])
    direction = str(row["direction"])
    improved = observed > baseline if direction == "higher" else observed < baseline
    verdict = "PASS" if improved else "REJECT"
    payload = {"mode":"shadow", "metric_name":metric, "baseline":baseline, "observed":observed, "verdict":verdict, "direct_integration_authority":False}
    conn.execute("update studio_evolution_proposals set shadow_json=?,status=? where id=?", (json.dumps(payload,sort_keys=True), "SHADOW_PASS" if improved else "SHADOW_REJECT", int(proposal_id)))
    decision_id = _decision(conn, int(proposal_id), "SHADOW", verdict, payload)
    _brain_event(conn, "EVIDENCE", "Studio evolution shadow evaluation", f"proposal={proposal_id} verdict={verdict} metric={metric}", {"proposal_id":proposal_id,"decision_id":decision_id,"shadow":payload})
    conn.commit()
    return payload


def _attestation_pass(policy: Mapping[str, Any], raw: str) -> bool:
    fields: dict[str,str] = {}
    for part in str(raw or "").split(";"):
        key, _, value = part.partition("=")
        if key.strip() and value.strip():
            fields[key.strip().casefold()] = value.strip()
    reviewer = fields.get("reviewer", "")
    forbidden = {str(x).casefold() for x in policy.get("forbidden_attestation_reviewers", [])}
    return bool(reviewer) and reviewer.casefold() not in forbidden and fields.get("verdict", "").upper() == "PASS"


def _active_policy(conn: sqlite3.Connection) -> tuple[int, dict[str, Any]]:
    state = conn.execute("select active_version from studio_evolution_state where singleton=1").fetchone()
    if state is None:
        return 0, _empty_policy_state()
    version = int(state[0])
    row = conn.execute("select policy_json from studio_policy_versions where version=?", (version,)).fetchone()
    if row is None:
        if version == 0:
            return 0, _empty_policy_state()
        raise ValueError(f"missing active policy version: {version}")
    return version, json.loads(row[0])


def promote_policy(conn: sqlite3.Connection, policy: Mapping[str, Any], proposal_id: int, independent_attestation: str) -> dict[str, Any]:
    ensure_schema(conn)
    row = _proposal(conn, proposal_id)
    if str(row["status"]) != "SHADOW_PASS":
        raise ValueError("shadow evaluation PASS is required before policy promotion")
    if not _attestation_pass(policy, independent_attestation):
        raise ValueError("independent verification PASS attestation is required")
    patch = validate_patch(policy, json.loads(row["patch_json"]))
    current_version, current_policy = _active_policy(conn)
    current_policy = validate_policy_state(policy, current_policy)
    if conn.execute("select 1 from studio_policy_versions where version=0").fetchone() is None:
        conn.execute("insert into studio_policy_versions(version,created_at,source_proposal_id,policy_json,evidence_json,independent_attestation,status) values(0,?,?,?,?,?,?)", (_now(), None, json.dumps(_empty_policy_state(),sort_keys=True), json.dumps({"kind":"baseline"}), "SYSTEM_BASELINE", "VERIFIED"))
    merged = json.loads(json.dumps(current_policy))
    merged["departments"].setdefault(str(row["department"]), {}).update(patch)
    merged = validate_policy_state(policy, merged)
    version = int(conn.execute("select coalesce(max(version),0)+1 from studio_policy_versions").fetchone()[0])
    conn.execute("update studio_policy_versions set status='VERIFIED' where status='ACTIVE_VERIFIED'")
    evidence = {"proposal_id":int(proposal_id),"shadow":json.loads(row["shadow_json"]),"contract":json.loads(row["contract_json"]),"source_evidence":json.loads(row["evidence_json"])}
    conn.execute("insert into studio_policy_versions(version,created_at,source_proposal_id,policy_json,evidence_json,independent_attestation,status) values(?,?,?,?,?,?,?)", (version,_now(),int(proposal_id),json.dumps(merged,sort_keys=True),json.dumps(evidence,sort_keys=True),str(independent_attestation),"ACTIVE_VERIFIED"))
    conn.execute("insert into studio_evolution_state(singleton,active_version,last_decision_id,last_rollback_from,last_rollback_at) values(1,?,null,null,null) on conflict(singleton) do update set active_version=excluded.active_version", (version,))
    conn.execute("update studio_evolution_proposals set status='PROMOTED_VERIFIED' where id=?", (int(proposal_id),))
    decision_id = _decision(conn, int(proposal_id), "PROMOTION", "KEEP", {"version":version,"patch":patch,"attestation":independent_attestation,"direct_integration_authority":False})
    _brain_event(conn, "DECISION", "Verified studio policy promoted", f"proposal={proposal_id} policy_version={version}; no direct integration authority", {"proposal_id":proposal_id,"version":version,"decision_id":decision_id,"authority":AUTHORITY})
    conn.commit()
    return {"version":version,"status":"ACTIVE_VERIFIED","direct_integration_authority":False,"authority":AUTHORITY}


def rollback_if_regressed(conn: sqlite3.Connection, policy: Mapping[str, Any], metrics: Mapping[str, Any]) -> dict[str, Any]:
    ensure_schema(conn)
    state = conn.execute("select active_version from studio_evolution_state where singleton=1").fetchone()
    if state is None or int(state[0]) == 0:
        return {"rolled_back":False,"reason":"no promoted policy"}
    active = int(state[0])
    row = conn.execute("select source_proposal_id from studio_policy_versions where version=?", (active,)).fetchone()
    proposal = _proposal(conn, int(row[0])) if row and row[0] is not None else None
    guard = policy.get("rollback", {})
    required = {"verification_pass_rate", "rework_rate", "regressions"}
    if proposal is not None:
        required.add(str(proposal["metric_name"]))
    missing = sorted(key for key in required if key not in metrics)
    if missing:
        raise ValueError("missing rollback metric: " + ",".join(missing))
    verification = _finite(metrics["verification_pass_rate"], "verification_pass_rate")
    rework = _finite(metrics["rework_rate"], "rework_rate")
    regressions = _finite(metrics["regressions"], "regressions")
    breached = verification < float(guard.get("verification_pass_rate_min", 0.0)) or rework > float(guard.get("rework_rate_max", 1.0)) or regressions > float(guard.get("regressions_max", 1e9))
    if proposal is not None and proposal["metric_name"] in metrics:
        objective = _finite(metrics[proposal["metric_name"]], str(proposal["metric_name"]))
        threshold = float(proposal["rollback_threshold"])
        breached = breached or (objective < threshold if proposal["direction"] == "higher" else objective > threshold)
    if not breached:
        return {"rolled_back":False,"active_version":active}
    prior = conn.execute("select version from studio_policy_versions where version<? and status in ('VERIFIED','ACTIVE_VERIFIED') order by version desc limit 1", (active,)).fetchone()
    previous = int(prior[0]) if prior else 0
    conn.execute("update studio_policy_versions set status='ROLLED_BACK' where version=?", (active,))
    conn.execute("update studio_policy_versions set status='ACTIVE_VERIFIED' where version=?", (previous,))
    stamp = _now()
    conn.execute("update studio_evolution_state set active_version=?,last_rollback_from=?,last_rollback_at=? where singleton=1", (previous,active,stamp))
    decision_id = _decision(conn, int(proposal["id"]) if proposal is not None else None, "ROLLBACK", "ROLLBACK", {"from_version":active,"active_version":previous,"reason":"objective regression threshold breached"})
    _brain_event(conn, "DECISION", "Studio policy automatic rollback", f"from={active} active={previous}", {"from_version":active,"active_version":previous,"decision_id":decision_id})
    conn.commit()
    return {"rolled_back":True,"from_version":active,"active_version":previous,"reason":"objective regression threshold breached"}


def restart_state(conn: sqlite3.Connection) -> dict[str, Any]:
    ensure_schema(conn)
    state = conn.execute("select * from studio_evolution_state where singleton=1").fetchone()
    versions = [dict(r) for r in conn.execute("select version,created_at,source_proposal_id,status from studio_policy_versions order by version")]
    recent = [dict(r) for r in conn.execute("select id,created_at,proposal_id,phase,verdict,details_json from studio_evolution_decisions order by id desc limit 20")]
    return {"active_version": int(state["active_version"]) if state else 0, "last_rollback_from": state["last_rollback_from"] if state else None, "last_rollback_at": state["last_rollback_at"] if state else None, "versions":versions, "decisions":recent, "authority":AUTHORITY}


def closed_loop_canary(conn: sqlite3.Connection, policy: Mapping[str, Any], outcome: Mapping[str, Any], *, shadow_multiplier: float, independent_attestation: str) -> dict[str, Any]:
    proposal = propose_improvement(conn, policy, outcome)
    baseline = float(proposal["baseline_value"])
    factor = _finite(shadow_multiplier, "shadow_multiplier")
    if factor <= 0:
        raise ValueError("shadow_multiplier must be positive")
    observed = baseline / factor if proposal["direction"] == "higher" and factor < 1.0 else baseline * factor
    if proposal["direction"] == "lower" and factor > 1.0:
        observed = baseline / factor
    shadow = record_shadow_result(conn, policy, proposal["proposal_id"], {proposal["contract"]["metric_name"]: observed})
    if shadow["verdict"] != "PASS":
        raise ValueError("closed-loop canary shadow evaluation did not improve objective")
    promoted = promote_policy(conn, policy, proposal["proposal_id"], independent_attestation)
    return {"status":"CANARY_PASS","proposal_id":proposal["proposal_id"],"policy_version":promoted["version"],"direct_integration_authority":False,"authority":AUTHORITY}
