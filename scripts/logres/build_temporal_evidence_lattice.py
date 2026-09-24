#!/usr/bin/env python3
"""Build a version-scoped temporal evidence lattice for Logres reconstruction.

The lattice records endpoint facts for Global 3.0.24 (2017-05-25) and the
current-JP capture (2026-09-24). It never invents the exact intermediate change
point when no dated intermediate evidence exists.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

GLOBAL_SNAPSHOT = {
    "id": "GLOBAL_3_0_24_2017_05_25",
    "version": "3.0.24",
    "date": "2017-05-25",
    "scope": "Global client",
    "authority": "HISTORICAL_TARGET",
}
JP_SNAPSHOT = {
    "id": "CURRENT_JP_2026_09_24",
    "version": "current-jp-capture",
    "date": "2026-09-24",
    "scope": "Current JP client/public patch",
    "authority": "LINEAGE_REFERENCE_ONLY",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def interval(reason: str) -> dict[str, Any]:
    return {
        "after": GLOBAL_SNAPSHOT["date"],
        "on_or_before": JP_SNAPSHOT["date"],
        "exact_change_time_known": False,
        "reason": reason,
    }


def endpoint_policy(relation: str) -> dict[str, Any]:
    return {
        "relation": relation,
        "continuous_history_proven": False,
        "statement": (
            "The relation is proven only between observed endpoints; no claim "
            "is made that the property remained unchanged throughout the "
            "unobserved interval."
        ),
    }


def protocol_entities(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for message in payload["messages"]:
        lineage = message["lineage"]
        grade = lineage["grade"]
        global_args = [
            field["normalized_type"]
            for field in message.get("fields", [])
        ]
        global_state = {
            "snapshot": GLOBAL_SNAPSHOT["id"],
            "present": True,
            "opcode_hex": message["opcode_hex"],
            "opcode_u32": message["opcode_u32"],
            "normalized_args": global_args,
            "schema_evidence": message["top_level_schema_evidence"],
        }
        jp_present = bool(lineage.get("jp_present"))
        jp_state = {
            "snapshot": JP_SNAPSHOT["id"],
            "present": jp_present,
            "opcode_hex": lineage.get("jp_opcode_hex"),
            "opcode_u32": lineage.get("jp_opcode_u32"),
            "normalized_args": lineage.get("normalized_jp_args", []),
        }

        if grade == "GLOBAL_JP_IDENTICAL_TOP_LEVEL_SCHEMA":
            relation = "ENDPOINTS_IDENTICAL_OPCODE_AND_SCHEMA"
            uncertainty = endpoint_policy(relation)
        elif grade == "JP_LINEAGE_OPCODE_STABLE_SCHEMA_CHANGED":
            relation = "ENDPOINTS_OPCODE_STABLE_SCHEMA_CHANGED"
            uncertainty = {
                **endpoint_policy(relation),
                "change_interval": interval(
                    "Schema differs between Global target and current JP while opcode is stable."
                ),
            }
        elif grade == "JP_LINEAGE_OPCODE_STABLE_GLOBAL_SCHEMA_UNRESOLVED":
            relation = "ENDPOINTS_OPCODE_STABLE_JP_COMPARISON_INCOMPLETE"
            uncertainty = {
                **endpoint_policy(relation),
                "comparison_gap": (
                    "JP endpoint exists with stable opcode, but normalized "
                    "top-level comparison is unresolved."
                ),
            }
        elif grade == "GLOBAL_ONLY_OR_REMOVED_IN_CURRENT_JP":
            relation = "GLOBAL_PRESENT_CURRENT_JP_ABSENT_OR_RENAMED"
            uncertainty = {
                **endpoint_policy(relation),
                "change_interval": interval(
                    "Global procedure has no current-JP name match; removal versus rename is unresolved."
                ),
            }
        else:
            relation = f"UNMAPPED_PROTOCOL_LINEAGE:{grade}"
            uncertainty = endpoint_policy(relation)

        rows.append(
            {
                "entity_id": f"protocol:{message['name']}",
                "kind": "protocol_message",
                "name": message["name"],
                "global": global_state,
                "current_jp": jp_state,
                "relation": relation,
                "source_lineage_grade": grade,
                "temporal_uncertainty": uncertainty,
            }
        )
    return rows


def resource_entities(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    source_sets = [
        ("global_bootstrap_lineage", payload["global_bootstrap_lineage"]),
        ("recovered_global_cache_lineage", payload["recovered_global_cache_lineage"]),
    ]
    for source_name, entries in source_sets:
        for entry in entries:
            classification = entry["classification"]
            matches = entry.get("jp_exact_matches", [])
            same_path = entry.get("jp_same_path")
            if classification == "EXACT_BYTES_SAME_PATH":
                relation = "ENDPOINTS_BYTES_IDENTICAL_SAME_PATH"
                jp_paths = [entry["path"]]
                uncertainty = endpoint_policy(relation)
            elif classification == "EXACT_BYTES_RENAMED_OR_MOVED":
                relation = "ENDPOINTS_BYTES_IDENTICAL_PATH_CHANGED"
                jp_paths = sorted({row["path"] for row in matches})
                uncertainty = {
                    **endpoint_policy(relation),
                    "change_interval": interval(
                        "Bytes are identical at endpoints but path identity changed; exact rename/move time is unknown."
                    ),
                }
            elif classification == "SAME_PATH_CHANGED_BYTES":
                relation = "ENDPOINTS_SAME_PATH_BYTES_CHANGED"
                jp_paths = [entry["path"]] if same_path else []
                uncertainty = {
                    **endpoint_policy(relation),
                    "change_interval": interval(
                        "Same resource path has different endpoint bytes."
                    ),
                }
            else:
                relation = "GLOBAL_RECOVERED_NO_CURRENT_JP_MATCH"
                jp_paths = []
                uncertainty = {
                    **endpoint_policy(relation),
                    "change_interval": interval(
                        "Recovered Global resource has no current-JP identity predicate; removal, move or replacement time is unknown."
                    ),
                }

            rows.append(
                {
                    "entity_id": f"resource:{source_name}:{entry['path']}",
                    "kind": "resource",
                    "name": entry["path"],
                    "global": {
                        "snapshot": GLOBAL_SNAPSHOT["id"],
                        "present": True,
                        "path": entry["path"],
                        "sha1": entry["sha1"],
                        "size": entry["size"],
                        "timestamp": entry.get("timestamp"),
                        "source": source_name,
                    },
                    "current_jp": {
                        "snapshot": JP_SNAPSHOT["id"],
                        "present": bool(jp_paths or same_path),
                        "paths": jp_paths,
                        "same_path_record": same_path,
                    },
                    "relation": relation,
                    "source_lineage_grade": entry["lineage_grade"],
                    "temporal_uncertainty": uncertainty,
                }
            )
    return rows


def map_entities(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for entry in payload["global_to_jp"]:
        relation = "ENDPOINTS_MAP_PACKAGE_AND_STRUCTURE_IDENTICAL"
        rows.append(
            {
                "entity_id": f"map:{entry['base_id']}",
                "kind": "map_package",
                "name": entry["base_id"],
                "global": {
                    "snapshot": GLOBAL_SNAPSHOT["id"],
                    "present": True,
                    "path": entry["global_path"],
                    "package_sha256": entry["global_package_sha256"],
                },
                "current_jp": {
                    "snapshot": JP_SNAPSHOT["id"],
                    "present": True,
                    "base_path": entry["current_jp_base_path"],
                    "ans_path": entry["current_jp_ans_path"],
                    "package_byte_identical_to_base": entry["package_byte_identical_to_jp_base"],
                    "map_payload_identical_to_base": entry["map_payload_identical_to_jp_base"],
                    "structure_identical_to_base": entry["structure_identical_to_jp_base"],
                },
                "relation": relation,
                "source_lineage_grade": entry["lineage_grade"],
                "temporal_uncertainty": endpoint_policy(relation),
            }
        )
    return rows


def build(args: argparse.Namespace) -> dict[str, Any]:
    protocol = json.loads(args.protocol_schema.read_text())
    resources = json.loads(args.resource_genealogy.read_text())
    maps = json.loads(args.map_genealogy.read_text())
    merkle = json.loads(args.merkle_manifest.read_text())

    entities = (
        protocol_entities(protocol)
        + resource_entities(resources)
        + map_entities(maps)
    )
    entities.sort(key=lambda row: (row["kind"], row["entity_id"]))
    relation_counts = Counter(row["relation"] for row in entities)
    kind_counts = Counter(row["kind"] for row in entities)

    changed_relations = {
        "ENDPOINTS_OPCODE_STABLE_SCHEMA_CHANGED",
        "GLOBAL_PRESENT_CURRENT_JP_ABSENT_OR_RENAMED",
        "ENDPOINTS_BYTES_IDENTICAL_PATH_CHANGED",
        "ENDPOINTS_SAME_PATH_BYTES_CHANGED",
        "GLOBAL_RECOVERED_NO_CURRENT_JP_MATCH",
    }
    identical_endpoint_relations = {
        "ENDPOINTS_IDENTICAL_OPCODE_AND_SCHEMA",
        "ENDPOINTS_BYTES_IDENTICAL_SAME_PATH",
        "ENDPOINTS_MAP_PACKAGE_AND_STRUCTURE_IDENTICAL",
    }

    changed = [
        row["entity_id"] for row in entities
        if row["relation"] in changed_relations
    ]
    endpoint_identical = [
        row["entity_id"] for row in entities
        if row["relation"] in identical_endpoint_relations
    ]
    unknown_interval_entities = [
        row["entity_id"] for row in entities
        if not row["temporal_uncertainty"]["continuous_history_proven"]
    ]

    core = {
        "snapshots": [GLOBAL_SNAPSHOT, JP_SNAPSHOT],
        "merkle_root": merkle["merkle_root"],
        "entities": entities,
    }
    lattice_id = hashlib.sha256(
        json.dumps(
            core,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()

    return {
        "provenance": "HYPERDIMENSION_VERSION_SCOPED_TEMPORAL_EVIDENCE_LATTICE",
        "lattice_id": lattice_id,
        "creates_intermediate_history": False,
        "snapshots": [GLOBAL_SNAPSHOT, JP_SNAPSHOT],
        "sealed_evidence_merkle_root": merkle["merkle_root"],
        "sources": {
            "protocol_schema": {
                "path": str(args.protocol_schema),
                "sha256": sha256_file(args.protocol_schema),
            },
            "resource_genealogy": {
                "path": str(args.resource_genealogy),
                "sha256": sha256_file(args.resource_genealogy),
            },
            "map_genealogy": {
                "path": str(args.map_genealogy),
                "sha256": sha256_file(args.map_genealogy),
            },
            "merkle_manifest": {
                "path": str(args.merkle_manifest),
                "sha256": sha256_file(args.merkle_manifest),
                "merkle_root": merkle["merkle_root"],
            },
        },
        "counts": {
            "entities": len(entities),
            "kinds": dict(sorted(kind_counts.items())),
            "relations": dict(sorted(relation_counts.items())),
            "endpoint_identical_entities": len(endpoint_identical),
            "changed_or_missing_endpoint_entities": len(changed),
            "entities_with_unobserved_intermediate_history": len(unknown_interval_entities),
        },
        "entities": entities,
        "indexes": {
            "changed_or_missing": changed,
            "endpoint_identical": endpoint_identical,
        },
        "temporal_policy": {
            "endpoint_identity": (
                "Equal endpoint bytes/opcodes/schemas prove endpoint identity only. "
                "They do not prove continuous unchanged history between 2017 and 2026."
            ),
            "change_interval": (
                "When endpoints differ, the exact change date/version remains unknown "
                "unless a dated intermediate snapshot independently narrows it."
            ),
            "current_jp": (
                "Current JP is a lineage reference and never backfills a missing Global fact."
            ),
            "absence": (
                "No current-JP name/path match is not automatically interpreted as deletion; "
                "rename, move or replacement may remain unresolved."
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path("/home/ubuntu/logres/artifacts")
    parser.add_argument("--protocol-schema", type=Path, default=root / "global-jp-protocol-schema-20260924.json")
    parser.add_argument("--resource-genealogy", type=Path, default=root / "global-jp-resource-genealogy-20260924.json")
    parser.add_argument("--map-genealogy", type=Path, default=root / "global-jp-map-genealogy-20260924.json")
    parser.add_argument("--merkle-manifest", type=Path, default=root / "logres-galaxy-evidence-merkle-20260924.json")
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "lattice_id": result["lattice_id"],
        "counts": result["counts"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
