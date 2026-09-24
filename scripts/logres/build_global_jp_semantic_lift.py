#!/usr/bin/env python3
"""Lift matched Global functions into evidence-scoped semantic records.

Inputs are pre-indexed artifacts only:
- Global/JP native function matcher
- Global protocol schema
- Global critical state machine

Global 3.0.24 remains the behavioral authority. Current JP appears only as a
lineage predicate attached to the Global function; no JP-only behavior is
transferred into the historical model.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

PROVENANCE = "OMEGA_GLOBAL_NATIVE_SEMANTIC_LIFT_WITH_EXPLICIT_PREDICATES"

RESOURCE_EXTENSIONS = (
    ".mbn",
    ".lua",
    ".png",
    ".dds",
    ".jpg",
    ".jpeg",
    ".bin",
    ".json",
    ".plist",
    ".wav",
    ".ogg",
)

TAG_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("network", ("NetworkSession", "GmCl", "GMCL")),
    ("authentication", ("Auth", "Login", "Account")),
    ("onboarding", ("CharcterMake", "CharacterCreate", "CharacterLogin")),
    ("field", ("GameField", "Field", "Area", "Zone")),
    ("movement", ("Move", "Mover", "AStar", "Coord")),
    ("npc_interaction", ("Talk", "NPC", "Npc")),
    ("encounter", ("Enemy", "Encounter")),
    ("battle", ("Battle", "Bout")),
    ("skill", ("Skill",)),
    ("quest", ("Quest",)),
    ("reward", ("Reward", "Drop")),
    ("inventory", ("ItemBox", "Inventory", "Garage", "Equipment", "Item")),
    ("social", ("Party", "Friend", "Clan", "Chat")),
    ("ui_scene", ("Scene", "Window", "View", "Button", "gui::")),
    ("resource_patch", ("Resource", "Patch", "FileSystem")),
)

READ_PREFIXES = ("get", "is", "has", "can", "find", "current", "selected")
WRITE_PREFIXES = (
    "set",
    "add",
    "remove",
    "delete",
    "change",
    "update",
    "clear",
    "apply",
    "insert",
    "push",
    "pop",
    "reset",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_cpp(name: str) -> str:
    return (
        name.replace("std::__ndk1::", "std::")
        .replace("std::__1::", "std::")
        .strip()
    )


def prefix_without_args(name: str) -> str:
    return canonical_cpp(name).split("(", 1)[0].strip()


def short_symbol(name: str) -> str:
    value = prefix_without_args(name)
    return value[5:] if value.startswith("lfs::") else value


def method_name(name: str) -> str:
    return prefix_without_args(name).rsplit("::", 1)[-1]


def resource_literals(strings: list[str]) -> list[str]:
    out = []
    for value in strings:
        lower = value.lower()
        if lower.endswith(RESOURCE_EXTENSIONS) or (
            "/" in value
            and any(token in lower for token in ("gui/", "map", "sound/", "motion/", "shader/"))
        ):
            out.append(value)
    return sorted(set(out))


def semantic_tags(name: str) -> list[dict[str, str]]:
    tags = []
    for tag, tokens in TAG_RULES:
        if any(token in name for token in tokens):
            tags.append(
                {
                    "tag": tag,
                    "evidence": "DIRECT_GLOBAL_SYMBOL_LEXEME",
                    "authority": "DESCRIPTIVE_TAG_ONLY",
                }
            )
    return tags


def heuristic_state_access(name: str) -> list[dict[str, str]]:
    method = method_name(name)
    lower = method.lower()
    out = []
    if lower.startswith(READ_PREFIXES):
        out.append(
            {
                "kind": "READ_CANDIDATE",
                "basis": f"method-name prefix: {method}",
                "authority": "HEURISTIC_NAME_ONLY",
            }
        )
    if lower.startswith(WRITE_PREFIXES):
        out.append(
            {
                "kind": "WRITE_CANDIDATE",
                "basis": f"method-name prefix: {method}",
                "authority": "HEURISTIC_NAME_ONLY",
            }
        )
    return out


def longest_protocol_refs(
    function_name: str,
    protocol_names: list[str],
) -> list[str]:
    matches = [name for name in protocol_names if name in function_name]
    if not matches:
        return []
    longest = max(len(name) for name in matches)
    # A NetworkSession handler/generator has one primary procedure name. Keep
    # all equally-long matches only for the unlikely collision case.
    return sorted(name for name in matches if len(name) == longest)


def compact_protocol(message: dict[str, Any]) -> dict[str, Any]:
    lineage = message.get("lineage") or {}
    return {
        "name": message["name"],
        "opcode_hex": message["opcode_hex"],
        "opcode_u32": message["opcode_u32"],
        "direction": message.get("direction"),
        "fields": message.get("fields", []),
        "top_level_schema_evidence": message.get("top_level_schema_evidence"),
        "jp_lineage_grade": lineage.get("grade"),
        "authority": "GLOBAL_3_0_24_PROTOCOL",
    }


def match_records(
    matcher: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    high = []
    medium = []

    for row in matcher["exact_matches"]:
        if row.get("normalized_instruction_hash_identical"):
            lineage = "EXACT_SYMBOL_PLUS_NORMALIZED_BODY_IDENTITY"
        elif row.get("global_size") and row.get("jp_size"):
            lineage = "EXACT_SYMBOL_BODY_DIVERGED"
        else:
            lineage = "EXACT_SYMBOL_BODY_UNAVAILABLE"
        high.append(
            {
                "global_name": row["global_name"],
                "jp_name": row["jp_name"],
                "match_tier": "EXACT_SYMBOL_CORRESPONDENCE",
                "lineage_predicate": lineage,
                "match_score": 1.0,
                "match_evidence": {
                    "exact_symbol": True,
                    "normalized_instruction_hash_identical": row.get(
                        "normalized_instruction_hash_identical"
                    ),
                    "global_size": row.get("global_size"),
                    "jp_size": row.get("jp_size"),
                },
                "behavioral_transfer_from_jp": False,
            }
        )

    for row in matcher["structural_candidates"]:
        if not row.get("provisional_resolution"):
            continue
        top = row["top_candidates"][0]
        record = {
            "global_name": row["global_name"],
            "jp_name": top["jp_name"],
            "match_tier": top["tier"],
            "lineage_predicate": top["tier"],
            "match_score": top["score"],
            "match_evidence": top["signals"],
            "behavioral_transfer_from_jp": False,
        }
        if top["tier"] == "STRUCTURAL_HIGH":
            high.append(record)
        elif top["tier"] == "STRUCTURAL_MEDIUM":
            medium.append(record)

    high.sort(key=lambda row: row["global_name"])
    medium.sort(key=lambda row: row["global_name"])
    return high, medium


def build(args: argparse.Namespace) -> dict[str, Any]:
    matcher = json.loads(args.function_match.read_text())
    protocol = json.loads(args.protocol_schema.read_text())
    state = json.loads(args.state_machine.read_text())

    global_inventory = {
        row["name"]: row for row in matcher["inventories"]["global"]
    }
    canonical_to_raw: dict[str, list[str]] = defaultdict(list)
    for name in global_inventory:
        canonical_to_raw[canonical_cpp(name)].append(name)

    callers: dict[str, set[str]] = defaultdict(set)
    for caller_name, feature in global_inventory.items():
        caller_canonical = canonical_cpp(caller_name)
        for callee in feature.get("direct_calls", []):
            callers[canonical_cpp(callee)].add(caller_canonical)

    protocol_by_name = {
        row["name"]: row for row in protocol["messages"]
    }
    protocol_names = sorted(protocol_by_name, key=lambda value: (-len(value), value))

    transitions_by_message: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for index, transition in enumerate(state["transitions"]):
        message = transition.get("message")
        if message:
            transitions_by_message[message].append((index, transition))

    high_matches, medium_matches = match_records(matcher)

    transition_bindings: dict[int, set[str]] = defaultdict(set)
    records = []
    missing_inventory = []

    for match in high_matches:
        global_name = match["global_name"]
        feature = global_inventory.get(global_name)
        if feature is None:
            missing_inventory.append(global_name)
            continue

        canonical_name = canonical_cpp(global_name)
        proto_names = longest_protocol_refs(canonical_name, protocol_names)
        proto_refs = [
            compact_protocol(protocol_by_name[name])
            for name in proto_names
        ]

        state_effects = []
        seen_transition_indexes: set[int] = set()

        for proto_name in proto_names:
            for index, transition in transitions_by_message.get(proto_name, []):
                seen_transition_indexes.add(index)
                transition_bindings[index].add(global_name)
                state_effects.append(
                    {
                        "transition_index": index,
                        "from": transition["from"],
                        "to": transition["to"],
                        "message": transition.get("message"),
                        "trigger": transition.get("trigger"),
                        "guard": transition.get("guard"),
                        "action": transition.get("action"),
                        "evidence": transition.get("evidence"),
                        "binding_evidence": "EXACT_GLOBAL_PROTOCOL_MESSAGE_IN_FUNCTION_SYMBOL",
                    }
                )

        short = short_symbol(global_name)
        for index, transition in enumerate(state["transitions"]):
            if index in seen_transition_indexes:
                continue
            action = str(transition.get("action") or "")
            trigger = str(transition.get("trigger") or "")
            if short and (short in action or short in trigger):
                transition_bindings[index].add(global_name)
                state_effects.append(
                    {
                        "transition_index": index,
                        "from": transition["from"],
                        "to": transition["to"],
                        "message": transition.get("message"),
                        "trigger": transition.get("trigger"),
                        "guard": transition.get("guard"),
                        "action": transition.get("action"),
                        "evidence": transition.get("evidence"),
                        "binding_evidence": "EXACT_GLOBAL_SYMBOL_IN_STATE_MACHINE_ACTION_OR_TRIGGER",
                    }
                )

        state_effects.sort(key=lambda row: row["transition_index"])
        state_reads = sorted({row["from"] for row in state_effects})
        state_writes = sorted({row["to"] for row in state_effects})

        literals = list(feature.get("string_refs", []))
        direct_resources = resource_literals(literals)
        normalized_callees = sorted(
            set(canonical_cpp(value) for value in feature.get("direct_calls", []))
        )
        normalized_callers = sorted(callers.get(canonical_name, set()))

        tags = semantic_tags(global_name)
        # Confirmed state/protocol context adds stronger semantic tags.
        if proto_refs and not any(row["tag"] == "network" for row in tags):
            tags.append(
                {
                    "tag": "network",
                    "evidence": "GLOBAL_PROTOCOL_BINDING",
                    "authority": "CONFIRMED_CONTEXT",
                }
            )
        if state_effects:
            states = sorted(set(state_reads + state_writes))
            for state_name in states:
                tags.append(
                    {
                        "tag": f"state:{state_name}",
                        "evidence": "GLOBAL_STATE_MACHINE_BINDING",
                        "authority": "CONFIRMED_CONTEXT",
                    }
                )

        predicates = [
            {
                "predicate": "GLOBAL_FUNCTION_PRESENT",
                "satisfied": True,
                "evidence": "exact Global ELF FUNC inventory",
            },
            {
                "predicate": "JP_LINEAGE_MATCH",
                "satisfied": True,
                "evidence": match["lineage_predicate"],
            },
            {
                "predicate": "JP_BEHAVIOR_TRANSFER_USED",
                "satisfied": False,
                "evidence": "semantics derive from Global-side evidence only",
            },
        ]
        if proto_refs:
            predicates.append(
                {
                    "predicate": "GLOBAL_PROTOCOL_BINDING",
                    "satisfied": True,
                    "evidence": [row["name"] for row in proto_refs],
                }
            )
        if state_effects:
            predicates.append(
                {
                    "predicate": "GLOBAL_STATE_MACHINE_BINDING",
                    "satisfied": True,
                    "evidence": [row["transition_index"] for row in state_effects],
                }
            )

        semantic_claims = []
        if proto_refs:
            semantic_claims.append(
                {
                    "claim": "PROTOCOL_PROCEDURE_BOUNDARY",
                    "authority": "CONFIRMED_GLOBAL_SYMBOL_PLUS_PROTOCOL_SCHEMA",
                    "evidence": [row["name"] for row in proto_refs],
                }
            )
        if state_effects:
            semantic_claims.append(
                {
                    "claim": "CLIENT_STATE_TRANSITION_PARTICIPANT",
                    "authority": "CONFIRMED_GLOBAL_STATE_MACHINE_BINDING",
                    "evidence": [row["transition_index"] for row in state_effects],
                }
            )
        if direct_resources:
            semantic_claims.append(
                {
                    "claim": "RESOURCE_LITERAL_REFERENCE",
                    "authority": "GLOBAL_BINARY_DERIVED_LITERAL",
                    "evidence": direct_resources,
                }
            )

        records.append(
            {
                "global_function": global_name,
                "global_address_hex": feature["address_hex"],
                "global_size": feature["size"],
                "jp_lineage": match,
                "control_flow": {
                    "normalized_callers": normalized_callers,
                    "normalized_callees": normalized_callees,
                    "authority": "GLOBAL_BINARY_DERIVED_DIRECT_CALL_NEIGHBORHOOD",
                },
                "literals": {
                    "strings": literals,
                    "resource_reference_candidates": direct_resources,
                    "authority": "GLOBAL_BINARY_DERIVED_LITERAL_REFERENCE",
                },
                "protocol_references": proto_refs,
                "state_reads": state_reads,
                "state_writes": state_writes,
                "state_effects": state_effects,
                "semantic_tags": tags,
                "heuristic_state_access": heuristic_state_access(global_name),
                "semantic_claims": semantic_claims,
                "evidence_predicates": predicates,
            }
        )

    records.sort(key=lambda row: row["global_function"])

    bound_transition_rows = []
    for index, transition in enumerate(state["transitions"]):
        names = sorted(transition_bindings.get(index, set()))
        bound_transition_rows.append(
            {
                "transition_index": index,
                "from": transition["from"],
                "to": transition["to"],
                "message": transition.get("message"),
                "bound_global_functions": names,
                "bound": bool(names),
            }
        )

    counts = {
        "high_confidence_lifted_functions": len(records),
        "exact_symbol_lifted": sum(
            row["jp_lineage"]["match_tier"] == "EXACT_SYMBOL_CORRESPONDENCE"
            for row in records
        ),
        "structural_high_lifted": sum(
            row["jp_lineage"]["match_tier"] == "STRUCTURAL_HIGH"
            for row in records
        ),
        "structural_medium_candidates_not_lifted": len(medium_matches),
        "unresolved_global_functions": matcher["counts"]["unresolved_global_functions"],
        "functions_with_callers": sum(
            bool(row["control_flow"]["normalized_callers"]) for row in records
        ),
        "functions_with_callees": sum(
            bool(row["control_flow"]["normalized_callees"]) for row in records
        ),
        "functions_with_literals": sum(
            bool(row["literals"]["strings"]) for row in records
        ),
        "functions_with_resource_reference_candidates": sum(
            bool(row["literals"]["resource_reference_candidates"])
            for row in records
        ),
        "functions_with_protocol_references": sum(
            bool(row["protocol_references"]) for row in records
        ),
        "functions_with_confirmed_state_effects": sum(
            bool(row["state_effects"]) for row in records
        ),
        "protocol_messages_referenced": len(
            {
                ref["name"]
                for row in records
                for ref in row["protocol_references"]
            }
        ),
        "state_transitions_bound": sum(
            bool(row["bound_global_functions"]) for row in bound_transition_rows
        ),
        "state_transitions_total": len(state["transitions"]),
        "missing_function_inventory_records": len(missing_inventory),
    }

    return {
        "provenance": PROVENANCE,
        "historical_authority": "Global 3.0.24 / 2017-05-25",
        "current_jp_role": "LINEAGE_PREDICATE_ONLY",
        "sources": {
            "function_match": {
                "path": str(args.function_match),
                "sha256": sha256_file(args.function_match),
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
        "semantic_policy": {
            "global_authority": (
                "All semantic claims are derived from Global-side symbols, "
                "control flow, literals, protocol or state-machine evidence."
            ),
            "jp_lineage": (
                "Current JP identifies lineage only. No JP-only behavior is "
                "copied into a Global semantic claim."
            ),
            "exact_symbol": (
                "Exact symbol correspondence is not behavioral identity; body "
                "divergence remains visible in the lineage predicate."
            ),
            "heuristic_tags": (
                "Name-derived tags and state-access candidates are search aids "
                "only and never become confirmed semantic claims."
            ),
            "state_effects": (
                "Confirmed state reads/writes are emitted only from exact "
                "Global protocol-message or state-machine action/trigger bindings."
            ),
        },
        "function_semantics": records,
        "medium_lineage_candidates": medium_matches,
        "unresolved": {
            "global_function_names": matcher["unresolved_global_function_names"],
            "ambiguous_structural_candidates": matcher["counts"]["structural_ambiguous"],
            "missing_inventory_records": missing_inventory,
        },
        "state_transition_coverage": bound_transition_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path("/home/ubuntu/logres/artifacts")
    parser.add_argument(
        "--function-match",
        type=Path,
        default=root / "global-jp-function-match-20260924.json",
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
