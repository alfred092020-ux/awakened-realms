#!/usr/bin/env python3
"""Inspect current public Japanese Logres libgame for field-renderer native symbols.

The XAPK is public and downloaded to temporary storage only. Output is bounded
symbol/call metadata, not binary bytes or full disassembly dumps.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from io import BytesIO
from zipfile import ZipFile

MAX_DOWNLOAD = 180 * 1024 * 1024
MAX_SYMBOLS = 500
MAX_FUNCTION_BYTES = 4096
MAX_CALLS_PER_SYMBOL = 80

SYMBOL_RE = re.compile(
    r"(FieldTerrain|FieldAnimator|FieldCamera|FieldView|DataParser|"
    r"Field[A-Za-z0-9_:<>~]*Node|Map(?:Chip|Object|Grid|Vertex|Data)|"
    r"setCameraMask|CameraFlag|DepthOrder|Pathway|Prohibition|projection|project)",
    re.I,
)
CALL_LINE_RE = re.compile(r"^\s*([0-9a-f]+):\s+.*\bbl\b\s+([0-9a-fx]+)(?:\s+<([^>]+)>)?", re.I)
NM_LINE_RE = re.compile(r"^\s*([0-9a-fA-F]+)\s+([A-Za-z])\s+(.+)$")


def download(url: str, output: Path) -> dict[str, object]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"})
    total = 0
    digest = hashlib.sha256()
    with urllib.request.urlopen(req, timeout=120) as response, output.open("wb") as target:
        declared = response.headers.get("Content-Length")
        if declared and int(declared) > MAX_DOWNLOAD:
            raise ValueError("download too large")
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_DOWNLOAD:
                raise ValueError("download exceeded limit")
            digest.update(chunk)
            target.write(chunk)
    return {"size": total, "sha256": digest.hexdigest()}


def find_libgame(xapk: Path) -> tuple[str, bytes]:
    candidates: list[tuple[str, bytes]] = []
    with ZipFile(xapk) as outer:
        for info in outer.infolist():
            if not info.filename.lower().endswith(".apk"):
                continue
            payload = outer.read(info)
            try:
                with ZipFile(BytesIO(payload)) as apk:
                    for member in apk.infolist():
                        if member.filename == "lib/arm64-v8a/libgame.so":
                            candidates.append((info.filename, apk.read(member)))
            except Exception:
                continue
    if not candidates:
        raise ValueError("arm64 libgame.so not found")
    candidates.sort(key=lambda item: len(item[1]), reverse=True)
    return candidates[0]


def run_text(args: list[str], timeout: int = 120) -> str:
    exe = shutil.which(args[0])
    if not exe:
        raise ValueError(f"tool unavailable: {args[0]}")
    result = subprocess.run(
        [exe, *args[1:]],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
        check=False,
    )
    return result.stdout


def parse_symbols(nm_text: str) -> list[dict[str, object]]:
    symbols = []
    for line in nm_text.splitlines():
        match = NM_LINE_RE.match(line)
        if not match:
            continue
        name = match.group(3)
        if not SYMBOL_RE.search(name):
            continue
        symbols.append({
            "address": int(match.group(1), 16),
            "address_hex": "0x" + match.group(1).lower(),
            "type": match.group(2),
            "name": name[:500],
        })
        if len(symbols) >= MAX_SYMBOLS:
            break
    symbols.sort(key=lambda item: (item["address"], item["name"]))
    return symbols


def symbol_ranges(symbols: list[dict[str, object]]) -> list[tuple[dict[str, object], int]]:
    result = []
    addresses = sorted({int(item["address"]) for item in symbols})
    for item in symbols:
        address = int(item["address"])
        higher = [other for other in addresses if other > address]
        if higher:
            size = min(higher[0] - address, MAX_FUNCTION_BYTES)
        else:
            size = MAX_FUNCTION_BYTES
        if size <= 0:
            size = 256
        result.append((item, size))
    return result


def calls_for_symbol(so: Path, item: dict[str, object], size: int) -> list[dict[str, object]]:
    start = int(item["address"])
    stop = start + min(size, MAX_FUNCTION_BYTES)
    output = run_text([
        "objdump", "-d", "-C",
        f"--start-address={start}",
        f"--stop-address={stop}",
        str(so),
    ])
    calls = []
    for line in output.splitlines():
        match = CALL_LINE_RE.match(line)
        if not match:
            continue
        target_name = match.group(3)
        calls.append({
            "site": "0x" + match.group(1).lower(),
            "target_address": match.group(2).lower(),
            "target_name": target_name[:500] if target_name else None,
        })
        if len(calls) >= MAX_CALLS_PER_SYMBOL:
            break
    return calls


def inspect(url: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        xapk = root / "logres.xapk"
        download_meta = download(url, xapk)
        apk_name, data = find_libgame(xapk)
        so = root / "libgame.so"
        so.write_bytes(data)

        nm_text = run_text(["nm", "-D", "-C", "--defined-only", str(so)])
        symbols = parse_symbols(nm_text)
        detailed = []
        for item, size in symbol_ranges(symbols):
            row = dict(item)
            row["bounded_span_bytes"] = size
            try:
                row["calls"] = calls_for_symbol(so, item, size)
            except Exception as exc:
                row["call_scan_error"] = type(exc).__name__
            detailed.append(row)

        categories = {}
        for label, pattern in (
            ("terrain", re.compile(r"FieldTerrain", re.I)),
            ("animator", re.compile(r"FieldAnimator", re.I)),
            ("camera", re.compile(r"Camera|projection|project", re.I)),
            ("parser", re.compile(r"DataParser", re.I)),
            ("map_data", re.compile(r"Map(?:Chip|Object|Grid|Vertex|Data)", re.I)),
            ("depth_path", re.compile(r"DepthOrder|Pathway|Prohibition", re.I)),
        ):
            categories[label] = sum(bool(pattern.search(str(item["name"]))) for item in detailed)

        return {
            "provenance": "PUBLIC_CURRENT_JP_FIELD_NATIVE_METADATA",
            "policy": (
                "Public libgame derived symbol/call metadata only. Function ranges are "
                "bounded and based on neighboring filtered symbols, so call lists are "
                "discovery evidence rather than complete control-flow recovery."
            ),
            "download": download_meta,
            "apk": apk_name,
            "libgame": {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()},
            "matching_symbol_count": len(detailed),
            "category_counts": categories,
            "symbols": detailed,
        }


def self_test() -> None:
    sample = """0000000000010000 T lfs::field::FieldTerrainNode::onDraw()
0000000000011000 T lfs::field::FieldAnimator::update(float)
0000000000012000 T lfs::field::DataParser::addConvexhullVertices()
0000000000013000 T unrelated::thing()
"""
    found = parse_symbols(sample)
    assert len(found) == 3
    assert found[0]["name"].endswith("onDraw()")
    assert found[1]["name"].endswith("update(float)")
    assert found[2]["name"].endswith("addConvexhullVertices()")
    print("Logres public field native inspector self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.url:
        print("--url required", file=sys.stderr)
        return 2
    try:
        result = inspect(args.url)
    except Exception as exc:
        print(f"inspection failed: {type(exc).__name__}: {exc}", file=sys.stderr)
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
