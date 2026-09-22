#!/usr/bin/env python3
"""Extract bounded tutorial/first-field evidence from the private Logres cache.

This tool intentionally exports metadata, JSON pointers, contextual scalar values,
resource IDs, hashes, and byte offsets only. It never exports dialogue, Lua source,
binary payloads, texture data, or surrounding private text.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import tempfile
from typing import Any
from zipfile import ZipFile

from hydrate_private_assets import _make_synthetic_mbn, parse_mbn

RESOURCE_ID_RE = re.compile(r"^\d{3}_\d{3}_\d{5}$")
RESOURCE_ID_BYTES_RE = re.compile(rb"(?<!\d)(\d{3}_\d{3}_\d{5})(?!\d)")
MAP_PACKAGE_RE = re.compile(r"^\d{3}_\d{3}_\d{5}$")
SOURCE_SUFFIXES = {".json", ".lua", ".luac", ".txt", ".xml", ".bin"}
MAX_MBN_BYTES = 128 * 1024 * 1024
NEARBY_LIMIT = 4096
MAX_RESULTS_PER_SOURCE = 200

CONTEXT_TERMS = {
    "tutorial": ("tutorial",),
    "map": ("map",),
    "field": ("field",),
    "spawn": ("spawn",),
    "warp": ("warp",),
    "start": ("start", "entry", "initial"),
    "position": ("position", "pos", "coordinate", "coord"),
    "encounter": ("encounter", "battle"),
    "character": ("character", "charcreate", "char_create", "chara_create"),
    "quest": ("quest",),
}

BYTE_KEYWORDS = tuple(
    sorted(
        {
            token.encode("ascii")
            for values in CONTEXT_TERMS.values()
            for token in values
        }
    )
)

DIRECT_SCALAR_KEYS = (
    "map",
    "field",
    "spawn",
    "warp",
    "position",
    "posx",
    "posy",
    "startx",
    "starty",
    "entryx",
    "entryy",
    "coordinate",
    "coord",
    "column",
    "col",
    "row",
)


def pointer_escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def context_categories(parts: list[str]) -> list[str]:
    haystack = "/".join(part.lower() for part in parts)
    categories = [
        category
        for category, terms in CONTEXT_TERMS.items()
        if any(term in haystack for term in terms)
    ]
    return sorted(set(categories))


def json_tutorial_evidence(value: Any, source_name: str) -> dict[str, Any]:
    resources: list[dict[str, Any]] = []
    scalars: list[dict[str, Any]] = []
    source_categories = context_categories([source_name])

    def walk(item: Any, pointer: str, keys: list[str], direct_key: str) -> None:
        if isinstance(item, dict):
            for key, child in sorted(item.items(), key=lambda pair: str(pair[0])):
                key_text = str(key)
                walk(
                    child,
                    pointer + "/" + pointer_escape(key_text),
                    keys + [key_text],
                    key_text,
                )
            return

        if isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, pointer + "/" + str(index), keys, direct_key)
            return

        categories = sorted(
            set(source_categories + context_categories(keys + [direct_key]))
        )

        if isinstance(item, str) and RESOURCE_ID_RE.fullmatch(item):
            if categories:
                resources.append(
                    {
                        "pointer": pointer,
                        "resource_id": item,
                        "contexts": categories,
                    }
                )
            return

        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return

        key_token = normalized(direct_key)
        coordinate_scalar = (
            key_token in {"x", "y"}
            and bool({"spawn", "warp", "start", "position"} & set(categories))
        )
        direct_semantic = (
            any(token in key_token for token in DIRECT_SCALAR_KEYS)
            or coordinate_scalar
        )
        tutorial_context = "tutorial" in categories or "character" in categories
        location_context = bool(
            {"map", "field", "spawn", "warp", "start", "position"} & set(categories)
        )
        if direct_semantic and (tutorial_context or location_context):
            scalars.append(
                {
                    "pointer": pointer,
                    "key": direct_key,
                    "value": item,
                    "contexts": categories,
                }
            )

    walk(value, "", [], "")
    return {
        "resource_refs": resources[:MAX_RESULTS_PER_SOURCE],
        "resource_ref_count": len(resources),
        "context_scalars": scalars[:MAX_RESULTS_PER_SOURCE],
        "context_scalar_count": len(scalars),
    }


def all_offsets(data_lower: bytes, needle: bytes) -> list[int]:
    offsets: list[int] = []
    start = 0
    while True:
        index = data_lower.find(needle, start)
        if index < 0:
            return offsets
        offsets.append(index)
        start = index + max(1, len(needle))


def nearest_offset(target: int, offsets: list[int]) -> tuple[int, int] | None:
    if not offsets:
        return None
    index = bisect_left(offsets, target)
    candidates = []
    if index < len(offsets):
        candidates.append(offsets[index])
    if index:
        candidates.append(offsets[index - 1])
    best = min(candidates, key=lambda value: abs(value - target))
    return best, abs(best - target)


def binary_context_evidence(data: bytes) -> dict[str, Any]:
    lower = data.lower()
    keyword_offsets = {
        keyword.decode("ascii"): all_offsets(lower, keyword)
        for keyword in BYTE_KEYWORDS
    }
    refs: list[dict[str, Any]] = []

    for match in RESOURCE_ID_BYTES_RE.finditer(data):
        resource_id = match.group(1).decode("ascii")
        best: tuple[str, int, int] | None = None
        for keyword, offsets in keyword_offsets.items():
            nearest = nearest_offset(match.start(), offsets)
            if nearest is None:
                continue
            offset, distance = nearest
            if best is None or distance < best[2]:
                best = (keyword, offset, distance)

        if best is None or best[2] > NEARBY_LIMIT:
            continue

        refs.append(
            {
                "resource_id": resource_id,
                "offset": match.start(),
                "nearest_keyword": best[0],
                "keyword_offset": best[1],
                "distance": best[2],
            }
        )

    keyword_counts = {
        keyword: len(offsets)
        for keyword, offsets in keyword_offsets.items()
        if offsets
    }
    return {
        "contextual_resource_refs": refs[:MAX_RESULTS_PER_SOURCE],
        "contextual_resource_ref_count": len(refs),
        "keyword_counts": keyword_counts,
    }


def read_mbn_manifest(source: ZipFile, info) -> list[dict[str, Any]]:
    with source.open(info) as handle:
        header = handle.read(8)
        if len(header) != 8:
            raise ValueError("short MBN header")
        reserved, manifest_size = struct.unpack("<II", header)
        if reserved != 0 or manifest_size > 8 * 1024 * 1024:
            raise ValueError("invalid MBN manifest header")
        raw = handle.read(manifest_size)
    manifest = json.loads(raw)
    if not isinstance(manifest, list):
        raise ValueError("MBN manifest is not a list")
    return manifest


def inspect_archive(archive: Path) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    map_packages: set[str] = set()

    with ZipFile(archive) as source:
        for info in sorted(source.infolist(), key=lambda item: item.filename):
            member = info.filename
            member_path = Path(member)

            if (
                member.startswith("files/cache/patch/map/")
                and member.endswith(".mbn")
                and MAP_PACKAGE_RE.fullmatch(member_path.stem)
            ):
                map_packages.add(member_path.stem)

            if member_path.suffix.lower() != ".mbn":
                continue

            try:
                manifest = read_mbn_manifest(source, info)
            except (ValueError, json.JSONDecodeError, struct.error) as exc:
                errors.append({"member": member, "reason": type(exc).__name__})
                continue

            candidate_names = [
                record.get("name")
                for record in manifest
                if isinstance(record, dict)
                and isinstance(record.get("name"), str)
                and Path(record["name"]).suffix.lower() in SOURCE_SUFFIXES
            ]
            if not candidate_names:
                continue
            if info.file_size > MAX_MBN_BYTES:
                errors.append({"member": member, "reason": "scan-bound"})
                continue

            try:
                entries = parse_mbn(source.read(info))
            except ValueError:
                errors.append({"member": member, "reason": "parse-mbn"})
                continue

            for entry_name in candidate_names:
                data = entries.get(entry_name)
                if data is None:
                    continue

                source_result: dict[str, Any] = {
                    "container": member,
                    "entry": entry_name,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "size": len(data),
                }
                suffix = Path(entry_name).suffix.lower()

                if suffix == ".json":
                    try:
                        parsed = json.loads(data)
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        source_result["format"] = "json-unparsed"
                        source_result["binary_context"] = binary_context_evidence(data)
                    else:
                        source_result["format"] = "json"
                        source_result["json_context"] = json_tutorial_evidence(
                            parsed, f"{member}/{entry_name}"
                        )
                else:
                    if data.startswith(b"\x1bLua"):
                        source_result["format"] = "lua-bytecode"
                    elif data.startswith(b"\x1bLJ"):
                        source_result["format"] = "luajit-bytecode"
                    else:
                        source_result["format"] = suffix.lstrip(".") or "unclassified"
                    source_result["binary_context"] = binary_context_evidence(data)

                json_context = source_result.get("json_context", {})
                binary_context = source_result.get("binary_context", {})
                meaningful = (
                    json_context.get("resource_ref_count", 0)
                    or json_context.get("context_scalar_count", 0)
                    or binary_context.get("contextual_resource_ref_count", 0)
                    or (
                        "tutorial" in context_categories([member, entry_name])
                        and binary_context.get("keyword_counts")
                    )
                )
                if meaningful:
                    evidence.append(source_result)

    summary: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "json_context_ref_count": 0,
            "binary_context_ref_count": 0,
            "contexts": Counter(),
            "source_count": 0,
        }
    )

    for item in evidence:
        source_ids: set[str] = set()
        for ref in item.get("json_context", {}).get("resource_refs", []):
            resource_id = ref["resource_id"]
            source_ids.add(resource_id)
            summary[resource_id]["json_context_ref_count"] += 1
            summary[resource_id]["contexts"].update(ref.get("contexts", []))
        for ref in item.get("binary_context", {}).get("contextual_resource_refs", []):
            resource_id = ref["resource_id"]
            source_ids.add(resource_id)
            summary[resource_id]["binary_context_ref_count"] += 1
            summary[resource_id]["contexts"].update([ref["nearest_keyword"]])
        for resource_id in source_ids:
            summary[resource_id]["source_count"] += 1

    summary_out = {}
    for resource_id, item in sorted(summary.items()):
        summary_out[resource_id] = {
            "json_context_ref_count": item["json_context_ref_count"],
            "binary_context_ref_count": item["binary_context_ref_count"],
            "source_count": item["source_count"],
            "contexts": [
                {"name": name, "count": count}
                for name, count in item["contexts"].most_common()
            ],
            "present_as_recovered_map_package": resource_id in map_packages,
        }

    return {
        "provenance": "PRIVATE_CACHE_TUTORIAL_CONTEXT_METADATA",
        "semantic_policy": (
            "Resource-ID syntax alone does not identify maps. A recovered map-package "
            "match is reported separately. JSON pointers and nearby keyword offsets "
            "are evidence locations, not semantic proof of tutorial selection."
        ),
        "nearby_byte_limit": NEARBY_LIMIT,
        "recovered_map_package_ids": sorted(map_packages),
        "evidence_source_count": len(evidence),
        "evidence_sources": evidence,
        "resource_summary": summary_out,
        "errors": errors,
    }


def self_test() -> None:
    private_dialog = "SECRET DIALOGUE MUST NOT EXPORT"
    private_source = b"SECRET LUA SOURCE tutorial map 001_000_00700 spawn"
    with tempfile.TemporaryDirectory() as raw:
        archive = Path(raw) / "private.zip"
        tutorial = {
            "tutorial": {
                "map_id": "001_000_00700",
                "spawn": {"x": 12, "y": 34},
                "dialog": private_dialog,
            }
        }
        noise = {
            "sound_id": "100_002_00065",
            "dialog": private_dialog,
        }
        with ZipFile(archive, "w") as target:
            target.writestr(
                "files/cache/patch/tutorial/settings.mbn",
                _make_synthetic_mbn(
                    "tutorial_settings.json",
                    json.dumps(tutorial).encode("utf-8"),
                ),
            )
            target.writestr(
                "files/cache/patch/tutorial/script.mbn",
                _make_synthetic_mbn("tutorial.lua", private_source),
            )
            target.writestr(
                "files/cache/patch/audio/noise.mbn",
                _make_synthetic_mbn(
                    "audio.json",
                    json.dumps(noise).encode("utf-8"),
                ),
            )
            target.writestr(
                "files/cache/patch/map/001_000_00700.mbn",
                b"",
            )

        result = inspect_archive(archive)
        encoded = json.dumps(result, sort_keys=True)
        if private_dialog in encoded or "SECRET LUA SOURCE" in encoded:
            raise AssertionError("private source/dialogue leaked into metadata")
        candidate = result["resource_summary"].get("001_000_00700")
        if not candidate:
            raise AssertionError("contextual tutorial resource ID was not found")
        if not candidate["present_as_recovered_map_package"]:
            raise AssertionError("map-package cross-reference was not retained")
        if "100_002_00065" in result["resource_summary"]:
            raise AssertionError("uncontextualized audio resource was misclassified")
        pointers = [
            scalar["pointer"]
            for source in result["evidence_sources"]
            for scalar in source.get("json_context", {}).get("context_scalars", [])
        ]
        if "/tutorial/spawn/x" not in pointers or "/tutorial/spawn/y" not in pointers:
            raise AssertionError("tutorial spawn scalar pointers were not found")

    print("Logres private tutorial evidence inspector self-test: PASS")


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
        print(
            "archive argument is required unless --self-test is used",
            file=sys.stderr,
        )
        return 2

    try:
        result = inspect_archive(args.archive)
    except (OSError, ValueError) as exc:
        print(f"Logres tutorial evidence inspection failed: {exc}", file=sys.stderr)
        return 1

    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        sys.stdout.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
