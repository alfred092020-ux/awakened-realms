#!/usr/bin/env python3
"""Extract exact initialized float constants used by current-Japanese field projection helpers.

This bounded follow-up reuses the established public XAPK extraction helpers,
disassembles only mapToScreen/screenToMap/positionToCoord3/gridSizeHalf, resolves
file-backed PT_LOAD virtual addresses, and exports exact float32 bits/values.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
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
    ("grid_size_half", re.compile(r"^lfs::FieldConstant::gridSizeHalf\(\)$")),
)

OBJDUMP_RE = re.compile(
    r"^\s*([0-9a-fA-F]+):\s+[0-9a-fA-F]{8}\s+([A-Za-z.][A-Za-z0-9.]*)\s*(.*)$"
)
LLVM_RE = re.compile(
    r"^\s*([0-9a-fA-F]+):\s+(?:[0-9a-fA-F]{2}\s+){4}([A-Za-z.][A-Za-z0-9.]*)\s*(.*)$"
)
REG_PAGE_RE = re.compile(r"^(x\d+),\s*(0x[0-9a-fA-F]+)")
ADD_SELF_RE = re.compile(r"^(x\d+),\s*\1,\s*#(0x[0-9a-fA-F]+|\d+)")
LDR_FLOAT_RE = re.compile(r"^(s\d+),\s*\[(x\d+)(?:,\s*#(0x[0-9a-fA-F]+|\d+))?\]")
RETURN_REG = "x0"


def parse_all(text: str) -> list[dict[str, str]]:
    rows = []
    for line in text.splitlines():
        match = OBJDUMP_RE.match(line) or LLVM_RE.match(line)
        if not match:
            continue
        rows.append({
            "address": "0x" + match.group(1).lower(),
            "mnemonic": match.group(2).lower(),
            "operands": match.group(3).strip()[:500],
        })
    return rows


def load_segments(data: bytes) -> list[dict[str, int]]:
    if len(data) < 64 or data[:4] != b"\x7fELF":
        raise ValueError("not-elf")
    if data[4] != 2 or data[5] != 1:
        raise ValueError("requires-little-endian-elf64")
    phoff = struct.unpack_from("<Q", data, 32)[0]
    phentsize = struct.unpack_from("<H", data, 54)[0]
    phnum = struct.unpack_from("<H", data, 56)[0]
    if phentsize < 56:
        raise ValueError("invalid-program-header-size")
    segments = []
    for index in range(phnum):
        off = phoff + index * phentsize
        if off + 56 > len(data):
            raise ValueError("truncated-program-header")
        p_type, p_flags, p_offset, p_vaddr, _p_paddr, p_filesz, p_memsz, p_align = struct.unpack_from(
            "<IIQQQQQQ", data, off
        )
        if p_type == 1:
            segments.append({
                "flags": p_flags,
                "offset": p_offset,
                "vaddr": p_vaddr,
                "filesz": p_filesz,
                "memsz": p_memsz,
                "align": p_align,
            })
    return segments


def vaddr_to_offset(segments: list[dict[str, int]], address: int) -> int | None:
    for segment in segments:
        start = segment["vaddr"]
        end = start + segment["filesz"]
        if start <= address < end:
            return segment["offset"] + (address - start)
    return None


def read_word(data: bytes, segments: list[dict[str, int]], address: int) -> dict[str, object] | None:
    offset = vaddr_to_offset(segments, address)
    if offset is None or offset + 4 > len(data):
        return None
    raw = data[offset:offset + 4]
    bits = struct.unpack("<I", raw)[0]
    value = struct.unpack("<f", raw)[0]
    return {
        "address": f"0x{address:x}",
        "file_offset": f"0x{offset:x}",
        "bits_hex": f"0x{bits:08x}",
        "float32": value,
    }


def resolve(symbols: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[str]]:
    found = []
    missing = []
    for label, pattern in TARGETS:
        matches = [s for s in symbols if pattern.search(str(s["name"]))]
        if not matches:
            missing.append(label)
            continue
        found.append({"label": label, **matches[0]})
    return found, missing


def referenced_constants(rows: list[dict[str, str]], data: bytes, segments: list[dict[str, int]]) -> list[dict[str, object]]:
    regs: dict[str, int] = {}
    refs = []
    seen = set()

    for row in rows:
        mnemonic = row["mnemonic"]
        operands = row["operands"]

        if mnemonic == "adrp":
            match = REG_PAGE_RE.match(operands)
            if match:
                regs[match.group(1)] = int(match.group(2), 16)
            continue

        if mnemonic == "add":
            match = ADD_SELF_RE.match(operands)
            if match and match.group(1) in regs:
                regs[match.group(1)] += int(match.group(2), 0)
            continue

        if mnemonic == "ldr":
            match = LDR_FLOAT_RE.match(operands)
            if not match:
                continue
            base = regs.get(match.group(2))
            if base is None:
                continue
            offset = int(match.group(3), 0) if match.group(3) else 0
            address = base + offset
            key = (row["address"], address)
            if key in seen:
                continue
            seen.add(key)
            word = read_word(data, segments, address)
            refs.append({
                "instruction_address": row["address"],
                "destination": match.group(1),
                "virtual_address": f"0x{address:x}",
                "word": word,
            })

    return refs


def returned_pointer_words(rows: list[dict[str, str]], data: bytes, segments: list[dict[str, int]]) -> list[dict[str, object]]:
    regs: dict[str, int] = {}
    for row in rows:
        if row["mnemonic"] == "adrp":
            match = REG_PAGE_RE.match(row["operands"])
            if match:
                regs[match.group(1)] = int(match.group(2), 16)
        elif row["mnemonic"] == "add":
            match = ADD_SELF_RE.match(row["operands"])
            if match and match.group(1) in regs:
                regs[match.group(1)] += int(match.group(2), 0)

    base = regs.get(RETURN_REG)
    if base is None:
        return []
    words = []
    for index in range(4):
        word = read_word(data, segments, base + index * 4)
        if word is not None:
            words.append(word)
    return words


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
        segments = load_segments(data)

        output = []
        for target in targets:
            start = int(target["address"])
            stop = function_end(symbols, start)
            rows = parse_all(disassemble(tool, so, start, stop))
            output.append({
                "label": target["label"],
                "name": target["name"],
                "address": f"0x{start:x}",
                "bounded_stop": f"0x{stop:x}",
                "instruction_count": len(rows),
                "instructions": rows,
                "float_references": referenced_constants(rows, data, segments),
                "returned_pointer_words": returned_pointer_words(rows, data, segments),
            })

        return {
            "provenance": "PUBLIC_CURRENT_JP_FIELD_PROJECTION_CONSTANTS",
            "policy": (
                "Exact float32 words referenced by an explicit projection/coordinate helper "
                "allowlist. Values are read from file-backed PT_LOAD segments only. No binary "
                "payload or unrelated static data is exported."
            ),
            "download": download_meta,
            "apk": apk_name,
            "libgame": {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()},
            "disassembler": tool,
            "target_count": len(output),
            "missing_labels": missing,
            "targets": output,
        }


def synthetic_elf() -> bytes:
    data = bytearray(0x300)
    data[:4] = b"\x7fELF"
    data[4] = 2
    data[5] = 1
    struct.pack_into("<Q", data, 32, 64)
    struct.pack_into("<H", data, 54, 56)
    struct.pack_into("<H", data, 56, 1)
    struct.pack_into("<IIQQQQQQ", data, 64, 1, 4, 0x100, 0x400000, 0, 0x100, 0x100, 0x1000)
    struct.pack_into("<f", data, 0x120, 0.5)
    struct.pack_into("<f", data, 0x124, 2.0)
    return bytes(data)


def self_test() -> None:
    data = synthetic_elf()
    segments = load_segments(data)
    rows = [
        {"address":"0x1000","mnemonic":"adrp","operands":"x9, 0x400000"},
        {"address":"0x1004","mnemonic":"ldr","operands":"s1, [x9, #0x20]"},
        {"address":"0x1008","mnemonic":"adrp","operands":"x0, 0x400000"},
        {"address":"0x100c","mnemonic":"add","operands":"x0, x0, #0x20"},
        {"address":"0x1010","mnemonic":"ret","operands":""},
    ]
    refs = referenced_constants(rows, data, segments)
    assert refs[0]["word"]["float32"] == 0.5
    words = returned_pointer_words(rows, data, segments)
    assert [w["float32"] for w in words[:2]] == [0.5, 2.0]
    print("Logres public projection constants inspector self-test: PASS")


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
    text = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
