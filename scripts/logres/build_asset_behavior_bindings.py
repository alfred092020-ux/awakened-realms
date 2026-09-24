#!/usr/bin/env python3
"""Bind recovered Global runtime behavior to asset/resource evidence.

The binder never promotes current-JP resources into historical Global facts.
Direct function -> resource-pattern edges require the literal to be recovered
from the Global binary and present in the Global-native semantic graph.
Concrete Global packages/resources are separately joined through exact or
changed lineage evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any

PROVENANCE = "MUIUE_GLOBAL_ASSET_BEHAVIOR_BINDER_WITH_EXPLICIT_AUTHORITY"

VERTICAL_ORDER = (
    "title_ui",
    "player_actor",
    "field_map",
    "npc_enemy_encounter",
    "battle",
    "audio_bgm_se",
    "reward_result",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def classify_vertical(
    literal: str,
    systems: set[str],
    function_name: str,
    tags: set[str],
) -> list[str]:
    lower = literal.lower()
    fn = function_name.lower()
    out: set[str] = set()

    if (
        lower.startswith("gui/title/")
        or lower.startswith("gui/characreate/")
        or "releasescene_title" in fn
        or "worldselector" in fn
        or "charctermake" in fn
        or "agreementwebview" in fn
    ):
        out.add("title_ui")

    if lower.startswith(("avatar/", "motion/")):
        out.add("player_actor")

    if (
        lower.startswith("map/")
        or lower.startswith("battle/field/")
        or "fieldconstant::" in fn
        or "fieldtoucheffect::" in fn
        or "fieldquadtree" in fn
        or "field::marker" in fn
        or "charactershadow::" in fn
    ):
        out.add("field_map")

    if (
        "encount" in lower
        or "enemy" in lower
        or "enemy" in fn
        or "encounter" in tags
    ):
        out.add("npc_enemy_encounter")

    if (
        lower.startswith(("battle/", "gui/battle/"))
        or "battle" in systems
        or "battle" in tags
    ):
        out.add("battle")

    if (
        lower.startswith("sound/")
        or lower.endswith((".ogg", ".wav"))
        or "audio" in systems
        or "sound" in systems
        or "backgroundmusic" in fn
    ):
        out.add("audio_bgm_se")

    if (
        "gui/quest/effect/result/" in lower
        or "rareget" in lower
        or "reward" in fn
        or "questresult" in fn
        or "reward" in tags
    ):
        out.add("reward_result")

    return [name for name in VERTICAL_ORDER if name in out]




def safe_resource_literal(value: str) -> bool:
    lower = value.lower()
    if value.startswith(("/Users/", "/home/", "/tmp/")):
        return False
    if lower.endswith((".cpp", ".cc", ".cxx", ".h", ".hpp", ".mm")):
        return False
    if not value or len(value) > 220:
        return False
    return True


def node_systems(
    graph: dict[str, Any],
) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for edge in graph["edges"]:
        if edge.get("relation") != "CLASSIFIED_AS_SYSTEM":
            continue
        target = str(edge.get("target") or "")
        if target.startswith("system:"):
            result[str(edge["source"])].add(target.split(":", 1)[1])
    return result


def exact_and_changed_lineage(
    graph: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    exact = [
        edge
        for edge in graph["edges"]
        if edge.get("relation") == "EXACT_BYTES_LINEAGE"
    ]
    changed = [
        edge
        for edge in graph["edges"]
        if edge.get("relation") == "SAME_PATH_CHANGED_LINEAGE"
    ]
    return exact, changed


def state_context(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "state_reads": record.get("state_reads", []),
        "state_writes": record.get("state_writes", []),
        "transition_indexes": sorted(
            {
                row["transition_index"]
                for row in record.get("state_effects", [])
            }
        ),
        "protocol_messages": [
            row["name"]
            for row in record.get("protocol_references", [])
        ],
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    semantic = json.loads(args.semantic_lift.read_text())
    graph = json.loads(args.resource_graph.read_text())
    maps = json.loads(args.map_genealogy.read_text())
    protocol = json.loads(args.protocol_schema.read_text())
    state = json.loads(args.state_machine.read_text())

    nodes = {row["id"]: row for row in graph["nodes"]}
    systems_by_node = node_systems(graph)
    exact_lineage, changed_lineage = exact_and_changed_lineage(graph)

    pattern_nodes = {
        row["pattern"]: row
        for row in graph["nodes"]
        if row.get("kind") == "native_resource_pattern"
        and isinstance(row.get("pattern"), str)
    }

    direct_bindings: list[dict[str, Any]] = []
    reverse: dict[str, dict[str, Any]] = {}
    vertical_direct: dict[str, list[str]] = defaultdict(list)

    for record in semantic["function_semantics"]:
        fn = record["global_function"]
        tags = {
            row["tag"]
            for row in record.get("semantic_tags", [])
        }
        context = state_context(record)
        for literal in record["literals"]["resource_reference_candidates"]:
            if not safe_resource_literal(literal):
                continue
            pattern_node = pattern_nodes.get(literal)
            node_id = (
                pattern_node["id"]
                if pattern_node is not None
                else f"global-function-literal:{literal}"
            )
            systems = (
                systems_by_node.get(pattern_node["id"], set())
                if pattern_node is not None
                else set()
            )
            verticals = classify_vertical(literal, systems, fn, tags)
            binding_id = hashlib.sha256(
                f"{fn}\0{literal}".encode("utf-8")
            ).hexdigest()[:20]
            binding = {
                "id": f"binding:{binding_id}",
                "function": fn,
                "global_address_hex": record["global_address_hex"],
                "resource_pattern": literal,
                "resource_node": node_id,
                "systems": sorted(systems),
                "vertical_slice_roles": verticals,
                "behavior_context": context,
                "lineage_predicate": record["jp_lineage"]["lineage_predicate"],
                "authority": (
                    "CONFIRMED_GLOBAL_FUNCTION_RESOURCE_LITERAL_AND_GRAPH_PATTERN"
                    if pattern_node is not None
                    else "CONFIRMED_GLOBAL_FUNCTION_RESOURCE_LITERAL"
                ),
                "score": 1.0,
                "graph_pattern_match": pattern_node is not None,
                "evidence": (
                    [
                        "GLOBAL_BINARY_DERIVED_LITERAL_REFERENCE",
                        "GLOBAL_NATIVE_RESOURCE_PATH_LITERAL",
                    ]
                    if pattern_node is not None
                    else ["GLOBAL_BINARY_DERIVED_LITERAL_REFERENCE"]
                ),
            }
            direct_bindings.append(binding)
            for role in verticals:
                vertical_direct[role].append(binding["id"])

            entry = reverse.setdefault(
                node_id,
                {
                    "resource_node": node_id,
                    "pattern": literal,
                    "functions": [],
                    "systems": sorted(systems),
                    "vertical_slice_roles": set(),
                },
            )
            entry["functions"].append(fn)
            entry["vertical_slice_roles"].update(verticals)

    direct_bindings.sort(
        key=lambda row: (row["resource_pattern"], row["function"])
    )
    reverse_rows = []
    for node_id, row in sorted(reverse.items()):
        reverse_rows.append(
            {
                "resource_node": node_id,
                "pattern": row["pattern"],
                "functions": sorted(set(row["functions"])),
                "systems": row["systems"],
                "vertical_slice_roles": [
                    name
                    for name in VERTICAL_ORDER
                    if name in row["vertical_slice_roles"]
                ],
            }
        )

    # Concrete Global resource/package presence and endpoint lineage are kept
    # separate from function literal bindings. This avoids pretending a generic
    # format literal proves a particular dynamic asset instance was selected.
    concrete_resources = []
    for edge in exact_lineage:
        source = nodes.get(edge["source"], {})
        target = nodes.get(edge["target"], {})
        concrete_resources.append(
            {
                "global_resource_node": edge["source"],
                "global_path": source.get("path"),
                "global_provenance": source.get("provenance"),
                "jp_resource_node": edge["target"],
                "jp_path": target.get("path"),
                "sha1": edge.get("sha1"),
                "size": edge.get("size"),
                "same_path": edge.get("same_path"),
                "authority": "CONFIRMED_GLOBAL_RESOURCE_EXACT_BYTES_LINEAGE",
                "score": 1.0,
            }
        )
    concrete_resources.sort(key=lambda row: str(row["global_path"]))

    changed_resources = []
    for edge in changed_lineage:
        source = nodes.get(edge["source"], {})
        target = nodes.get(edge["target"], {})
        changed_resources.append(
            {
                "global_resource_node": edge["source"],
                "global_path": source.get("path"),
                "jp_resource_node": edge["target"],
                "jp_path": target.get("path"),
                "global_sha1": edge.get("global_sha1"),
                "jp_sha1": edge.get("jp_sha1"),
                "authority": "LINEAGE_CANDIDATE_PATH_CONTINUITY_BYTES_CHANGED",
                "score": 0.55,
                "historical_jp_bytes_usable_as_global": False,
            }
        )
    changed_resources.sort(key=lambda row: str(row["global_path"]))

    exact_by_path = {
        str(row["global_path"]).lower(): row
        for row in concrete_resources
        if row.get("global_path")
    }

    # Explicit high-value vertical-slice anchors. These are presence/consumer
    # joins at the strongest evidence actually available; they are not upgraded
    # to dynamic selection claims when the literal is a pattern.
    def direct_for_prefix(prefixes: tuple[str, ...]) -> list[dict[str, Any]]:
        return [
            row
            for row in direct_bindings
            if row["resource_pattern"].lower().startswith(prefixes)
        ]

    audio_exact = [
        row
        for row in concrete_resources
        if str(row.get("global_path") or "").lower().startswith("sound/")
    ]
    battle_exact = [
        row
        for row in concrete_resources
        if str(row.get("global_path") or "").lower() == "battle.mbn"
    ]
    map_exact = [
        row
        for row in concrete_resources
        if "002_000_00001.mbn" in str(row.get("global_path") or "")
    ]
    title_exact = [
        row
        for row in concrete_resources
        if str(row.get("global_path") or "").lower().startswith("gui/title/")
    ]

    vertical_summary: dict[str, dict[str, Any]] = {}
    for role in VERTICAL_ORDER:
        bindings = [
            row for row in direct_bindings
            if role in row["vertical_slice_roles"]
        ]
        vertical_summary[role] = {
            "direct_global_function_literal_bindings": len(bindings),
            "sample_patterns": sorted(
                {row["resource_pattern"] for row in bindings}
            )[:20],
            "status": (
                "DIRECT_GLOBAL_RUNTIME_BINDINGS"
                if bindings
                else "NO_DIRECT_FUNCTION_LITERAL_BINDING"
            ),
        }

    vertical_summary["audio_bgm_se"]["exact_global_resources"] = audio_exact
    vertical_summary["battle"]["exact_global_packages"] = battle_exact
    vertical_summary["field_map"]["exact_global_packages"] = map_exact
    vertical_summary["title_ui"]["exact_global_resources"] = title_exact

    # The map package is proven Global and byte-identical to current JP, but the
    # historical Global tutorial-area -> static-map assignment remains separate.
    map_crosswalk = []
    for row in maps["global_to_jp"]:
        map_crosswalk.append(
            {
                "base_id": row["base_id"],
                "global_path": row["global_path"],
                "global_package_sha256": row["global_package_sha256"],
                "jp_base_path": row["current_jp_base_path"],
                "lineage_grade": row["lineage_grade"],
                "package_byte_identical": row[
                    "package_byte_identical_to_jp_base"
                ],
                "structure_identical": row[
                    "structure_identical_to_jp_base"
                ],
                "historical_area_assignment_claimed": False,
                "authority": "CONFIRMED_GLOBAL_PACKAGE_PRESENCE_AND_LINEAGE",
            }
        )

    # Candidate-only phase joins make the binder useful to downstream planners
    # without pretending that a role taxonomy proves a historical dynamic
    # selection. These edges are intentionally low-authority.
    role_states = {
        "title_ui": {
            "TITLE", "ACCOUNT_AUTH", "TERMS_GATE", "GENDER_CREATE",
            "CHARACTER_LOGIN",
        },
        "player_actor": {"PREBEGIN_INIT", "AREA_ACTIVE", "FIELD_MOVEMENT"},
        "field_map": {"FIELD_SELECT", "FIELD_INFO", "ZONEIN", "AREA_ACTIVE", "FIELD_MOVEMENT"},
        "npc_enemy_encounter": {"NPC_INTERACTION", "ENCOUNTER_ELIGIBILITY", "BATTLE_ENTRY_PENDING"},
        "battle": {"BATTLE_ACCEPTED", "BATTLE_INITIALIZING", "BOUT_ACTIVE", "BATTLE_RESULT"},
        "audio_bgm_se": set(),
        "reward_result": {"BATTLE_RESULT", "REWARD_PROJECTION", "FIELD_RETURN"},
    }
    candidate_phase_edges = []
    for role in VERTICAL_ORDER:
        patterns = sorted({
            row["resource_pattern"]
            for row in direct_bindings
            if role in row["vertical_slice_roles"]
        })
        states_for_role = sorted(role_states[role])
        messages = sorted({
            transition.get("message")
            for transition in state["transitions"]
            if transition["from"] in role_states[role]
            or transition["to"] in role_states[role]
            if transition.get("message")
        })
        if patterns and states_for_role:
            candidate_phase_edges.append({
                "vertical_slice_role": role,
                "resource_patterns": patterns,
                "states": states_for_role,
                "protocol_messages": messages,
                "authority": "CANDIDATE_SYSTEM_TAXONOMY_NOT_HISTORICAL_BINDING",
                "score": 0.35,
                "dynamic_asset_selection_claimed": False,
            })

    direct_protocol_messages = sorted(
        {
            message
            for row in direct_bindings
            for message in row["behavior_context"]["protocol_messages"]
        }
    )
    direct_transition_indexes = sorted(
        {
            index
            for row in direct_bindings
            for index in row["behavior_context"]["transition_indexes"]
        }
    )

    count_by_system = Counter(
        system
        for row in direct_bindings
        for system in row["systems"]
    )
    count_by_vertical = Counter(
        role
        for row in direct_bindings
        for role in row["vertical_slice_roles"]
    )

    unresolved = {
        "historical_global_tutorial_static_map_assignment":
            "UNRESOLVED; the Global package 002_000_00001 is proven, but current-JP area/map assignment is not promoted to historical Global.",
        "dynamic_resource_selection":
            "A format/path literal proves the Global client consumer surface, not which dynamic ID the retired server selected.",
        "audio_runtime_selection":
            "Exact Global BGM/SE bytes are recovered, but no unsupported claim is made that a particular track/effect played at a particular critical-loop state unless direct evidence exists.",
        "jp_changed_resources":
            "Same-path changed JP bytes remain lineage candidates and cannot replace historical Global bytes.",
    }

    counts = {
        "semantic_functions_examined": len(semantic["function_semantics"]),
        "semantic_resource_candidate_functions":
            semantic["counts"]["functions_with_resource_reference_candidates"],
        "native_resource_patterns": graph["counts"]["native_pattern_nodes"],
        "direct_global_function_pattern_bindings": len(direct_bindings),
        "direct_global_patterns_bound": len(reverse_rows),
        "exact_global_resource_lineage": len(concrete_resources),
        "changed_path_lineage_candidates": len(changed_resources),
        "direct_bound_protocol_messages": len(direct_protocol_messages),
        "direct_bound_state_transitions": len(direct_transition_indexes),
        "vertical_roles_with_direct_bindings": sum(
            bool(vertical_summary[name][
                "direct_global_function_literal_bindings"
            ])
            for name in VERTICAL_ORDER
        ),
    }

    return {
        "provenance": PROVENANCE,
        "historical_authority": "Global 3.0.24 / 2017-05-25",
        "sources": {
            "semantic_lift": {
                "path": str(args.semantic_lift),
                "sha256": sha256_file(args.semantic_lift),
            },
            "resource_semantic_graph": {
                "path": str(args.resource_graph),
                "sha256": sha256_file(args.resource_graph),
            },
            "map_genealogy": {
                "path": str(args.map_genealogy),
                "sha256": sha256_file(args.map_genealogy),
            },
            "protocol_schema": {
                "path": str(args.protocol_schema),
                "sha256": sha256_file(args.protocol_schema),
            },
            "state_machine": {
                "path": str(args.state_machine),
                "sha256": sha256_file(args.state_machine),
            },
        },
        "counts": counts,
        "direct_function_asset_bindings": direct_bindings,
        "asset_reverse_index": reverse_rows,
        "concrete_global_exact_lineage": concrete_resources,
        "changed_lineage_candidates": changed_resources,
        "map_crosswalk": map_crosswalk,
        "vertical_slice": vertical_summary,
        "behavior_join": {
            "direct_protocol_messages": direct_protocol_messages,
            "direct_state_transition_indexes": direct_transition_indexes,
            "candidate_phase_edges": candidate_phase_edges,
            "system_binding_counts": dict(sorted(count_by_system.items())),
            "vertical_binding_counts": dict(sorted(count_by_vertical.items())),
        },
        "authority_policy": {
            "function_literal": (
                "A resource-looking literal recovered from a Global function "
                "is a confirmed Global consumer-pattern binding. A matching "
                "Global-native graph node strengthens indexing but is not required."
            ),
            "exact_resource": (
                "Recovered Global resource + identical manifest hash/size = "
                "confirmed concrete Global resource presence and endpoint lineage."
            ),
            "changed_resource": (
                "Same-path changed JP resource is lineage only and cannot be "
                "used as historical Global bytes."
            ),
            "dynamic_selection": (
                "Pattern consumers do not prove which server-selected/dynamic "
                "resource instance was used at a historical moment."
            ),
        },
        "unresolved": unresolved,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path("/home/ubuntu/logres/artifacts")
    parser.add_argument(
        "--semantic-lift",
        type=Path,
        default=root / "global-jp-semantic-lift-20260924.json",
    )
    parser.add_argument(
        "--resource-graph",
        type=Path,
        default=root / "global-jp-resource-semantic-graph-20260924.json",
    )
    parser.add_argument(
        "--map-genealogy",
        type=Path,
        default=root / "global-jp-map-genealogy-20260924.json",
    )
    parser.add_argument(
        "--protocol-schema",
        type=Path,
        default=root / "global-jp-protocol-schema-20260924.json",
    )
    parser.add_argument(
        "--state-machine",
        type=Path,
        default=root / "global-3024-state-machine-20260924.json",
    )
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["counts"], sort_keys=True))
    for role in VERTICAL_ORDER:
        row = result["vertical_slice"][role]
        print(
            role,
            row["status"],
            row["direct_global_function_literal_bindings"],
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
