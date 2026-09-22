#!/usr/bin/env python3
"""Decompress recovered Logres zlib file lists and profile their real structure."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import urlsplit, urlunsplit
from zipfile import ZipFile
import zlib

TARGETS = (
    "files/cache/filelist.bin",
    "files/cache/extra_filelist.bin",
    "files/cache/patch/binfilelist.bin",
)
TEXT_LISTS = (
    "files/cache/download_filelist.txt",
    "files/cache/download_extra_filelist.txt",
    "files/cache/download_binfilelist.txt",
)
PRINTABLE_RE = re.compile(rb"[ -~]{4,500}")
URL_RE = re.compile(rb"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]{4,1024}", re.I)
HOST_RE = re.compile(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?::\d+)?$")
HEX40_RE = re.compile(r"^[0-9a-fA-F]{40}$")
INT_RE = re.compile(r"^-?\d+$")
PATH_RE = re.compile(r"^(?:\.?/)?[A-Za-z0-9_./@%+~-]+(?:\.mbn|\.json|\.png|\.dds|\.astc|\.lua|\.luac|\.plist|\.lfla|\.bss)$", re.I)
MAX_SAMPLES = 32


def sanitize_url(value: str) -> str | None:
    try:
        parsed = urlsplit(value.rstrip("\"'<>),]}"))
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
    return urlunsplit((parsed.scheme.lower(), netloc, parsed.path or "/", "", ""))


def classify_field(value: str) -> object:
    v = value.strip()
    if not v:
        return ""
    if HEX40_RE.fullmatch(v):
        return {"kind": "SHA1", "prefix": v[:12].lower()}
    if INT_RE.fullmatch(v):
        try:
            return int(v)
        except ValueError:
            return "<int>"
    if v.lower().startswith(("http://", "https://")):
        return sanitize_url(v) or "<invalid-url>"
    if PATH_RE.fullmatch(v) or v.lower().endswith(".mbn"):
        return v[:400]
    return "<text>"


def printable_metadata(data: bytes) -> dict:
    strings = [m.group(0).decode("ascii", errors="ignore") for m in PRINTABLE_RE.finditer(data)]
    paths = []
    hosts = []
    urls = []
    seen_paths = set()
    seen_hosts = set()
    seen_urls = set()
    for token in strings:
        if token.lower().startswith(("http://", "https://")):
            url = sanitize_url(token)
            if url and url not in seen_urls:
                seen_urls.add(url)
                urls.append(url)
        if HOST_RE.fullmatch(token):
            host = token.lower()
            if host not in seen_hosts:
                seen_hosts.add(host)
                hosts.append(host)
        if (PATH_RE.fullmatch(token) or token.lower().endswith(".mbn")) and token not in seen_paths:
            seen_paths.add(token)
            paths.append(token)
    return {
        "printable_string_count": len(strings),
        "paths": paths[:MAX_SAMPLES],
        "hosts": hosts[:MAX_SAMPLES],
        "urls": urls[:MAX_SAMPLES],
    }


def text_like_profile(data: bytes) -> dict:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return {"utf8": False}
    lines = text.splitlines()
    nonempty = [line for line in lines if line]
    delimiter_counts = Counter()
    for line in nonempty[:2000]:
        for delim, label in (("\t", "TAB"), ("|", "PIPE"), (",", "COMMA"), (";", "SEMICOLON")):
            if delim in line:
                delimiter_counts[label] += 1
    samples = []
    shape_counts = Counter()
    for line in nonempty[:2000]:
        if "\t" in line:
            fields = line.split("\t")
        elif "|" in line:
            fields = line.split("|")
        elif "," in line:
            fields = line.split(",")
        else:
            fields = line.split()
        shape = []
        safe = []
        for field in fields[:12]:
            v = field.strip()
            if HEX40_RE.fullmatch(v):
                shape.append("SHA1")
            elif INT_RE.fullmatch(v):
                shape.append("INT")
            elif PATH_RE.fullmatch(v) or v.lower().endswith(".mbn"):
                shape.append("PATH")
            elif v.lower().startswith(("http://", "https://")):
                shape.append("URL")
            elif not v:
                shape.append("EMPTY")
            else:
                shape.append("TEXT")
            safe.append(classify_field(v))
        shape_counts["|".join(shape)] += 1
        if len(samples) < MAX_SAMPLES:
            samples.append(safe)
    printable = sum(1 for byte in data if byte in b"\t\n\r" or 32 <= byte <= 126)
    return {
        "utf8": True,
        "line_count": len(lines),
        "nonempty_line_count": len(nonempty),
        "printable_ratio": round(printable / max(1, len(data)), 6),
        "delimiter_line_counts": dict(delimiter_counts),
        "shapes": dict(shape_counts.most_common(16)),
        "sample_records": samples,
    }


def profile_zlib(name: str, compressed: bytes) -> dict:
    result = {
        "member": name,
        "compressed_size": len(compressed),
        "compressed_sha256": hashlib.sha256(compressed).hexdigest(),
        "compressed_header_hex": compressed[:16].hex(),
    }
    try:
        data = zlib.decompress(compressed)
    except zlib.error as exc:
        result["zlib_error"] = str(exc)
        return result
    result.update({
        "decompressed_size": len(data),
        "decompressed_sha256": hashlib.sha256(data).hexdigest(),
        "decompressed_header_hex": data[:64].hex(),
        "compression_ratio": round(len(compressed) / max(1, len(data)), 6),
        "nul_ratio": round(data.count(0) / max(1, len(data)), 6),
        "mbn_ascii_count": data.lower().count(b".mbn"),
        "text_profile": text_like_profile(data),
        "printable_metadata": printable_metadata(data),
    })
    return result


def compare_to_texts(source: ZipFile, decompressed: bytes) -> list[dict]:
    out = []
    for name in TEXT_LISTS:
        if name not in source.namelist():
            continue
        raw = source.read(name)
        out.append({
            "text_member": name,
            "exact_byte_match": raw == decompressed,
            "text_size": len(raw),
            "text_sha256": hashlib.sha256(raw).hexdigest(),
            "decompressed_prefix_match_bytes": next(
                (i for i, (a, b) in enumerate(zip(raw, decompressed)) if a != b),
                min(len(raw), len(decompressed)),
            ),
        })
    return out


def inspect_archive(archive: Path) -> dict:
    results = {}
    missing = []
    with ZipFile(archive) as source:
        names = set(source.namelist())
        for name in TARGETS:
            if name not in names:
                missing.append(name)
                continue
            compressed = source.read(name)
            profile = profile_zlib(name, compressed)
            if "zlib_error" not in profile:
                data = zlib.decompress(compressed)
                profile["text_comparisons"] = compare_to_texts(source, data)
            results[name] = profile
    return {
        "provenance": "PRIVATE_CACHE_DECOMPRESSED_PATCH_FILELIST_METADATA",
        "policy": (
            "Exports decompressed file-list structure and bounded metadata only. "
            "No game resource payloads, dialogue, images, geometry or textures are exported."
        ),
        "targets": results,
        "missing": missing,
    }


def self_test() -> None:
    payload = (
        "0123456789abcdef0123456789abcdef01234567 123 ./gui/title.mbn 456\n"
        "89abcdef0123456789abcdef0123456789abcdef 789 ./map/001_000_00001.mbn 999\n"
    ).encode()
    with tempfile.TemporaryDirectory() as raw:
        archive = Path(raw) / "private.zip"
        with ZipFile(archive, "w") as target:
            target.writestr("files/cache/filelist.bin", zlib.compress(payload))
            target.writestr("files/cache/download_filelist.txt", payload)
        result = inspect_archive(archive)
        item = result["targets"]["files/cache/filelist.bin"]
        if item.get("decompressed_size") != len(payload):
            raise AssertionError("zlib payload was not decompressed")
        if not item["text_profile"]["utf8"]:
            raise AssertionError("text payload not detected")
        if not item["text_comparisons"][0]["exact_byte_match"]:
            raise AssertionError("decompressed/text identity was not detected")
    print("Logres decompressed patch file-list inspector self-test: PASS")


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
        print(f"Logres decompressed file-list inspection failed: {exc}", file=sys.stderr)
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
