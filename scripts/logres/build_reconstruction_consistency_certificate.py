#!/usr/bin/env python3
"""Build a deterministic cross-artifact consistency certificate for Logres.

A PASS means the recovered evidence domains agree with each other and their
declared source hashes. It never means retired-server internals are known.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected object")
    return value


def source_check(owner: str, label: str, path_text: str, expected: str) -> dict[str, Any]:
    path = Path(path_text)
    if not path.is_file():
        return {
            "owner": owner,
            "label": label,
            "path": path_text,
            "expected_sha256": expected,
            "status": "MISSING_SOURCE_PATH",
        }
    actual = sha256_file(path)
    return {
        "owner": owner,
        "label": label,
        "path": path_text,
        "expected_sha256": expected,
        "actual_sha256": actual,
        "status": "PASS" if actual == expected else "STALE_HASH",
    }


def collect_declared_sources(
    owner: str,
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sources = payload.get("sources")
    if isinstance(sources, dict):
        for label, value in sorted(sources.items()):
            if (
                isinstance(value, dict)
                and isinstance(value.get("path"), str)
                and isinstance(value.get("sha256"), str)
            ):
                rows.append(
                    source_check(
                        owner,
                        str(label),
                        value["path"],
                        value["sha256"],
                    )
                )

    # The state-machine artifact predates the uniform {path,sha256} source shape.
    source = payload.get("source")
    if isinstance(source, dict):
        path_text = source.get("protocol_schema")
        expected = source.get("protocol_schema_sha256")
        if isinstance(path_text, str) and isinstance(expected, str):
            rows.append(source_check(owner, "protocol_schema", path_text, expected))

    # Offline twin uses one source-schema record instead of sources{}.
    source_schema = payload.get("source_schema")
    if (
        isinstance(source_schema, dict)
        and isinstance(source_schema.get("path"), str)
        and isinstance(source_schema.get("sha256"), str)
    ):
        rows.append(
            source_check(
                owner,
                "source_schema",
                source_schema["path"],
                source_schema["sha256"],
            )
        )
    return rows


def build(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "protocol": args.protocol_schema,
        "state": args.state_machine,
        "twin": args.protocol_twin,
        "map": args.map_genealogy,
        "resource": args.resource_genealogy,
        "semantic": args.resource_semantic_graph,
        "fuzzer": args.evidence_fuzzer,
        "arbiter": args.contradiction_arbiter,
    }
    artifacts = {name: load(path) for name, path in paths.items()}
    hashes = {name: sha256_file(path) for name, path in paths.items()}

    invariants: list[dict[str, Any]] = []

    def check(
        invariant_id: str,
        ok: bool,
        statement: str,
        *,
        details: Any = None,
        severity: str = "ERROR",
    ) -> None:
        invariants.append(
            {
                "id": invariant_id,
                "status": "PASS" if ok else "FAIL",
                "severity": severity,
                "statement": statement,
                "details": details,
            }
        )

    protocol = artifacts["protocol"]
    state = artifacts["state"]
    twin = artifacts["twin"]
    maps = artifacts["map"]
    resource = artifacts["resource"]
    semantic = artifacts["semantic"]
    fuzzer = artifacts["fuzzer"]
    arbiter = artifacts["arbiter"]

    # Protocol corpus invariants.
    pc = protocol["counts"]
    check(
        "protocol.total",
        pc["global_messages"] == 631,
        "Global protocol catalog contains exactly 631 recovered procedures.",
        details=pc["global_messages"],
    )
    check(
        "protocol.coverage",
        pc["global_generator_schema_messages"] + pc["global_handler_schema_messages"]
        == pc["global_messages"]
        and pc["global_unresolved_top_level_schema_messages"] == 0,
        "Every Global procedure has a recovered top-level schema source.",
        details={
            "generator": pc["global_generator_schema_messages"],
            "handler": pc["global_handler_schema_messages"],
            "unresolved": pc["global_unresolved_top_level_schema_messages"],
        },
    )

    protocol_by_name = {row["name"]: row for row in protocol["messages"]}
    state_protocol_ids = state["protocol_ids"]
    opcode_mismatches = []
    missing_protocol = []
    for name, opcode in sorted(state_protocol_ids.items()):
        row = protocol_by_name.get(name)
        if row is None:
            missing_protocol.append(name)
        elif str(row["opcode_hex"]).lower() != str(opcode).lower():
            opcode_mismatches.append(
                {"name": name, "state": opcode, "protocol": row["opcode_hex"]}
            )
    check(
        "state.protocol_bindings",
        not missing_protocol
        and not opcode_mismatches
        and len(state_protocol_ids) == state["counts"]["bound_protocol_ids"] == 30,
        "All 30 critical state-machine protocol bindings resolve to the exact Global opcode catalog.",
        details={
            "missing": missing_protocol,
            "opcode_mismatches": opcode_mismatches,
            "bound": len(state_protocol_ids),
        },
    )

    states = set(state["states"])
    bad_transition_states = []
    bad_transition_messages = []
    for index, row in enumerate(state["transitions"]):
        if row["from"] not in states or row["to"] not in states:
            bad_transition_states.append(
                {"index": index, "from": row["from"], "to": row["to"]}
            )
        message = row.get("message")
        if message and message not in state_protocol_ids:
            bad_transition_messages.append({"index": index, "message": message})
    check(
        "state.graph_integrity",
        not bad_transition_states
        and not bad_transition_messages
        and len(states) == state["counts"]["states"] == 23
        and len(state["transitions"]) == state["counts"]["transitions"] == 28,
        "State graph endpoints, message bindings and declared counts are internally consistent.",
        details={
            "bad_states": bad_transition_states,
            "bad_messages": bad_transition_messages,
            "states": len(states),
            "transitions": len(state["transitions"]),
        },
    )
    retry = state["response_semantics"]["battle_entry"]
    check(
        "state.retry_semantics",
        retry["RETRY_WAIT"] == 2 and float(retry["RETRY_SECONDS"]) == 1.0,
        "Battle-entry retry remains code 2 with exactly 1.0 second wait.",
        details=retry,
    )

    # Offline protocol twin invariants.
    check(
        "twin.protocol_coverage",
        twin["fixture_counts"]["total_messages"] == pc["global_messages"] == 631,
        "Offline protocol twin accounts for the complete recovered Global procedure set.",
        details=twin["fixture_counts"],
    )
    replay = twin["critical_replay_counts"]
    check(
        "twin.critical_replay",
        replay["events"] == state["counts"]["bound_protocol_ids"] == 30
        and replay["exact_client_request_frames"] + replay["server_authority_stubs"]
        == replay["events"],
        "Critical offline replay covers the same 30-message boundary as the recovered state machine.",
        details=replay,
    )

    # Fuzzer invariants.
    fc = fuzzer["coverage"]
    check(
        "fuzzer.coverage",
        fc["critical_schema_messages"]
        == fc["critical_schema_messages_mutated"]
        == state["counts"]["bound_protocol_ids"]
        == 30
        and fc["known_state_machine_states"] == state["counts"]["states"]
        and fc["known_state_machine_transitions"] == state["counts"]["transitions"],
        "Evidence fuzzer covers every critical schema message and the exact recovered state graph dimensions.",
        details=fc,
    )
    check(
        "fuzzer.wire_rejection",
        fc["kind_counts"]["WIRE_MUTATION"] == 7
        and fc["expected_class_counts"]["OFFLINE_WIRE_CONTRACT_REJECT"] == 7
        and fc["wire_mutations_all_rejected"] is True,
        "All seven malformed recovered-wire mutations are rejected offline.",
        details={
            "wire_cases": fc["kind_counts"]["WIRE_MUTATION"],
            "wire_rejects": fc["expected_class_counts"]["OFFLINE_WIRE_CONTRACT_REJECT"],
        },
    )

    # Map/resource lineage invariants.
    mt = maps["millennium_tree"]
    global_map_row = next(
        (
            row
            for row in maps["global_to_jp"]
            if row.get("base_id") == "002_000_00001"
        ),
        None,
    )
    check(
        "map.millennium_tree_identity",
        bool(global_map_row)
        and global_map_row["lineage_grade"] == "GLOBAL_JP_IDENTICAL"
        and mt["same_chip_atlas_bytes"] is True
        and mt["same_object_atlas_bytes"] is True
        and mt["same_map_payload"] is False
        and mt["same_structure_fingerprint"] is False,
        "Millennium Tree candidate 00001 has exact Global↔JP package continuity while 00008 is rejected as a texture-only structural mismatch.",
        details={
            "lineage": global_map_row,
            "same_chip_atlas": mt["same_chip_atlas_bytes"],
            "same_object_atlas": mt["same_object_atlas_bytes"],
            "same_map_payload_00008": mt["same_map_payload"],
            "same_structure_00008": mt["same_structure_fingerprint"],
        },
    )

    exact_map_edges = [
        row
        for row in resource["exact_identity_edges"]
        if row["global_path"] == "map-002/002_000_00001.mbn"
        and row["jp_path"] == "map/002_000_00001.mbn"
    ]
    check(
        "resource.map_crosswalk",
        len(exact_map_edges) == 1
        and resource["counts"]["exact_identity_edges"] == 14
        and resource["counts"]["jp_manifest_records"] == 31241,
        "Resource genealogy independently corroborates Millennium Tree package continuity and exact release-manifest cardinality.",
        details={
            "millennium_tree_edges": exact_map_edges,
            "exact_identity_edges": resource["counts"]["exact_identity_edges"],
            "jp_manifest_records": resource["counts"]["jp_manifest_records"],
        },
    )

    sgc = semantic["counts"]
    edge_counts = sgc["edge_relations"]
    check(
        "semantic.lineage_counts",
        edge_counts["EXACT_BYTES_LINEAGE"] == resource["counts"]["exact_identity_edges"] == 14
        and edge_counts["SAME_PATH_CHANGED_LINEAGE"]
        == resource["counts"]["same_path_changed_edges"]
        == 15,
        "Semantic resource graph preserves exact and changed-path resource genealogy counts.",
        details={
            "semantic_exact": edge_counts["EXACT_BYTES_LINEAGE"],
            "resource_exact": resource["counts"]["exact_identity_edges"],
            "semantic_changed": edge_counts["SAME_PATH_CHANGED_LINEAGE"],
            "resource_changed": resource["counts"]["same_path_changed_edges"],
        },
    )
    terrain_count = maps["inventory"]["jp_categories"]["terrain"]
    check(
        "semantic.map_atlas_counts",
        edge_counts["MAP_USES_CHIP_ATLAS"] == terrain_count == 1263
        and edge_counts["MAP_USES_OBJECT_ATLAS"] == terrain_count,
        "Every decoded terrain package has one semantic chip-atlas and object-atlas relation.",
        details={
            "terrain": terrain_count,
            "chip_edges": edge_counts["MAP_USES_CHIP_ATLAS"],
            "object_edges": edge_counts["MAP_USES_OBJECT_ATLAS"],
        },
    )

    # Contradiction arbitration invariants.
    winner_authorities = arbiter["counts"]["winner_authorities"]
    check(
        "arbiter.no_weak_winners",
        "SPECULATION_OR_UNRESOLVED" not in winner_authorities
        and arbiter["creates_new_facts"] is False,
        "Contradiction arbiter never promotes speculation into a winning historical fact.",
        details=winner_authorities,
    )
    state_result = next(
        (row for row in arbiter["results"] if row["task_id"] == "GJP-STATE-MACHINE-001"),
        None,
    )
    tutorial_result = next(
        (row for row in arbiter["results"] if row["task_id"] == "G17-TUT-001"),
        None,
    )
    check(
        "arbiter.state_machine_authority",
        bool(state_result)
        and state_result["status"] == "RESOLVED_BY_AUTHORITY"
        and any(
            row["authority"] == "GLOBAL_DIRECT"
            for row in state_result["winner_claims"]
        ),
        "State-machine conflict resolves to direct Global evidence.",
        details=state_result,
    )
    check(
        "arbiter.tutorial_tie_preserved",
        bool(tutorial_result)
        and tutorial_result["status"] == "UNRESOLVED_SAME_AUTHORITY_TIE"
        and not tutorial_result["winner_claims"],
        "Same-authority Millennium Tree historical-video disagreement remains unresolved.",
        details=tutorial_result,
    )

    # Declared source-hash invariants.
    source_rows: list[dict[str, Any]] = []
    for name, payload in artifacts.items():
        source_rows.extend(collect_declared_sources(name, payload))

    stale = [row for row in source_rows if row["status"] == "STALE_HASH"]
    missing = [row for row in source_rows if row["status"] == "MISSING_SOURCE_PATH"]
    check(
        "sources.no_stale_hashes",
        not stale,
        "No available declared source path has drifted from its recorded SHA-256.",
        details={"checked": len(source_rows), "stale": stale, "missing": missing},
    )

    # The important cross-artifact hashes must be linked explicitly even if an
    # old worker worktree source path disappears later.
    check(
        "sources.state_protocol_hash",
        state["source"]["protocol_schema_sha256"] == hashes["protocol"],
        "State-machine artifact binds to the exact protocol-schema artifact bytes.",
        details={
            "declared": state["source"]["protocol_schema_sha256"],
            "actual": hashes["protocol"],
        },
    )
    check(
        "sources.fuzzer_core_hashes",
        fuzzer["sources"]["protocol_schema"]["sha256"] == hashes["protocol"]
        and fuzzer["sources"]["state_machine"]["sha256"] == hashes["state"]
        and fuzzer["sources"]["map_genealogy"]["sha256"] == hashes["map"],
        "Evidence fuzzer binds to the exact protocol, state and map evidence artifacts.",
        details={
            "protocol": fuzzer["sources"]["protocol_schema"]["sha256"],
            "state": fuzzer["sources"]["state_machine"]["sha256"],
            "map": fuzzer["sources"]["map_genealogy"]["sha256"],
        },
    )
    check(
        "sources.semantic_core_hashes",
        semantic["sources"]["map_genealogy"]["sha256"] == hashes["map"]
        and semantic["sources"]["resource_genealogy"]["sha256"] == hashes["resource"],
        "Semantic resource graph binds to the exact map/resource genealogy artifacts.",
        details={
            "map": semantic["sources"]["map_genealogy"]["sha256"],
            "resource": semantic["sources"]["resource_genealogy"]["sha256"],
        },
    )

    # Arbiter's own snapshot hashes must still agree where paths remain present.
    arbiter_drift = []
    for path_text, expected in sorted(arbiter.get("artifact_hashes", {}).items()):
        path = Path(path_text)
        if path.is_file():
            actual = sha256_file(path)
            if actual != expected:
                arbiter_drift.append(
                    {"path": path_text, "expected": expected, "actual": actual}
                )
    check(
        "sources.arbiter_snapshot_hashes",
        not arbiter_drift,
        "Available artifacts snapshotted by the contradiction arbiter have not drifted.",
        details=arbiter_drift,
    )

    failures = [
        row for row in invariants
        if row["status"] == "FAIL" and row["severity"] == "ERROR"
    ]
    core = {
        "artifact_hashes": hashes,
        "invariants": invariants,
        "scope": {
            "protocol_messages": pc["global_messages"],
            "state_machine_states": state["counts"]["states"],
            "state_machine_transitions": state["counts"]["transitions"],
            "critical_protocol_bindings": state["counts"]["bound_protocol_ids"],
            "jp_manifest_records": resource["counts"]["jp_manifest_records"],
            "jp_map_related_packages": maps["inventory"]["jp_map_related_packages"],
            "semantic_resource_nodes": sgc["nodes"],
            "semantic_resource_edges": sgc["edges"],
            "fuzzer_cases": fc["total_cases"],
            "explicit_conflict_tasks": arbiter["counts"]["explicit_conflict_tasks"],
        },
        "limitations": [
            "PASS certifies cross-artifact consistency, not completeness of retired-server validation, persistence, formulas or database semantics.",
            "Current-JP-only data remains non-authoritative unless an explicit identity/lineage predicate exists.",
            "Same-authority evidence disagreements remain unresolved.",
            "Function-level semantic lifting is outside this certificate until GJP-FUNC-MATCH-001 completes.",
        ],
        "missing_source_paths": missing,
    }
    certificate_id = stable_hash(core)

    return {
        "provenance": "ZENITH_DETERMINISTIC_CROSS_ARTIFACT_CONSISTENCY_CERTIFICATE",
        "status": "PASS" if not failures else "FAIL",
        "certificate_id": certificate_id,
        "creates_new_historical_facts": False,
        "artifact_hashes": hashes,
        "scope": core["scope"],
        "invariant_counts": {
            "total": len(invariants),
            "passed": sum(row["status"] == "PASS" for row in invariants),
            "failed": len(failures),
            "missing_source_paths": len(missing),
        },
        "invariants": invariants,
        "limitations": core["limitations"],
        "missing_source_paths": missing,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path("/home/ubuntu/logres/artifacts")
    parser.add_argument("--protocol-schema", type=Path, default=root / "global-jp-protocol-schema-20260924.json")
    parser.add_argument("--state-machine", type=Path, default=root / "global-3024-state-machine-20260924.json")
    parser.add_argument("--protocol-twin", type=Path, default=root / "global3024-offline-protocol-twin-20260924.json")
    parser.add_argument("--map-genealogy", type=Path, default=root / "global-jp-map-genealogy-20260924.json")
    parser.add_argument("--resource-genealogy", type=Path, default=root / "global-jp-resource-genealogy-20260924.json")
    parser.add_argument("--resource-semantic-graph", type=Path, default=root / "global-jp-resource-semantic-graph-20260924.json")
    parser.add_argument("--evidence-fuzzer", type=Path, default=root / "global3024-evidence-fuzzer-20260924.json")
    parser.add_argument("--contradiction-arbiter", type=Path, default=root / "global-contradiction-arbiter-20260924.json")
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": result["status"],
        "certificate_id": result["certificate_id"],
        "invariant_counts": result["invariant_counts"],
        "scope": result["scope"],
    }, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
