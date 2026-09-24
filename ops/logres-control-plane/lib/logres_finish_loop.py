from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from typing import Any


STATES = {
    "EXECUTE",
    "WAIT_ACTIVE",
    "BLOCKED_DEP",
    "BLOCKED_EVIDENCE",
    "BLOCKED_EXTERNAL",
    "CERTIFY",
    "COMPLETE",
}
BLOCKED_STATES = {"BLOCKED_DEP", "BLOCKED_EVIDENCE", "BLOCKED_EXTERNAL"}
CONTRACT_TO_FINISH = {
    "RUNNABLE": "EXECUTE",
    "WAIT_ACTIVE": "WAIT_ACTIVE",
    "BLOCKED_DEP": "BLOCKED_DEP",
    "BLOCKED_EVIDENCE": "BLOCKED_EVIDENCE",
    "BLOCKED_EXTERNAL": "BLOCKED_EXTERNAL",
}


@dataclass(frozen=True)
class FinishDecision:
    milestone_id: str
    state: str
    progress_percent: float
    integration_sha: str
    contract_fingerprint: str
    certificate_valid: bool
    remaining: tuple[str, ...]
    active: tuple[str, ...]
    blockers: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "milestone_id": self.milestone_id,
            "state": self.state,
            "progress_percent": self.progress_percent,
            "integration_sha": self.integration_sha,
            "contract_fingerprint": self.contract_fingerprint,
            "certificate_valid": self.certificate_valid,
            "remaining": list(self.remaining),
            "active": list(self.active),
            "blockers": [dict(item) for item in self.blockers],
        }


def active_milestone_id(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        """select id
             from milestones
            where status not in ('DONE','RESOLVED','SUPERSEDED','CANCELLED')
            order by sort_order,id
            limit 1"""
    ).fetchone()
    if row:
        return str(row[0])
    row = conn.execute(
        """select id
             from milestones
            where status in ('DONE','RESOLVED')
            order by sort_order desc,id desc
            limit 1"""
    ).fetchone()
    if row:
        return str(row[0])
    raise ValueError("no active or completed milestone")


def _state(contract_state: str, certificate_valid: bool) -> str:
    if contract_state == "COMPLETE":
        return "COMPLETE" if certificate_valid else "CERTIFY"
    state = CONTRACT_TO_FINISH.get(str(contract_state))
    if state not in STATES:
        raise ValueError(f"unsupported contract state: {contract_state!r}")
    return state


def decide(contract: dict[str, Any], *, certificate_valid: bool) -> FinishDecision:
    criteria = list(contract.get("criteria") or [])
    remaining = tuple(
        str(item.get("criterion_id"))
        for item in criteria
        if not bool(item.get("passed"))
    )
    active = tuple(
        str(item.get("task_id") or item.get("criterion_id"))
        for item in criteria
        if not bool(item.get("passed")) and item.get("status") == "ACTIVE"
    )
    blockers = tuple(
        {
            "criterion_id": str(item.get("criterion_id") or ""),
            "status": str(item.get("status") or "UNKNOWN"),
            "reason": str(item.get("reason") or ""),
            "task_id": (
                str(item.get("task_id"))
                if item.get("task_id") is not None
                else None
            ),
        }
        for item in criteria
        if not bool(item.get("passed"))
        and item.get("status")
        in {"BLOCKED_DEP", "BLOCKED_EVIDENCE", "BLOCKED_EXTERNAL"}
    )
    return FinishDecision(
        milestone_id=str(contract["milestone_id"]),
        state=_state(str(contract["state"]), certificate_valid),
        progress_percent=float(contract.get("progress_percent") or 0.0),
        integration_sha=str(contract.get("integration_sha") or ""),
        contract_fingerprint=str(contract.get("contract_fingerprint") or ""),
        certificate_valid=bool(certificate_valid),
        remaining=remaining,
        active=active,
        blockers=blockers,
    )


def decision_fingerprint(decision: FinishDecision) -> str:
    payload: dict[str, Any] = {
        "milestone_id": decision.milestone_id,
        "state": decision.state,
        "contract_fingerprint": decision.contract_fingerprint,
        "remaining": decision.remaining,
        "active": decision.active,
        "blockers": decision.blockers,
    }
    if decision.state in {"CERTIFY", "COMPLETE"}:
        payload["integration_sha"] = decision.integration_sha
        payload["certificate_valid"] = decision.certificate_valid
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def event_payload(decision: FinishDecision) -> dict[str, str] | None:
    if decision.state not in BLOCKED_STATES:
        return None
    reasons = "; ".join(
        f"{item['criterion_id']}={item['status']}: {item['reason']}"
        for item in decision.blockers
    ) or "contract has unresolved blockers"
    return {
        "subject": f"Finish loop {decision.state}: {decision.milestone_id}",
        "body": (
            f"progress={decision.progress_percent:.2f}% "
            f"remaining={','.join(decision.remaining) or '-'}; {reasons}"
        ),
        "dedupe": (
            f"finish-loop:{decision.milestone_id}:"
            f"{decision_fingerprint(decision)}"
        ),
    }


def status_payload(decision: FinishDecision) -> dict[str, Any]:
    return {
        **decision.to_dict(),
        "working": list(decision.active),
        "why_blocked": [
            f"{item['criterion_id']}: {item['reason']}"
            for item in decision.blockers
        ],
        "certifiably_complete": (
            decision.state == "COMPLETE" and decision.certificate_valid
        ),
    }


def action_for(decision: FinishDecision) -> str | None:
    if decision.state == "EXECUTE":
        return "goal-executor"
    if decision.state == "CERTIFY":
        return "goal-certifier"
    return None


def apply_decision(
    decision: FinishDecision,
    runner,
) -> Any:
    action = action_for(decision)
    if action is None:
        return None
    return runner(action, decision.milestone_id)
