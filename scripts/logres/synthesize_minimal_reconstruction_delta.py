#!/usr/bin/env python3
"""Synthesize the smallest evidence-sufficient reconstruction delta.

This tool never applies, commits, merges, or deploys a patch. It reads a
certified differential packet and compares it with a regenerated current
differential plus truth/consistency certificates. If the certified gap is
already satisfied in canonical code, the smallest valid delta is the empty
set. If the gap is still active, the tool emits only the bounded file scope,
verification plan, evidence hashes, and rollback predicate required for a
separate implementation worker.

Historical claims fail closed: current-JP evidence or unresolved server
semantics can never authorize a Global behavior patch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

PROVENANCE = "ZENITH_EVIDENCE_SUFFICIENT_MINIMAL_RECONSTRUCTION_SYNTHESIS"
DEFAULT_ROOT = Path("/home/ubuntu/logres")
DEFAULT_REPO = DEFAULT_ROOT / "src/awakened-realms"
DEFAULT_PACKET = "DIFF-FIX-BATTLE-ENTRY-BOUNDARY"

DEFAULT_TESTS = (
    "tests/ReconstructedLogresEncounterAuthority.test.ts",
    "tests/ReconstructedLogresBattleEntryBridge.test.ts",
    "tests/LogresGlobalDifferentialEvidence.test.ts",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def source_predicates(repo: Path) -> list[dict[str, Any]]:
    controller = (
        repo
        / "src/game/logres/field/controllers/LogresFieldEncounterController.ts"
    )
    authority = (
        repo
        / "src/game/logres/encounter/ReconstructedLogresEncounterAuthority.ts"
    )
    controller_text = controller.read_text()
    authority_text = authority.read_text()

    checks = [
        {
            "id": "field-controller-requests-entry",
            "path": str(controller.relative_to(repo)),
            "needle": "bridge.requestEntry()",
            "satisfied": "bridge.requestEntry()" in controller_text,
        },
        {
            "id": "field-controller-records-entry-response",
            "path": str(controller.relative_to(repo)),
            "needle": "bridge.recordEntryResponse({",
            "satisfied": "bridge.recordEntryResponse({" in controller_text,
        },
        {
            "id": "field-controller-records-battle-initialized-after-response",
            "path": str(controller.relative_to(repo)),
            "needle": "bridge.recordBattleInitialized({",
            "satisfied": "bridge.recordBattleInitialized({" in controller_text,
        },
        {
            "id": "field-controller-explicit-server-authority-stub",
            "path": str(controller.relative_to(repo)),
            "needle": "RECONSTRUCTED_SERVER_AUTHORITY_STUB",
            "satisfied": "RECONSTRUCTED_SERVER_AUTHORITY_STUB" in controller_text,
        },
        {
            "id": "authority-uses-exact-retry-seconds",
            "path": str(authority.relative_to(repo)),
            "needle": "LOGRES_GLOBAL_BATTLE_ENTRY_RETRY_SECONDS",
            "satisfied": "LOGRES_GLOBAL_BATTLE_ENTRY_RETRY_SECONDS" in authority_text,
        },
        {
            "id": "authority-rejects-preelapsed-retry",
            "path": str(authority.relative_to(repo)),
            "needle": "Battle entry retry wait has not elapsed",
            "satisfied": "Battle entry retry wait has not elapsed" in authority_text,
        },
        {
            "id": "authority-sets-entry-accepted",
            "path": str(authority.relative_to(repo)),
            "needle": "this.entryAccepted =",
            "satisfied": "this.entryAccepted =" in authority_text,
        },
    ]

    # Ordering inside the field controller matters: request -> response -> init.
    request_index = controller_text.find("bridge.requestEntry()")
    response_index = controller_text.find("bridge.recordEntryResponse({")
    init_index = controller_text.find("bridge.recordBattleInitialized({")
    checks.append(
        {
            "id": "field-controller-boundary-order",
            "path": str(controller.relative_to(repo)),
            "expected": "requestEntry < recordEntryResponse < recordBattleInitialized",
            "actual_indexes": {
                "requestEntry": request_index,
                "recordEntryResponse": response_index,
                "recordBattleInitialized": init_index,
            },
            "satisfied": (
                request_index >= 0
                and response_index > request_index
                and init_index > response_index
            ),
        }
    )
    return checks


def build(args: argparse.Namespace) -> dict[str, Any]:
    certified = load_json(args.certified_differential)
    current = load_json(args.current_differential)
    truth = load_json(args.truth_kernel)
    consistency = load_json(args.consistency_certificate)
    trace = load_json(args.trace_certificate)

    packet = next(
        (
            row
            for row in certified.get("implementation_packets", [])
            if row.get("id") == args.packet_id
        ),
        None,
    )
    if packet is None:
        raise ValueError(
            f"certified differential missing packet {args.packet_id}"
        )

    certified_bugs = [
        row
        for row in certified.get("divergences", [])
        if row.get("classification") == "IMPLEMENTATION_BUG"
        and float(row.get("evidence_score", 0)) >= 1.0
    ]
    current_bugs = [
        row
        for row in current.get("divergences", [])
        if row.get("classification") == "IMPLEMENTATION_BUG"
    ]
    current_packet_ids = {
        str(row.get("id"))
        for row in current.get("implementation_packets", [])
    }

    truth_ok = (
        truth.get("read_only") is True
        and truth.get("stats", {}).get("status") == "RESOLVED"
        and int(truth.get("stats", {}).get("claims", 0)) > 0
    )
    consistency_ok = (
        consistency.get("status") == "PASS"
        and consistency.get("creates_new_historical_facts") is False
        and int(
            consistency.get("invariant_counts", {}).get("failed", -1)
        )
        == 0
    )
    trace_ok = (
        trace.get("offline_only") is True
        and trace.get("production_server_access") in (False, None)
    )

    predicates = source_predicates(args.repo)
    source_ok = all(bool(row["satisfied"]) for row in predicates)

    scope = [str(path) for path in packet.get("scope", [])]
    source_hashes = {}
    for rel in scope:
        path = args.repo / rel
        if not path.is_file():
            raise FileNotFoundError(
                f"packet scope file missing from repo: {rel}"
            )
        source_hashes[rel] = sha256_file(path)

    tests = []
    for rel in DEFAULT_TESTS:
        path = args.repo / rel
        if not path.is_file():
            raise FileNotFoundError(
                f"required synthesis verification test missing: {rel}"
            )
        tests.append(
            {
                "path": rel,
                "sha256": sha256_file(path),
            }
        )

    certified_gap_exists = bool(certified_bugs)
    active_gap_exists = (
        bool(current_bugs)
        or args.packet_id in current_packet_ids
        or not source_ok
    )

    evidence_gate = (
        certified_gap_exists
        and truth_ok
        and consistency_ok
        and trace_ok
    )

    if not evidence_gate:
        status = "REJECTED_INSUFFICIENT_EVIDENCE"
        files_to_modify: list[str] = []
        reason = (
            "Certified divergence/truth/consistency/trace predicates are not "
            "all satisfied; no implementation delta is authorized."
        )
    elif not active_gap_exists:
        status = "ZERO_DELTA_ALREADY_SATISFIED"
        files_to_modify = []
        reason = (
            "The certified implementation bug existed in the earlier "
            "differential, but current canonical code satisfies every source "
            "predicate and the regenerated current differential contains no "
            "IMPLEMENTATION_BUG or matching implementation packet."
        )
    else:
        status = "BOUNDED_PATCH_REQUIRED"
        files_to_modify = scope
        reason = (
            "The certified implementation bug remains active. Only the "
            "packet's exact scope is authorized for a separate implementation "
            "worker; this synthesizer does not apply the patch."
        )

    rollback = {
        "invalidate_synthesis_if_any": [
            (
                f"current differential contains implementation packet "
                f"{args.packet_id}"
            ),
            "current differential contains any IMPLEMENTATION_BUG for the bounded encounter/battle-entry gap",
            "any source predicate in source_predicates becomes false",
            "truth kernel no longer reports read_only=true and status=RESOLVED",
            "consistency certificate no longer reports PASS with zero failed invariants",
            "any targeted verification test hash changes without regenerating this synthesis",
        ],
        "verification_command": (
            "npx vitest run "
            + " ".join(row["path"] for row in tests)
        ),
        "differential_regeneration_command": (
            "python3 scripts/logres/run_global_differential_emulator.py "
            "--repo . --output <current-differential.json>"
        ),
    }

    return {
        "provenance": PROVENANCE,
        "status": status,
        "reason": reason,
        "packet": {
            "id": packet["id"],
            "classification": packet.get("classification"),
            "scope": scope,
            "acceptance": packet.get("acceptance", []),
            "auto_apply": False,
            "auto_merge": False,
        },
        "delta": {
            "files_to_modify": files_to_modify,
            "file_count": len(files_to_modify),
            "existing_implementation_reuse_preferred": True,
            "patch_applied": False,
            "commit_created": False,
            "merge_performed": False,
            "deployment_performed": False,
        },
        "predicates": {
            "certified_gap_exists": certified_gap_exists,
            "active_gap_exists": active_gap_exists,
            "truth_kernel_resolved": truth_ok,
            "consistency_certificate_pass": consistency_ok,
            "trace_certificate_offline_only": trace_ok,
            "current_source_predicates_pass": source_ok,
            "current_implementation_packet_present": (
                args.packet_id in current_packet_ids
            ),
            "current_implementation_bug_count": len(current_bugs),
            "current_classifications": current.get(
                "counts",
                {},
            ).get("classifications", {}),
        },
        "source_predicates": predicates,
        "evidence": {
            "certified_differential": {
                "path": str(args.certified_differential),
                "sha256": sha256_file(args.certified_differential),
                "implementation_bug_ids": [
                    row["id"]
                    for row in certified_bugs
                ],
            },
            "current_differential": {
                "path": str(args.current_differential),
                "sha256": sha256_file(args.current_differential),
                "implementation_bug_ids": [
                    row["id"]
                    for row in current_bugs
                ],
                "implementation_packet_ids": sorted(
                    current_packet_ids
                ),
            },
            "truth_kernel": {
                "path": str(args.truth_kernel),
                "sha256": sha256_file(args.truth_kernel),
                "truth_kernel_id": truth.get("truth_kernel_id"),
                "claims": truth.get("stats", {}).get("claims"),
                "status": truth.get("stats", {}).get("status"),
            },
            "consistency_certificate": {
                "path": str(args.consistency_certificate),
                "sha256": sha256_file(args.consistency_certificate),
                "certificate_id": consistency.get("certificate_id"),
                "status": consistency.get("status"),
                "invariant_counts": consistency.get(
                    "invariant_counts"
                ),
            },
            "trace_certificate": {
                "path": str(args.trace_certificate),
                "sha256": sha256_file(args.trace_certificate),
                "certificate_id": trace.get("certificate_id"),
                "offline_only": trace.get("offline_only"),
            },
            "current_scope_source_hashes": source_hashes,
            "targeted_tests": tests,
        },
        "rollback_predicate": rollback,
        "historical_authority_policy": {
            "current_jp_may_authorize_historical_global_patch": False,
            "retired_server_semantics_may_be_invented": False,
            "unknown_server_semantics_remain_unknown": True,
            "intentional_server_stub_is_not_an_implementation_bug": True,
        },
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    artifacts = DEFAULT_ROOT / "artifacts"
    p.add_argument(
        "--repo",
        type=Path,
        default=DEFAULT_REPO,
    )
    p.add_argument(
        "--certified-differential",
        type=Path,
        default=artifacts / "global3024-differential-emulator-20260924.json",
    )
    p.add_argument(
        "--current-differential",
        type=Path,
        default=artifacts
        / "global3024-differential-emulator-current-20260924.json",
    )
    p.add_argument(
        "--truth-kernel",
        type=Path,
        default=artifacts / "logres-truth-kernel-20260924.json",
    )
    p.add_argument(
        "--consistency-certificate",
        type=Path,
        default=artifacts
        / "logres-reconstruction-consistency-certificate-20260924.json",
    )
    p.add_argument(
        "--trace-certificate",
        type=Path,
        default=artifacts / "global3024-trace-certificate-20260924.json",
    )
    p.add_argument(
        "--packet-id",
        default=DEFAULT_PACKET,
    )
    p.add_argument(
        "--output",
        type=Path,
        default=artifacts / "minimal-reconstruction-delta-20260924.json",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    result = build(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(args.output),
                "sha256": sha256_file(args.output),
                "delta_file_count": result["delta"]["file_count"],
                "active_gap_exists": result["predicates"][
                    "active_gap_exists"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return (
        0
        if result["status"]
        in {
            "ZERO_DELTA_ALREADY_SATISFIED",
            "BOUNDED_PATCH_REQUIRED",
        }
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
