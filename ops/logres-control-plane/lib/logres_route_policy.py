from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class RouteDecision:
    route: str
    reason: str
    child_task_id: str | None = None


def implementation_allowed(
    canonical_confidence: str,
    evidence_policy: str,
    provenance: str,
) -> bool:
    normalized_provenance = provenance.lower()
    if "current_jp" in normalized_provenance or "later_jp" in normalized_provenance:
        return False
    if canonical_confidence == "CONFIRMED ORIGINAL":
        return True
    if canonical_confidence == "SUPPORTED INFERENCE":
        return "allow-supported-inference" in evidence_policy.lower()
    return False


def classify_evidence_event(event, task, metadata, config) -> RouteDecision:
    meta_raw = event.get("meta_json") if hasattr(event, "get") else None
    try:
        meta = json.loads(meta_raw or "{}")
    except (TypeError, json.JSONDecodeError):
        meta = {}

    kind = str(meta.get("kind", "")).lower()
    artifact_bytes = int(meta.get("artifact_bytes", 0) or 0)
    subject = str(event.get("subject") or "").lower()
    artifact_path = str(event.get("artifact_path") or "").lower()

    control_plane_markers = (
        "control-plane",
        "control plane",
        "autoflow rollout",
        "autoflow-rollout",
        "finder-autoflow-rollout",
    )
    if any(
        marker in subject or marker in artifact_path
        for marker in control_plane_markers
    ):
        return RouteDecision(
            route="SKIP_DETERMINISTIC",
            reason="control-plane rollout evidence is not Logres gameplay/history evidence",
        )

    if kind == "symbol_lookup" or (artifact_bytes and artifact_bytes <= 4096):
        return RouteDecision(
            route="SKIP_DETERMINISTIC",
            reason="small deterministic artifact",
        )

    if (
        event.get("event_type") in {"EVIDENCE", "DISCOVERY"}
        and event.get("artifact_path")
        and event.get("artifact_sha256")
    ):
        return RouteDecision(route="AI", reason="substantive evidence artifact")

    return RouteDecision(route="SKIP_DETERMINISTIC", reason="not AI-eligible")
