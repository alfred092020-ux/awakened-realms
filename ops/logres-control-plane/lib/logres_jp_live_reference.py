#!/usr/bin/env python3
"""Offline compiler for JP live-reference capture requests.

This module never executes ADB or mutates a device. It validates the approved
workflow contract and exact JP client provenance, then emits deterministic plans
for a separate governed device executor.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


VERSION_SENSITIVE = "VERSION SENSITIVE"


class ReferencePlanError(ValueError):
    """Raised when a reference request violates provenance or safety policy."""


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _provenance_libgame_sha(client: dict[str, Any]) -> str | None:
    direct = client.get("libgame_arm64_sha256")
    if direct:
        return str(direct)
    for item in client.get("native_libraries") or []:
        path = str(item.get("path", ""))
        if path == "lib/arm64-v8a/libgame.so":
            value = item.get("sha256")
            return None if value is None else str(value)
    return None


def validate_client_binding(
    contract: dict[str, Any],
    provenance: dict[str, Any],
) -> None:
    binding = contract.get("client_binding") or {}
    client = provenance.get("client") or {}
    pairs = {
        "package": (binding.get("package"), client.get("package_name")),
        "version_name": (binding.get("version_name"), client.get("version_name")),
        "version_code": (binding.get("version_code"), client.get("version_code")),
        "xapk_sha256": (binding.get("xapk_sha256"), client.get("xapk_sha256")),
        "libgame_arm64_sha256": (
            binding.get("libgame_arm64_sha256"),
            _provenance_libgame_sha(client),
        ),
    }
    for key, (expected, actual) in pairs.items():
        if str(expected or "") != str(actual or ""):
            raise ReferencePlanError(f"client binding mismatch: {key}")


def validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("classification_default") != VERSION_SENSITIVE:
        raise ReferencePlanError(
            "current JP plans must default to VERSION SENSITIVE"
        )
    if not isinstance(contract.get("named_workflows"), dict):
        raise ReferencePlanError("named_workflows missing")
    if not isinstance(contract.get("request_dsl", {}).get("step_types"), list):
        raise ReferencePlanError("request_dsl.step_types missing")


def _forbidden_tokens(contract: dict[str, Any]) -> tuple[str, ...]:
    safety = contract.get("safety") or {}
    raw = safety.get("forbidden_actions") or []
    return tuple(str(item).strip().lower() for item in raw if str(item).strip())


def _reject_forbidden(contract: dict[str, Any], text: str) -> None:
    lowered = text.strip().lower()
    for token in _forbidden_tokens(contract):
        if token in lowered:
            raise ReferencePlanError(f"forbidden action in workflow: {text}")


def _compile_items(
    contract: dict[str, Any],
    workflow_id: str,
    stack: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    workflows = contract["named_workflows"]
    if workflow_id not in workflows:
        raise ReferencePlanError(f"unknown workflow: {workflow_id}")
    if workflow_id in stack:
        chain = " -> ".join((*stack, workflow_id))
        raise ReferencePlanError(f"workflow cycle: {chain}")

    primitives = set(contract["request_dsl"]["step_types"])
    out: list[dict[str, Any]] = []
    for raw in workflows[workflow_id]:
        item = str(raw)
        _reject_forbidden(contract, item)
        if item in workflows:
            out.extend(_compile_items(contract, item, (*stack, workflow_id)))
            continue
        if item in primitives:
            out.append({"type": item})
            continue
        prefix, sep, value = item.partition(":")
        if sep and prefix in primitives:
            out.append({"type": prefix, "value": value})
            continue
        out.append({"type": "checkpoint", "instruction": item})
    return out


def _packet_skeleton(
    contract: dict[str, Any],
    workflow_id: str,
) -> dict[str, Any]:
    binding = dict(contract["client_binding"])
    return {
        "workflow_id": workflow_id,
        "client": binding,
        "device": {},
        "started_at": None,
        "finished_at": None,
        "classification": VERSION_SENSITIVE,
        "input_sequence": [],
        "artifacts": [],
        "artifact_sha256": {},
        "logcat_excerpt_index": [],
        "observations": [],
        "contradictions": [],
        "unresolved": [],
        "expected_artifacts": list(
            contract.get("capture_packet", {}).get("artifacts", [])
        ),
        "brain_registration": contract.get("capture_packet", {}).get(
            "brain_registration", ""
        ),
    }


def compile_workflow(
    contract: dict[str, Any],
    provenance: dict[str, Any],
    workflow_id: str,
) -> dict[str, Any]:
    validate_contract(contract)
    validate_client_binding(contract, provenance)
    if provenance.get("classification") != VERSION_SENSITIVE:
        raise ReferencePlanError(
            "JP provenance must remain VERSION SENSITIVE"
        )
    steps = _compile_items(contract, workflow_id)
    return {
        "schema_version": 1,
        "workflow_id": workflow_id,
        "classification": VERSION_SENSITIVE,
        "client_binding": dict(contract["client_binding"]),
        "steps": steps,
        "failure_policy": contract.get("request_dsl", {}).get(
            "failure_policy", ""
        ),
        "comparison_policy": dict(contract.get("comparison_policy") or {}),
        "g17_policy": dict(contract.get("g17_policy") or {}),
        "safety": dict(contract.get("safety") or {}),
        "capture_packet": _packet_skeleton(contract, workflow_id),
    }


def compile_all(
    contract: dict[str, Any],
    provenance: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    validate_contract(contract)
    return {
        workflow_id: compile_workflow(contract, provenance, workflow_id)
        for workflow_id in sorted(contract["named_workflows"])
    }


def _write_result(data: Any, output: str | None) -> None:
    rendered = json.dumps(data, indent=2, sort_keys=True) + "\n"
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


def _add_sources(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--contract", required=True)
    parser.add_argument("--provenance", required=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list")
    list_parser.add_argument("--contract", required=True)

    compile_parser = sub.add_parser("compile")
    _add_sources(compile_parser)
    compile_parser.add_argument("workflow")
    compile_parser.add_argument("--output")

    all_parser = sub.add_parser("compile-all")
    _add_sources(all_parser)
    all_parser.add_argument("--output")

    args = parser.parse_args(argv)
    contract = load_json(args.contract)
    if args.command == "list":
        validate_contract(contract)
        _write_result(sorted(contract["named_workflows"]), None)
        return 0

    provenance = load_json(args.provenance)
    if args.command == "compile":
        _write_result(
            compile_workflow(contract, provenance, args.workflow),
            args.output,
        )
        return 0
    if args.command == "compile-all":
        _write_result(
            compile_all(contract, provenance),
            args.output,
        )
        return 0

    raise ReferencePlanError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
