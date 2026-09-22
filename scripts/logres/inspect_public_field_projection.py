#!/usr/bin/env python3
"""Recover exact current-Japanese projection/depth field formulas.

This is a bounded follow-up to inspect_public_field_formulas.py. It reuses the
established public XAPK extraction helpers and targets only projection, coordinate
conversion, depth, and screening helpers needed by the playable field slice.
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

TARGETS = (
    ("map_to_screen", re.compile(r"^lfs::Isometric::mapToScreen\(lfs::Vector3 const&\)$")),
    ("screen_to_map", re.compile(r"^lfs::Isometric::screenToMap\(")),
    ("position_to_coord3", re.compile(r"^lfs::FieldConstant::positionToCoord3\(lfs::Vector3 const&\)$")),
    ("coord_to_index", re.compile(r"^lfs::FieldConstant::coordToIndex\(")),
    ("grid_size_half", re.compile(r"^lfs::FieldConstant::gridSizeHalf\(\)$")),
    ("tile_side_height", re.compile(r"^lfs::FieldConstant::tileSideHeight\(\)$")),
    ("terrain_depth", re.compile(r"^lfs::field::FieldTerrain::getDepthOrder\(\) const$")),
    ("tile_depth", re.compile(r"^lfs::field::FieldTile::getDepthOrder\(\) const$")),
    ("tile_node_pos", re.compile(r"^lfs::field::FieldTile::getNodePos\(\) const$")),
    ("block_depth", re.compile(r"^lfs::FieldBlockBase::getDepthOrder\(\) const$")),
    ("screening_tile", re.compile(r"^lfs::field::FieldTerrain::getScreeningTile\(")),
    ("check_screening_tile", re.compile(r"^lfs::field::FieldTerrain::checkScreeningTile\(")),
)

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
MAX_INSTRUCTIONS = 1200


def resolve(symbols: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[str]]:
    found = []
    missing = []
    for label, pattern in TARGETS:
        matches = [s for s in symbols if pattern.search(str(s["name"]))]
        normal = [s for s in matches if not str(s["name"]).startswith("non-virtual thunk")]
        if normal:
            matches = normal
        if not matches:
            missing.append(label)
            continue
        for item in matches[:3]:
            found.append({"label": label, **item})
    return found, missing


def parse_instructions(text: str) -> list[dict[str, str]]:
    out = []
    for line in text.splitlines():
        match = OBJDUMP_RE.match(line) or LLVM_RE.match(line)
        if not match:
            continue
        mnemonic = match.group(2).lower()
        if not KEEP.fullmatch(mnemonic):
            continue
        operands = match.group(3).strip()
        out.append({
            "address": "0x" + match.group(1).lower(),
            "mnemonic": mnemonic,
            "operands": operands[:500],
        })
        if len(out) >= MAX_INSTRUCTIONS:
            break
    return out


def summarize(rows: list[dict[str, str]]) -> dict[str, object]:
    counts: dict[str, int] = {}
    calls = []
    immediates = []
    for row in rows:
        mnemonic = row["mnemonic"]
        counts[mnemonic] = counts.get(mnemonic, 0) + 1
        if mnemonic in {"bl", "blr"}:
            calls.append(row)
        for token in re.findall(r"#(?:-?0x[0-9a-fA-F]+|-?\d+(?:\.\d+)?)", row["operands"]):
            if token not in immediates and len(immediates) < 160:
                immediates.append(token)
    return {
        "mnemonic_counts": counts,
        "calls": calls[:120],
        "immediates": immediates,
    }


def inspect(url: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        xapk = root / "logres.xapk"
        download_meta = download(url, xapk)
        apk_name, data = find_libgame(xapk)
        so = root / "libgame.so"
        so.write_bytes(data)

        symbols = all_symbols(so)
        targets, missing = resolve(symbols)
        tool = choose_objdump()
        results = []
        for target in targets:
            start = int(target["address"])
            stop = function_end(symbols, start)
            rows = parse_instructions(disassemble(tool, so, start, stop))
            results.append({
                "label": target["label"],
                "name": target["name"],
                "address": f"0x{start:x}",
                "bounded_stop": f"0x{stop:x}",
                "bounded_bytes": stop - start,
                "instruction_count": len(rows),
                "summary": summarize(rows),
                "instructions": rows,
            })

        return {
            "provenance": "PUBLIC_CURRENT_JP_FIELD_PROJECTION_DEPTH_METADATA",
            "policy": (
                "Bounded public native instruction metadata for an explicit projection/depth "
                "allowlist only. Missing labels are reported rather than broadened. No binary "
                "bytes or whole-library disassembly are exported."
            ),
            "download": download_meta,
            "apk": apk_name,
            "libgame": {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()},
            "disassembler": tool,
            "target_count": len(results),
            "missing_labels": missing,
            "targets": results,
        }


def self_test() -> None:
    symbols = [
        {"address": 0x1000, "type": "T", "name": "lfs::Isometric::mapToScreen(lfs::Vector3 const&)"},
        {"address": 0x1100, "type": "T", "name": "lfs::field::FieldTile::getDepthOrder() const"},
    ]
    found, missing = resolve(symbols)
    assert {x["label"] for x in found} == {"map_to_screen", "tile_depth"}
    assert "coord_to_index" in missing
    sample = (
        " 1000: 1e202820 fadd s0, s1, s0\n"
        " 1004: 1e2c0c20 fcsel s0, s1, s12, eq\n"
        " 1008: 5a80b421 csneg w1, w1, w0, lt\n"
        " 100c: d65f03c0 ret\n"
    )
    rows = parse_instructions(sample)
    assert [r["mnemonic"] for r in rows] == ["fadd", "fcsel", "csneg", "ret"]
    print("Logres public field projection inspector self-test: PASS")


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
