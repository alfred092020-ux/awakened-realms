#!/usr/bin/env python3
"""Build a provenance-safe Global -> current-JP resource genealogy database.

The compiler uses the locally cached JP public patch manifest and recovered
Global evidence. It deliberately avoids re-hashing/downloading the whole JP
patch corpus. Exact identity is proven by manifest SHA-1 + size, optionally
corroborated by local SHA-256 evidence for bounded recovered files.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from download_public_patch import parse_filelist


def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def category(path: str) -> str:
    return path.split("/", 1)[0] if "/" in path else "(root)"


def parse_global_bootstrap(path: Path) -> list[dict[str, Any]]:
    rows = []
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) < 4:
            raise ValueError(f"invalid Global filelist row: {line!r}")
        rows.append(
            {
                "path": fields[2].removeprefix("./"),
                "sha1": fields[0],
                "size": int(fields[1]),
                "timestamp": int(fields[3]),
                "extra_fields": fields[4:],
                "source": "GLOBAL_3_0_24_BOOTSTRAP_FILELIST",
            }
        )
    return rows


def parse_jp_manifest(path: Path) -> list[dict[str, Any]]:
    _, records = parse_filelist(path.read_bytes(), path.name)
    return [
        {
            "path": row.path,
            "sha1": row.sha1,
            "size": row.size,
            "timestamp": row.timestamp,
            "extra_fields": list(row.fields),
            "category": category(row.path),
        }
        for row in records
    ]


def recovered_global_cache(root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        rows.append(
            {
                "path": rel,
                "sha1": sha1_file(path),
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
                "source": "RECOVERED_GLOBAL_TARGET_CACHE",
            }
        )
    return rows


def select_exact_matches(
    record: dict[str, Any],
    jp_by_hash: dict[tuple[str, int], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    return jp_by_hash.get((record["sha1"], record["size"]), [])


def classify_global_record(
    record: dict[str, Any],
    jp_by_path: dict[str, dict[str, Any]],
    jp_by_hash: dict[tuple[str, int], list[dict[str, Any]]],
) -> dict[str, Any]:
    same_path = jp_by_path.get(record["path"])
    exact = select_exact_matches(record, jp_by_hash)
    same_path_exact = bool(
        same_path
        and same_path["sha1"] == record["sha1"]
        and same_path["size"] == record["size"]
    )
    exact_other = [row for row in exact if row["path"] != record["path"]]

    if same_path_exact:
        classification = "EXACT_BYTES_SAME_PATH"
    elif exact_other:
        classification = "EXACT_BYTES_RENAMED_OR_MOVED"
    elif same_path:
        classification = "SAME_PATH_CHANGED_BYTES"
    else:
        classification = "GLOBAL_ONLY_RECOVERED"

    result = {
        **record,
        "classification": classification,
        "jp_same_path": same_path,
        "jp_exact_matches": exact,
    }
    if same_path and "timestamp" in record:
        result["timestamp_delta_seconds"] = (
            same_path["timestamp"] - record["timestamp"]
        )
        if same_path["timestamp"] == record["timestamp"]:
            order = "SAME_TIMESTAMP"
        elif same_path["timestamp"] > record["timestamp"]:
            order = "JP_RECORD_NEWER_TIMESTAMP"
        else:
            order = "JP_RECORD_OLDER_TIMESTAMP"
        result["timestamp_lineage"] = {
            "classification": order,
            "evidence": "TIMESTAMP_LINEAGE_CANDIDATE_NOT_IDENTITY_PROOF",
        }
    return result


def lineage_grade(classification: str) -> str:
    if classification in {
        "EXACT_BYTES_SAME_PATH",
        "EXACT_BYTES_RENAMED_OR_MOVED",
    }:
        return "GLOBAL_JP_IDENTICAL"
    if classification == "SAME_PATH_CHANGED_BYTES":
        return "PATH_CONTINUITY_BYTES_CHANGED"
    return "NO_CURRENT_JP_IDENTITY_PREDICATE"


def build(args: argparse.Namespace) -> dict[str, Any]:
    jp = parse_jp_manifest(args.jp_filelist)
    jp_by_path = {row["path"]: row for row in jp}
    jp_by_hash: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in jp:
        jp_by_hash[(row["sha1"], row["size"])].append(row)

    bootstrap = parse_global_bootstrap(args.global_filelist)
    cache = recovered_global_cache(args.global_cache_root)

    bootstrap_lineage = [
        classify_global_record(row, jp_by_path, jp_by_hash)
        for row in bootstrap
    ]
    cache_lineage = [
        classify_global_record(row, jp_by_path, jp_by_hash)
        for row in cache
    ]
    for row in bootstrap_lineage + cache_lineage:
        row["lineage_grade"] = lineage_grade(row["classification"])

    path_to_global = defaultdict(list)
    exact_jp_paths = defaultdict(list)
    for source_kind, rows in (
        ("bootstrap", bootstrap_lineage),
        ("recovered_cache", cache_lineage),
    ):
        for row in rows:
            path_to_global[row["path"]].append(
                {
                    "source_kind": source_kind,
                    "classification": row["classification"],
                    "lineage_grade": row["lineage_grade"],
                    "sha1": row["sha1"],
                    "size": row["size"],
                }
            )
            for match in row["jp_exact_matches"]:
                exact_jp_paths[match["path"]].append(
                    {
                        "source_kind": source_kind,
                        "global_path": row["path"],
                        "classification": row["classification"],
                    }
                )

    jp_records = []
    for row in jp:
        exact = exact_jp_paths.get(row["path"], [])
        path_links = path_to_global.get(row["path"], [])
        if exact:
            relation = "EXACT_GLOBAL_LINEAGE"
        elif path_links:
            relation = "SAME_PATH_GLOBAL_LINEAGE_BYTES_CHANGED"
        else:
            relation = "JP_ONLY_OR_UNCORROBORATED"
        jp_records.append(
            {
                **row,
                "genealogy_relation": relation,
                "exact_global_links": exact,
                "same_path_global_links": path_links,
            }
        )

    classifications = Counter(
        row["classification"] for row in bootstrap_lineage + cache_lineage
    )
    bootstrap_counts = Counter(row["classification"] for row in bootstrap_lineage)
    cache_counts = Counter(row["classification"] for row in cache_lineage)
    jp_relation_counts = Counter(row["genealogy_relation"] for row in jp_records)
    category_counts = Counter(row["category"] for row in jp_records)

    exact_edges = []
    seen_edges = set()
    for source_kind, rows in (
        ("GLOBAL_3_0_24_BOOTSTRAP_FILELIST", bootstrap_lineage),
        ("RECOVERED_GLOBAL_TARGET_CACHE", cache_lineage),
    ):
        for row in rows:
            for match in row["jp_exact_matches"]:
                edge = (
                    source_kind,
                    row["path"],
                    match["path"],
                    row["sha1"],
                    row["size"],
                )
                if edge in seen_edges:
                    continue
                seen_edges.add(edge)
                exact_edges.append(
                    {
                        "global_source": source_kind,
                        "global_path": row["path"],
                        "jp_path": match["path"],
                        "sha1": row["sha1"],
                        "size": row["size"],
                        "same_path": row["path"] == match["path"],
                        "provenance": "GLOBAL_JP_IDENTICAL_MANIFEST_HASH_AND_SIZE",
                    }
                )

    same_path_changed = []
    for source_kind, rows in (
        ("GLOBAL_3_0_24_BOOTSTRAP_FILELIST", bootstrap_lineage),
        ("RECOVERED_GLOBAL_TARGET_CACHE", cache_lineage),
    ):
        for row in rows:
            if row["classification"] != "SAME_PATH_CHANGED_BYTES":
                continue
            same_path_changed.append(
                {
                    "global_source": source_kind,
                    "path": row["path"],
                    "global_sha1": row["sha1"],
                    "global_size": row["size"],
                    "global_timestamp": row.get("timestamp"),
                    "jp_sha1": row["jp_same_path"]["sha1"],
                    "jp_size": row["jp_same_path"]["size"],
                    "jp_timestamp": row["jp_same_path"]["timestamp"],
                    "timestamp_lineage": row.get("timestamp_lineage"),
                    "provenance": "PATH_CONTINUITY_ONLY_BYTES_CHANGED",
                }
            )

    high_value = [
        edge
        for edge in exact_edges
        if edge["global_path"] in {
            "map-002/002_000_00001.mbn",
            "tutorial.mbn",
            "Battle.mbn",
            "info.mbn",
            "json_resource.mbn",
            "system.mbn",
        }
        or edge["jp_path"] in {
            "map/002_000_00001.mbn",
            "gui/tutorial.mbn",
            "gui/Battle.mbn",
            "map/info.mbn",
            "json_resource.mbn",
            "system.mbn",
        }
    ]

    return {
        "provenance": (
            "GLOBAL_AUTHORITY_WITH_CURRENT_JP_PUBLIC_MANIFEST_LINEAGE"
        ),
        "sources": {
            "global_bootstrap_filelist": {
                "path": str(args.global_filelist),
                "sha256": sha256_file(args.global_filelist),
            },
            "recovered_global_cache_root": str(args.global_cache_root),
            "jp_public_filelist": {
                "path": str(args.jp_filelist),
                "sha256": sha256_file(args.jp_filelist),
            },
        },
        "counts": {
            "jp_manifest_records": len(jp_records),
            "global_bootstrap_records": len(bootstrap_lineage),
            "recovered_global_cache_records": len(cache_lineage),
            "combined_global_evidence_records": (
                len(bootstrap_lineage) + len(cache_lineage)
            ),
            "combined_classifications": dict(sorted(classifications.items())),
            "bootstrap_classifications": dict(sorted(bootstrap_counts.items())),
            "cache_classifications": dict(sorted(cache_counts.items())),
            "jp_genealogy_relations": dict(sorted(jp_relation_counts.items())),
            "jp_categories": dict(sorted(category_counts.items())),
            "exact_identity_edges": len(exact_edges),
            "same_path_changed_edges": len(same_path_changed),
        },
        "global_bootstrap_lineage": bootstrap_lineage,
        "recovered_global_cache_lineage": cache_lineage,
        "exact_identity_edges": exact_edges,
        "same_path_changed_edges": same_path_changed,
        "high_value_verified_lineage": high_value,
        "jp_manifest": jp_records,
        "policy": {
            "GLOBAL_JP_IDENTICAL": (
                "SHA-1 and size identity between recovered Global evidence and "
                "the current JP public patch manifest. This proves byte identity "
                "for the resource, not unchanged surrounding game behavior."
            ),
            "PATH_CONTINUITY_BYTES_CHANGED": (
                "The same path survives in JP but bytes differ. Timestamps may "
                "support ancestry ordering only and are not identity proof."
            ),
            "JP_ONLY_OR_UNCORROBORATED": (
                "No recovered Global evidence links this JP resource. Do not "
                "promote it to historical Global presence."
            ),
        },
        "unresolved": [
            "JP-only resources cannot establish historical Global presence.",
            "Same-path timestamps are lineage hints, not proof of semantic continuity.",
            "Exact resource bytes do not prove unchanged server rules or code behavior around that resource.",
            "Remote Global patch resources not recovered in bootstrap/cache remain absent unless independently archived.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--global-filelist",
        type=Path,
        default=Path(
            "/home/ubuntu/logres/private/global-apk/3.0.24/"
            "extracted/assets/filelist.txt"
        ),
    )
    parser.add_argument(
        "--global-cache-root",
        type=Path,
        default=Path("/home/ubuntu/logres/private/global-target"),
    )
    parser.add_argument(
        "--jp-filelist",
        type=Path,
        default=Path(
            "/home/ubuntu/logres/private/jp-live-patch-cache/"
            "_meta/filelist.bin"
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
