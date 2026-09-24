#!/usr/bin/env python3
"""Offline counterfactual explorer for the recovered Global 3.0.24 client.

Counterfactuals are analysis objects, never historical claims. The lab proves
shortest client-valid traces through the recovered state machine, identifies
server-authority boundaries, and maps adversarial cases into four explicit
classes:
  CLIENT_KNOWN_BRANCH
  CLIENT_IMPOSSIBLE
  SERVER_UNKNOWN
  EVIDENCE_MISMATCH
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
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


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected object")
    return value


def requires_server_authority(transition: dict[str, Any]) -> bool:
    message = str(transition.get("message") or "")
    trigger = str(transition.get("trigger") or "").lower()
    unresolved = str(transition.get("unresolved") or "")
    if message.startswith("S_") or message.endswith("_Response"):
        return True
    if "server" in trigger or unresolved:
        return True
    return False


def transition_projection(transition: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "index": index,
        "from": transition["from"],
        "to": transition["to"],
        "trigger": transition["trigger"],
        "message": transition.get("message"),
        "guard": transition.get("guard"),
        "evidence": transition.get("evidence"),
        "action": transition.get("action"),
        "requires_server_authority": requires_server_authority(transition),
        "server_boundary_note": (
            "Client reaction/projection is recovered; retired-server decision or payload production is not inferred."
            if requires_server_authority(transition)
            else None
        ),
    }


def shortest_traces(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    states = state["states"]
    transitions = state["transitions"]
    adjacency: dict[str, list[tuple[int, dict[str, Any]]]] = {name: [] for name in states}
    for index, row in enumerate(transitions):
        adjacency[row["from"]].append((index, row))

    start = "TITLE"
    queue = deque([start])
    parent: dict[str, tuple[str, int] | None] = {start: None}

    while queue:
        current = queue.popleft()
        for index, row in adjacency.get(current, []):
            target = row["to"]
            if target in parent:
                continue
            parent[target] = (current, index)
            queue.append(target)

    result: dict[str, dict[str, Any]] = {}
    for target in states:
        if target not in parent:
            result[target] = {
                "reachable": False,
                "steps": None,
                "server_authority_steps": None,
                "trace": [],
            }
            continue
        indices: list[int] = []
        cursor = target
        while cursor != start:
            link = parent[cursor]
            assert link is not None
            previous, index = link
            indices.append(index)
            cursor = previous
        indices.reverse()
        trace = [
            transition_projection(transitions[index], index)
            for index in indices
        ]
        result[target] = {
            "reachable": True,
            "steps": len(trace),
            "server_authority_steps": sum(
                1 for row in trace if row["requires_server_authority"]
            ),
            "trace": trace,
        }
    return result


def classify_fuzzer_case(row: dict[str, Any]) -> str | None:
    expected_class = row["expected_class"]
    kind = row["kind"]

    if expected_class == "GLOBAL_KNOWN_BRANCH" and kind in {
        "ENUM_BRANCH",
        "RETRY_TIMING",
    }:
        return "CLIENT_KNOWN_BRANCH"
    if expected_class == "OFFLINE_STATE_MODEL_REJECT":
        return "CLIENT_IMPOSSIBLE"
    if expected_class == "SERVER_BEHAVIOR_UNKNOWN":
        return "SERVER_UNKNOWN"
    if expected_class == "EVIDENCE_MISMATCH_REJECT":
        return "EVIDENCE_MISMATCH"
    return None


def build(args: argparse.Namespace) -> dict[str, Any]:
    state = load(args.state_machine)
    fuzzer = load(args.evidence_fuzzer)
    consistency = load(args.consistency_certificate)

    if consistency.get("status") != "PASS":
        raise RuntimeError("counterfactual lab requires a PASS consistency certificate")

    traces = shortest_traces(state)
    unreachable = sorted(
        name for name, row in traces.items() if not row["reachable"]
    )

    behavioral_cases = []
    for row in fuzzer["cases"]:
        classification = classify_fuzzer_case(row)
        if classification is None:
            continue
        behavioral_cases.append(
            {
                "id": row["id"],
                "classification": classification,
                "kind": row["kind"],
                "subject": row["subject"],
                "mutation": row["mutation"],
                "evidence": row["evidence"],
                "historical_claim": False,
                "details": row.get("details", {}),
            }
        )
    behavioral_cases.sort(
        key=lambda row: (row["classification"], row["kind"], row["id"])
    )
    class_counts = Counter(row["classification"] for row in behavioral_cases)

    server_transitions = [
        transition_projection(row, index)
        for index, row in enumerate(state["transitions"])
        if requires_server_authority(row)
    ]
    client_only_transitions = [
        transition_projection(row, index)
        for index, row in enumerate(state["transitions"])
        if not requires_server_authority(row)
    ]

    # Recovered state semantics may know how the client reacts to a server code.
    # It does not establish what unseen/invalid values the retired server emits.
    unknown_enum_cases = [
        row
        for row in behavioral_cases
        if row["classification"] == "SERVER_UNKNOWN"
    ]
    impossible_cases = [
        row
        for row in behavioral_cases
        if row["classification"] == "CLIENT_IMPOSSIBLE"
    ]

    longest = max(
        (row["steps"] or 0 for row in traces.values()),
        default=0,
    )
    longest_states = sorted(
        name for name, row in traces.items() if row["steps"] == longest
    )

    core = {
        "state_hash": sha256_file(args.state_machine),
        "fuzzer_hash": sha256_file(args.evidence_fuzzer),
        "consistency_hash": sha256_file(args.consistency_certificate),
        "trace_lengths": {
            name: row["steps"]
            for name, row in sorted(traces.items())
        },
        "case_ids": [row["id"] for row in behavioral_cases],
        "server_transition_indices": [row["index"] for row in server_transitions],
    }
    lab_id = hashlib.sha256(
        json.dumps(core, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    return {
        "provenance": "ZENITH_OFFLINE_COUNTERFACTUAL_MODEL_FROM_CONFIRMED_GLOBAL_CLIENT_EVIDENCE",
        "lab_id": lab_id,
        "historical_claims_created": False,
        "offline_only": True,
        "sources": {
            "state_machine": {
                "path": str(args.state_machine),
                "sha256": sha256_file(args.state_machine),
            },
            "evidence_fuzzer": {
                "path": str(args.evidence_fuzzer),
                "sha256": sha256_file(args.evidence_fuzzer),
            },
            "consistency_certificate": {
                "path": str(args.consistency_certificate),
                "sha256": sha256_file(args.consistency_certificate),
                "certificate_id": consistency["certificate_id"],
            },
        },
        "coverage": {
            "states": len(state["states"]),
            "reachable_states": len(state["states"]) - len(unreachable),
            "unreachable_states": len(unreachable),
            "transitions": len(state["transitions"]),
            "server_authority_transitions": len(server_transitions),
            "client_only_transitions": len(client_only_transitions),
            "behavioral_counterfactual_cases": len(behavioral_cases),
            "classification_counts": dict(sorted(class_counts.items())),
            "longest_shortest_trace_steps": longest,
            "longest_shortest_trace_states": longest_states,
        },
        "shortest_valid_traces": traces,
        "server_authority_boundaries": server_transitions,
        "client_only_transitions": client_only_transitions,
        "counterfactual_cases": behavioral_cases,
        "server_unknown_cases": unknown_enum_cases,
        "client_impossible_cases": impossible_cases,
        "classification_policy": {
            "CLIENT_KNOWN_BRANCH": (
                "The recovered Global client has a directly evidenced branch for this input/result."
            ),
            "CLIENT_IMPOSSIBLE": (
                "The sequence is not an evidenced outgoing transition from that recovered client state."
            ),
            "SERVER_UNKNOWN": (
                "Client evidence does not establish how the retired server behaves for this value/condition."
            ),
            "EVIDENCE_MISMATCH": (
                "The alternative contradicts a confirmed recovered client/resource fact."
            ),
        },
        "guardrails": [
            "Counterfactuals are never promoted to historical observations.",
            "A server-authority boundary preserves the recovered client reaction while leaving server validation/payload production unknown.",
            "Current-JP behavior is not used to fill retired-Global server gaps.",
            "Shortest-path reachability proves graph reachability only, not that every route occurred historically.",
            "No live production game server is contacted.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path("/home/ubuntu/logres/artifacts")
    parser.add_argument(
        "--state-machine",
        type=Path,
        default=root / "global-3024-state-machine-20260924.json",
    )
    parser.add_argument(
        "--evidence-fuzzer",
        type=Path,
        default=root / "global3024-evidence-fuzzer-20260924.json",
    )
    parser.add_argument(
        "--consistency-certificate",
        type=Path,
        default=root / "logres-reconstruction-consistency-certificate-20260924.json",
    )
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "lab_id": result["lab_id"],
        "coverage": result["coverage"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
