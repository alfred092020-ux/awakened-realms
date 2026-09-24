#!/usr/bin/env python3
"""Build an evidence-ranked world reconstruction plan without JP backporting."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def classify_system(path: str) -> str:
    p = path.lower()
    if p.startswith(("map", "info.mbn")):
        return "field_world"
    if "battle" in p:
        return "battle"
    if p.startswith("gui/title") or "splash" in p:
        return "title"
    if "characreate" in p or "tutorial" in p:
        return "onboarding"
    if p.startswith("sound/"):
        return "audio"
    if p.startswith("motion/"):
        return "animation"
    if p.startswith("graphicsettings/"):
        return "renderer"
    if p.startswith("gui"):
        return "gui"
    if "json_resource" in p or p.startswith("system"):
        return "configuration"
    return "other"


def active_scopes(database: Path) -> list[str]:
    conn = sqlite3.connect(database)
    rows = conn.execute(
        """
        select distinct s.path_prefix
          from task_scopes s
          join tasks t on t.id=s.task_id
         where t.status='ACTIVE'
        """
    ).fetchall()
    conn.close()
    return sorted(row[0] for row in rows)


def overlaps(scope: str, active: list[str]) -> list[str]:
    normalized = scope.rstrip("/") + "/"
    result = []
    for item in active:
        other = item.rstrip("/") + "/"
        if normalized.startswith(other) or other.startswith(normalized):
            result.append(item)
    return result


def build(args: argparse.Namespace) -> dict[str, Any]:
    maps = json.loads(args.map_genealogy.read_text())
    resources = json.loads(args.resource_genealogy.read_text())
    semantic = json.loads(args.semantic_graph.read_text())

    jp_base_maps = [
        row for row in maps["jp_packages"]
        if row.get("category") == "terrain" and row.get("variant") == "base"
    ]
    direct_global_ids = {
        row["base_id"]
        for row in maps["global_to_jp"]
        if row.get("lineage_grade") == "GLOBAL_JP_IDENTICAL"
    }

    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in jp_base_maps:
        parts = row["base_id"].split("_")
        family = "_".join(parts[:2])
        families[family].append(row)

    family_rows = []
    for family, rows in sorted(families.items()):
        ids = sorted(row["base_id"] for row in rows)
        direct = sorted(set(ids) & direct_global_ids)
        if direct:
            grade = "GLOBAL_DIRECT_SEEDED"
            rank = 4
            disposition = "IMPLEMENTATION_ELIGIBLE_FOR_PROVEN_GLOBAL_MEMBERS_ONLY"
        else:
            grade = "JP_LINEAGE_CANDIDATE_ONLY"
            rank = 1
            disposition = "RESEARCH_ONLY_UNTIL_GLOBAL_PRIMARY_EVIDENCE"
        family_rows.append(
            {
                "family": family,
                "base_map_count": len(rows),
                "base_map_ids": ids,
                "global_direct_members": direct,
                "evidence_grade": grade,
                "evidence_rank": rank,
                "disposition": disposition,
            }
        )

    exact_edges = resources["exact_identity_edges"]
    changed_edges = resources["same_path_changed_edges"]
    exact_by_system: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in exact_edges:
        exact_by_system[classify_system(row["global_path"])].append(row)
    changed_by_system: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in changed_edges:
        changed_by_system[classify_system(row["path"])].append(row)

    native_patterns = [
        node for node in semantic["nodes"]
        if node.get("kind") == "native_resource_pattern"
    ]
    native_exact = [
        edge for edge in semantic["edges"]
        if edge.get("relation") == "NATIVE_REFERENCES_RESOURCE"
    ]

    active = active_scopes(args.database)
    proposed = [
        {
            "id": "WORLD-BATCH-A-DIRECT-GLOBAL",
            "evidence_rank": 4,
            "evidence_grade": "GLOBAL_DIRECT_OR_BYTE_IDENTICAL",
            "scope": "src/game/logres/world-expansion/direct-global/",
            "content": {
                "direct_global_map_ids": sorted(direct_global_ids),
                "exact_resource_edges": exact_edges,
            },
            "acceptance": [
                "Implement only members directly recovered from Global or proven byte-identical Global↔JP.",
                "Preserve original Global map geometry/collision/resource bytes where available.",
                "Do not generalize neighboring JP maps into Global content.",
            ],
        },
        {
            "id": "WORLD-BATCH-B-EXACT-CONTINUITY",
            "evidence_rank": 4,
            "evidence_grade": "GLOBAL_JP_IDENTICAL",
            "scope": "src/game/logres/world-expansion/exact-continuity/",
            "content": {
                "systems": {
                    key: len(value)
                    for key, value in sorted(exact_by_system.items())
                },
                "resources": exact_edges,
            },
            "acceptance": [
                "Reuse or reconstruct only exact byte-continuous resources.",
                "Byte identity proves asset continuity only; surrounding behavior still requires independent evidence.",
            ],
        },
        {
            "id": "WORLD-BATCH-C-CHANGED-CONTINUITY",
            "evidence_rank": 3,
            "evidence_grade": "GLOBAL_PATH_CONTINUITY_BYTES_CHANGED",
            "scope": "src/game/logres/world-expansion/changed-continuity/",
            "content": {
                "systems": {
                    key: len(value)
                    for key, value in sorted(changed_by_system.items())
                },
                "resources": changed_edges,
            },
            "acceptance": [
                "Treat same-path JP resources as descendants, not drop-in historical assets.",
                "Require bounded binary/visual/resource diff before implementing a historical reconstruction.",
            ],
        },
        {
            "id": "WORLD-BATCH-D-NATIVE-PATTERN-BINDINGS",
            "evidence_rank": 2,
            "evidence_grade": "GLOBAL_NATIVE_PATTERN_ONLY",
            "scope": "src/game/logres/world-expansion/native-patterns/",
            "content": {
                "native_resource_patterns": len(native_patterns),
                "native_exact_resource_links": len(native_exact),
            },
            "acceptance": [
                "Use Global-native resource patterns to identify expected content classes and runtime consumers.",
                "A format string or path pattern proves client expectation, not the historical existence of every possible ID.",
            ],
        },
        {
            "id": "WORLD-BATCH-E-JP-LINEAGE-RESEARCH",
            "evidence_rank": 1,
            "evidence_grade": "JP_LINEAGE_CANDIDATE_ONLY",
            "scope": "reference/logres/world-lineage-candidates/",
            "content": {
                "families": family_rows,
                "jp_base_terrain_maps": len(jp_base_maps),
                "jp_only_base_terrain_maps": (
                    len(jp_base_maps) - len(direct_global_ids)
                ),
            },
            "acceptance": [
                "Do not implement JP-only map families as confirmed Global content.",
                "Use candidate families only to target archival, function, manifest or server-payload evidence searches.",
            ],
        },
    ]

    for batch in proposed:
        conflicts = overlaps(batch["scope"], active)
        batch["active_scope_conflicts"] = conflicts
        batch["scope_safe_now"] = not conflicts

    unsafe = [row["id"] for row in proposed if not row["scope_safe_now"]]

    evidence_counts = {
        "recovered_global_map_packages": maps["inventory"]["recovered_global_map_packages"],
        "direct_global_map_ids": len(direct_global_ids),
        "jp_base_terrain_maps": len(jp_base_maps),
        "jp_map_families": len(family_rows),
        "exact_resource_identity_edges": len(exact_edges),
        "same_path_changed_resource_edges": len(changed_edges),
        "native_resource_patterns": len(native_patterns),
        "native_exact_resource_links": len(native_exact),
    }

    return {
        "provenance": "GALAXY_EVIDENCE_RANKED_WORLD_RECONSTRUCTION_PLAN",
        "sources": {
            "map_genealogy": {
                "path": str(args.map_genealogy),
                "sha256": sha256_file(args.map_genealogy),
            },
            "resource_genealogy": {
                "path": str(args.resource_genealogy),
                "sha256": sha256_file(args.resource_genealogy),
            },
            "resource_semantic_graph": {
                "path": str(args.semantic_graph),
                "sha256": sha256_file(args.semantic_graph),
            },
        },
        "evidence_counts": evidence_counts,
        "evidence_order": [
            "GLOBAL_DIRECT_OR_BYTE_IDENTICAL",
            "GLOBAL_PATH_CONTINUITY_BYTES_CHANGED",
            "GLOBAL_NATIVE_PATTERN_ONLY",
            "JP_LINEAGE_CANDIDATE_ONLY",
            "EXTERNAL_CEILING",
        ],
        "map_families": family_rows,
        "exact_resources_by_system": {
            key: value for key, value in sorted(exact_by_system.items())
        },
        "changed_resources_by_system": {
            key: value for key, value in sorted(changed_by_system.items())
        },
        "implementation_batches": proposed,
        "active_scopes_snapshot": active,
        "unsafe_batch_ids": unsafe,
        "guardrails": [
            "Current-JP-only maps and resources are research candidates, not historical Global facts.",
            "Exact byte identity transfers asset bytes, not server rules or surrounding runtime semantics.",
            "Same-path changed resources require reconstruction/diff evidence before historical implementation.",
            "Native resource patterns prove client content expectations but not every concrete historical resource ID.",
            "External server-side schedules, spawn tables, world-state validation and unrecovered map-name bindings remain evidence ceilings.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path("/home/ubuntu/logres/artifacts")
    parser.add_argument("--map-genealogy", type=Path, default=root / "global-jp-map-genealogy-20260924.json")
    parser.add_argument("--resource-genealogy", type=Path, default=root / "global-jp-resource-genealogy-20260924.json")
    parser.add_argument("--semantic-graph", type=Path, default=root / "global-jp-resource-semantic-graph-20260924.json")
    parser.add_argument("--database", type=Path, default=Path("/home/ubuntu/logres/control/control.sqlite"))
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build(args)
    if result["unsafe_batch_ids"]:
        raise RuntimeError(
            "proposed batch scopes overlap active work: "
            + ",".join(result["unsafe_batch_ids"])
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "evidence_counts": result["evidence_counts"],
        "batch_count": len(result["implementation_batches"]),
        "unsafe_batch_ids": result["unsafe_batch_ids"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
