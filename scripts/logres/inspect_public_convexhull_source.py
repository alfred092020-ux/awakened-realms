#!/usr/bin/env python3
"""Trace construction/call provenance for native Logres field Convexhull records.

Bounded goals:
- disassemble DataParser::DataParser only;
- enumerate non-stdlib exported symbols containing Convexhull;
- find direct call sites to DataParser::DataParser in the public current libgame
  and capture bounded instruction windows plus caller symbol names.

No binary bytes or whole-library disassembly are exported.
"""
from __future__ import annotations

import argparse
from collections import deque
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from zipfile import ZipFile

from inspect_public_field_formulas import (
    all_symbols,
    choose_objdump,
    disassemble,
    download,
    find_libgame,
    function_end,
)

CONSTRUCTOR_RE = re.compile(
    r"^lfs::field::DataParser::DataParser\(.*vector<lfs::field::Convexhull"
)
FUNCTION_HEADER_RE = re.compile(r"^([0-9a-fA-F]+) <(.+)>:$")
INSTRUCTION_RE = re.compile(
    r"^\s*([0-9a-fA-F]+):\s+(?:[0-9a-fA-F]{8}|(?:[0-9a-fA-F]{2}\s+){4})\s+"
    r"([A-Za-z.][A-Za-z0-9.]*)\s*(.*)$"
)
CALL_TARGET_NEEDLES = (
    "lfs::field::DataParser::DataParser(",
    "_ZN3lfs5field10DataParserC",
)
MAX_WINDOW_BEFORE = 36
MAX_WINDOW_AFTER = 12
MAX_CALL_SITES = 24
MAX_CONVEX_SYMBOLS = 120
MAX_FUNCTION_BYTES = 8192

KEEP = re.compile(
    r"^(?:b|bl|br|blr|cbz|cbnz|tbz|tbnz|ret|"
    r"add|adds|sub|subs|mul|madd|msub|sdiv|udiv|lsl|lsr|asr|and|orr|eor|"
    r"neg|cneg|csneg|csel|csinc|cset|cmp|cmn|tst|"
    r"fadd|fsub|fmul|fdiv|fmadd|fmsub|fneg|fabs|fcmp|fcmpe|fcsel|"
    r"fcvt|fcvtzs|scvtf|ucvtf|mov|movz|movk|fmov|adr|adrp|"
    r"ldr|ldur|ldp|str|stur|stp)$",
    re.I,
)


def parse_instruction(line: str) -> dict[str, str] | None:
    match = INSTRUCTION_RE.match(line)
    if not match:
        return None
    mnemonic = match.group(2).lower()
    if not KEEP.fullmatch(mnemonic):
        return None
    return {
        "address": "0x" + match.group(1).lower(),
        "mnemonic": mnemonic,
        "operands": match.group(3).strip()[:500],
    }


def constructor_targets(symbols: list[dict[str, object]]) -> list[dict[str, object]]:
    matches = [item for item in symbols if CONSTRUCTOR_RE.search(str(item["name"]))]
    dedup = {}
    for item in matches:
        dedup[(int(item["address"]), str(item["name"]))] = item
    return list(dedup.values())[:4]


def convex_symbols(symbols: list[dict[str, object]]) -> list[dict[str, object]]:
    result = []
    for item in symbols:
        name = str(item["name"])
        if "Convexhull" not in name:
            continue
        if name.startswith("std::__ndk1::"):
            continue
        result.append({
            "address": f"0x{int(item['address']):x}",
            "type": item.get("type"),
            "name": name[:700],
        })
        if len(result) >= MAX_CONVEX_SYMBOLS:
            break
    return result


