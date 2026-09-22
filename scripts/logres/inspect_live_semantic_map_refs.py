#!/usr/bin/env python3
"""Find semantically contextualized references to confirmed live Logres map IDs.

This scanner uses JSON key/ancestor structure and bounded Lua symbol proximity.
It exports identifiers, key names, offsets, hashes and evidence classes only.
It never exports source text, dialogue, binary payloads, geometry or textures.
"""
from __future__ import annotations

import argparse
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

CACHE_NAME = "jp-live-patch-cache"
MAP_NAME_RE = re.compile(r"^[0-9]{3}_[0-9]{3}_[0-9]{5}(?:__ans)?$")
MAP_TEXT_RE = re.compile(r"(?<![0-9])([0-9]{3}_[0-9]{3}_[0-9]{5})(?![0-9])")
MAP_BYTES_RE = re.compile(rb"(?<![0-9])([0-9]{3}_[0-9]{3}_[0-9]{5})(?![0-9])")

SOURCE_SUFFIXES = {".json", ".lua", ".luac", ".txt", ".xml", ".bin"}
SCAN_TOPS = {"(root)", "gui", "system", "skitevent", "battle"}
MAX_MBN = 128 * 1024 * 1024
MAX_MANIFEST = 16 * 1024 * 1024
MAX_REFS = 8000
MAX_REFS_PER_SOURCE = 500
LUA_WINDOW = 512

POSITIVE_PATTERNS = (
    ("tutorial", re.compile(r"tutorial|beginner", re.I)),
    ("map", re.compile(r"(^|[_-])map(?:[_-]?id)?($|[_-])|mapid", re.I)),
    ("field", re.compile(r"(^|[_-])field(?:[_-]?id)?($|[_-])|fieldid", re.I)),
    ("warp", re.compile(r"warp|teleport|transfer", re.I)),
    ("destination", re.compile(r"destination|dest(?:ination)?[_-]?map|next[_-]?map|target[_-]?map", re.I)),
    ("area", re.compile(r"(^|[_-])area(?:[_-]?id)?($|[_-])|areaid", re.I)),
    ("stage", re.compile(r"(^|[_-])stage(?:[_-]?id)?($|[_-])|stageid", re.I)),
    ("scene", re.compile(r"(^|[_-])scene(?:[_-]?id)?($|[_-])|sceneid", re.I)),
    ("spawn", re.compile(r"spawn|respawn", re.I)),
    ("start", re.compile(r"(^|[_-])(start|initial|entry)([_-]|$)", re.I)),
    ("location", re.compile(r"location|position|coordinate|coord", re.I)),
    ("quest", re.compile(r"quest", re.I)),
)

NEGATIVE_PATTERNS = (
    ("sound", re.compile(r"sound|soundid|se[_-]?id|bgm", re.I)),
    ("icon", re.compile(r"icon", re.I)),
    ("skill", re.compile(r"skill", re.I)),
    ("buff", re.compile(r"buff|debuff", re.I)),
    ("effect", re.compile(r"effect|efc", re.I)),
    ("image", re.compile(r"image|sprite|texture", re.I)),
    ("resource", re.compile(r"resource", re.I)),
)

LUA_SYMBOLS = (
    b"map_id", b"mapid", b"field_id", b"fieldid", b"warp", b"teleport",
    b"change_field", b"field_change", b"destination", b"next_map",
    b"area_id", b"stage_id", b"scene_id", b"tutorial", b"spawn",
)


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


def map_ids(root: Path) -> set[str]:
    result: set[str] = set()
    map_root = root / "map"
    if not map_root.is_dir():
        return result
    for path in map_root.rglob("*.mbn"):
        stem = path.stem
        if not MAP_NAME_RE.fullmatch(stem):
            continue
        if stem.endswith("__ans"):
            stem = stem[:-5]
        result.add(stem)
    return result


def top_category(relative: str) -> str:
    return relative.split("/", 1)[0] if "/" in relative else "(root)"


def safe_key(value: Any) -> str:
    text = str(value)
    return text if len(text) <= 96 else "<long-key>"


def labels_for_key(key: str) -> tuple[list[str], list[str]]:
    positive = [name for name, pattern in POSITIVE_PATTERNS if pattern.search(key)]
    negative = [name for name, pattern in NEGATIVE_PATTERNS if pattern.search(key)]
    return positive, negative


def context_labels(stack: list[str]) -> tuple[list[str], list[str]]:
    positive: list[str] = []
    negative: list[str] = []
    for key in stack[-12:]:
        pos, neg = labels_for_key(key)
        for label in pos:
            if label not in positive:
                positive.append(label)
        for label in neg:
            if label not in negative:
                negative.append(label)
    return positive, negative


