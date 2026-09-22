#!/usr/bin/env python3
"""Privacy-bounded term scanner for the fully mirrored live Japanese Logres cache.

The scanner exports package/entry metadata, JSON key paths, numeric/bool scalar
values, collection sizes, source hashes, occurrence counts and byte offsets only.
It never exports JSON string values, Lua/text snippets, dialogue, binary payloads,
geometry, images, audio or textures.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
from typing import Any
from zipfile import ZipFile

from hydrate_private_assets import _make_synthetic_mbn, parse_mbn

CACHE_NAME = "jp-live-patch-cache"
SOURCE_SUFFIXES = {".json", ".lua", ".luac", ".txt", ".xml", ".bin", ".ini", ".tbl"}
DEFAULT_TOPS = {
    "(root)", "gui", "system", "skitevent", "battle", "map", "motion",
    "avatar", "lotitem", "weather", "shader", "graphicSettings", "palette",
}
MAX_MBN = 128 * 1024 * 1024
MAX_MANIFEST = 16 * 1024 * 1024
MAX_RESULTS = 4000
MAX_MATCHES_PER_SOURCE = 200
MAX_OFFSETS_PER_TERM = 16


def read_manifest(path: Path) -> list[dict[str, Any]]:
    with path.open("rb") as handle:
        head = handle.read(8)
        if len(head) != 8:
            raise ValueError("short-header")
        reserved, size = struct.unpack("<II", head)
        if reserved != 0 or size > MAX_MANIFEST:
            raise ValueError("bad-header")
        raw = handle.read(size)
        if len(raw) != size:
            raise ValueError("short-manifest")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, list):
        raise ValueError("manifest-not-array")
    return value


def top_category(relative: str) -> str:
    return relative.split("/", 1)[0] if "/" in relative else "(root)"


def esc(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def value_type(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if value is None:
        return "null"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def key_hits(value: Any, terms: tuple[str, ...]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    def walk(item: Any, pointer: str) -> None:
        if len(results) >= MAX_MATCHES_PER_SOURCE:
            return
        if isinstance(item, dict):
            for raw_key, child in sorted(item.items(), key=lambda pair: str(pair[0])):
                key = str(raw_key)
                low = key.lower()
                child_pointer = pointer + "/" + esc(key)
                matched = [term for term in terms if term in low]
                if matched:
                    result: dict[str, Any] = {
                        "pointer": child_pointer,
                        "key": key if len(key) <= 120 else "<long-key>",
                        "terms": matched,
                        "value_type": value_type(child),
                    }
                    if isinstance(child, bool):
                        result["value"] = child
                    elif isinstance(child, (int, float)) and not isinstance(child, bool):
                        result["value"] = child
                    elif isinstance(child, (list, dict)):
                        result["size"] = len(child)
                    results.append(result)
                walk(child, child_pointer)
        elif isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, pointer + "/" + str(index))

    walk(value, "")
    return results


def term_offsets(data: bytes, terms: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    lower = data.lower()
    result: dict[str, dict[str, Any]] = {}
    for term in terms:
        needle = term.encode("utf-8")
        offsets = []
        start = 0
        count = 0
        while True:
            offset = lower.find(needle, start)
            if offset < 0:
                break
            count += 1
            if len(offsets) < MAX_OFFSETS_PER_TERM:
                offsets.append(offset)
            start = offset + max(1, len(needle))
        if count:
            result[term] = {"count": count, "first_offsets": offsets}
    return result


def name_terms(name: str, terms: tuple[str, ...]) -> list[str]:
    low = name.lower()
    return [term for term in terms if term in low]


def inspect(anchor: Path, terms: tuple[str, ...], tops: set[str]) -> dict[str, Any]:
    root = anchor.resolve().parent / CACHE_NAME
    if not root.is_dir():
        raise ValueError("live patch cache not found")
    if not terms:
        raise ValueError("at least one term is required")

    package_name_hits = []
    entry_name_hits = []
    source_hits = []
    errors = []
    scanned_mbn = 0
    scanned_sources = 0

    for package in sorted(root.rglob("*.mbn")):
        relative = package.relative_to(root).as_posix()
        if top_category(relative) not in tops:
            continue

        matched_package = name_terms(relative, terms)
        if matched_package and len(package_name_hits) < MAX_RESULTS:
            package_name_hits.append({
                "package": relative,
                "terms": matched_package,
                "size": package.stat().st_size,
            })

        try:
            size = package.stat().st_size
        except OSError:
            continue
        if size > MAX_MBN:
            continue

        try:
            manifest = read_manifest(package)
        except Exception as exc:
            errors.append({"package": relative, "reason": type(exc).__name__})
            continue
        scanned_mbn += 1

        candidates = []
        for record in manifest:
            if not isinstance(record, dict) or not isinstance(record.get("name"), str):
                continue
            entry = record["name"]
            matched_entry = name_terms(entry, terms)
            if matched_entry and len(entry_name_hits) < MAX_RESULTS:
                entry_name_hits.append({
                    "package": relative,
                    "entry": entry,
                    "terms": matched_entry,
                })
            if Path(entry).suffix.lower() in SOURCE_SUFFIXES:
                candidates.append(entry)

        if not candidates:
            continue

        try:
            entries = parse_mbn(package.read_bytes())
        except Exception as exc:
            errors.append({"package": relative, "reason": "parse-" + type(exc).__name__})
            continue

        for entry in candidates:
            data = entries.get(entry)
            if data is None:
                continue
            scanned_sources += 1
            suffix = Path(entry).suffix.lower()
            result: dict[str, Any] = {
                "container": relative,
                "entry": entry,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "format": suffix.lstrip(".") or "unclassified",
            }

            if suffix == ".json":
                try:
                    parsed = json.loads(data)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    offsets = term_offsets(data, terms)
                    if offsets:
                        result["byte_hits"] = offsets
                else:
                    hits = key_hits(parsed, terms)
                    if hits:
                        result["json_key_hits"] = hits
                    offsets = term_offsets(data, terms)
                    # Byte counts are useful as a bounded recall signal, but no text is exported.
                    if offsets:
                        result["byte_hits"] = offsets
            else:
                offsets = term_offsets(data, terms)
                if offsets:
                    result["byte_hits"] = offsets

            if result.get("json_key_hits") or result.get("byte_hits"):
                source_hits.append(result)
                if len(source_hits) >= MAX_RESULTS:
                    break
        if len(source_hits) >= MAX_RESULTS:
            break

    term_summary: dict[str, dict[str, int]] = {}
    for term in terms:
        term_summary[term] = {
            "package_name_hits": sum(term in item["terms"] for item in package_name_hits),
            "entry_name_hits": sum(term in item["terms"] for item in entry_name_hits),
            "source_hits": sum(
                term in item.get("byte_hits", {})
                or any(term in hit["terms"] for hit in item.get("json_key_hits", []))
                for item in source_hits
            ),
            "byte_occurrences": sum(
                item.get("byte_hits", {}).get(term, {}).get("count", 0)
                for item in source_hits
            ),
            "json_key_occurrences": sum(
                1
                for item in source_hits
                for hit in item.get("json_key_hits", [])
                if term in hit["terms"]
            ),
        }

    return {
        "provenance": "PUBLIC_LIVE_JP_BOUNDED_TERM_METADATA",
        "policy": (
            "Search metadata only. JSON string values, source text/snippets, binary "
            "payloads, geometry, images, audio and textures are never exported. "
            "Term occurrence alone does not establish gameplay semantics."
        ),
        "terms": list(terms),
        "tops": sorted(tops),
        "scanned_mbn_count": scanned_mbn,
        "scanned_source_count": scanned_sources,
        "package_name_hits": package_name_hits,
        "entry_name_hits": entry_name_hits,
        "source_hits": source_hits,
        "term_summary": term_summary,
        "errors": errors[:200],
    }


def self_test() -> None:
    secret = "SECRET_PRIVATE_STRING_MUST_NOT_EXPORT"
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        anchor = root / "private.zip"
        anchor.write_bytes(b"x")
        cache = root / CACHE_NAME
        (cache / "gui").mkdir(parents=True)

        payload = {
            "tutorial": {
                "next_map_id": "001_000_00001",
                "spawn_x": 12,
                "dialogue": secret,
            },
            "battle_skill": {"interval": 0.25},
        }
        (cache / "gui" / "tutorial_battle.mbn").write_bytes(
            _make_synthetic_mbn("tutorial_settings.json", json.dumps(payload).encode())
        )
        source = (secret + " change_field tutorial battle_skill").encode()
        (cache / "gui" / "field.mbn").write_bytes(
            _make_synthetic_mbn("field.lua", source)
        )

        result = inspect(anchor, ("tutorial", "map", "battle", "spawn"), {"gui"})
        encoded = json.dumps(result, sort_keys=True)
        if secret in encoded:
            raise AssertionError("private string leaked")
        if result["term_summary"]["tutorial"]["source_hits"] < 1:
            raise AssertionError("tutorial evidence not found")
        numeric = [
            hit
            for source_item in result["source_hits"]
            for hit in source_item.get("json_key_hits", [])
            if hit["key"] == "spawn_x"
        ]
        if not numeric or numeric[0].get("value") != 12:
            raise AssertionError("numeric key metadata missing")

    print("Logres live bounded term inspector self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchor", type=Path)
    parser.add_argument("--term", action="append", default=[])
    parser.add_argument("--top", action="append", default=[])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0
    if not args.anchor or not args.term:
        print("--anchor and at least one --term are required", file=sys.stderr)
        return 2

    terms = tuple(sorted({term.strip().lower() for term in args.term if term.strip()}))
    tops = set(args.top) if args.top else set(DEFAULT_TOPS)
    try:
        result = inspect(args.anchor, terms, tops)
    except Exception as exc:
        print(f"scan failed: {type(exc).__name__}: {exc}", file=sys.stderr)
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
