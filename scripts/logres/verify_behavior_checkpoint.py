#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

CHECKPOINT = "playable-field-battle-reward-return"
OBJECTIVE = "BEHAVIORAL_FIDELITY"
EXPECTED = {
    "events": [
        "FIELD_READY",
        "BATTLE_ACTIVE",
        "BATTLE_VICTORY_READY",
        "FIELD_RETURN_READY",
        "FIELD_READY_RETURNED",
    ],
    "final_state": {
        "mapId": "002_000_00001",
        "rewardApplied": True,
        "resolutionPhase": "field-return-ready",
        "inputProvenance": "RECONSTRUCTED_PLAYABILITY_FALLBACK",
        "authorityPhase": "victory-ready",
        "inventoryRevision": 1,
        "returnScene": "LogresFieldScene",
    },
}
PROVENANCE = {
    "expected_trace": "RECONSTRUCTED_PLAYABILITY_CONTRACT",
    "historical_order": "GLOBAL_CLIENT_OBSERVED_RESULT_REWARD_FIELD_RETURN",
    "historical_damage_formula": "UNRESOLVED",
    "historical_enemy_hp": "UNRESOLVED",
    "playable_resolution": "RECONSTRUCTED_SERVER_AUTHORITY_STUB",
}


def load_observed(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"observed behavior trace missing: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("observed behavior trace must be an object")
    if not isinstance(payload.get("events"), list):
        raise ValueError("observed behavior trace events must be a list")
    if not isinstance(payload.get("final_state"), dict):
        raise ValueError("observed behavior trace final_state must be an object")
    return payload


def recorder_argv(recorder: str, sha: str, observed: dict) -> list[str]:
    if len(sha) != 40:
        raise ValueError("exact 40-character source SHA required")
    return [
        recorder,
        "record",
        sha,
        CHECKPOINT,
        "--expected",
        json.dumps(EXPECTED, sort_keys=True, separators=(",", ":")),
        "--observed",
        json.dumps(observed, sort_keys=True, separators=(",", ":")),
        "--objective",
        OBJECTIVE,
        "--provenance",
        json.dumps(PROVENANCE, sort_keys=True, separators=(",", ":")),
    ]


def record_behavior_truth(
    observed_path: Path,
    *,
    sha: str,
    recorder: str,
    runner=subprocess.run,
) -> dict:
    observed = load_observed(observed_path)
    proc = runner(
        recorder_argv(recorder, sha, observed),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode not in (0, 1):
        raise RuntimeError(
            "behavior truth recorder failed: "
            + ((proc.stderr or proc.stdout or "").strip())
        )
    try:
        payload = json.loads((proc.stdout or "").strip())
    except json.JSONDecodeError as exc:
        raise RuntimeError("behavior truth recorder returned invalid JSON") from exc
    verdict = str(payload.get("verdict") or "")
    if verdict not in {"PASS", "FAIL"}:
        raise RuntimeError(f"unexpected behavior truth verdict: {verdict!r}")
    return {
        "checkpoint": CHECKPOINT,
        "sha": sha,
        "verdict": verdict,
        "record": payload,
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="verify_behavior_checkpoint")
    parser.add_argument("--observed", type=Path, required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument(
        "--recorder",
        default="/home/ubuntu/logres/bin/logres-behavior-trace",
    )
    args = parser.parse_args()
    try:
        result = record_behavior_truth(
            args.observed,
            sha=args.sha,
            recorder=args.recorder,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"BEHAVIOR_CHECKPOINT ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