def evidence_class(direct_pos: list[str], ancestor_pos: list[str], direct_neg: list[str]) -> str:
    location = {"map", "field", "warp", "destination", "area", "stage", "scene", "spawn"}
    if direct_neg and not direct_pos:
        return "negative-resource-context"
    if location.intersection(direct_pos):
        return "direct-location-key"
    combined = set(direct_pos) | set(ancestor_pos)
    if "tutorial" in combined and location.intersection(combined):
        return "tutorial-location-context"
    if location.intersection(combined):
        return "location-context"
    if "tutorial" in combined or "quest" in combined or "start" in combined:
        return "workflow-context"
    return "weak-context"


def json_references(value: Any, ids: set[str], container: str, entry: str) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []

    def add(mid: str, kind: str, pointer: str, stack: list[str], direct_key: str | None) -> None:
        direct_pos, direct_neg = labels_for_key(direct_key or "")
        ancestor_pos, ancestor_neg = context_labels(stack)
        refs.append({
            "map_id": mid,
            "container": container,
            "entry": entry,
            "format": "json",
            "kind": kind,
            "pointer": pointer,
            "direct_key": safe_key(direct_key) if direct_key else None,
            "direct_positive_labels": direct_pos,
            "ancestor_positive_labels": ancestor_pos,
            "negative_labels": sorted(set(direct_neg + ancestor_neg)),
            "evidence_class": evidence_class(direct_pos, ancestor_pos, direct_neg),
        })

    def walk(item: Any, pointer: str, stack: list[str]) -> None:
        if len(refs) >= MAX_REFS_PER_SOURCE:
            return
        if isinstance(item, dict):
            for raw_key, child in item.items():
                key = str(raw_key)
                escaped = key.replace("~", "~0").replace("/", "~1")
                child_pointer = pointer + "/" + escaped
                if key in ids:
                    add(key, "key", child_pointer, stack + [key], key)
                walk(child, child_pointer, stack + [key])
            return
        if isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, pointer + "/" + str(index), stack)
            return
        if not isinstance(item, str):
            return
        direct_key = stack[-1] if stack else None
        for match in MAP_TEXT_RE.finditer(item):
            mid = match.group(1)
            if mid in ids:
                add(mid, "value" if item == mid else "embedded-string", pointer, stack, direct_key)

    walk(value, "", [])
    return refs


def lua_symbol_context(data: bytes, offset: int) -> list[dict[str, Any]]:
    lo = max(0, offset - LUA_WINDOW)
    hi = min(len(data), offset + LUA_WINDOW)
    chunk = data[lo:hi].lower()
    found = []
    for symbol in LUA_SYMBOLS:
        start = 0
        best = None
        while True:
            pos = chunk.find(symbol, start)
            if pos < 0:
                break
            absolute = lo + pos
            distance = abs(absolute - offset)
            if best is None or distance < best[1]:
                best = (absolute, distance)
            start = pos + 1
        if best is not None:
            found.append({
                "symbol": symbol.decode("ascii"),
                "offset": best[0],
                "distance": best[1],
            })
    found.sort(key=lambda item: (item["distance"], item["symbol"]))
    return found[:12]


def byte_references(data: bytes, ids: set[str], container: str, entry: str) -> list[dict[str, Any]]:
    refs = []
    for match in MAP_BYTES_RE.finditer(data):
        mid = match.group(1).decode("ascii")
        if mid not in ids:
            continue
        symbols = lua_symbol_context(data, match.start())
        if not symbols:
            continue
        refs.append({
            "map_id": mid,
            "container": container,
            "entry": entry,
            "format": Path(entry).suffix.lower().lstrip("."),
            "kind": "byte-reference",
            "offset": match.start(),
            "symbol_context": symbols,
            "evidence_class": "symbol-proximity",
        })
        if len(refs) >= MAX_REFS_PER_SOURCE:
            break
    return refs


