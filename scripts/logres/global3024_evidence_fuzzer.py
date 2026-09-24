#!/usr/bin/env python3
"""Deterministic, offline, provenance-aware mutation suite for Global 3.0.24.

This tool does not contact any game server. It mutates recovered Global
protocol frames, schemas, state-machine transitions and resource identities.
Outcomes are explicitly classified so harness rejection is never mislabeled as
historical retired-server behavior.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent


def load_twin(path: Path):
    spec = importlib.util.spec_from_file_location("global3024_protocol_twin", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import protocol twin: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_case_id(kind: str, subject: str, mutation: str) -> str:
    digest = hashlib.sha256(
        f"{kind}\n{subject}\n{mutation}".encode("utf-8")
    ).hexdigest()[:12]
    return f"{kind}:{digest}"


def case(
    kind: str,
    subject: str,
    mutation: str,
    expected_class: str,
    expected: str,
    evidence: str,
    *,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": stable_case_id(kind, subject, mutation),
        "kind": kind,
        "subject": subject,
        "mutation": mutation,
        "expected_class": expected_class,
        "expected": expected,
        "evidence": evidence,
        "details": details or {},
    }


def wire_mutations(twin) -> list[dict[str, Any]]:
    payload = b"GLOBAL3024-MUIUE"
    valid = twin.encode_wire(payload, 0x10203040)

    mutations: list[tuple[str, bytes]] = []
    mutations.append(("bad_packet_marker", bytes([0x02]) + valid[1:]))
    mutations.append(("truncated_packet_header", valid[:4]))
    mutations.append(("declared_packet_payload_too_long", valid[:-1]))
    mutations.append(
        (
            "varuint_more_than_five_bytes",
            bytes([twin.PACKET_MARKER])
            + struct.pack("<I", 1)
            + bytes([0x80] * 6),
        )
    )

    # Mutate the recovered compressor marker inside a freshly constructed frame.
    split = twin.split_to_contract(payload)
    compressed = twin.compressor_forward(split)
    bad_compression = bytes([0x7F]) + compressed[1:]
    mutations.append(
        (
            "unknown_compressor_marker",
            twin.packetize(bad_compression, 2),
        )
    )

    # Contract ID mismatch survives packet/compression parsing but must be rejected
    # by the recovered GmCl contract boundary.
    wrong_contract = twin.split_to_contract(payload, twin.GMCL_CONTRACT_ID ^ 1)
    mutations.append(
        (
            "wrong_gmcl_contract_id",
            twin.packetize(twin.compressor_forward(wrong_contract), 3),
        )
    )

    # Nested contract length mismatch.
    split_bad_len = bytearray(split)
    struct.pack_into("<I", split_bad_len, 4, len(payload) + 9)
    mutations.append(
        (
            "nested_contract_length_mismatch",
            twin.packetize(twin.compressor_forward(bytes(split_bad_len)), 4),
        )
    )

    rows = []
    for mutation, frame in mutations:
        try:
            twin.decode_wire(frame)
            observed = "ACCEPTED_BY_OFFLINE_DECODER"
            rejected = False
        except Exception as exc:  # WireError is intentionally local to the twin.
            observed = f"{type(exc).__name__}: {exc}"
            rejected = True
        rows.append(
            case(
                "WIRE_MUTATION",
                "oneup/GmCl recovered transport",
                mutation,
                "OFFLINE_WIRE_CONTRACT_REJECT",
                "reject malformed frame in deterministic offline codec",
                "GLOBAL_BINARY_DERIVED_ONEUP_TRANSPORT",
                details={
                    "observed": observed,
                    "rejected": rejected,
                    "frame_hex_prefix": frame.hex()[:96],
                    "does_not_claim_server_behavior": True,
                },
            )
        )
    return rows


def schema_mutations(schema: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for message in schema["critical_vertical_slice"]:
        if message.get("missing_from_global_catalog"):
            continue
        name = message["name"]
        fields = message.get("fields", [])
        if fields:
            rows.append(
                case(
                    "SCHEMA_MUTATION",
                    name,
                    "remove_last_top_level_field",
                    "OFFLINE_SCHEMA_REJECT",
                    "fixture no longer satisfies recovered Global top-level schema",
                    message["top_level_schema_evidence"],
                    details={
                        "original_field_count": len(fields),
                        "mutated_field_count": len(fields) - 1,
                        "does_not_claim_server_behavior": True,
                    },
                )
            )
        rows.append(
            case(
                "SCHEMA_MUTATION",
                name,
                "append_unknown_top_level_field",
                "OFFLINE_SCHEMA_REJECT",
                "fixture exceeds recovered Global top-level schema",
                message["top_level_schema_evidence"],
                details={
                    "original_field_count": len(fields),
                    "mutated_field_count": len(fields) + 1,
                    "does_not_claim_server_behavior": True,
                },
            )
        )
    return rows


def enum_boundary_mutations(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    semantics = state["response_semantics"]
    known_targets = {
        "account_login": {
            1: "CHARACTER_LIST",
            2: "CHARACTER_LIST",
            3: "TERMS_GATE",
            4: "ERROR_OR_EXTERNAL_AUTHORITY",
            5: "ERROR_OR_EXTERNAL_AUTHORITY",
            6: "ERROR_OR_EXTERNAL_AUTHORITY",
            7: "ERROR_OR_EXTERNAL_AUTHORITY",
        },
        "character_create": {
            0: "CHARACTER_LOGIN",
            1: "GENDER_CREATE_NO_ADVANCE",
            2: "GENDER_CREATE_NO_ADVANCE",
            3: "GENDER_CREATE_NO_ADVANCE",
        },
        "character_login": {
            1: "PREBEGIN_INIT",
            2: "PREBEGIN_INIT",
            3: "PREBEGIN_INIT_RECOVERY_EVENT",
            4: "PREBEGIN_INIT",
            0: "ERROR_OR_EXTERNAL_AUTHORITY",
            5: "ERROR_OR_EXTERNAL_AUTHORITY",
            6: "ERROR_OR_EXTERNAL_AUTHORITY",
            7: "ERROR_OR_EXTERNAL_AUTHORITY",
        },
        "battle_entry": {
            1: "BATTLE_ACCEPTED",
            2: "BATTLE_ENTRY_RETRY_WAIT_1.0_SECONDS",
        },
    }
    for family, labels in semantics.items():
        value_to_label = {value: label for label, value in labels.items() if isinstance(value, int)}
        # RETRY_SECONDS is metadata, not an enum member.
        if family == "battle_entry":
            value_to_label.pop(1, None) if value_to_label.get(1) == "RETRY_SECONDS" else None
            value_to_label = {
                value: label
                for label, value in labels.items()
                if label != "RETRY_SECONDS" and isinstance(value, int)
            }
        for value, label in sorted(value_to_label.items()):
            rows.append(
                case(
                    "ENUM_BRANCH",
                    family,
                    f"known_value_{value}_{label}",
                    "GLOBAL_KNOWN_BRANCH",
                    known_targets.get(family, {}).get(value, "GLOBAL_ENUM_VALUE_KNOWN_TARGET_NOT_LIFTED"),
                    "CONFIRMED_GLOBAL_3_0_24_STATE_MACHINE",
                    details={"value": value, "enum_label": label},
                )
            )
        if value_to_label:
            minimum = min(value_to_label)
            maximum = max(value_to_label)
            for boundary in (minimum - 1, maximum + 1):
                if boundary in value_to_label:
                    continue
                rows.append(
                    case(
                        "ENUM_BRANCH",
                        family,
                        f"outside_recovered_enum_{boundary}",
                        "SERVER_BEHAVIOR_UNKNOWN",
                        "do not infer retired-server or client branch beyond recovered enum evidence",
                        "EXTERNAL_OR_UNRESOLVED_EVIDENCE_CEILING",
                        details={
                            "value": boundary,
                            "known_values": sorted(value_to_label),
                        },
                    )
                )
    return rows


def transition_mutations(state: dict[str, Any]) -> list[dict[str, Any]]:
    transitions = state["transitions"]
    states = state["states"]
    rows = []

    exact = {
        (row["from"], row["to"], row.get("message"), row["trigger"])
        for row in transitions
    }

    high_value = [
        ("TITLE", "S_GMCL_BATTLE_RESULT", "battle result before authentication"),
        ("CHARACTER_LOGIN", "S_GMCL_AREA_ENTER", "area enter before field bootstrap"),
        ("AREA_ACTIVE", "S_GMCL_BATTLE_RESULT", "battle result before accepted battle"),
        ("BATTLE_ENTRY_PENDING", "S_GMCL_BATTLE_RESULT", "battle result before battle initialize"),
        ("BATTLE_INITIALIZING", "S_GMCL_QUEST_INFO_STATE_RETURN", "quest return before battle result"),
        ("BOUT_ACTIVE", "S_GMCL_AREA_ENTER", "field area enter during active bout"),
        ("BATTLE_RESULT", "C_GMCL_CHAR_MOVE_REQ", "movement before field return"),
        ("REWARD_PROJECTION", "C_GMCL_BATTLE_ENTRY_REQ", "new encounter before reward return"),
    ]
    messages = {
        row.get("message")
        for row in transitions
        if row.get("message")
    }
    for from_state, message, description in high_value:
        if from_state not in states or message not in messages:
            continue
        if any(
            row["from"] == from_state and row.get("message") == message
            for row in transitions
        ):
            continue
        rows.append(
            case(
                "TRANSITION_ORDER",
                message,
                description,
                "OFFLINE_STATE_MODEL_REJECT",
                f"{message} is not an evidenced outgoing transition from {from_state}",
                "CONFIRMED_GLOBAL_3_0_24_CRITICAL_STATE_MACHINE",
                details={
                    "from_state": from_state,
                    "does_not_claim_server_behavior": True,
                },
            )
        )
    return rows


def retry_mutations(state: dict[str, Any]) -> list[dict[str, Any]]:
    retry = state["response_semantics"]["battle_entry"]
    rows = [
        case(
            "RETRY_TIMING",
            "C_GMCL_BATTLE_ENTRY_REQ_Response",
            "response_code_2",
            "GLOBAL_KNOWN_BRANCH",
            "enter BATTLE_ENTRY_RETRY_WAIT for exactly 1.0 seconds",
            "GLOBAL_DIRECT_ENCOUNTER_NATIVE_EVIDENCE",
            details={
                "code": retry["RETRY_WAIT"],
                "retry_seconds": retry["RETRY_SECONDS"],
            },
        )
    ]
    for mutated in (0.0, 0.5, 2.0):
        rows.append(
            case(
                "RETRY_TIMING",
                "C_GMCL_BATTLE_ENTRY_REQ_Response",
                f"replace_retry_delay_with_{mutated}",
                "EVIDENCE_MISMATCH_REJECT",
                "reconstruction must not replace confirmed 1.0-second retry with another delay",
                "GLOBAL_DIRECT_ENCOUNTER_NATIVE_EVIDENCE",
                details={
                    "confirmed_seconds": retry["RETRY_SECONDS"],
                    "mutated_seconds": mutated,
                },
            )
        )
    return rows


def resource_mutations(map_path: Path | None) -> list[dict[str, Any]]:
    if map_path is None or not map_path.exists():
        return []
    maps = json.loads(map_path.read_text())
    mt = maps["millennium_tree"]
    rows = [
        case(
            "RESOURCE_IDENTITY",
            "Millennium Tree terrain candidate",
            "substitute_002_000_00008_using_texture_similarity_only",
            "EVIDENCE_MISMATCH_REJECT",
            "do not substitute 00008 for 00001: atlases match but decoded map payload/structure differ",
            "GLOBAL_JP_MAP_GENEALOGY",
            details={
                "confirmed_candidate": "002_000_00001",
                "alternative": "002_000_00008",
                "same_chip_atlas": mt["same_chip_atlas_bytes"],
                "same_object_atlas": mt["same_object_atlas_bytes"],
                "same_map_payload": mt["same_map_payload"],
                "same_structure": mt["same_structure_fingerprint"],
            },
        )
    ]
    return rows


def build(args: argparse.Namespace) -> dict[str, Any]:
    twin = load_twin(args.protocol_twin)
    schema = json.loads(args.protocol_schema.read_text())
    state = json.loads(args.state_machine.read_text())

    cases = []
    cases.extend(wire_mutations(twin))
    cases.extend(schema_mutations(schema))
    cases.extend(enum_boundary_mutations(state))
    cases.extend(transition_mutations(state))
    cases.extend(retry_mutations(state))
    cases.extend(resource_mutations(args.map_genealogy))

    cases.sort(key=lambda row: (row["kind"], row["subject"], row["mutation"], row["id"]))
    ids = [row["id"] for row in cases]
    if len(ids) != len(set(ids)):
        raise RuntimeError("non-unique deterministic case IDs")

    class_counts = Counter(row["expected_class"] for row in cases)
    kind_counts = Counter(row["kind"] for row in cases)
    wire_rows = [row for row in cases if row["kind"] == "WIRE_MUTATION"]
    if not wire_rows or not all(row["details"].get("rejected") for row in wire_rows):
        raise RuntimeError("wire mutation suite did not deterministically reject every malformed frame")

    critical_messages = {
        row["name"]
        for row in schema["critical_vertical_slice"]
        if not row.get("missing_from_global_catalog")
    }
    schema_subjects = {
        row["subject"]
        for row in cases
        if row["kind"] == "SCHEMA_MUTATION"
    }
    if not critical_messages.issubset(schema_subjects):
        missing = sorted(critical_messages - schema_subjects)
        raise RuntimeError(f"critical schema mutation coverage gap: {missing}")

    return {
        "provenance": "OFFLINE_MUTATION_SUITE_DERIVED_FROM_CONFIRMED_GLOBAL_3_0_24_EVIDENCE",
        "offline_only": True,
        "sources": {
            "protocol_schema": {
                "path": str(args.protocol_schema),
                "sha256": sha256_file(args.protocol_schema),
            },
            "state_machine": {
                "path": str(args.state_machine),
                "sha256": sha256_file(args.state_machine),
            },
            "protocol_twin": {
                "path": str(args.protocol_twin),
                "sha256": sha256_file(args.protocol_twin),
            },
            "map_genealogy": (
                {
                    "path": str(args.map_genealogy),
                    "sha256": sha256_file(args.map_genealogy),
                }
                if args.map_genealogy and args.map_genealogy.exists()
                else None
            ),
        },
        "coverage": {
            "total_cases": len(cases),
            "kind_counts": dict(sorted(kind_counts.items())),
            "expected_class_counts": dict(sorted(class_counts.items())),
            "critical_schema_messages": len(critical_messages),
            "critical_schema_messages_mutated": len(schema_subjects & critical_messages),
            "wire_mutations_all_rejected": True,
            "known_state_machine_states": state["counts"]["states"],
            "known_state_machine_transitions": state["counts"]["transitions"],
        },
        "cases": cases,
        "policy": {
            "GLOBAL_KNOWN_BRANCH": "Outcome is directly supported by recovered Global client evidence.",
            "OFFLINE_WIRE_CONTRACT_REJECT": "Recovered offline codec rejects malformed framing; this does not claim historical server behavior.",
            "OFFLINE_SCHEMA_REJECT": "Fixture violates recovered Global schema and is rejected by the offline harness before server emulation.",
            "OFFLINE_STATE_MODEL_REJECT": "Sequence contradicts the recovered Global client transition graph; this does not claim server response semantics.",
            "EVIDENCE_MISMATCH_REJECT": "Mutation conflicts with a confirmed recovered fact and must not enter reconstruction.",
            "SERVER_BEHAVIOR_UNKNOWN": "Client evidence is insufficient; preserve as an explicit retired-server evidence ceiling.",
        },
        "guardrails": [
            "No sockets or production game-server calls are used.",
            "Harness rejection is not labeled as historical retired-server rejection.",
            "Unknown enum branches remain unknown rather than guessed.",
            "Malformed-frame behavior is asserted only for the recovered offline codec.",
            "Resource substitutions require byte/structure identity predicates, not visual similarity.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol-schema",
        type=Path,
        default=Path("/home/ubuntu/logres/artifacts/global-jp-protocol-schema-20260924.json"),
    )
    parser.add_argument(
        "--state-machine",
        type=Path,
        default=Path("/home/ubuntu/logres/artifacts/global-3024-state-machine-20260924.json"),
    )
    parser.add_argument(
        "--protocol-twin",
        type=Path,
        default=SCRIPT_DIR / "global3024_protocol_twin.py",
    )
    parser.add_argument(
        "--map-genealogy",
        type=Path,
        default=Path("/home/ubuntu/logres/artifacts/global-jp-map-genealogy-20260924.json"),
    )
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["coverage"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
