#!/usr/bin/env python3
"""Recover the exact native terrain-Z handoff used by current Japanese Logres.

Bounded scope: DataParser::generateConvexhullToVertices and its direct calls to
DataParser::addConvexhullVertices. Output is instruction/call metadata only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile

from inspect_public_field_formulas import (
    all_symbols,
    choose_objdump,
    disassemble,
    download,
    find_libgame,
    function_end,
)

TARGET = re.compile(r"^lfs::field::DataParser::generateConvexhullToVertices\(")
ADD_HULL = "DataParser::addConvexhullVertices"

OBJDUMP_RE = re.compile(
    r"^\s*([0-9a-fA-F]+):\s+[0-9a-fA-F]{8}\s+([A-Za-z.][A-Za-z0-9.]*)\s*(.*)$"
)
LLVM_RE = re.compile(
    r"^\s*([0-9a-fA-F]+):\s+(?:[0-9a-fA-F]{2}\s+){4}([A-Za-z.][A-Za-z0-9.]*)\s*(.*)$"
)
KEEP = re.compile(
    r"^(?:"
    r"b|bl|br|blr|cbz|cbnz|tbz|tbnz|ret|"
    r"add|adds|sub|subs|mul|madd|msub|sdiv|udiv|lsl|lsr|asr|and|orr|eor|"
    r"neg|cneg|csneg|csel|csinc|cset|cmp|cmn|tst|"
    r"fadd|fsub|fmul|fdiv|fmadd|fmsub|fneg|fabs|fcmp|fcmpe|fcsel|"
    r"fcvt|fcvtzs|scvtf|ucvtf|"
    r"mov|movz|movk|fmov|adr|adrp|"
    r"ldr|ldur|ldp|str|stur|stp"
    r")$",
    re.I,
)


def parse(text: str) -> list[dict[str, str]]:
    rows = []
    for line in text.splitlines():
        match = OBJDUMP_RE.match(line) or LLVM_RE.match(line)
        if not match:
            continue
        mnemonic = match.group(2).lower()
        if not KEEP.fullmatch(mnemonic):
            continue
        rows.append({
            "address": "0x" + match.group(1).lower(),
            "mnemonic": mnemonic,
            "operands": match.group(3).strip()[:500],
        })
    return rows


def call_sites(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    sites = []
    for index, row in enumerate(rows):
        if row["mnemonic"] != "bl" or ADD_HULL not in row["operands"]:
            continue
        start = max(0, index - 24)
        end = min(len(rows), index + 8)
        sites.append({"call": row, "window": rows[start:end]})
    return sites


def resolve(symbols: list[dict[str, object]]) -> list[dict[str, object]]:
    matches = [item for item in symbols if TARGET.search(str(item["name"]))]
    normal = [item for item in matches if not str(item["name"]).startswith("non-virtual thunk")]
    return (normal or matches)[:3]


def inspect(url: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        xapk = root / "logres.xapk"
        download_meta = download(url, xapk)
        apk_name, data = find_libgame(xapk)
        so = root / "libgame.so"
        so.write_bytes(data)

        symbols = all_symbols(so)
        targets = resolve(symbols)
        if not targets:
            return {
                "provenance": "PUBLIC_CURRENT_JP_TERRAIN_Z_METADATA",
                "policy": "Target missing; bounded scan stopped without broadening.",
                "download": download_meta,
                "apk": apk_name,
                "libgame": {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()},
                "target_count": 0,
                "targets": [],
            }

        tool = choose_objdump()
        results = []
        for target in targets:
            start = int(target["address"])
            stop = function_end(symbols, start)
            rows = parse(disassemble(tool, so, start, stop))
            sites = call_sites(rows)
            results.append({
                "name": target["name"],
                "address": f"0x{start:x}",
                "bounded_stop": f"0x{stop:x}",
                "bounded_bytes": stop - start,
                "instruction_count": len(rows),
                "add_convexhull_call_count": len(sites),
                "add_convexhull_call_sites": sites,
                "instructions": rows,
            })

        return {
            "provenance": "PUBLIC_CURRENT_JP_TERRAIN_Z_METADATA",
            "policy": (
                "Bounded current-public native instruction metadata for "
                "DataParser::generateConvexhullToVertices only. The stopping condition "
                "is the direct Z-argument handoff into addConvexhullVertices."
            ),
            "download": download_meta,
            "apk": apk_name,
            "libgame": {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()},
            "disassembler": tool,
            "target_count": len(results),
            "targets": results,
        }


def self_test() -> None:
    sample = (
        " 1000: 1e220020 scvtf s0, w1\n"
        " 1004: 1e221800 fdiv s0, s0, s2\n"
        " 1008: 94000001 bl 2000 <lfs::field::DataParser::addConvexhullVertices(...)>\n"
        " 100c: d65f03c0 ret\n"
    )
    rows = parse(sample)
    sites = call_sites(rows)
    assert [row["mnemonic"] for row in rows] == ["scvtf", "fdiv", "bl", "ret"]
    assert len(sites) == 1
    assert sites[0]["call"]["mnemonic"] == "bl"
    print("Logres public terrain Z inspector self-test: PASS")


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