def inspect(anchor: Path) -> dict[str, Any]:
    root = anchor.resolve().parent / CACHE_NAME
    if not root.is_dir():
        raise ValueError("live patch cache not found")
    ids = map_ids(root)

    refs = []
    errors = []
    scanned_mbn = 0
    scanned_sources = 0

    for package in sorted(root.rglob("*.mbn")):
        relative = package.relative_to(root).as_posix()
        if top_category(relative) not in SCAN_TOPS:
            continue
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

        candidates = [
            item.get("name")
            for item in manifest
            if isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and Path(item["name"]).suffix.lower() in SOURCE_SUFFIXES
        ]
        if not candidates:
            continue
        scanned_mbn += 1

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
            source_refs: list[dict[str, Any]] = []
            suffix = Path(entry).suffix.lower()
            if suffix == ".json":
                try:
                    source_refs = json_references(json.loads(data), ids, relative, entry)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    source_refs = byte_references(data, ids, relative, entry)
            else:
                source_refs = byte_references(data, ids, relative, entry)

            if source_refs:
                digest = hashlib.sha256(data).hexdigest()
                for ref in source_refs:
                    ref["source_sha256"] = digest
                    refs.append(ref)
                    if len(refs) >= MAX_REFS:
                        break
            if len(refs) >= MAX_REFS:
                break
        if len(refs) >= MAX_REFS:
            break

    priority = {
        "direct-location-key": 0,
        "tutorial-location-context": 1,
        "location-context": 2,
        "symbol-proximity": 3,
        "workflow-context": 4,
        "weak-context": 5,
        "negative-resource-context": 6,
    }
    refs.sort(key=lambda item: (
        priority.get(item["evidence_class"], 99),
        item["map_id"],
        item["container"],
        item["entry"],
        item.get("pointer", ""),
        item.get("offset", -1),
    ))

    per_map: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"classes": Counter(), "sources": set(), "refs": 0}
    )
    for ref in refs:
        item = per_map[ref["map_id"]]
        item["classes"][ref["evidence_class"]] += 1
        item["sources"].add((ref["container"], ref["entry"]))
        item["refs"] += 1

    ranked = []
    for mid, item in per_map.items():
        classes = item["classes"]
        strong = (
            classes["direct-location-key"] * 8
            + classes["tutorial-location-context"] * 7
            + classes["location-context"] * 5
            + classes["symbol-proximity"] * 3
            + classes["workflow-context"] * 2
            - classes["negative-resource-context"] * 4
        )
        ranked.append({
            "map_id": mid,
            "evidence_score": strong,
            "reference_count": item["refs"],
            "source_count": len(item["sources"]),
            "classes": dict(classes),
        })
    ranked.sort(key=lambda item: (-item["evidence_score"], -item["source_count"], -item["reference_count"], item["map_id"]))

    return {
        "provenance": "PUBLIC_LIVE_JP_SEMANTIC_MAP_REFERENCE_METADATA",
        "policy": (
            "Only IDs independently confirmed by live map package filenames are considered. "
            "JSON evidence uses key/ancestor structure; byte evidence uses bounded allowlisted "
            "symbol proximity. Scores prioritize evidence for review and are not proof of "
            "tutorial selection. No source text, dialogue, geometry or textures are exported."
        ),
        "confirmed_map_id_count": len(ids),
        "scanned_mbn_count": scanned_mbn,
        "scanned_source_count": scanned_sources,
        "reference_count": len(refs),
        "ranked_summary": ranked[:500],
        "references": refs[:MAX_REFS],
        "errors": errors[:200],
    }


def self_test() -> None:
    secret = "SECRET_DIALOGUE_MUST_NOT_EXPORT"
    good = "001_000_00001"
    collision = "001_000_00002"
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        anchor = root / "private.zip"
        anchor.write_bytes(b"x")
        cache = root / CACHE_NAME
        (cache / "map").mkdir(parents=True)
        (cache / "gui").mkdir()
        (cache / "map" / f"{good}.mbn").write_bytes(_make_synthetic_mbn(f"{good}.map", b"x"))
        (cache / "map" / f"{collision}.mbn").write_bytes(_make_synthetic_mbn(f"{collision}.map", b"x"))

        payload = {
            "tutorial": {"next_map_id": good, "dialogue": secret},
            "soundID": collision,
        }
        (cache / "json_resource.mbn").write_bytes(
            _make_synthetic_mbn("tutorial.json", json.dumps(payload).encode())
        )
        lua = f"{secret} change_field map_id {good}".encode()
        (cache / "gui" / "tutorial.mbn").write_bytes(_make_synthetic_mbn("tutorial.lua", lua))

        result = inspect(anchor)
        encoded = json.dumps(result, sort_keys=True)
        assert secret not in encoded
        good_refs = [r for r in result["references"] if r["map_id"] == good]
        bad_refs = [r for r in result["references"] if r["map_id"] == collision]
        assert any(r["evidence_class"] == "direct-location-key" for r in good_refs)
        assert any(r["evidence_class"] == "symbol-proximity" for r in good_refs)
        assert bad_refs and all(r["evidence_class"] == "negative-resource-context" for r in bad_refs)

    print("Logres live semantic map reference inspector self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchor", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0
    if not args.anchor:
        print("--anchor required", file=sys.stderr)
        return 2
    try:
        result = inspect(args.anchor)
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
