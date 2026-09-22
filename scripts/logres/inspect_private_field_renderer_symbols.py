#!/usr/bin/env python3
"""Scan packaged private client source for field-renderer symbol evidence.

Exports only source metadata plus allowlisted term counts/offsets. It never exports
source text, snippets, dialogue, binaries, images, geometry, or textures.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
from zipfile import ZipFile

from hydrate_private_assets import _make_synthetic_mbn, parse_mbn

MAX_MBN_BYTES = 128 * 1024 * 1024
MAX_OFFSETS = 12
SOURCE_SUFFIXES = {".lua", ".luac", ".json", ".txt", ".xml", ".bin"}

TERMS = (
    "FieldAnimator",
    "addAnimationData",
    "FieldTerrain",
    "FieldTerrainNode",
    "FieldVertex",
    "setCameraMask",
    "CameraFlag",
    "cameraMask",
    "fieldCamera",
    "field_camera",
    "animationInterval",
    "animation_interval",
    "frameInterval",
    "frame_interval",
    "UvPos",
    "uvPos",
    "uv_pose",
)


def all_offsets(data: bytes, needle: bytes) -> list[int]:
    result = []
    start = 0
    lower = data.lower()
    token = needle.lower()
    while True:
        offset = lower.find(token, start)
        if offset < 0:
            return result
        result.append(offset)
        start = offset + max(1, len(token))


def scan_terms(data: bytes) -> dict[str, dict[str, object]]:
    hits = {}
    for term in TERMS:
        offsets = all_offsets(data, term.encode("ascii"))
        if offsets:
            hits[term] = {
                "count": len(offsets),
                "first_offsets": offsets[:MAX_OFFSETS],
            }
    return hits


def manifest(source: ZipFile, info) -> list[dict]:
    with source.open(info) as handle:
        header = handle.read(8)
        if len(header) != 8:
            raise ValueError("short MBN header")
        reserved, size = struct.unpack("<II", header)
        if reserved != 0 or size > 8 * 1024 * 1024:
            raise ValueError("invalid MBN manifest header")
        raw = handle.read(size)
    value = json.loads(raw)
    if not isinstance(value, list):
        raise ValueError("MBN manifest is not a list")
    return value


def inspect_archive(archive: Path) -> dict:
    sources = []
    manifest_name_hits = []
    errors = []

    with ZipFile(archive) as source:
        for info in sorted(source.infolist(), key=lambda item: item.filename):
            if Path(info.filename).suffix.lower() != ".mbn":
                continue

            try:
                records = manifest(source, info)
            except (ValueError, json.JSONDecodeError, struct.error) as exc:
                errors.append({"member": info.filename, "reason": type(exc).__name__})
                continue

            names = [
                record["name"]
                for record in records
                if isinstance(record, dict) and isinstance(record.get("name"), str)
            ]
            candidates = [
                name
                for name in names
                if Path(name).suffix.lower() in SOURCE_SUFFIXES
            ]

            for name in names:
                name_hits = scan_terms(name.encode("utf-8", errors="ignore"))
                if name_hits:
                    manifest_name_hits.append(
                        {
                            "container": info.filename,
                            "entry": name,
                            "hits": name_hits,
                        }
                    )

            if not candidates:
                continue
            if info.file_size > MAX_MBN_BYTES:
                errors.append({"member": info.filename, "reason": "scan-bound"})
                continue

            try:
                entries = parse_mbn(source.read(info))
            except ValueError:
                errors.append({"member": info.filename, "reason": "parse-mbn"})
                continue

            for name in candidates:
                data = entries.get(name)
                if data is None:
                    continue
                hits = scan_terms(data)
                if not hits:
                    continue
                if data.startswith(b"\x1bLua"):
                    fmt = "lua-bytecode"
                elif data.startswith(b"\x1bLJ"):
                    fmt = "luajit-bytecode"
                else:
                    fmt = Path(name).suffix.lower().lstrip(".") or "unclassified"
                sources.append(
                    {
                        "container": info.filename,
                        "entry": name,
                        "format": fmt,
                        "size": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "hits": hits,
                    }
                )

    term_summary = {}
    for term in TERMS:
        source_count = 0
        total_count = 0
        for item in sources:
            if term in item["hits"]:
                source_count += 1
                total_count += item["hits"][term]["count"]
        name_count = sum(
            item["hits"].get(term, {}).get("count", 0)
            for item in manifest_name_hits
        )
        if source_count or name_count:
            term_summary[term] = {
                "source_count": source_count,
                "content_occurrence_count": total_count,
                "manifest_name_occurrence_count": name_count,
            }

    return {
        "provenance": "PRIVATE_CACHE_FIELD_RENDER_SYMBOL_METADATA",
        "semantic_policy": (
            "Allowlisted string occurrences and offsets are search evidence only. "
            "They do not establish call semantics, timing values, camera layering, "
            "or renderer behavior without further corroboration."
        ),
        "terms": list(TERMS),
        "source_hit_count": len(sources),
        "sources": sources,
        "manifest_name_hit_count": len(manifest_name_hits),
        "manifest_name_hits": manifest_name_hits,
        "term_summary": term_summary,
        "errors": errors,
    }


def self_test() -> None:
    private = "SECRET SOURCE MUST NEVER EXPORT"
    with tempfile.TemporaryDirectory() as raw:
        archive = Path(raw) / "private.zip"
        lua = (
            private
            + " FieldAnimator addAnimationData setCameraMask cameraMask "
            + "animationInterval"
        ).encode("utf-8")
        with ZipFile(archive, "w") as target:
            target.writestr(
                "files/cache/patch/script.mbn",
                _make_synthetic_mbn("FieldTerrainNode.lua", lua),
            )

        result = inspect_archive(archive)
        encoded = json.dumps(result, sort_keys=True)
        if private in encoded:
            raise AssertionError("private source text leaked")
        if result["source_hit_count"] != 1:
            raise AssertionError("source hit was not found")
        hits = result["sources"][0]["hits"]
        for term in ("FieldAnimator", "addAnimationData", "setCameraMask"):
            if hits.get(term, {}).get("count") != 1:
                raise AssertionError(f"missing expected term: {term}")
        if result["manifest_name_hit_count"] != 1:
            raise AssertionError("manifest name term was not found")

    print("Logres private field renderer symbol inspector self-test: PASS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", nargs="?", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.archive is None:
        print("archive argument required unless --self-test", file=sys.stderr)
        return 2

    try:
        result = inspect_archive(args.archive)
    except (OSError, ValueError) as exc:
        print(f"Logres renderer symbol scan failed: {exc}", file=sys.stderr)
        return 1

    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        sys.stdout.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
