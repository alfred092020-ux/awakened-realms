#!/usr/bin/env python3
"""Build a deterministic Merkle seal for the authoritative Logres evidence universe.

The seal references private/local evidence by path and SHA-256 only. It copies
no APKs/assets into the repository and creates no new historical claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

ROOT_ARTIFACTS = (
    "global-3024-gmcl-protocol-evidence-20260924.json",
    "global-jp-protocol-schema-20260924.json",
    "global-3024-state-machine-20260924.json",
    "global3024-offline-protocol-twin-20260924.json",
    "global-jp-map-genealogy-20260924.json",
    "global-jp-resource-genealogy-20260924.json",
    "global-jp-resource-semantic-graph-20260924.json",
    "global3024-client-observed-server-model-20260924.json",
    "global3024-evidence-fuzzer-20260924.json",
    "global-contradiction-arbiter-20260924.json",
    "logres-reconstruction-consistency-certificate-20260924.json",
    "global3024-counterfactual-lab-20260924.json",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_sha(repo: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def provenance_of(payload: dict[str, Any]) -> str | None:
    value = payload.get("provenance")
    return str(value) if value is not None else None


def declared_sources(value: Any, owner: str, out: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        path = value.get("path")
        expected = value.get("sha256")
        if (
            isinstance(path, str)
            and isinstance(expected, str)
            and Path(path).is_absolute()
        ):
            out.append(
                {
                    "owner": owner,
                    "path": path,
                    "declared_sha256": expected.lower(),
                }
            )
        for child in value.values():
            declared_sources(child, owner, out)
    elif isinstance(value, list):
        for child in value:
            declared_sources(child, owner, out)


def canonical_leaf_payload(leaf: dict[str, Any]) -> bytes:
    material = {
        "kind": leaf["kind"],
        "path": leaf["path"],
        "sha256": leaf["sha256"],
        "provenance": leaf.get("provenance"),
        "owners": leaf.get("owners", []),
    }
    return json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def merkle_root(leaves: list[dict[str, Any]]) -> tuple[str, list[list[str]]]:
    hashes = [
        hashlib.sha256(b"leaf\x00" + canonical_leaf_payload(leaf)).hexdigest()
        for leaf in leaves
    ]
    levels = [hashes]
    if not hashes:
        return hashlib.sha256(b"empty").hexdigest(), levels
    current = hashes
    while len(current) > 1:
        if len(current) % 2:
            current = current + [current[-1]]
        nxt = []
        for index in range(0, len(current), 2):
            pair = bytes.fromhex(current[index]) + bytes.fromhex(current[index + 1])
            nxt.append(hashlib.sha256(b"node\x00" + pair).hexdigest())
        current = nxt
        levels.append(current)
    return current[0], levels


def build(args: argparse.Namespace) -> dict[str, Any]:
    artifact_rows: list[dict[str, Any]] = []
    source_declarations: list[dict[str, Any]] = []

    for name in ROOT_ARTIFACTS:
        path = args.artifact_root / name
        if not path.is_file():
            raise FileNotFoundError(path)
        payload = json.loads(path.read_text())
        if not isinstance(payload, dict):
            raise ValueError(f"{path}: expected JSON object")
        artifact_rows.append(
            {
                "kind": "authoritative_artifact",
                "path": str(path),
                "sha256": sha256_file(path),
                "provenance": provenance_of(payload),
                "owners": [name],
            }
        )
        declared_sources(payload, name, source_declarations)

    # Collapse repeated source declarations by canonical path while preserving
    # all owning evidence artifacts and requiring all declarations to agree.
    source_by_path: dict[str, dict[str, Any]] = {}
    declaration_conflicts = []
    for row in source_declarations:
        path_text = row["path"]
        entry = source_by_path.setdefault(
            path_text,
            {
                "declared_hashes": set(),
                "owners": set(),
            },
        )
        entry["declared_hashes"].add(row["declared_sha256"])
        entry["owners"].add(row["owner"])

    source_rows = []
    missing_paths = []
    stale_paths = []
    for path_text, entry in sorted(source_by_path.items()):
        expected_hashes = sorted(entry["declared_hashes"])
        if len(expected_hashes) != 1:
            declaration_conflicts.append(
                {
                    "path": path_text,
                    "declared_sha256_values": expected_hashes,
                    "owners": sorted(entry["owners"]),
                }
            )
            continue
        path = Path(path_text)
        if not path.is_file():
            missing_paths.append(
                {
                    "path": path_text,
                    "expected_sha256": expected_hashes[0],
                    "owners": sorted(entry["owners"]),
                }
            )
            continue
        actual = sha256_file(path)
        if actual != expected_hashes[0]:
            stale_paths.append(
                {
                    "path": path_text,
                    "expected_sha256": expected_hashes[0],
                    "actual_sha256": actual,
                    "owners": sorted(entry["owners"]),
                }
            )
        source_rows.append(
            {
                "kind": "declared_source",
                "path": path_text,
                "sha256": actual,
                "provenance": "DECLARED_SOURCE_INPUT",
                "owners": sorted(entry["owners"]),
            }
        )

    if declaration_conflicts or missing_paths or stale_paths:
        raise RuntimeError(
            json.dumps(
                {
                    "declaration_conflicts": declaration_conflicts,
                    "missing_paths": missing_paths,
                    "stale_paths": stale_paths,
                },
                indent=2,
                sort_keys=True,
            )
        )

    repo_sha = git_sha(args.repo)
    special_rows = [
        {
            "kind": "canonical_repo",
            "path": str(args.repo),
            "sha256": repo_sha,
            "provenance": "EXACT_GIT_SHA",
            "owners": ["GALAXY-EVIDENCE-MERKLE-001"],
        }
    ]

    # Canonical order is kind/path/hash, independent of discovery order.
    leaves = artifact_rows + source_rows + special_rows
    leaves.sort(key=lambda row: (row["kind"], row["path"], row["sha256"]))
    root, levels = merkle_root(leaves)

    leaf_index = []
    for index, row in enumerate(leaves):
        leaf_hash = hashlib.sha256(
            b"leaf\x00" + canonical_leaf_payload(row)
        ).hexdigest()
        leaf_index.append(
            {
                "index": index,
                **row,
                "leaf_hash": leaf_hash,
            }
        )

    return {
        "provenance": "GALAXY_CRYPTOGRAPHIC_EVIDENCE_SEAL",
        "creates_new_historical_facts": False,
        "hash_algorithm": "SHA-256",
        "merkle_algorithm": {
            "leaf": "SHA256('leaf\\0' || canonical-json)",
            "node": "SHA256('node\\0' || left-bytes || right-bytes)",
            "ordering": "kind,path,sha256 ascending",
            "odd_level_rule": "duplicate final hash",
        },
        "canonical_repo_sha": repo_sha,
        "root_artifact_names": list(ROOT_ARTIFACTS),
        "counts": {
            "authoritative_artifacts": len(artifact_rows),
            "declared_sources": len(source_rows),
            "special_leaves": len(special_rows),
            "total_leaves": len(leaves),
            "merkle_levels": len(levels),
            "declaration_conflicts": 0,
            "missing_paths": 0,
            "stale_paths": 0,
        },
        "merkle_root": root,
        "leaves": leaf_index,
        "levels": levels,
        "verification_policy": {
            "drift": "Any changed artifact/source/repo SHA changes at least one leaf and therefore the Merkle root.",
            "privacy": "Private/local evidence bytes are not copied into the repository; only path/hash/provenance metadata is sealed.",
            "history": "The seal authenticates the evidence universe used by reconstruction; it does not strengthen the historical authority of any leaf.",
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=Path("/home/ubuntu/logres/artifacts"),
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path("/home/ubuntu/logres/src/awakened-realms"),
    )
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "merkle_root": result["merkle_root"],
                "canonical_repo_sha": result["canonical_repo_sha"],
                "counts": result["counts"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
