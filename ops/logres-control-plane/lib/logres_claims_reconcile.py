from __future__ import annotations


RELEASABLE_STATES = {
    "DONE",
    "READY",
    "RESOLVED",
    "INTEGRATED",
    "SUPERSEDED",
    "CANCELLED",
}


def claim_releasable(
    status: str | None,
    *,
    has_active_lease: bool,
) -> bool:
    if has_active_lease:
        return False
    normalized = str(status or "").strip().upper()
    if not normalized or normalized == "UNKNOWN":
        return False
    return normalized in RELEASABLE_STATES or normalized.startswith("BLOCKED")
