"""Bounded autonomy completion canary."""

AUTONOMY_CANARY_VERSION = 3


def canary_status() -> str:
    """Return the deterministic readiness status for the autonomy canary."""
    return "ready"
