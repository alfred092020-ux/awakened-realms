#!/usr/bin/env python3
"""Compile Global 3.0.24 protocol schemas with bounded current-JP lineage.

Global generator signatures and NetworkSession handler signatures are direct
client evidence for top-level argument order. Constructor signatures are used
only as weaker nested-type shape evidence and are never promoted to proven
wire order by themselves.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any

STD_STRING_PREFIX = "std::__ndk1::basic_string<char"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_cpp_args(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    out: list[str] = []
    start = 0
    angle = paren = bracket = 0
    for index, char in enumerate(text):
        if char == "<":
            angle += 1
        elif char == ">":
            angle = max(0, angle - 1)
        elif char == "(":
            paren += 1
        elif char == ")":
            paren = max(0, paren - 1)
        elif char == "[":
            bracket += 1
        elif char == "]":
            bracket = max(0, bracket - 1)
        elif char == "," and angle == 0 and paren == 0 and bracket == 0:
            out.append(text[start:index].strip())
            start = index + 1
    tail = text[start:].strip()
    if tail:
        out.append(tail)
    return out


def strip_cvref(cpp_type: str) -> str:
    value = cpp_type.strip()
    value = re.sub(r"\s+const\s*&$", "", value)
    value = re.sub(r"\s*&$", "", value)
    value = re.sub(r"\s+const$", "", value)
    return value.strip()


def normalize_cpp_type(cpp_type: str) -> str:
    value = strip_cvref(cpp_type)
    if value.startswith(STD_STRING_PREFIX):
        return "string"
    aliases = {
        "int": "int32",
        "unsigned int": "uint32",
        "long": "int64_or_abi_long",
        "unsigned long": "uint64_or_abi_ulong",
        "long long": "int64",
        "unsigned long long": "uint64",
        "float": "float32",
        "double": "float64",
        "bool": "bool",
        "char": "char8",
        "unsigned char": "uint8",
        "short": "int16",
        "unsigned short": "uint16",
    }
    if value in aliases:
        return aliases[value]
    if value.startswith("std::__ndk1::vector<"):
        return "array<cpp_vector_element>"
    if value.startswith("GmClProto::"):
        return value.removeprefix("GmClProto::")
    return value


def classify_type(cpp_type: str) -> str:
    norm = normalize_cpp_type(cpp_type)
    if norm in {
        "int32", "uint32", "int64_or_abi_long", "uint64_or_abi_ulong",
        "int64", "uint64", "float32", "float64", "bool", "char8",
        "uint8", "int16", "uint16", "string",
    }:
        return "primitive"
    if norm.startswith("array<"):
        return "array"
    leaf = norm.split("::")[-1]
    if (
        leaf.startswith("t_arr")
        or leaf.endswith("Array")
        or leaf.endswith("List")
        or leaf.endswith("List_t")
        or leaf.endswith("s_t")
        or leaf.endswith("_list")
    ):
        return "array_or_collection"
    if leaf.startswith("e_"):
        return "enum"
    return "composite_or_alias"


def parse_network_signatures(path: Path) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    prefix = "lfs::NetworkSession::"
    for raw in path.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if not line.startswith(prefix) or not line.endswith(")"):
            continue
        open_paren = line.find("(", len(prefix))
        if open_paren < 0:
            continue
        name = line[len(prefix):open_paren]
        args = split_cpp_args(line[open_paren + 1:-1])
        if name.startswith(("C_GMCL_", "S_GMCL_", "S_COMMUNICATION_")):
            result[name] = args
    return result


def choose_constructor(signatures: list[str]) -> list[str]:
    candidates = [split_cpp_args(item) for item in signatures if item.strip()]
    if not candidates:
        return []
    return max(candidates, key=lambda row: (len(row), sum(len(x) for x in row)))


def constructor_shape(
    cpp_type: str,
    constructors: dict[str, list[str]],
    depth: int = 0,
    seen: set[str] | None = None,
) -> dict[str, Any] | None:
    if depth > 2:
        return None
    value = strip_cvref(cpp_type)
    if value.startswith("GmClProto::"):
        key = value
    else:
        return None
    signatures = constructors.get(key)
    if not signatures:
        return None
    seen = set() if seen is None else set(seen)
    if key in seen:
        return {"type": key, "recursive": True}
    seen.add(key)
    args = choose_constructor(signatures)
    fields = []
    for index, arg in enumerate(args):
        field: dict[str, Any] = {
            "index": index,
            "cpp_type": arg,
            "normalized_type": normalize_cpp_type(arg),
            "kind": classify_type(arg),
            "evidence": "GLOBAL_BINARY_DERIVED_CONSTRUCTOR_SHAPE",
        }
        nested = constructor_shape(arg, constructors, depth + 1, seen)
        if nested is not None:
            field["nested"] = nested
        fields.append(field)
    return {
        "type": key,
        "fields": fields,
        "evidence": "GLOBAL_BINARY_DERIVED_CONSTRUCTOR_SHAPE",
        "warning": "Constructor argument order is nested shape evidence, not independently proven serialization order.",
    }


def schema_fields(
    args: list[str],
    evidence: str,
    constructors: dict[str, list[str]],
) -> list[dict[str, Any]]:
    fields = []
    for index, arg in enumerate(args):
        field: dict[str, Any] = {
            "index": index,
            "cpp_type": arg,
            "normalized_type": normalize_cpp_type(arg),
            "kind": classify_type(arg),
            "evidence": evidence,
        }
        nested = constructor_shape(arg, constructors)
        if nested is not None:
            field["nested_constructor_shape"] = nested
        fields.append(field)
    return fields


def generator_args(signature: str | None) -> list[str]:
    if not signature:
        return []
    args = split_cpp_args(signature)
    if args and strip_cvref(args[0]) == "oneup::Buffer":
        args = args[1:]
    return args


def jp_index(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in catalog.get("procedures", []):
        index[row["name"]] = {
            "name": row["name"],
            "opcode_hex": row["opcode_hex"],
            "opcode_u32": row["opcode_u32"],
            "args": row.get("request_args", []),
            "kind": "request",
        }
        response = row.get("response_handler")
        response_name = row.get("response_handler_name")
        if response and response_name:
            index[response_name] = {
                "name": response_name,
                "opcode_hex": row.get("response_opcode_hex"),
                "opcode_u32": row.get("response_opcode_u32"),
                "args": response.get("args", []),
                "kind": "response",
            }
    for row in catalog.get("incoming_procedures", []):
        index.setdefault(
            row["name"],
            {
                "name": row["name"],
                "opcode_hex": row["opcode_hex"],
                "opcode_u32": row["opcode_u32"],
                "args": row.get("handler_args", []),
                "kind": row.get("kind", "incoming"),
            },
        )
    return index


def normalized_args(args: list[str]) -> list[str]:
    return [normalize_cpp_type(arg) for arg in args]


def classify_lineage(
    global_opcode: int,
    global_args: list[str],
    jp: dict[str, Any] | None,
) -> dict[str, Any]:
    if jp is None:
        return {
            "grade": "GLOBAL_ONLY_OR_REMOVED_IN_CURRENT_JP",
            "jp_present": False,
        }
    opcode_same = jp.get("opcode_u32") == global_opcode
    global_norm = normalized_args(global_args)
    jp_norm = normalized_args(jp.get("args", []))
    if global_args:
        args_same = global_norm == jp_norm
    else:
        args_same = None
    if opcode_same and args_same is True:
        grade = "GLOBAL_JP_IDENTICAL_TOP_LEVEL_SCHEMA"
    elif opcode_same and args_same is False:
        grade = "JP_LINEAGE_OPCODE_STABLE_SCHEMA_CHANGED"
    elif opcode_same:
        grade = "JP_LINEAGE_OPCODE_STABLE_GLOBAL_SCHEMA_UNRESOLVED"
    else:
        grade = "JP_LINEAGE_OPCODE_CHANGED"
    return {
        "grade": grade,
        "jp_present": True,
        "jp_opcode_hex": jp.get("opcode_hex"),
        "jp_opcode_u32": jp.get("opcode_u32"),
        "opcode_identical": opcode_same,
        "jp_args": jp.get("args", []),
        "normalized_jp_args": jp_norm,
        "top_level_schema_identical": args_same,
    }


CRITICAL_FLOW = [
    "C_GMCL_ACCOUNT_LOGIN_REQ",
    "C_GMCL_ACCOUNT_LOGIN_REQ_Response",
    "C_GMCL_CHAR_CREATE_REQ",
    "C_GMCL_CHAR_CREATE_REQ_Response",
    "C_GMCL_CHAR_LOGIN_REQ",
    "C_GMCL_CHAR_LOGIN_REQ_Response",
    "C_GMCL_FIELD_SELECT_REQ",
    "S_GMCL_FIELD_SELECT_REQ",
    "C_GMCL_FIELD_INFO_REQ",
    "C_GMCL_FIELD_INFO_REQ_Response",
    "C_GMCL_ZONEIN_REQ",
    "C_GMCL_ZONEIN_REQ_Response",
    "S_GMCL_AREA_ENTER",
    "C_GMCL_CHAR_MOVE_REQ",
    "S_GMCL_CHAR_MOVE_REQ",
    "C_GMCL_CHAR_TALK_REQ",
    "C_GMCL_CHAR_TALK_REQ_Response",
    "S_GMCL_NPC_APPEAR",
    "S_GMCL_ENEMY_APPEAR",
    "C_GMCL_BATTLE_ENTRY_REQ",
    "C_GMCL_BATTLE_ENTRY_REQ_Response",
    "S_GMCL_BATTLE_INITIALIZE",
    "S_GMCL_BATTLE_BOUT_INITIALIZE",
    "C_GMCL_BATTLE_USE_SKILL_REQ",
    "C_GMCL_BATTLE_USE_SKILL_REQ_Response",
    "S_GMCL_BATTLE_BOUT_EVENT_DROP",
    "S_GMCL_BATTLE_RESULT",
    "S_GMCL_ITEM_INFO",
    "S_GMCL_QUEST_INFO_STATE_RESULT",
    "S_GMCL_QUEST_INFO_STATE_RETURN",
]


def build(args: argparse.Namespace) -> dict[str, Any]:
    global_catalog = json.loads(args.global_catalog.read_text())
    constructors = json.loads(args.global_constructors.read_text())
    handlers = parse_network_signatures(args.global_network_signatures)
    jp_catalog = json.loads(args.jp_catalog.read_text())
    jp_by_name = jp_index(jp_catalog)

    global_names = {row["name"] for row in global_catalog}
    rows = []
    direct_generator = direct_handler = unresolved = 0
    lineage_counts = Counter()
    identical_schema = changed_schema = 0

    for row in global_catalog:
        name = row["name"]
        gen_args = generator_args(row.get("generator_signature"))
        handler_args = handlers.get(name, [])
        if gen_args or row.get("generator_signature") is not None:
            top_args = gen_args
            top_evidence = "GLOBAL_DIRECT_GENERATOR_SIGNATURE"
            direction = "client_to_server"
            direct_generator += 1
        elif handler_args or name in handlers:
            top_args = handler_args
            top_evidence = "GLOBAL_DIRECT_NETWORKSESSION_HANDLER_SIGNATURE"
            direction = "server_to_client"
            direct_handler += 1
        else:
            top_args = []
            top_evidence = "UNRESOLVED_TOP_LEVEL_SCHEMA"
            direction = "unknown"
            unresolved += 1

        lineage = classify_lineage(row["id"], top_args, jp_by_name.get(name))
        lineage_counts[lineage["grade"]] += 1
        if lineage.get("top_level_schema_identical") is True:
            identical_schema += 1
        elif lineage.get("top_level_schema_identical") is False:
            changed_schema += 1

        response_of = None
        if name.endswith("_Response"):
            candidate = name[:-9]
            if candidate in global_names:
                response_of = candidate

        record = {
            "name": name,
            "opcode_u32": row["id"],
            "opcode_hex": row["hex"],
            "direction": direction,
            "top_level_schema_evidence": top_evidence,
            "fields": schema_fields(top_args, top_evidence, constructors),
            "global_generator_signature": row.get("generator_signature"),
            "global_handler_args": handler_args or None,
            "response_of": response_of,
            "lineage": lineage,
        }
        rows.append(record)

    by_name = {row["name"]: row for row in rows}
    request_response_pairs = []
    for row in rows:
        if row["response_of"]:
            request = by_name[row["response_of"]]
            request_response_pairs.append(
                {
                    "request_name": request["name"],
                    "request_opcode_hex": request["opcode_hex"],
                    "response_name": row["name"],
                    "response_opcode_hex": row["opcode_hex"],
                    "request_schema_evidence": request["top_level_schema_evidence"],
                    "response_schema_evidence": row["top_level_schema_evidence"],
                }
            )

    critical = []
    for name in CRITICAL_FLOW:
        if name in by_name:
            critical.append(by_name[name])
        else:
            critical.append(
                {
                    "name": name,
                    "missing_from_global_catalog": True,
                    "evidence": "UNRESOLVED",
                }
            )

    constructor_records = []
    for type_name, signatures in sorted(constructors.items()):
        chosen = choose_constructor(signatures)
        constructor_records.append(
            {
                "type": type_name,
                "constructor_overloads": signatures,
                "chosen_shape": schema_fields(
                    chosen,
                    "GLOBAL_BINARY_DERIVED_CONSTRUCTOR_SHAPE",
                    constructors,
                ),
            }
        )

    return {
        "provenance": "GLOBAL_3_0_24_PROTOCOL_AUTHORITY_WITH_BOUNDED_CURRENT_JP_LINEAGE",
        "sources": {
            "global_protocol_catalog": {
                "path": str(args.global_catalog),
                "sha256": sha256_file(args.global_catalog),
            },
            "global_constructor_catalog": {
                "path": str(args.global_constructors),
                "sha256": sha256_file(args.global_constructors),
            },
            "global_network_session_signatures": {
                "path": str(args.global_network_signatures),
                "sha256": sha256_file(args.global_network_signatures),
            },
            "current_jp_protocol_catalog": {
                "path": str(args.jp_catalog),
                "sha256": sha256_file(args.jp_catalog),
            },
        },
        "counts": {
            "global_messages": len(rows),
            "global_generator_schema_messages": direct_generator,
            "global_handler_schema_messages": direct_handler,
            "global_unresolved_top_level_schema_messages": unresolved,
            "global_request_response_pairs": len(request_response_pairs),
            "global_constructor_types": len(constructor_records),
            "current_jp_present_global_messages": sum(
                1 for row in rows if row["lineage"]["jp_present"]
            ),
            "top_level_schema_identical_global_jp": identical_schema,
            "top_level_schema_changed_global_jp": changed_schema,
            "lineage_grades": dict(sorted(lineage_counts.items())),
        },
        "messages": rows,
        "request_response_pairs": request_response_pairs,
        "constructor_shapes": constructor_records,
        "critical_vertical_slice": critical,
        "evidence_policy": {
            "GLOBAL_DIRECT_GENERATOR_SIGNATURE": (
                "Top-level client->server argument order/types from original Global generator."
            ),
            "GLOBAL_DIRECT_NETWORKSESSION_HANDLER_SIGNATURE": (
                "Top-level server->client argument order/types from original Global NetworkSession handler."
            ),
            "GLOBAL_BINARY_DERIVED_CONSTRUCTOR_SHAPE": (
                "Nested C++ constructor shape from original Global symbols; useful for structure, not independently proven wire order."
            ),
            "GLOBAL_JP_IDENTICAL_TOP_LEVEL_SCHEMA": (
                "Current JP retains identical opcode and normalized top-level schema; JP is corroboration only."
            ),
            "JP_LINEAGE_OPCODE_STABLE_SCHEMA_CHANGED": (
                "Opcode survived but top-level schema changed; current JP schema must not be backported."
            ),
            "UNRESOLVED_TOP_LEVEL_SCHEMA": (
                "No original Global generator or NetworkSession signature was recovered for this procedure."
            ),
        },
        "unresolved": [
            "Semantic field names are not invented where native signatures expose only positional C++ types.",
            "Constructor argument order is not treated as independently proven nested serialization order.",
            "Server-side validation, persistence and database semantics are outside client protocol evidence.",
            "Current-JP-only messages and schema changes are not promoted into Global behavior.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path("/home/ubuntu/logres/private/global-apk/3.0.24/re/reports")
    parser.add_argument(
        "--global-catalog",
        type=Path,
        default=base / "gmcl-protocol-catalog.json",
    )
    parser.add_argument(
        "--global-constructors",
        type=Path,
        default=base / "gmclproto-constructor-signatures.json",
    )
    parser.add_argument(
        "--global-network-signatures",
        type=Path,
        default=base / "network-session-signatures.txt",
    )
    parser.add_argument(
        "--jp-catalog",
        type=Path,
        default=Path(
            "/home/ubuntu/logres/private/evidence/"
            "protocol-current-jp-2026-09-22/protocol-catalog.json"
        ),
    )
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    print(json.dumps(result["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
