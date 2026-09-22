#!/usr/bin/env python3
"""Find exact client-source references to confirmed recovered Logres map packages.

Only metadata is exported: map IDs already proven by cache package paths, source
container/entry names, JSON pointers or byte offsets, hashes, and nearest keyword
metadata. No dialogue, Lua/text snippets, binaries, geometry, or textures are
exported.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any
from zipfile import ZipFile

from hydrate_private_assets import _make_synthetic_mbn, parse_mbn
from inspect_private_tutorial_evidence import (
    BYTE_KEYWORDS,
    MAP_PACKAGE_RE,
    MAX_MBN_BYTES,
    SOURCE_SUFFIXES,
    all_offsets,
    context_categories,
    nearest_offset,
    pointer_escape,
    read_mbn_manifest,
)


def recovered_map_ids(source: ZipFile) -> set[str]:
    return {
        Path(info.filename).stem
        for info in source.infolist()
        if info.filename.startswith("files/cache/patch/map/")
        and info.filename.endswith(".mbn")
        and MAP_PACKAGE_RE.fullmatch(Path(info.filename).stem)
    }


def json_map_references(value: Any, map_ids: set[str]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []

    def walk(item: Any, pointer: str, keys: list[str]) -> None:
        if isinstance(item, dict):
            for raw_key, child in sorted(item.items(), key=lambda pair: str(pair[0])):
                key = str(raw_key)
                child_pointer = pointer + "/" + pointer_escape(key)
                if key in map_ids:
                    refs.append(
                        {
                            "map_id": key,
                            "kind": "key",
                            "pointer": child_pointer,
                            "contexts": context_categories(keys + [key]),
                        }
                    )
                walk(child, child_pointer, keys + [key])
            return

        if isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, pointer + "/" + str(index), keys)
            return

        if isinstance(item, str) and item in map_ids:
            refs.append(
                {
                    "map_id": item,
                    "kind": "value",
                    "pointer": pointer,
                    "contexts": context_categories(keys),
                }
            )

    walk(value, "", [])
    return refs


def nearest_keyword_metadata(data: bytes, offset: int) -> dict[str, Any] | None:
    lower = data.lower()
    best: tuple[str, int, int] | None = None
    for keyword in BYTE_KEYWORDS:
        offsets = all_offsets(lower, keyword)
        nearest = nearest_offset(offset, offsets)
        if nearest is None:
            continue
        keyword_offset, distance = nearest
        label = keyword.decode("ascii")
        if best is None or distance < best[2]:
            best = (label, keyword_offset, distance)

    if best is None:
        return None
    return {
        "nearest_keyword": best[0],
        "keyword_offset": best[1],
        "distance": best[2],
    }


def binary_map_references(data: bytes, map_ids: set[str]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for map_id in sorted(map_ids):
        needle = map_id.encode("ascii")
        start = 0
        while True:
            offset = data.find(needle, start)
            if offset < 0:
                break
            item: dict[str, Any] = {
                "map_id": map_id,
                "offset": offset,
            }
            keyword = nearest_keyword_metadata(data, offset)
            if keyword is not None:
                item.update(keyword)
            refs.append(item)
            start = offset + len(needle)
    return refs


def inspect_archive(archive: Path) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    with ZipFile(archive) as source:
        map_ids = recovered_map_ids(source)

        for info in sorted(source.infolist(), key=lambda item: item.filename):
            if Path(info.filename).suffix.lower() != ".mbn":
                continue

            try:
                manifest = read_mbn_manifest(source, info)
            except (ValueError, json.JSONDecodeError) as exc:
                errors.append(
                    {"member": info.filename, "reason": type(exc).__name__}
                )
                continue

            candidate_names = [
                record.get("name")
                for record in manifest
                if isinstance(record, dict)
                and isinstance(record.get("name"), str)
                and Path(record["name"]).suffix.lower() in SOURCE_SUFFIXES
            ]
            manifest_refs = [
                {
                    "map_id": map_id,
                    "entry": name,
                }
                for name in candidate_names
                for map_id in sorted(map_ids)
                if map_id in name
            ]

            if not candidate_names and not manifest_refs:
                continue
            if info.file_size > MAX_MBN_BYTES:
                errors.append({"member": info.filename, "reason": "scan-bound"})
                continue

            try:
                entries = parse_mbn(source.read(info))
            except ValueError:
                errors.append({"member": info.filename, "reason": "parse-mbn"})
                continue

            for entry_name in candidate_names:
                data = entries.get(entry_name)
                if data is None:
                    continue

                result: dict[str, Any] = {
                    "container": info.filename,
                    "entry": entry_name,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "size": len(data),
                }
                suffix = Path(entry_name).suffix.lower()

                if suffix == ".json":
                    try:
                        parsed = json.loads(data)
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        result["format"] = "json-unparsed"
                        refs = binary_map_references(data, map_ids)
                        if refs:
                            result["byte_refs"] = refs
                    else:
                        result["format"] = "json"
                        refs = json_map_references(parsed, map_ids)
                        if refs:
                            result["json_refs"] = refs
                else:
                    if data.startswith(b"\x1bLua"):
                        result["format"] = "lua-bytecode"
                    elif data.startswith(b"\x1bLJ"):
                        result["format"] = "luajit-bytecode"
                    else:
                        result["format"] = suffix.lstrip(".") or "unclassified"
                    refs = binary_map_references(data, map_ids)
                    if refs:
                        result["byte_refs"] = refs

                if result.get("json_refs") or result.get("byte_refs"):
                    sources.append(result)

            if manifest_refs:
                sources.append(
                    {
                        "container": info.filename,
                        "format": "manifest",
                        "manifest_refs": manifest_refs,
                    }
                )

    summary = {
        map_id: {
            "source_count": 0,
            "json_key_count": 0,
            "json_value_count": 0,
            "byte_ref_count": 0,
            "manifest_ref_count": 0,
            "contexts": Counter(),
        }
        for map_id in sorted(map_ids)
    }

    for source_item in sources:
        touched: set[str] = set()
        for ref in source_item.get("json_refs", []):
            map_id = ref["map_id"]
            touched.add(map_id)
            summary[map_id][
                "json_key_count" if ref["kind"] == "key" else "json_value_count"
            ] += 1
            summary[map_id]["contexts"].update(ref.get("contexts", []))
        for ref in source_item.get("byte_refs", []):
            map_id = ref["map_id"]
            touched.add(map_id)
            summary[map_id]["byte_ref_count"] += 1
            if "nearest_keyword" in ref:
                summary[map_id]["contexts"].update([ref["nearest_keyword"]])
        for ref in source_item.get("manifest_refs", []):
            map_id = ref["map_id"]
            touched.add(map_id)
            summary[map_id]["manifest_ref_count"] += 1
        for map_id in touched:
            summary[map_id]["source_count"] += 1

    encoded_summary = {}
    for map_id, item in summary.items():
        encoded_summary[map_id] = {
            "source_count": item["source_count"],
            "json_key_count": item["json_key_count"],
            "json_value_count": item["json_value_count"],
            "byte_ref_count": item["byte_ref_count"],
            "manifest_ref_count": item["manifest_ref_count"],
            "contexts": [
                {"name": name, "count": count}
                for name, count in item["contexts"].most_common()
            ],
        }

    return {
        "provenance": "PRIVATE_CACHE_CONFIRMED_MAP_REFERENCE_METADATA",
        "semantic_policy": (
            "Only IDs independently confirmed by files/cache/patch/map/<id>.mbn "
            "are searched. A source occurrence proves a reference to that recovered "
            "map package ID but does not by itself prove tutorial selection."
        ),
        "confirmed_map_package_ids": sorted(map_ids),
        "source_reference_count": len(sources),
        "sources": sources,
        "summary": encoded_summary,
        "errors": errors,
    }


def self_test() -> None:
    private_text = "SECRET PRIVATE CONTENT MUST NOT EXPORT"
    map_id = "001_000_00700"
    other_id = "100_002_00065"

    with tempfile.TemporaryDirectory() as raw:
        archive = Path(raw) / "private.zip"
        json_data = {
            map_id: {"spawn": {"x": 4, "y": 7}, "secret": private_text},
            "tutorial": {"map_id": map_id, "sound_id": other_id},
        }
        lua_data = (
            f"{private_text} tutorial map {map_id} spawn {other_id}"
        ).encode("utf-8")

        with ZipFile(archive, "w") as target:
            target.writestr(
                f"files/cache/patch/map/{map_id}.mbn",
                _make_synthetic_mbn("map.bin", b"x"),
            )
            target.writestr(
                "files/cache/patch/tutorial/json.mbn",
                _make_synthetic_mbn(
                    "tutorial.json",
                    json.dumps(json_data).encode("utf-8"),
                ),
            )
            target.writestr(
                "files/cache/patch/tutorial/lua.mbn",
                _make_synthetic_mbn("tutorial.lua", lua_data),
            )

        result = inspect_archive(archive)
        encoded = json.dumps(result, sort_keys=True)
        if private_text in encoded:
            raise AssertionError("private content leaked into map-reference metadata")
        if other_id in result["summary"]:
            raise AssertionError("non-map resource ID entered confirmed-map summary")
        item = result["summary"][map_id]
        if item["json_key_count"] != 1 or item["json_value_count"] != 1:
            raise AssertionError("JSON map key/value references were not both found")
        if item["byte_ref_count"] != 1:
            raise AssertionError("binary/text exact map reference was not found")
        if item["source_count"] != 2:
            raise AssertionError("map source count is incorrect")

    print("Logres confirmed private map reference inspector self-test: PASS")


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
        print(f"Logres map-reference inspection failed: {exc}", file=sys.stderr)
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
