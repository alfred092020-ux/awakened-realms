#!/usr/bin/env python3
"""Build and verify deterministic offline Logres critical-loop trace certificates.

The certificate is evidence-only and server-independent. It binds each trace
step to exact state, protocol, resource and available function-semantic hashes.
Server-authored decisions are explicitly classified as stubbed server authority.

Verification rejects illegal transitions, altered evidence hashes, chain breaks,
and any attempt to promote a server-authority step to a proven client fact.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
from typing import Any

PROVENANCE = "ZENITH_OFFLINE_REPLAYABLE_TRACE_CERTIFICATE"

PRIMARY_TRACE_IDS = (
    0, 2, 3, 4, 7, 8, 10, 11, 12, 13,
    16, 17, 18, 21, 22, 23, 24, 25, 26, 27,
)
MOVEMENT_TRACE_IDS = (14,)
NPC_TRACE_IDS = (15,)
RETRY_TRACE_IDS = (16, 17, 19, 20)

ALLOWED_CLASSIFICATIONS = {
    "proven",
    "stubbed_server_authority",
    "lineage_supported",
    "implementation_only",
    "unresolved",
}

RESOURCE_ROLES_BY_STATE = {
    "TITLE": ("title_ui", "audio_bgm_se"),
    "ACCOUNT_AUTH": ("title_ui",),
    "CHARACTER_LIST": ("title_ui",),
    "PREBEGIN_INIT": ("title_ui",),
    "GENDER_CREATE": ("title_ui", "player_actor"),
    "CHARACTER_LOGIN": ("title_ui", "player_actor"),
    "FIELD_SELECT": ("field_map", "player_actor"),
    "FIELD_INFO": ("field_map", "player_actor"),
    "ZONEIN": ("field_map", "player_actor"),
    "AREA_ACTIVE": ("field_map", "player_actor"),
    "FIELD_MOVEMENT": ("field_map", "player_actor"),
    "NPC_INTERACTION": ("field_map", "npc_enemy_encounter"),
    "ENCOUNTER_ELIGIBILITY": ("field_map", "npc_enemy_encounter"),
    "BATTLE_ENTRY_PENDING": ("battle", "npc_enemy_encounter"),
    "BATTLE_ACCEPTED": ("battle", "npc_enemy_encounter"),
    "BATTLE_ENTRY_RETRY_WAIT": ("battle", "npc_enemy_encounter"),
    "BATTLE_INITIALIZING": ("battle", "audio_bgm_se"),
    "BOUT_ACTIVE": ("battle", "audio_bgm_se"),
    "BATTLE_RESULT": ("battle", "reward_result"),
    "REWARD_PROJECTION": ("reward_result", "battle"),
    "FIELD_RETURN": ("field_map", "reward_result"),
}


class CertificateError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise CertificateError(f"{path}: expected JSON object")
    return value


def transition_authority_from_runtime(path: Path) -> dict[int, bool]:
    text = path.read_text()
    pattern = re.compile(
        r"\{\s*id:\s*(\d+),.*?serverAuthority:\s*(true|false),\s*\}",
        re.DOTALL,
    )
    rows = {
        int(match.group(1)): match.group(2) == "true"
        for match in pattern.finditer(text)
    }
    if set(rows) != set(range(28)):
        raise CertificateError(
            f"behavior runtime transition parse mismatch: ids={sorted(rows)}"
        )
    return rows


def protocol_evidence_map(protocol_twin: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    # Prefer critical replay events because they contain exact request wire
    # hashes or explicit server-authority stub policy.
    for row in protocol_twin.get("critical_offline_replay", []):
        name = row.get("message")
        if isinstance(name, str) and name not in result:
            result[name] = row
    for row in protocol_twin.get("fixtures", []):
        name = row.get("name")
        if isinstance(name, str) and name not in result:
            result[name] = row
    return result


def semantic_maps(semantic: dict[str, Any]) -> tuple[
    dict[int, list[str]],
    dict[str, dict[str, Any]],
]:
    transition_functions = {
        int(row["transition_index"]): list(row.get("bound_global_functions", []))
        for row in semantic.get("state_transition_coverage", [])
    }
    functions = {
        row["global_function"]: row
        for row in semantic.get("function_semantics", [])
    }
    return transition_functions, functions


def hash_row(row: Any) -> str:
    return sha256_bytes(canonical_json(row).encode("utf-8"))


def roles_for_transition(transition: dict[str, Any]) -> list[str]:
    roles = set()
    for state in (transition["from"], transition["to"]):
        roles.update(RESOURCE_ROLES_BY_STATE.get(state, ()))
    return sorted(roles)


def resource_evidence(
    binder: dict[str, Any],
    roles: list[str],
) -> list[dict[str, Any]]:
    vertical = binder.get("vertical_slice") or {}
    rows = []
    for role in roles:
        value = vertical.get(role)
        if not isinstance(value, dict):
            rows.append(
                {
                    "role": role,
                    "status": "unresolved",
                    "role_sha256": None,
                    "exact_resource_hashes": [],
                }
            )
            continue
        exact = []
        for key in ("exact_global_resources", "exact_global_packages"):
            for item in value.get(key, []) or []:
                exact.append(
                    {
                        "path": item.get("global_path"),
                        "sha1": item.get("sha1"),
                        "size": item.get("size"),
                        "evidence_sha256": hash_row(item),
                        "authority": item.get("authority"),
                    }
                )
        rows.append(
            {
                "role": role,
                "status": str(value.get("status") or "unresolved"),
                "role_sha256": hash_row(value),
                "exact_resource_hashes": sorted(
                    exact,
                    key=lambda item: (
                        str(item.get("path") or ""),
                        str(item.get("evidence_sha256") or ""),
                    ),
                ),
            }
        )
    return rows


def classify_step(
    transition_id: int,
    *,
    server_authority: bool,
    transition: dict[str, Any],
) -> str:
    if server_authority:
        return "stubbed_server_authority"
    evidence = str(transition.get("evidence") or "")
    if evidence.startswith("GLOBAL_"):
        return "proven"
    return "unresolved"


def build_step(
    *,
    sequence: int,
    transition_id: int,
    transitions: list[dict[str, Any]],
    authority_map: dict[int, bool],
    protocol_by_name: dict[str, dict[str, Any]],
    transition_functions: dict[int, list[str]],
    function_by_name: dict[str, dict[str, Any]],
    binder: dict[str, Any],
) -> dict[str, Any]:
    transition = transitions[transition_id]
    state_hash = hash_row(transition)
    message = transition.get("message")

    protocol_row = protocol_by_name.get(message) if message else None
    protocol_hash = hash_row(protocol_row) if protocol_row is not None else None
    protocol_status = None
    if protocol_row is not None:
        protocol_status = (
            protocol_row.get("status")
            or protocol_row.get("payload_encoding_status")
            or protocol_row.get("schema_status")
        )

    function_rows = []
    for name in sorted(transition_functions.get(transition_id, [])):
        row = function_by_name.get(name)
        if row is None:
            function_rows.append(
                {
                    "global_function": name,
                    "status": "unresolved",
                    "evidence_sha256": None,
                }
            )
        else:
            function_rows.append(
                {
                    "global_function": name,
                    "status": "high_confidence_semantic_lift",
                    "evidence_sha256": hash_row(row),
                }
            )

    resource_rows = resource_evidence(
        binder,
        roles_for_transition(transition),
    )
    server_authority = authority_map[transition_id]
    classification = classify_step(
        transition_id,
        server_authority=server_authority,
        transition=transition,
    )
    if classification not in ALLOWED_CLASSIFICATIONS:
        raise CertificateError(
            f"invalid classification {classification} for transition {transition_id}"
        )

    evidence_bundle = {
        "state_transition_sha256": state_hash,
        "protocol_evidence_sha256": protocol_hash,
        "protocol_status": protocol_status,
        "function_evidence": function_rows,
        "resource_evidence": resource_rows,
    }
    step_core = {
        "sequence": sequence,
        "transition_id": transition_id,
        "from": transition["from"],
        "to": transition["to"],
        "message": message,
        "guard": transition.get("guard"),
        "action": transition.get("action"),
        "source_evidence": transition.get("evidence"),
        "classification": classification,
        "server_authority": server_authority,
        "evidence": evidence_bundle,
    }
    return {
        **step_core,
        "step_sha256": hash_row(step_core),
    }


def build_trace(
    name: str,
    ids: tuple[int, ...],
    *,
    transitions: list[dict[str, Any]],
    authority_map: dict[int, bool],
    protocol_by_name: dict[str, dict[str, Any]],
    transition_functions: dict[int, list[str]],
    function_by_name: dict[str, dict[str, Any]],
    binder: dict[str, Any],
) -> dict[str, Any]:
    steps = [
        build_step(
            sequence=index,
            transition_id=transition_id,
            transitions=transitions,
            authority_map=authority_map,
            protocol_by_name=protocol_by_name,
            transition_functions=transition_functions,
            function_by_name=function_by_name,
            binder=binder,
        )
        for index, transition_id in enumerate(ids)
    ]
    for previous, current in zip(steps, steps[1:]):
        if previous["to"] != current["from"]:
            raise CertificateError(
                f"{name}: chain break {previous['transition_id']} "
                f"{previous['to']} != {current['from']} "
                f"for transition {current['transition_id']}"
            )
    trace_core = {
        "name": name,
        "initial_state": steps[0]["from"] if steps else None,
        "final_state": steps[-1]["to"] if steps else None,
        "transition_ids": list(ids),
        "steps": steps,
    }
    return {
        **trace_core,
        "trace_sha256": hash_row(trace_core),
    }


def validate_step(
    step: dict[str, Any],
    *,
    transitions: list[dict[str, Any]],
    authority_map: dict[int, bool],
    protocol_by_name: dict[str, dict[str, Any]],
    transition_functions: dict[int, list[str]],
    function_by_name: dict[str, dict[str, Any]],
    binder: dict[str, Any],
) -> list[str]:
    errors = []
    transition_id = step.get("transition_id")
    if not isinstance(transition_id, int) or not (0 <= transition_id < len(transitions)):
        return [f"illegal transition id {transition_id}"]

    expected = build_step(
        sequence=int(step.get("sequence", -1)),
        transition_id=transition_id,
        transitions=transitions,
        authority_map=authority_map,
        protocol_by_name=protocol_by_name,
        transition_functions=transition_functions,
        function_by_name=function_by_name,
        binder=binder,
    )
    for key in (
        "from",
        "to",
        "message",
        "guard",
        "action",
        "source_evidence",
        "server_authority",
        "evidence",
    ):
        if step.get(key) != expected.get(key):
            errors.append(
                f"transition {transition_id}: {key} differs from evidence"
            )

    classification = step.get("classification")
    if classification not in ALLOWED_CLASSIFICATIONS:
        errors.append(
            f"transition {transition_id}: unsupported classification {classification}"
        )
    if authority_map[transition_id] and classification == "proven":
        errors.append(
            f"transition {transition_id}: unsupported confidence promotion "
            "of server-authority step to proven"
        )
    if classification != expected["classification"]:
        errors.append(
            f"transition {transition_id}: classification {classification} "
            f"!= expected {expected['classification']}"
        )

    expected_core = {
        key: step.get(key)
        for key in (
            "sequence",
            "transition_id",
            "from",
            "to",
            "message",
            "guard",
            "action",
            "source_evidence",
            "classification",
            "server_authority",
            "evidence",
        )
    }
    if step.get("step_sha256") != hash_row(expected_core):
        errors.append(
            f"transition {transition_id}: step SHA-256 mismatch"
        )
    return errors


def validate_certificate(
    certificate: dict[str, Any],
    *,
    args: argparse.Namespace,
) -> list[str]:
    errors = []
    if certificate.get("provenance") != PROVENANCE:
        errors.append("certificate provenance mismatch")
    if certificate.get("offline_only") is not True:
        errors.append("certificate must be offline_only")
    if certificate.get("production_server_access") is not False:
        errors.append("certificate must forbid production server access")

    sources = certificate.get("sources") or {}
    for key, path in source_paths(args).items():
        row = sources.get(key)
        if not isinstance(row, dict):
            errors.append(f"missing source record {key}")
            continue
        actual = sha256_file(path)
        if row.get("sha256") != actual:
            errors.append(
                f"source hash mismatch {key}: {row.get('sha256')} != {actual}"
            )

    state = load(args.state_machine)
    protocol_twin = load(args.protocol_twin)
    semantic = load(args.semantic_lift)
    binder = load(args.asset_binder)
    authority_map = transition_authority_from_runtime(
        args.behavior_runtime
    )
    transitions = state["transitions"]
    protocol_by_name = protocol_evidence_map(protocol_twin)
    transition_functions, function_by_name = semantic_maps(semantic)

    traces = certificate.get("traces")
    if not isinstance(traces, list):
        return errors + ["certificate traces must be a list"]

    for trace in traces:
        name = str(trace.get("name") or "")
        steps = trace.get("steps") or []
        ids = trace.get("transition_ids") or []
        if ids != [step.get("transition_id") for step in steps]:
            errors.append(f"{name}: transition_ids disagree with steps")
        for index, step in enumerate(steps):
            if step.get("sequence") != index:
                errors.append(f"{name}: sequence mismatch at {index}")
            errors.extend(
                f"{name}: {message}"
                for message in validate_step(
                    step,
                    transitions=transitions,
                    authority_map=authority_map,
                    protocol_by_name=protocol_by_name,
                    transition_functions=transition_functions,
                    function_by_name=function_by_name,
                    binder=binder,
                )
            )
        for previous, current in zip(steps, steps[1:]):
            if previous.get("to") != current.get("from"):
                errors.append(
                    f"{name}: illegal chain {previous.get('to')} -> {current.get('from')}"
                )
        trace_core = {
            "name": trace.get("name"),
            "initial_state": trace.get("initial_state"),
            "final_state": trace.get("final_state"),
            "transition_ids": trace.get("transition_ids"),
            "steps": steps,
        }
        if trace.get("trace_sha256") != hash_row(trace_core):
            errors.append(f"{name}: trace SHA-256 mismatch")

    core = {
        key: certificate.get(key)
        for key in (
            "provenance",
            "offline_only",
            "production_server_access",
            "sources",
            "source_bundle_sha256",
            "classifications",
            "traces",
            "counts",
            "guardrails",
        )
    }
    if certificate.get("certificate_id") != hash_row(core):
        errors.append("certificate_id mismatch")
    return errors


def source_paths(args: argparse.Namespace) -> dict[str, Path]:
    return {
        "state_machine": args.state_machine,
        "behavior_twin": args.behavior_twin,
        "behavior_runtime": args.behavior_runtime,
        "protocol_twin": args.protocol_twin,
        "semantic_lift": args.semantic_lift,
        "asset_binder": args.asset_binder,
        "consistency_certificate": args.consistency_certificate,
        "differential_emulator": args.differential_emulator,
    }


def build_certificate(args: argparse.Namespace) -> dict[str, Any]:
    state = load(args.state_machine)
    behavior = load(args.behavior_twin)
    protocol_twin = load(args.protocol_twin)
    semantic = load(args.semantic_lift)
    binder = load(args.asset_binder)
    consistency = load(args.consistency_certificate)
    differential = load(args.differential_emulator)

    if consistency.get("status") != "PASS":
        raise CertificateError("consistency prerequisite is not PASS")
    if int(consistency["invariant_counts"]["failed"]) != 0:
        raise CertificateError("consistency prerequisite has failed invariants")
    if protocol_twin.get("network_policy") != "NO_SOCKET_OR_REMOTE_SERVER_ACCESS":
        raise CertificateError("protocol twin is not offline-only")
    if behavior.get("offline_only") is not True:
        raise CertificateError("behavior twin is not offline-only")
    if len(state.get("transitions", [])) != 28:
        raise CertificateError("state machine transition count changed")
    if int(behavior["counts"]["transitions"]) != 28:
        raise CertificateError("behavior twin transition count changed")
    if int(behavior["counts"]["successful_first_character_trace_steps"]) != 20:
        raise CertificateError("behavior critical trace step count changed")

    authority_map = transition_authority_from_runtime(
        args.behavior_runtime
    )
    if sum(authority_map.values()) != int(
        behavior["counts"]["explicit_server_authority_transitions"]
    ):
        raise CertificateError(
            "runtime server-authority transition count disagrees with twin artifact"
        )

    transitions = state["transitions"]
    protocol_by_name = protocol_evidence_map(protocol_twin)
    transition_functions, function_by_name = semantic_maps(semantic)

    traces = [
        build_trace(
            "first_character_critical_loop",
            PRIMARY_TRACE_IDS,
            transitions=transitions,
            authority_map=authority_map,
            protocol_by_name=protocol_by_name,
            transition_functions=transition_functions,
            function_by_name=function_by_name,
            binder=binder,
        ),
        build_trace(
            "field_movement_side_branch",
            MOVEMENT_TRACE_IDS,
            transitions=transitions,
            authority_map=authority_map,
            protocol_by_name=protocol_by_name,
            transition_functions=transition_functions,
            function_by_name=function_by_name,
            binder=binder,
        ),
        build_trace(
            "npc_interaction_side_branch",
            NPC_TRACE_IDS,
            transitions=transitions,
            authority_map=authority_map,
            protocol_by_name=protocol_by_name,
            transition_functions=transition_functions,
            function_by_name=function_by_name,
            binder=binder,
        ),
        build_trace(
            "battle_entry_retry_side_branch",
            RETRY_TRACE_IDS,
            transitions=transitions,
            authority_map=authority_map,
            protocol_by_name=protocol_by_name,
            transition_functions=transition_functions,
            function_by_name=function_by_name,
            binder=binder,
        ),
    ]

    all_steps = [
        step for trace in traces for step in trace["steps"]
    ]
    classifications = {
        classification: sum(
            step["classification"] == classification
            for step in all_steps
        )
        for classification in sorted(ALLOWED_CLASSIFICATIONS)
    }
    sources = {
        key: {
            "path": str(path),
            "sha256": sha256_file(path),
        }
        for key, path in source_paths(args).items()
    }
    source_bundle_sha = hash_row(sources)

    counts = {
        "traces": len(traces),
        "total_steps": len(all_steps),
        "primary_trace_steps": len(traces[0]["steps"]),
        "unique_transition_ids": len(
            {step["transition_id"] for step in all_steps}
        ),
        "state_machine_transitions": len(transitions),
        "server_authority_steps": sum(
            step["server_authority"] for step in all_steps
        ),
        "steps_with_protocol_hash": sum(
            bool(step["evidence"]["protocol_evidence_sha256"])
            for step in all_steps
        ),
        "steps_with_function_hash": sum(
            bool(step["evidence"]["function_evidence"])
            for step in all_steps
        ),
        "steps_with_resource_hash": sum(
            bool(step["evidence"]["resource_evidence"])
            for step in all_steps
        ),
        "consistency_invariants_passed": int(
            consistency["invariant_counts"]["passed"]
        ),
        "differential_checks": int(
            differential["counts"]["checks"]
        ),
    }

    core = {
        "provenance": PROVENANCE,
        "offline_only": True,
        "production_server_access": False,
        "sources": sources,
        "source_bundle_sha256": source_bundle_sha,
        "classifications": classifications,
        "traces": traces,
        "counts": counts,
        "guardrails": [
            "No socket, production server, or live retired backend is required for build or replay.",
            "SERVER_AUTHORITY_STUB transitions can never be promoted to proven client facts.",
            "Current-JP lineage cannot replace historical Global evidence without an explicit identity predicate.",
            "Missing protocol/function/resource dimensions remain explicit rather than being fabricated.",
            "Illegal transition IDs, state-chain breaks and altered evidence hashes fail verification.",
        ],
    }
    certificate = {
        **core,
        "certificate_id": hash_row(core),
    }
    errors = validate_certificate(certificate, args=args)
    if errors:
        raise CertificateError(
            "generated certificate failed self-verification: "
            + "; ".join(errors[:20])
        )
    return certificate


def self_test(certificate: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    results = []

    illegal = copy.deepcopy(certificate)
    illegal["traces"][0]["steps"][0]["transition_id"] = 99
    illegal_errors = validate_certificate(illegal, args=args)
    results.append(
        {
            "name": "illegal_transition_rejected",
            "pass": any("illegal transition id 99" in error for error in illegal_errors),
            "errors": illegal_errors[:5],
        }
    )

    promoted = copy.deepcopy(certificate)
    server_step = next(
        step
        for step in promoted["traces"][0]["steps"]
        if step["server_authority"]
    )
    server_step["classification"] = "proven"
    # Recompute the step hash so rejection must come from authority policy,
    # not merely hash tampering.
    step_core = {
        key: server_step.get(key)
        for key in (
            "sequence",
            "transition_id",
            "from",
            "to",
            "message",
            "guard",
            "action",
            "source_evidence",
            "classification",
            "server_authority",
            "evidence",
        )
    }
    server_step["step_sha256"] = hash_row(step_core)
    promoted_errors = validate_certificate(promoted, args=args)
    results.append(
        {
            "name": "server_authority_promotion_rejected",
            "pass": any(
                "unsupported confidence promotion" in error
                for error in promoted_errors
            ),
            "errors": promoted_errors[:5],
        }
    )

    altered = copy.deepcopy(certificate)
    altered["traces"][0]["steps"][0]["evidence"][
        "state_transition_sha256"
    ] = "0" * 64
    altered_errors = validate_certificate(altered, args=args)
    results.append(
        {
            "name": "altered_evidence_hash_rejected",
            "pass": any(
                "evidence differs from evidence" in error
                or "evidence" in error
                for error in altered_errors
            ),
            "errors": altered_errors[:5],
        }
    )

    return {
        "tests": results,
        "passed": sum(row["pass"] for row in results),
        "total": len(results),
        "all_pass": all(row["pass"] for row in results),
    }


def add_common_args(p: argparse.ArgumentParser) -> None:
    root = Path("/home/ubuntu/logres/artifacts")
    p.add_argument(
        "--state-machine",
        type=Path,
        default=root / "global-3024-state-machine-20260924.json",
    )
    p.add_argument(
        "--behavior-twin",
        type=Path,
        default=root / "global3024-behavior-twin-20260924.json",
    )
    p.add_argument(
        "--behavior-runtime",
        type=Path,
        default=Path(
            "src/game/logres/reverse/LogresGlobalBehaviorTwin.ts"
        ),
    )
    p.add_argument(
        "--protocol-twin",
        type=Path,
        default=root / "global3024-offline-protocol-twin-20260924.json",
    )
    p.add_argument(
        "--semantic-lift",
        type=Path,
        default=root / "global-jp-semantic-lift-20260924.json",
    )
    p.add_argument(
        "--asset-binder",
        type=Path,
        default=root / "global-asset-behavior-bindings-20260924.json",
    )
    p.add_argument(
        "--consistency-certificate",
        type=Path,
        default=root / "logres-reconstruction-consistency-certificate-20260924.json",
    )
    p.add_argument(
        "--differential-emulator",
        type=Path,
        default=root / "global3024-differential-emulator-20260924.json",
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    build_p = sub.add_parser("build")
    add_common_args(build_p)
    build_p.add_argument("--output", type=Path, required=True)

    verify_p = sub.add_parser("verify")
    add_common_args(verify_p)
    verify_p.add_argument("certificate", type=Path)

    test_p = sub.add_parser("self-test")
    add_common_args(test_p)
    test_p.add_argument("certificate", type=Path)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "build":
            certificate = build_certificate(args)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(certificate, indent=2, sort_keys=True) + "\n"
            )
            print(
                json.dumps(
                    {
                        "certificate_id": certificate["certificate_id"],
                        "counts": certificate["counts"],
                        "classifications": certificate["classifications"],
                        "sha256": sha256_file(args.output),
                    },
                    sort_keys=True,
                )
            )
            return 0

        certificate = load(args.certificate)
        if args.command == "verify":
            errors = validate_certificate(certificate, args=args)
            print(
                json.dumps(
                    {
                        "status": "PASS" if not errors else "REJECTED",
                        "errors": errors,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0 if not errors else 2

        result = self_test(certificate, args)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["all_pass"] else 2

    except (CertificateError, OSError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "status": "REJECTED",
                    "error": type(exc).__name__,
                    "message": str(exc),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
