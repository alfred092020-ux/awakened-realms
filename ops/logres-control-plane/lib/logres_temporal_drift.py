from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

MATERIAL_KINDS = (
    "ENTITY_ADDED",
    "ENTITY_REMOVED",
    "PREDICATE_CHANGED",
    "AUTHORITY_CHANGED",
    "UNCERTAINTY_CHANGED",
    "ENDPOINT_FACT_CHANGED",
)

def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def _entity_index(lattice: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = lattice.get("entities", [])
    if not isinstance(rows, list):
        raise ValueError("temporal lattice entities must be a list")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("temporal lattice entity must be an object")
        entity_id = row.get("entity_id")
        if not isinstance(entity_id, str) or not entity_id:
            raise ValueError("temporal lattice entity_id must be non-empty")
        if entity_id in result:
            raise ValueError(f"duplicate temporal entity_id: {entity_id}")
        result[entity_id] = row
    return result

def _claim_index(protected_claims: Iterable[dict[str, Any]] | None) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for claim in protected_claims or ():
        entity_id = claim.get("entity_id")
        if not isinstance(entity_id, str) or not entity_id:
            raise ValueError("protected claim entity_id must be non-empty")
        result.setdefault(entity_id, []).append({
            "claim_id": claim.get("claim_id"),
            "surface": claim.get("surface"),
            "authority": claim.get("authority"),
        })
    for rows in result.values():
        rows.sort(key=lambda row: (str(row.get("surface") or ""), str(row.get("claim_id") or "")))
    return result

def _drift(entity_id: str, kind: str, before: Any, after: Any, claims: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    impacted = claims.get(entity_id, [])
    return {
        "entity_id": entity_id,
        "kind": kind,
        "before": before,
        "after": after,
        "protected_claim_impacts": impacted,
        "requires_explicit_review": bool(impacted),
    }

def compare_temporal_lattices(
    previous: dict[str, Any],
    current: dict[str, Any],
    *,
    protected_claims: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    old = _entity_index(previous)
    new = _entity_index(current)
    claims = _claim_index(protected_claims)
    drift_rows: list[dict[str, Any]] = []

    for entity_id in sorted(set(old) | set(new)):
        before = old.get(entity_id)
        after = new.get(entity_id)
        if before is None:
            drift_rows.append(_drift(entity_id, "ENTITY_ADDED", None, after, claims))
            continue
        if after is None:
            drift_rows.append(_drift(entity_id, "ENTITY_REMOVED", before, None, claims))
            continue

        if before.get("relation") != after.get("relation"):
            drift_rows.append(_drift(entity_id, "PREDICATE_CHANGED", before.get("relation"), after.get("relation"), claims))
        if before.get("source_lineage_grade") != after.get("source_lineage_grade"):
            drift_rows.append(_drift(entity_id, "AUTHORITY_CHANGED", before.get("source_lineage_grade"), after.get("source_lineage_grade"), claims))
        if _canonical(before.get("temporal_uncertainty")) != _canonical(after.get("temporal_uncertainty")):
            drift_rows.append(_drift(entity_id, "UNCERTAINTY_CHANGED", before.get("temporal_uncertainty"), after.get("temporal_uncertainty"), claims))

        before_endpoints = {"global": before.get("global"), "current_jp": before.get("current_jp")}
        after_endpoints = {"global": after.get("global"), "current_jp": after.get("current_jp")}
        if _canonical(before_endpoints) != _canonical(after_endpoints):
            drift_rows.append(_drift(entity_id, "ENDPOINT_FACT_CHANGED", before_endpoints, after_endpoints, claims))

    drift_rows.sort(key=lambda row: (row["entity_id"], row["kind"], _canonical(row["before"]), _canonical(row["after"])))
    material = [row for row in drift_rows if row["kind"] in MATERIAL_KINDS]
    protected_impacts = [{
        "entity_id": row["entity_id"],
        "kind": row["kind"],
        "claims": row["protected_claim_impacts"],
    } for row in material if row["protected_claim_impacts"]]

    fingerprint_material = {
        "previous_lattice_id": previous.get("lattice_id"),
        "current_lattice_id": current.get("lattice_id"),
        "drift": [{
            "entity_id": row["entity_id"],
            "kind": row["kind"],
            "before": row["before"],
            "after": row["after"],
        } for row in material],
    }
    fingerprint = hashlib.sha256(_canonical(fingerprint_material).encode("utf-8")).hexdigest()

    return {
        "schema": "logres-temporal-drift-v1",
        "previous_lattice_id": previous.get("lattice_id"),
        "current_lattice_id": current.get("lattice_id"),
        "drift_fingerprint": fingerprint,
        "dedupe_key": f"temporal-drift:{fingerprint}",
        "changed": bool(material),
        "requires_explicit_review": bool(material),
        "protected_claim_impacts": protected_impacts,
        "counts": {
            "material_changes": len(material),
            "protected_claim_impacts": len(protected_impacts),
        },
        "changes": material,
        "automatic_actions": {
            "promote_confidence": False,
            "merge": False,
            "deploy": False,
            "modify_main": False,
        },
        "policy": {
            "review": "Any temporal predicate drift requires explicit review before downstream historical or implementation claims are updated.",
            "protected_claims": "Implementation and Truth-Kernel claims bound to a changed entity are surfaced as explicit invalidation candidates.",
            "dedupe": "The fingerprint is deterministic over lattice IDs and sorted material drift, preventing duplicate regression loops.",
        },
    }

def should_open_review(report: dict[str, Any]) -> bool:
    return bool(report.get("requires_explicit_review"))

def drift_fingerprint(report: dict[str, Any]) -> str:
    value = report.get("drift_fingerprint")
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError("invalid temporal drift fingerprint")
    return value
