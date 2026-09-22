#!/usr/bin/env python3
"""Inspect private Logres client cache for patch/update endpoint evidence.

Exports bounded metadata, sanitized HTTP(S) URLs, selected patch-related JSON
values, hashes, counts, filenames, and byte offsets. It never exports raw source
text, dialogue, binaries, images, geometry, textures, URL query strings, or
fragments.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import tempfile
from urllib.parse import urlsplit, urlunsplit
from zipfile import ZipFile

from hydrate_private_assets import _make_synthetic_mbn, parse_mbn

MAX_MBN_BYTES = 128 * 1024 * 1024
MAX_SOURCE_BYTES = 128 * 1024 * 1024
MAX_OFFSETS = 16
MAX_JSON_VALUES = 100
SOURCE_SUFFIXES = {
    ".lua", ".luac", ".json", ".txt", ".xml", ".bin", ".so", ".dex",
    ".cfg", ".ini", ".plist",
}
TERMS = (
    "patch", "manifest", "patchlist", "filelist", "download", "update",
    "resource_url", "download_url", "base_url", "cdn", "asset_version",
    "patch_version", "cache/patch", ".mbn",
)
URL_RE = re.compile(
    rb"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]{4,1024}",
    re.IGNORECASE,
)
INTERESTING_KEY_RE = re.compile(
    r"(patch|manifest|download|update|cdn|asset.*version|version.*asset|"
    r"resource.*url|url.*resource|base.*url|host)",
    re.IGNORECASE,
)
HOST_RE = re.compile(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?::\d+)?$")


def all_offsets(data: bytes, needle: bytes) -> list[int]:
    lower = data.lower()
    token = needle.lower()
    result = []
    start = 0
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


def sanitize_url(raw: bytes | str) -> str | None:
    if isinstance(raw, bytes):
        value = raw.decode("utf-8", errors="ignore")
    else:
        value = raw
    value = value.rstrip("\"'<>),]}")
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return None
    host = parsed.hostname.lower()
    try:
        port = parsed.port
    except ValueError:
        port = None
    netloc = host if port is None else f"{host}:{port}"
    path = parsed.path or "/"
    if len(path) > 300:
        path = path[:300] + "..."
    return urlunsplit((parsed.scheme.lower(), netloc, path, "", ""))


def extract_urls(data: bytes) -> list[str]:
    result = []
    seen = set()
    for match in URL_RE.finditer(data):
        url = sanitize_url(match.group(0))
        if url and url not in seen:
            seen.add(url)
            result.append(url)
    return result[:100]


def json_patch_values(value) -> list[dict[str, object]]:
    found = []

    def walk(item, pointer: str) -> None:
        if len(found) >= MAX_JSON_VALUES:
            return
        if isinstance(item, dict):
            for key, child in sorted(item.items(), key=lambda pair: str(pair[0])):
                escaped = str(key).replace("~", "~0").replace("/", "~1")
                child_pointer = pointer + "/" + escaped
                if INTERESTING_KEY_RE.search(str(key)):
                    if isinstance(child, str):
                        sanitized = sanitize_url(child) if child.lower().startswith(("http://", "https://")) else None
                        if sanitized:
                            found.append({"pointer": child_pointer, "kind": "url", "value": sanitized})
                        elif HOST_RE.fullmatch(child):
                            found.append({"pointer": child_pointer, "kind": "host", "value": child.lower()})
                        elif (
                            len(child) <= 256
                            and (
                                child.lower().endswith((".json", ".mbn", ".txt"))
                                or "manifest" in child.lower()
                                or "patch" in child.lower()
                            )
                        ):
                            found.append({"pointer": child_pointer, "kind": "path", "value": child})
                    elif (
                        isinstance(child, (int, float))
                        and not isinstance(child, bool)
                        and "version" in str(key).lower()
                    ):
                        found.append({"pointer": child_pointer, "kind": "version", "value": child})
                walk(child, child_pointer)
        elif isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, pointer + "/" + str(index))

    walk(value, "")
    return found[:MAX_JSON_VALUES]


def classify(name: str, data: bytes) -> str:
    if data.startswith(b"\x1bLua"):
        return "lua-bytecode"
    if data.startswith(b"\x1bLJ"):
        return "luajit-bytecode"
    if data.startswith(b"\x7fELF"):
        return "elf"
    if data.startswith(b"dex\n"):
        return "dex"
    return Path(name).suffix.lower().lstrip(".") or "unclassified"


def source_evidence(container: str | None, name: str, data: bytes) -> dict | None:
    hits = scan_terms(data)
    urls = extract_urls(data)
    json_values = []
    if Path(name).suffix.lower() == ".json":
        try:
            json_values = json_patch_values(json.loads(data))
        except (ValueError, UnicodeDecodeError):
            pass
    if not hits and not urls and not json_values:
        return None
    return {
        "container": container,
        "entry": name,
        "format": classify(name, data),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "hits": hits,
        "urls": urls,
        "json_patch_values": json_values,
    }


def read_mbn_manifest(source: ZipFile, info) -> list[dict]:
    with source.open(info) as handle:
        header = handle.read(8)
        if len(header) != 8:
            raise ValueError("short MBN header")
        reserved, size = struct.unpack("<II", header)
        if reserved != 0 or size > 8 * 1024 * 1024:
            raise ValueError("invalid MBN manifest header")
        raw = handle.read(size)
    manifest = json.loads(raw)
    if not isinstance(manifest, list):
        raise ValueError("MBN manifest is not a list")
    return manifest


def inspect_archive(archive: Path) -> dict:
    sources = []
    archive_name_hits = []
    manifest_name_hits = []
    errors = []
    patch_tree = Counter()
    patch_member_count = 0
    patch_total_bytes = 0

    with ZipFile(archive) as source:
        for info in sorted(source.infolist(), key=lambda item: item.filename):
            lower_name = info.filename.lower()
            marker = "/cache/patch/"
            if marker in lower_name:
                patch_member_count += 1
                patch_total_bytes += info.file_size
                rest = lower_name.split(marker, 1)[1]
                category = rest.split("/", 1)[0] if "/" in rest else "(root)"
                patch_tree[category] += 1

            name_hits = scan_terms(info.filename.encode("utf-8", errors="ignore"))
            if name_hits:
                archive_name_hits.append({"member": info.filename, "hits": name_hits})

            suffix = Path(info.filename).suffix.lower()
            if suffix == ".mbn":
                try:
                    manifest = read_mbn_manifest(source, info)
                except (ValueError, json.JSONDecodeError, struct.error) as exc:
                    errors.append({"member": info.filename, "reason": type(exc).__name__})
                    continue

                names = [
                    item.get("name")
                    for item in manifest
                    if isinstance(item, dict) and isinstance(item.get("name"), str)
                ]
                for name in names:
                    hits = scan_terms(name.encode("utf-8", errors="ignore"))
                    if hits:
                        manifest_name_hits.append({
                            "container": info.filename,
                            "entry": name,
                            "hits": hits,
                        })

                candidates = [
                    name for name in names
                    if Path(name).suffix.lower() in SOURCE_SUFFIXES
                ]
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
                    evidence = source_evidence(info.filename, name, data)
                    if evidence:
                        sources.append(evidence)
                continue

            if suffix in SOURCE_SUFFIXES and info.file_size <= MAX_SOURCE_BYTES:
                try:
                    data = source.read(info)
                except OSError:
                    errors.append({"member": info.filename, "reason": "read"})
                    continue
                evidence = source_evidence(None, info.filename, data)
                if evidence:
                    sources.append(evidence)

    host_counts = Counter()
    url_counts = Counter()
    for item in sources:
        for url in item["urls"]:
            url_counts[url] += 1
            host = urlsplit(url).hostname
            if host:
                host_counts[host] += 1
        for value in item["json_patch_values"]:
            if value["kind"] == "url":
                url = str(value["value"])
                url_counts[url] += 1
                host = urlsplit(url).hostname
                if host:
                    host_counts[host] += 1
            elif value["kind"] == "host":
                host_counts[str(value["value"])] += 1

    return {
        "provenance": "PRIVATE_CACHE_PATCH_SYSTEM_METADATA",
        "semantic_policy": (
            "Results are search evidence. URLs have query strings/fragments removed. "
            "No raw source, dialogue, binary payload, images, geometry, or textures are exported."
        ),
        "patch_tree": {
            "member_count": patch_member_count,
            "total_bytes": patch_total_bytes,
            "categories": dict(patch_tree.most_common()),
        },
        "host_summary": [
            {"host": host, "count": count}
            for host, count in host_counts.most_common(100)
        ],
        "url_summary": [
            {"url": url, "count": count}
            for url, count in url_counts.most_common(200)
        ],
        "source_hit_count": len(sources),
        "sources": sources,
        "archive_name_hits": archive_name_hits[:500],
        "manifest_name_hits": manifest_name_hits[:1000],
        "errors": errors,
    }


def self_test() -> None:
    secret = "PRIVATE_SOURCE_MUST_NOT_EXPORT"
    query_secret = "QUERY_SECRET_MUST_NOT_EXPORT"
    config = {
        "patch_manifest_url": f"https://patch.example.invalid/v12/manifest.json?token={query_secret}",
        "asset_version": 12101,
        "dialog": secret,
    }
    lua = (
        secret
        + " download https://cdn.example.invalid/game/data/file.mbn?auth="
        + query_secret
    ).encode("utf-8")

    with tempfile.TemporaryDirectory() as raw:
        archive = Path(raw) / "private.zip"
        with ZipFile(archive, "w") as target:
            target.writestr(
                "files/cache/patch/system/config.mbn",
                _make_synthetic_mbn(
                    "patch_config.json",
                    json.dumps(config).encode("utf-8"),
                ),
            )
            target.writestr(
                "files/cache/patch/script/updater.mbn",
                _make_synthetic_mbn("updater.lua", lua),
            )

        result = inspect_archive(archive)
        encoded = json.dumps(result, sort_keys=True)
        if secret in encoded or query_secret in encoded:
            raise AssertionError("private source or URL query leaked")
        urls = {item["url"] for item in result["url_summary"]}
        if "https://patch.example.invalid/v12/manifest.json" not in urls:
            raise AssertionError("patch manifest URL was not recovered")
        if "https://cdn.example.invalid/game/data/file.mbn" not in urls:
            raise AssertionError("CDN MBN URL was not recovered")
        if result["patch_tree"]["member_count"] != 2:
            raise AssertionError("patch tree inventory is incorrect")
        values = [
            value
            for item in result["sources"]
            for value in item["json_patch_values"]
        ]
        if not any(
            value["kind"] == "version" and value["value"] == 12101
            for value in values
        ):
            raise AssertionError("asset version was not recovered")

    print("Logres private patch system inspector self-test: PASS")


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
        print(f"Logres patch-system inspection failed: {exc}", file=sys.stderr)
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
