#!/usr/bin/env python3
"""Build a deterministic reproducibility capsule for Logres reconstruction.

The capsule contains hashes, Git refs, tool identities and replay recipes only.
It never embeds private APK/resource bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

TOOL_PATHS = (
    "scripts/logres/build_global_jp_protocol_schema.py",
    "scripts/logres/build_global_state_machine.py",
    "scripts/logres/global3024_protocol_twin.py",
    "scripts/logres/build_global_jp_map_genealogy.py",
    "scripts/logres/build_global_jp_resource_genealogy.py",
    "scripts/logres/build_global_jp_resource_semantic_graph.py",
    "scripts/logres/global3024_evidence_fuzzer.py",
    "scripts/logres/build_global_contradiction_arbiter.py",
    "scripts/logres/build_reconstruction_consistency_certificate.py",
    "scripts/logres/global3024_counterfactual_lab.py",
    "scripts/logres/build_evidence_merkle_manifest.py",
)

REPLAY_RECIPES = (
    {
        "artifact": "global-jp-protocol-schema-20260924.json",
        "command": "python3 scripts/logres/build_global_jp_protocol_schema.py --output /home/ubuntu/logres/artifacts/global-jp-protocol-schema-20260924.json",
    },
    {
        "artifact": "global-3024-state-machine-20260924.json",
        "command": "python3 scripts/logres/build_global_state_machine.py --output /home/ubuntu/logres/artifacts/global-3024-state-machine-20260924.json",
    },
    {
        "artifact": "global3024-offline-protocol-twin-20260924.json",
        "command": "python3 scripts/logres/global3024_protocol_twin.py --output /home/ubuntu/logres/artifacts/global3024-offline-protocol-twin-20260924.json",
    },
    {
        "artifact": "global-jp-map-genealogy-20260924.json",
        "command": "python3 scripts/logres/build_global_jp_map_genealogy.py --output /home/ubuntu/logres/artifacts/global-jp-map-genealogy-20260924.json",
    },
    {
        "artifact": "global-jp-resource-genealogy-20260924.json",
        "command": "python3 scripts/logres/build_global_jp_resource_genealogy.py --jp-filelist /home/ubuntu/logres/private/jp-public-manifest-1790230588/filelist.bin --output /home/ubuntu/logres/artifacts/global-jp-resource-genealogy-20260924.json",
    },
    {
        "artifact": "global-jp-resource-semantic-graph-20260924.json",
        "command": "python3 scripts/logres/build_global_jp_resource_semantic_graph.py --output /home/ubuntu/logres/artifacts/global-jp-resource-semantic-graph-20260924.json",
    },
    {
        "artifact": "global3024-evidence-fuzzer-20260924.json",
        "command": "python3 scripts/logres/global3024_evidence_fuzzer.py --output /home/ubuntu/logres/artifacts/global3024-evidence-fuzzer-20260924.json",
    },
    {
        "artifact": "global-contradiction-arbiter-20260924.json",
        "command": "python3 scripts/logres/build_global_contradiction_arbiter.py --output /home/ubuntu/logres/artifacts/global-contradiction-arbiter-20260924.json",
    },
    {
        "artifact": "logres-reconstruction-consistency-certificate-20260924.json",
        "command": "python3 scripts/logres/build_reconstruction_consistency_certificate.py --output /home/ubuntu/logres/artifacts/logres-reconstruction-consistency-certificate-20260924.json",
    },
    {
        "artifact": "global3024-counterfactual-lab-20260924.json",
        "command": "python3 scripts/logres/global3024_counterfactual_lab.py --output /home/ubuntu/logres/artifacts/global3024-counterfactual-lab-20260924.json",
    },
    {
        "artifact": "logres-galaxy-evidence-merkle-20260924.json",
        "command": "python3 scripts/logres/build_evidence_merkle_manifest.py --output /home/ubuntu/logres/artifacts/logres-galaxy-evidence-merkle-20260924.json",
    },
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        [*args],
        cwd=repo,
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()


def git_show(repo: Path, ref: str, path: str) -> bytes:
    return subprocess.check_output(
        ["git", "-C", str(repo), "show", f"{ref}:{path}"],
        stderr=subprocess.DEVNULL,
    )


def path_exists_at(repo: Path, ref: str, path: str) -> bool:
    proc = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", f"{ref}:{path}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.returncode == 0


def latest_ref_with_path(repo: Path, path: str) -> str:
    output = subprocess.check_output(
        ["git", "-C", str(repo), "log", "--all", "--format=%H", "--", path],
        text=True,
    )
    for line in output.splitlines():
        ref = line.strip()
        if ref and path_exists_at(repo, ref, path):
            return ref
    raise FileNotFoundError(f"no Git ref contains {path}")


def tool_record(repo: Path, canonical_sha: str, path: str) -> dict[str, Any]:
    if path_exists_at(repo, canonical_sha, path):
        ref = canonical_sha
        placement = "CANONICAL"
    else:
        ref = latest_ref_with_path(repo, path)
        placement = "VERIFIED_WORKER_REF"
    data = git_show(repo, ref, path)
    oid = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", f"{ref}:{path}"],
        text=True,
    ).strip()
    return {
        "path": path,
        "git_ref": ref,
        "placement": placement,
        "git_blob_oid": oid,
        "sha256": sha256_bytes(data),
        "bytes": len(data),
    }


def command_version(argv: list[str]) -> str:
    return subprocess.check_output(argv, text=True).strip()


def verify_merkle_inputs(merkle: dict[str, Any]) -> list[dict[str, Any]]:
    errors = []
    canonical = merkle["canonical_repo_sha"]
    for leaf in merkle["leaves"]:
        kind = leaf["kind"]
        if kind == "canonical_repo":
            if leaf["sha256"] != canonical:
                errors.append(
                    {
                        "path": leaf["path"],
                        "reason": "canonical repo leaf does not match manifest canonical SHA",
                    }
                )
            continue
        path = Path(leaf["path"])
        if not path.is_file():
            errors.append(
                {
                    "path": leaf["path"],
                    "reason": "sealed file missing",
                }
            )
            continue
        actual = sha256_file(path)
        if actual != leaf["sha256"]:
            errors.append(
                {
                    "path": leaf["path"],
                    "reason": "sealed file hash drift",
                    "expected": leaf["sha256"],
                    "actual": actual,
                }
            )
    return errors


def build(args: argparse.Namespace) -> dict[str, Any]:
    merkle = json.loads(args.merkle_manifest.read_text())
    if merkle.get("provenance") != "GALAXY_CRYPTOGRAPHIC_EVIDENCE_SEAL":
        raise RuntimeError("input is not a GALAXY evidence seal")
    drift = verify_merkle_inputs(merkle)
    if drift:
        raise RuntimeError(json.dumps({"merkle_input_drift": drift}, indent=2))

    canonical_sha = merkle["canonical_repo_sha"]
    current_canonical = subprocess.check_output(
        ["git", "-C", str(args.repo), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    if current_canonical != canonical_sha:
        raise RuntimeError(
            f"canonical repo drift: seal={canonical_sha} current={current_canonical}"
        )

    package_lock = git_show(args.repo, canonical_sha, "package-lock.json")
    tools = [
        tool_record(args.repo, canonical_sha, path)
        for path in TOOL_PATHS
    ]

    environment = {
        "node": command_version(["node", "--version"]),
        "npm": command_version(["npm", "--version"]),
        "python": command_version(["python3", "--version"]),
        "git": command_version(["git", "--version"]),
    }
    core = {
        "canonical_repo_sha": canonical_sha,
        "evidence_merkle_root": merkle["merkle_root"],
        "evidence_merkle_manifest_sha256": sha256_file(args.merkle_manifest),
        "package_lock_sha256": sha256_bytes(package_lock),
        "environment": environment,
        "tools": tools,
        "recipes": list(REPLAY_RECIPES),
    }
    capsule_id = sha256_bytes(
        json.dumps(
            core,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    )

    return {
        "provenance": "GALAXY_RECONSTRUCTION_REPRODUCIBILITY_CAPSULE",
        "capsule_id": capsule_id,
        "contains_private_evidence_bytes": False,
        **core,
        "counts": {
            "tool_records": len(tools),
            "canonical_tools": sum(
                row["placement"] == "CANONICAL" for row in tools
            ),
            "worker_ref_tools": sum(
                row["placement"] == "VERIFIED_WORKER_REF" for row in tools
            ),
            "replay_recipes": len(REPLAY_RECIPES),
            "sealed_input_leaves_verified": merkle["counts"]["total_leaves"],
            "sealed_input_drift": 0,
        },
        "reproduction_policy": {
            "private_inputs": (
                "Private APK/assets remain local and are referenced only by the "
                "Merkle-sealed path/hash metadata."
            ),
            "worker_refs": (
                "A generator not yet integrated into canonical is pinned to an "
                "exact verified worker commit and content hash."
            ),
            "identity": (
                "Capsule identity changes with canonical SHA, Merkle root, "
                "package-lock, environment versions, tool hashes or replay recipes."
            ),
            "historical_authority": (
                "Reproducibility authenticates computation; it does not elevate "
                "the historical confidence of the evidence being reproduced."
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path("/home/ubuntu/logres/src/awakened-realms"),
    )
    parser.add_argument(
        "--merkle-manifest",
        type=Path,
        default=Path(
            "/home/ubuntu/logres/artifacts/"
            "logres-galaxy-evidence-merkle-20260924.json"
        ),
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
                "capsule_id": result["capsule_id"],
                "canonical_repo_sha": result["canonical_repo_sha"],
                "evidence_merkle_root": result["evidence_merkle_root"],
                "counts": result["counts"],
                "environment": result["environment"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
