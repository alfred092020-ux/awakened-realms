#!/usr/bin/env python3
"""Trace the two Convexhull vector producers inside FieldQuadTreeLeaf::setupEntities.

Bounded scope:
- resolve exactly FieldQuadTreeLeaf::setupEntities in the public current JP libgame;
- disassemble only that function;
- preserve conditional branch mnemonics (b.*, cb*, tb*);
- track simple frame-relative aliases derived from x29;
- report accesses/calls involving the two std::vector<Convexhull> locals passed
  to DataParser as x29-0x38 and x29-0x50 at the constructor call.

No binary bytes or whole-library disassembly are exported.
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

TARGET_RE = re.compile(r"^lfs::field::FieldQuadTreeLeaf::setupEntities\(")
INSTRUCTION_RE = re.compile(
    r"^\s*([0-9a-fA-F]+):\s+(?:[0-9a-fA-F]{8}|(?:[0-9a-fA-F]{2}\s+){4})\s+"
    r"([A-Za-z.][A-Za-z0-9.]*)\s*(.*)$"
)
REGISTER_RE = re.compile(r"^(x(?:[12]?[0-9]|3[01])|x29)$")
MEMORY_RE = re.compile(
    r"\[(x(?:[12]?[0-9]|3[01])|x29)"
    r"(?:,\s*#(-?(?:0x[0-9a-fA-F]+|[0-9]+)))?"
)
MAX_FUNCTION_BYTES = 0x1200
MAX_INSTRUCTIONS = 1800

VECTOR_LOCALS = {
    "constructor_arg2_vector_at_fp_minus_0x38": (-0x38, -0x38 + 0x17),
    "constructor_arg3_vector_at_fp_minus_0x50": (-0x50, -0x50 + 0x17),
}


def parse_instruction(line: str) -> dict[str, str] | None:
    match = INSTRUCTION_RE.match(line)
    if not match:
        return None
    return {
        "address": "0x" + match.group(1).lower(),
        "mnemonic": match.group(2).lower(),
        "operands": match.group(3).strip()[:600],
    }


def resolve_target(symbols: list[dict[str, object]]) -> dict[str, object]:
    matches = [
        item for item in symbols
        if TARGET_RE.search(str(item.get("name", "")))
        and not str(item.get("name", "")).startswith("non-virtual thunk")
    ]
    if not matches:
        raise ValueError("setupEntities symbol not found")
    matches.sort(key=lambda item: int(item["address"]))
    return matches[0]


def parse_immediate(token: str) -> int:
    value = token.strip()
    if value.startswith("#"):
        value = value[1:]
    sign = -1 if value.startswith("-") else 1
    if value.startswith("-"):
        value = value[1:]
    base = 16 if value.lower().startswith("0x") else 10
    return sign * int(value, base)


def split_operands(operands: str) -> list[str]:
    # Good enough for the register/immediate forms used by alias propagation.
    return [part.strip() for part in operands.split(",")]


def vector_label(offset: int) -> str | None:
    for label, (start, stop) in VECTOR_LOCALS.items():
        if start <= offset <= stop:
            return label
    return None


def vector_base_label(offset: int) -> str | None:
    for label, (start, _stop) in VECTOR_LOCALS.items():
        if offset == start:
            return label
    return None


def analyze(instructions: list[dict[str, str]]) -> dict[str, object]:
    aliases: dict[str, int] = {"x29": 0}
    pointer_assignments = []
    vector_accesses = []
    calls_with_vector_args = []
    branch_instructions = []

    for row in instructions:
        mnemonic = row["mnemonic"]
        operands = row["operands"]

        if (
            mnemonic == "b"
            or mnemonic.startswith("b.")
            or mnemonic.startswith("cb")
            or mnemonic.startswith("tb")
        ):
            branch_instructions.append(row)

        for match in MEMORY_RE.finditer(operands):
            base = match.group(1)
            if base not in aliases:
                continue
            displacement = parse_immediate(match.group(2) or "0")
            effective = aliases[base] + displacement
            label = vector_label(effective)
            if label:
                vector_accesses.append({
                    "instruction": row,
                    "base_register": base,
                    "effective_frame_offset": effective,
                    "vector": label,
                })

        if mnemonic in {"bl", "blr"}:
            args = {}
            for index in range(8):
                reg = f"x{index}"
                if reg not in aliases:
                    continue
                label = vector_label(aliases[reg])
                if label:
                    args[reg] = {
                        "frame_offset": aliases[reg],
                        "vector": label,
                        "is_vector_base": vector_base_label(aliases[reg]) is not None,
                    }
            if args:
                calls_with_vector_args.append({
                    "call": row,
                    "arguments": args,
                })

            # AAPCS64: calls may clobber x0-x17. Keep frame/callee-saved aliases.
            for index in range(18):
                aliases.pop(f"x{index}", None)
            continue

        parts = split_operands(operands)
        dest = parts[0] if parts else ""
        if not REGISTER_RE.fullmatch(dest):
            continue

        propagated = False
        if mnemonic in {"add", "sub"} and len(parts) >= 3:
            base_reg = parts[1]
            immediate = parts[2]
            if base_reg in aliases and immediate.startswith("#"):
                delta = parse_immediate(immediate)
                if mnemonic == "sub":
                    delta = -delta
                aliases[dest] = aliases[base_reg] + delta
                label = vector_label(aliases[dest])
                if label:
                    pointer_assignments.append({
                        "instruction": row,
                        "register": dest,
                        "frame_offset": aliases[dest],
                        "vector": label,
                        "is_vector_base": vector_base_label(aliases[dest]) is not None,
                    })
                propagated = True
        elif mnemonic == "mov" and len(parts) >= 2:
            source = parts[1]
            if source in aliases:
                aliases[dest] = aliases[source]
                propagated = True

        if not propagated and mnemonic in {
            "adr", "adrp", "ldr", "ldur", "ldp", "mov", "movz", "movk",
            "mul", "madd", "msub", "sdiv", "udiv", "lsl", "lsr", "asr",
            "and", "orr", "eor", "csel", "csinc", "cset",
        }:
            aliases.pop(dest, None)

    return {
        "vector_locals": {
            label: {
                "frame_start": start,
                "frame_stop": stop,
                "size_bytes": stop - start + 1,
            }
            for label, (start, stop) in VECTOR_LOCALS.items()
        },
        "pointer_assignments": pointer_assignments,
        "vector_accesses": vector_accesses,
        "calls_with_vector_args": calls_with_vector_args,
        "branch_instructions": branch_instructions,
    }


def inspect(url: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        xapk = root / "logres.xapk"
        dl = download(url, xapk)
        apk_name, data = find_libgame(xapk)
        so = root / "libgame.so"
        so.write_bytes(data)

        symbols = all_symbols(so)
        target = resolve_target(symbols)
        start = int(target["address"])
        stop = min(function_end(symbols, start), start + MAX_FUNCTION_BYTES)
        tool = choose_objdump()

        instructions = []
        for line in disassemble(tool, so, start, stop).splitlines():
            parsed = parse_instruction(line)
            if parsed:
                instructions.append(parsed)
                if len(instructions) >= MAX_INSTRUCTIONS:
                    raise ValueError("setupEntities instruction bound exceeded")

        analysis = analyze(instructions)
        return {
            "provenance": "PUBLIC_CURRENT_JP_SETUPENTITIES_VECTOR_PRODUCER_METADATA",
            "policy": (
                "Bounded public native metadata for exactly FieldQuadTreeLeaf::setupEntities. "
                "The stopping condition is identifying producers/accesses/call consumers of the "
                "two frame-local Convexhull vectors passed to DataParser. If dataflow escapes the "
                "simple frame-alias model, it remains unresolved rather than broadening scope."
            ),
            "download": dl,
            "apk": apk_name,
            "libgame": {
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            },
            "disassembler": tool,
            "function": {
                "name": target["name"],
                "address": f"0x{start:x}",
                "bounded_stop": f"0x{stop:x}",
                "bounded_bytes": stop - start,
                "instruction_count": len(instructions),
            },
            "analysis": analysis,
            "instructions": instructions,
        }


def self_test() -> None:
    sample = [
        {"address":"0x1000","mnemonic":"sub","operands":"x2, x29, #0x38"},
        {"address":"0x1004","mnemonic":"sub","operands":"x3, x29, #0x50"},
        {"address":"0x1008","mnemonic":"stur","operands":"x8, [x29, #-0x30]"},
        {"address":"0x100c","mnemonic":"b.eq","operands":"0x1020 <branch>"},
        {"address":"0x1010","mnemonic":"bl","operands":"0x2000 <DataParser::DataParser()>"},
    ]
    result = analyze(sample)
    assert len(result["pointer_assignments"]) == 2
    assert result["pointer_assignments"][0]["is_vector_base"] is True
    assert result["pointer_assignments"][1]["is_vector_base"] is True
    assert result["vector_accesses"][0]["effective_frame_offset"] == -0x30
    assert result["branch_instructions"][0]["mnemonic"] == "b.eq"
    call = result["calls_with_vector_args"][0]
    assert call["arguments"]["x2"]["frame_offset"] == -0x38
    assert call["arguments"]["x3"]["frame_offset"] == -0x50

    parsed = parse_instruction("  100c: 54000080 b.eq 1020 <branch>")
    assert parsed and parsed["mnemonic"] == "b.eq"
    print("Logres setupEntities Convexhull vector inspector self-test: PASS")


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
