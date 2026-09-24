from __future__ import annotations
import copy

SCENARIOS={
 "supervisor_loss":{"inject":{"supervisor_alive":False},"invariants":["restartable_supervisor","no_unsafe_merge"]},
 "sqlite_lock":{"inject":{"control_db_locked":True},"invariants":["bounded_retry","no_state_corruption"]},
 "remote_outage":{"inject":{"remote_reachable":False},"invariants":["local_verification_fallback","no_gate_weakening"]},
 "expired_lease":{"inject":{"lease_expired":True},"invariants":["lease_recovery","no_double_owner"]},
 "duplicate_event":{"inject":{"duplicate_event":True},"invariants":["dedupe_preserves_single_effect"]},
 "stale_claim":{"inject":{"claim_without_lease":True},"invariants":["claim_reconcile","no_live_claim_loss"]},
 "preflight_crash":{"inject":{"preflight_process_alive":False,"preflight_state":"RUNNING"},"invariants":["stale_preflight_recovery","no_auto_apply"]},
 "network_loss":{"inject":{"network_reachable":False},"invariants":["no_unsafe_merge","retry_or_pause"]},
 "malformed_research":{"inject":{"research_artifact_valid":False},"invariants":["schema_reject","no_evidence_promotion"]},
 "conflicting_branch":{"inject":{"branch_conflict":True},"invariants":["quarantine_or_block","no_auto_merge"]},
}

DEFAULT_PROTECTIONS={
 "restartable_supervisor":True,"no_unsafe_merge":True,"bounded_retry":True,"no_state_corruption":True,
 "local_verification_fallback":True,"no_gate_weakening":True,"lease_recovery":True,"no_double_owner":True,
 "dedupe_preserves_single_effect":True,"claim_reconcile":True,"no_live_claim_loss":True,
 "stale_preflight_recovery":True,"no_auto_apply":True,"retry_or_pause":True,"schema_reject":True,
 "no_evidence_promotion":True,"quarantine_or_block":True,"no_auto_merge":True,
}

def list_scenarios():
    return sorted(SCENARIOS)

def simulate(name,state=None,protections=None):
    if name not in SCENARIOS:raise ValueError("unknown scenario")
    original=copy.deepcopy(state or {})
    injected=copy.deepcopy(original);injected.update(SCENARIOS[name]["inject"])
    p=dict(DEFAULT_PROTECTIONS);p.update(protections or {})
    checks=[{"invariant":i,"pass":bool(p.get(i,False))} for i in SCENARIOS[name]["invariants"]]
    return {"scenario":name,"sandbox_only":True,"original_state":original,"injected_state":injected,
            "checks":checks,"verdict":"PASS" if all(c["pass"] for c in checks) else "FAIL"}

def run_all(state=None,protections=None):
    return [simulate(name,state,protections) for name in list_scenarios()]
