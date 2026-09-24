from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class TemporalBackfillError(ValueError):
    """Raised when a query would invent facts inside an unobserved interval."""


VERSION_ALIASES = {
    "global": "GLOBAL_3_0_24_2017_05_25",
    "global-3.0.24": "GLOBAL_3_0_24_2017_05_25",
    "2017-05-25": "GLOBAL_3_0_24_2017_05_25",
    "jp": "CURRENT_JP_2026_09_24",
    "current-jp": "CURRENT_JP_2026_09_24",
    "2026-09-24": "CURRENT_JP_2026_09_24",
}


def load_lattice(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("temporal lattice must be a JSON object")
    if payload.get("provenance") != (
        "HYPERDIMENSION_VERSION_SCOPED_TEMPORAL_EVIDENCE_LATTICE"
    ):
        raise ValueError("input is not a HYPERDIMENSION temporal lattice")
    if not isinstance(payload.get("entities"), list):
        raise ValueError("temporal lattice entities must be a list")
    return payload


def resolve_version(lattice: dict[str, Any], version: str | None) -> str | None:
    if version is None:
        return None
    normalized = VERSION_ALIASES.get(version.lower(), version)
    valid = {row["id"] for row in lattice.get("snapshots", [])}
    if normalized not in valid:
        raise ValueError(
            f"unknown temporal snapshot {version!r}; valid={sorted(valid)}"
        )
    return normalized


def _fact_for_version(entity: dict[str, Any], snapshot_id: str) -> dict[str, Any]:
    if snapshot_id.startswith("GLOBAL_"):
        return entity.get("global") or {}
    if snapshot_id.startswith("CURRENT_JP_"):
        return entity.get("current_jp") or {}
    raise ValueError(f"unsupported temporal snapshot: {snapshot_id}")


def _source_bundle(lattice: dict[str, Any]) -> dict[str, Any]:
    return {
        "lattice_id": lattice.get("lattice_id"),
        "sealed_evidence_merkle_root": lattice.get(
            "sealed_evidence_merkle_root"
        ),
        "sources": lattice.get("sources", {}),
    }


def query_entities(
    lattice: dict[str, Any],
    *,
    entity: str | None = None,
    version: str | None = None,
    relation: str | None = None,
    evidence_grade: str | None = None,
    kind: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("limit must be >= 1")
    snapshot_id = resolve_version(lattice, version)
    entity_term = entity.casefold() if entity else None

    rows = []
    for row in lattice["entities"]:
        if entity_term and entity_term not in (
            f"{row.get('entity_id', '')} {row.get('name', '')}".casefold()
        ):
            continue
        if relation and row.get("relation") != relation:
            continue
        if evidence_grade and row.get("source_lineage_grade") != evidence_grade:
            continue
        if kind and row.get("kind") != kind:
            continue

        result = {
            "entity_id": row.get("entity_id"),
            "kind": row.get("kind"),
            "name": row.get("name"),
            "relation": row.get("relation"),
            "source_lineage_grade": row.get("source_lineage_grade"),
            "temporal_uncertainty": row.get("temporal_uncertainty"),
        }
        if snapshot_id is None:
            result["facts"] = {
                "global": row.get("global"),
                "current_jp": row.get("current_jp"),
            }
        else:
            result["snapshot"] = snapshot_id
            result["fact"] = _fact_for_version(row, snapshot_id)
        rows.append(result)
        if len(rows) >= limit:
            break

    return {
        **_source_bundle(lattice),
        "query": {
            "entity": entity,
            "version": snapshot_id,
            "relation": relation,
            "evidence_grade": evidence_grade,
            "kind": kind,
            "limit": limit,
        },
        "count": len(rows),
        "results": rows,
    }


def get_entity(lattice: dict[str, Any], entity_id: str) -> dict[str, Any]:
    for row in lattice["entities"]:
        if row.get("entity_id") == entity_id:
            return {
                **_source_bundle(lattice),
                "entity": row,
            }
    raise KeyError(entity_id)


def fact_at_date(
    lattice: dict[str, Any],
    entity_id: str,
    date: str,
) -> dict[str, Any]:
    snapshot = None
    for row in lattice.get("snapshots", []):
        if row.get("date") == date:
            snapshot = row
            break
    if snapshot is None:
        dates = sorted(
            row.get("date")
            for row in lattice.get("snapshots", [])
            if row.get("date")
        )
        raise TemporalBackfillError(
            "date is inside an unobserved temporal interval; "
            f"observed snapshots={dates}. Refusing to backfill {date} "
            "from current-JP or any other endpoint."
        )

    entity_payload = get_entity(lattice, entity_id)["entity"]
    fact = _fact_for_version(entity_payload, snapshot["id"])
    return {
        **_source_bundle(lattice),
        "entity_id": entity_id,
        "snapshot": snapshot,
        "fact": fact,
        "relation": entity_payload.get("relation"),
        "source_lineage_grade": entity_payload.get("source_lineage_grade"),
        "temporal_uncertainty": entity_payload.get("temporal_uncertainty"),
    }


def lattice_stats(lattice: dict[str, Any]) -> dict[str, Any]:
    return {
        **_source_bundle(lattice),
        "counts": lattice.get("counts", {}),
        "snapshots": lattice.get("snapshots", []),
        "temporal_policy": lattice.get("temporal_policy", {}),
    }