def scan_constructor_call_sites(tool: str, so: Path) -> list[dict[str, object]]:
    exe = shutil.which(tool)
    if not exe:
        raise ValueError(f"tool unavailable: {tool}")
    args = [exe, "-d", "--demangle", str(so)] if tool == "llvm-objdump" else [exe, "-d", "-C", str(so)]
    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
    )
    if process.stdout is None:
        raise ValueError("objdump stdout unavailable")

    before: deque[dict[str, str]] = deque(maxlen=MAX_WINDOW_BEFORE)
    current_function: str | None = None
    sites = []
    pending: dict[str, object] | None = None
    remaining_after = 0

    for raw_line in process.stdout:
        line = raw_line.rstrip("\n")
        header = FUNCTION_HEADER_RE.match(line)
        if header:
            current_function = header.group(2)[:700]
            before.clear()
            continue

        instruction = parse_instruction(line)
        if instruction is None:
            continue

        if pending is not None and remaining_after > 0:
            pending["after"].append(instruction)
            remaining_after -= 1
            if remaining_after == 0:
                sites.append(pending)
                pending = None
                if len(sites) >= MAX_CALL_SITES:
                    process.terminate()
                    break

        if (
            instruction["mnemonic"] == "bl"
            and any(needle in instruction["operands"] for needle in CALL_TARGET_NEEDLES)
            and pending is None
        ):
            pending = {
                "caller": current_function,
                "call": instruction,
                "before": list(before),
                "after": [],
            }
            remaining_after = MAX_WINDOW_AFTER

        before.append(instruction)

    if pending is not None:
        sites.append(pending)

    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        process.kill()

    return sites[:MAX_CALL_SITES]


def inspect(url: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        xapk = root / "logres.xapk"
        dl = download(url, xapk)
        apk_name, data = find_libgame(xapk)
        so = root / "libgame.so"
        so.write_bytes(data)

        symbols = all_symbols(so)
        constructors = constructor_targets(symbols)
        tool = choose_objdump()

        constructor_details = []
        for target in constructors:
            start = int(target["address"])
            stop = function_end(symbols, start)
            rows = []
            for line in disassemble(tool, so, start, stop).splitlines():
                parsed = parse_instruction(line)
                if parsed:
                    rows.append(parsed)
            constructor_details.append({
                "name": target["name"],
                "address": f"0x{start:x}",
                "bounded_stop": f"0x{stop:x}",
                "bounded_bytes": stop - start,
                "instructions": rows,
            })

        sites = scan_constructor_call_sites(tool, so)
        return {
            "provenance": "PUBLIC_CURRENT_JP_CONVEXHULL_SOURCE_METADATA",
            "policy": (
                "Bounded public native metadata only. The stopping condition is identifying "
                "direct DataParser constructor callers and nearby argument preparation for "
                "Convexhull vectors. If this does not reveal the record producer, the source "
                "remains unresolved rather than broadening automatically."
            ),
            "download": dl,
            "apk": apk_name,
            "libgame": {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()},
            "disassembler": tool,
            "constructor_count": len(constructor_details),
            "constructors": constructor_details,
            "convexhull_symbol_count": len(convex_symbols(symbols)),
            "convexhull_symbols": convex_symbols(symbols),
            "constructor_call_site_count": len(sites),
            "constructor_call_sites": sites,
        }


def self_test() -> None:
    symbols = [
        {"address":0x1000,"type":"T","name":"lfs::field::DataParser::DataParser(std::__ndk1::vector<lfs::field::Convexhull, X>&)"},
        {"address":0x1100,"type":"T","name":"lfs::field::Other::ConvexhullHelper()"},
        {"address":0x1200,"type":"T","name":"std::__ndk1::vector<lfs::field::Convexhull>::size()"},
    ]
    assert len(constructor_targets(symbols)) == 1
    listed = convex_symbols(symbols)
    assert len(listed) == 2
    line = "  1000: f9400262 ldr x2, [x19]"
    parsed = parse_instruction(line)
    assert parsed and parsed["mnemonic"] == "ldr"
    print("Logres public Convexhull source inspector self-test: PASS")


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
