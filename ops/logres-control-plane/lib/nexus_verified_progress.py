from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Iterable

CAPABILITY_BY_WORK_TYPE = {
    'implementation': 'code-change', 'builder': 'code-change',
    'research': 'historical-evidence', 'evidence': 'historical-evidence',
    'analysis': 'diagnosis', 'diagnostic': 'diagnosis',
    'verification': 'exact-sha-verification', 'regression': 'exact-sha-verification',
    'integration': 'canonical-integration', 'android': 'physical-device-qa',
    'device-qa': 'physical-device-qa', 'privileged': 'privileged-host-operation',
    'architecture': 'architecture-reasoning', 'reasoning': 'architecture-reasoning',
}

@dataclass(frozen=True)
class DecisionInput:
    task_id: str
    priority: int
    work_type: str
    unlock_value: float
    success_likelihood: float
    verification_confidence: float
    expected_minutes: float
    resource_cost: float = 1.0
    claimed_state: str = 'READY'
    observed_state: str = 'READY'

@dataclass(frozen=True)
class DecisionReceipt:
    task_id: str
    priority: int
    expected_verified_progress: float
    capability: str
    eligible: bool
    reconciliation: str
    rationale: tuple[str, ...]
    def to_dict(self) -> dict:
        value = asdict(self); value['rationale'] = list(self.rationale); return value

def capability_for(work_type: str) -> str:
    return CAPABILITY_BY_WORK_TYPE.get(str(work_type).lower(), 'general-execution')

def reconcile(claimed: str, observed: str) -> tuple[bool, str]:
    if claimed == observed:
        return True, 'claimed-state-matches-observed-state'
    return False, f'state-mismatch:{claimed}->{observed}'

def expected_verified_progress(item: DecisionInput) -> float:
    cost = max(0.01, float(item.resource_cost)) * max(1.0, float(item.expected_minutes))
    return (max(0.0, float(item.unlock_value)) * max(0.0, min(1.0, float(item.success_likelihood))) * max(0.0, min(1.0, float(item.verification_confidence)))) / cost

def decide(items: Iterable[DecisionInput]) -> list[DecisionReceipt]:
    receipts = []
    for item in items:
        reconciled, reconciliation = reconcile(item.claimed_state, item.observed_state)
        evp = expected_verified_progress(item) if reconciled else 0.0
        capability = capability_for(item.work_type)
        receipts.append(DecisionReceipt(item.task_id, item.priority, round(evp, 8), capability, reconciled, reconciliation, (
            f'P{item.priority}', f'unlock={item.unlock_value:g}', f'success={item.success_likelihood:.2f}',
            f'verification={item.verification_confidence:.2f}', f'expected={item.expected_minutes:g}m',
            f'resource_cost={item.resource_cost:g}', f'capability={capability}')))
    return sorted(receipts, key=lambda r: (r.priority, not r.eligible, -r.expected_verified_progress, r.task_id))
