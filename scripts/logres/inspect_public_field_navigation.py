#!/usr/bin/env python3
"""Inspect bounded current-Japanese field navigation helpers.

Targets only FieldTile containment/link helpers required to recover movement and
collision semantics. It reuses the established public XAPK/native extraction
helpers and never exports machine-code bytes or whole-library disassembly.
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
    (
        "tile_contains",
        re.compile(
            r"^lfs::field::FieldTile::contains\(cocos2d::Vec2 const&\) const$"
        ),
    ),
    (
        "tile_exists",
        re.compile(r"^lfs::field::FieldTile::exists\(\) const$"),
    ),
    (
        "link_node_num",
        re.compile(r"^lfs::field::FieldTile::getLinkNodeNum\(\) const$"),
    ),
    (
        "link_node",
        re.compile(r"^lfs::field::FieldTile::getLinkNode\(int\) const$"),
    ),
    (
        "link_node_cost",
        re.compile(
            r"^lfs::field::FieldTile::calculateLinkNodeCost"
            r"\(lfs::pathfinding::Node const&\) const$"
        ),
    ),
)

OBJDUMP_RE = re.compile(
    r"^\s*([0-9a-fA-F]+):\s+[0-9a-fA-F]{8}\s+([A-Za-z.][A-Za-z0-9.]*)\s*(.*)$"
)
LLVM_RE = re.compile(
    r"^\s*([0-9a-fA-F]+):\s+(?:[0-9a-fA-F]{2}\s+){4}"
    r"([A-Za-z.][A-Za-z0-9.]*)\s*(.*)$"
)
KEEP = re.compile(
    r"^(?:"
    r"b(?:\.[a-z]+)?|bl|br|blr|cbz|cbnz|tbz|tbnz|ret|"
    r"add|adds|sub|subs|mul|madd|msub|sdiv|udiv|lsl|lsr|asr|and|orr|eor|"
    r"neg|cneg|csneg|csel|csinc|cset|cmp|cmn|tst|"
    r"fadd|fsub|fmul|fdiv|fmadd|fmsub|fneg|fabs|fcmp|fcmpe|fcsel|"
    r"fcvt|fcvtzs|scvtf|ucvtf|"
    r"mov|movz|movk|fmov|adr|adrp|"
    r"ldr|ldur|ldp|ldrb|ldrh|ldrsw|str|stur|stp|strb|strh"
    r")$",
    re.I,
)
MAX_INSTRUCTIONS = 1600


def resolve(
    symbols: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[str]]:
    found = []
    missing = []
    for label, pattern in TARGETS:
        matches = [item for item in symbols if pattern.search(str(item["name"]))]
        normal = [
            item
            for item in matches
            if not str(item["name"]).startswith("non-virtual thunk")
        ]
        if normal:
            matches = normal
        if not matches:
            missing.append(label)
            continue
        for item in matches[:2]:
            found.append({"label": label, **item})
    return found, missing


def parse_instructions(text: str) -> list[dict[str, str]]:
    rows = []
    for line in text.splitlines():
        match = OBJDUMP_RE.match(line) or LLVM_RE.match(line)
        if not match:
            continue
        mnemonic = match.group(2).lower()
        if not KEEP.fullmatch(mnemonic):
            continue
        rows.append(
            {
                "address": "0x" + match.group(1).lower(),
                "mnemonic": mnemonic,
                "operands": match.group(3).strip()[:500],
            }
        )
        if len(rows) >= MAX_INSTRUCTIONS:
            break
    return rows


def summarize(rows: list[dict[str, str]]) -> dict[str, object]:
    counts: dict[str, int] = {}
    calls = []
    immediates = []
    branches = []
    for row in rows:
        mnemonic = row["mnemonic"]
        counts[mnemonic] = counts.get(mnemonic, 0) + 1
        if mnemonic in {"bl", "blr"}:
            calls.append(row)
        if (
            mnemonic.startswith("b")
            or mnemonic.startswith("cb")
            or mnemonic.startswith("tb")
        ):
            branches.append(row)
        for token in re.findall(
            r"#(?:-?0x[0-9a-fA-F]+|-?\d+(?:\.\d+)?)",
            row["operands"],
        ):
            if token not in immediates and len(immediates) < 200:
                immediates.append(token)
    return {
        "mnemonic_counts": counts,
        "calls": calls[:160],
        "branches": branches[:240],
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
            results.append(
                {
                    "label": target["label"],
                    "name": target["name"],
                    "address": f"0x{start:x}",
                    "bounded_stop": f"0x{stop:x}",
                    "bounded_bytes": stop - start,
                    "instruction_count": len(rows),
                    "summary": summarize(rows),
                    "instructions": rows,
                }
            )

        return {
            "provenance": "PUBLIC_CURRENT_JP_FIELD_NAVIGATION_METADATA",
            "policy": (
                "Bounded public native instruction metadata for an explicit "
                "FieldTile navigation allowlist only. Missing labels remain "
                "unresolved rather than broadening. No binary bytes or whole-"
                "library disassembly are exported."
            ),
            "download": download_meta,
            "apk": apk_name,
            "libgame": {
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            },
            "disassembler": tool,
            "target_count": len(results),
            "missing_labels": missing,
            "targets": results,
        }


def self_test() -> None:
    symbols = [
        {
            "address": 0x1000,
            "type": "T",
            "name": "lfs::field::FieldTile::getLinkNodeNum() const",
        },
        {
            "address": 0x1100,
            "type": "T",
            "name": (
                "lfs::field::FieldTile::calculateLinkNodeCost"
                "(lfs::pathfinding::Node const&) const"
            ),
        },
    ]
    found, missing = resolve(symbols)
    assert {item["label"] for item in found} == {
        "link_node_num",
        "link_node_cost",
    }
    assert "tile_contains" in missing

    sample = (
        " 1000: 7100081f cmp w0, #0x2\n"
        " 1004: 54000041 b.ne 0x100c\n"
        " 1008: 1e202820 fadd s0, s1, s0\n"
        " 100c: d65f03c0 ret\n"
    )
    rows = parse_instructions(sample)
    assert [row["mnemonic"] for row in rows] == [
        "cmp",
        "b.ne",
        "fadd",
        "ret",
    ]
    summary = summarize(rows)
    assert len(summary["branches"]) == 1
    print("Logres public field navigation inspector self-test: PASS")


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
        print(
            f"inspection failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    encoded = json.dumps(
        result,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        sys.stdout.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
