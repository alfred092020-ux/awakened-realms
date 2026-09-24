#!/usr/bin/env python3
"""Structural Global 3.0.24 -> current-JP native function matcher.

Global 3.0.24 is the historical authority. Current JP is lineage evidence only.

Matching tiers:
  EXACT_SYMBOL_CORRESPONDENCE
      Same demangled lfs:: function symbol at both endpoints. This proves
      symbol correspondence, not behavioral identity.
  STRUCTURAL_HIGH / STRUCTURAL_MEDIUM / STRUCTURAL_LOW
      Ranked evidence from address-independent normalized AArch64 body hashes,
      function size, referenced strings, direct-call neighborhood and
      class/method signature shape. Heuristics are never promoted to exact
      identity.

The script reads the exact libgame binaries and the already-indexed broader
symbol-diff cache. It performs no Ghidra/decompiler rescan.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
from typing import Any, Iterable

FUNC_RE = re.compile(
    r"^\s*\d+:\s+([0-9a-fA-F]+)\s+(\d+)\s+FUNC\s+"
    r"(\S+)\s+(\S+)\s+(\S+)\s+(.*)$"
)

GLOBAL_PROVENANCE = (
    "GLOBAL_3_0_24_AUTHORITY_WITH_CURRENT_JP_STRUCTURAL_LINEAGE"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_cpp(name: str) -> str:
    return (
        name.replace("std::__ndk1::", "std::")
        .replace("std::__1::", "std::")
        .replace("::__ndk1::", "::")
        .strip()
    )


def function_prefix(name: str) -> str:
    # C++ demangled names can contain nested template/function types. The first
    # '(' still gives a useful conservative method-name key for lfs symbols.
    return canonical_cpp(name).split("(", 1)[0].strip()


def method_key(name: str) -> str:
    prefix = function_prefix(name)
    return prefix.rsplit("::", 1)[-1]


def class_method_key(name: str) -> str:
    prefix = function_prefix(name)
    parts = prefix.split("::")
    if len(parts) >= 2:
        return "::".join(parts[-2:])
    return prefix


def argument_arity(name: str) -> int | None:
    text = canonical_cpp(name)
    start = text.find("(")
    if start < 0:
        return None
    depth = 0
    angle = 0
    count = 0
    saw_value = False
    for ch in text[start + 1 :]:
        if ch == "<":
            angle += 1
        elif ch == ">" and angle:
            angle -= 1
        elif ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                return count + (1 if saw_value else 0)
            depth -= 1
        elif ch == "," and depth == 0 and angle == 0:
            count += 1
            saw_value = False
        elif not ch.isspace() and depth == 0:
            saw_value = True
    return None


def sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def normalize_aarch64_word(word: int) -> int:
    # Branch immediates.
    if (word & 0x7C000000) == 0x14000000:  # B / BL
        return word & 0xFC000000
    if (word & 0xFF000010) == 0x54000000:  # B.cond
        return word & ~0x00FFFFE0
    if (word & 0x7E000000) == 0x34000000:  # CBZ / CBNZ
        return word & ~0x00FFFFE0
    if (word & 0x7E000000) == 0x36000000:  # TBZ / TBNZ
        return word & ~0x0007FFE0

    # ADR / ADRP. Mask the PC-relative immediate, preserve opcode + rd.
    if (word & 0x1F000000) == 0x10000000:
        return word & ~((0x3 << 29) | (0x7FFFF << 5))

    # LDR literal family. Mask imm19, preserve operation/register fields.
    if (word & 0x3B000000) == 0x18000000:
        return word & ~0x00FFFFE0
    return word


@dataclass(frozen=True)
class Symbol:
    name: str
    address: int
    size: int
    bind: str
    visibility: str
    ndx: str


@dataclass
class FunctionFeature:
    name: str
    address: int
    size: int
    body_hash: str | None
    instruction_count: int
    strings: tuple[str, ...]
    calls: tuple[str, ...]
    method: str
    class_method: str
    arity: int | None

    def compact(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "address_hex": f"0x{self.address:x}",
            "size": self.size,
            "normalized_instruction_sha256": self.body_hash,
            "instruction_count": self.instruction_count,
            "string_refs": list(self.strings),
            "direct_calls": list(self.calls),
            "method_key": self.method,
            "class_method_key": self.class_method,
            "arity": self.arity,
        }


class Elf64Image:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        if self.data[:4] != b"\x7fELF" or self.data[4] != 2:
            raise ValueError(f"{path}: expected ELF64")
        if self.data[5] != 1:
            raise ValueError(f"{path}: expected little-endian ELF")
        e_machine = struct.unpack_from("<H", self.data, 18)[0]
        if e_machine != 183:
            raise ValueError(f"{path}: expected AArch64 e_machine=183, got {e_machine}")
        phoff = struct.unpack_from("<Q", self.data, 32)[0]
        phentsize = struct.unpack_from("<H", self.data, 54)[0]
        phnum = struct.unpack_from("<H", self.data, 56)[0]
        self.loads: list[tuple[int, int, int, int]] = []
        for index in range(phnum):
            off = phoff + index * phentsize
            p_type, p_flags, p_offset, p_vaddr, _, p_filesz, _, _ = struct.unpack_from(
                "<IIQQQQQQ", self.data, off
            )
            if p_type == 1 and p_filesz:
                self.loads.append((p_vaddr, p_vaddr + p_filesz, p_offset, p_flags))

    def va_to_offset(self, address: int, size: int = 1) -> int | None:
        for start, end, offset, _flags in self.loads:
            if start <= address and address + size <= end:
                return offset + (address - start)
        return None

    def read_va(self, address: int, size: int) -> bytes | None:
        offset = self.va_to_offset(address, size)
        if offset is None:
            return None
        return self.data[offset : offset + size]

    def executable(self, address: int) -> bool:
        for start, end, _offset, flags in self.loads:
            if start <= address < end:
                return bool(flags & 1)
        return False

    def cstring(self, address: int, max_len: int = 160) -> str | None:
        offset = self.va_to_offset(address)
        if offset is None:
            return None
        end = min(len(self.data), offset + max_len)
        raw = self.data[offset:end]
        nul = raw.find(b"\x00")
        if nul < 0:
            return None
        raw = raw[:nul]
        if len(raw) < 4:
            return None
        if any(byte < 0x20 or byte > 0x7E for byte in raw):
            return None
        try:
            value = raw.decode("ascii")
        except UnicodeDecodeError:
            return None
        return value


def read_symbols(binary: Path) -> tuple[list[Symbol], dict[int, str], list[tuple[int, int, str]]]:
    first = subprocess.Popen(
        ["readelf", "--wide", "-Ws", str(binary)],
        stdout=subprocess.PIPE,
        text=True,
    )
    second = subprocess.Popen(
        ["c++filt"],
        stdin=first.stdout,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert first.stdout is not None
    first.stdout.close()
    assert second.stdout is not None

    lfs: dict[tuple[str, int, int], Symbol] = {}
    all_by_address: dict[int, str] = {}
    all_ranges: list[tuple[int, int, str]] = []
    for line in second.stdout:
        match = FUNC_RE.match(line)
        if not match:
            continue
        address_hex, size_text, bind, visibility, ndx, raw_name = match.groups()
        if ndx in {"UND", "ABS"}:
            continue
        address = int(address_hex, 16)
        size = int(size_text)
        if address == 0:
            continue
        name = raw_name.strip()
        previous = all_by_address.get(address)
        if previous is None or len(name) < len(previous):
            all_by_address[address] = name
        if size > 0:
            all_ranges.append((address, size, name))
        if name.startswith("lfs::"):
            symbol = Symbol(
                name=name,
                address=address,
                size=size,
                bind=bind,
                visibility=visibility,
                ndx=ndx,
            )
            lfs[(name, address, size)] = symbol

    second.wait()
    first.wait()
    if first.returncode or second.returncode:
        raise RuntimeError(f"symbol extraction failed for {binary}")

    # Keep one representative per demangled function name. Prefer nonzero size,
    # then the larger body when aliases/duplicate symbol tables exist.
    by_name: dict[str, Symbol] = {}
    for symbol in lfs.values():
        old = by_name.get(symbol.name)
        if old is None or (symbol.size, -symbol.address) > (old.size, -old.address):
            by_name[symbol.name] = symbol
    all_ranges.sort(key=lambda row: (row[0], row[1], row[2]))
    return (
        sorted(by_name.values(), key=lambda row: (row.name, row.address)),
        all_by_address,
        all_ranges,
    )


class FunctionResolver:
    def __init__(
        self,
        exact: dict[int, str],
        ranges: list[tuple[int, int, str]],
    ):
        self.exact = exact
        self.ranges = ranges
        self.starts = [row[0] for row in ranges]

    def resolve(self, address: int) -> str | None:
        direct = self.exact.get(address)
        if direct:
            return direct
        index = bisect_right(self.starts, address) - 1
        if index < 0:
            return None
        start, size, name = self.ranges[index]
        if start <= address < start + size:
            return name
        next_start = (
            self.starts[index + 1]
            if index + 1 < len(self.starts)
            else None
        )
        declared_end = start + size
        # LLVM annotates compiler-generated local helpers/pools as
        # KnownSymbol+offset even when they sit just beyond st_size. Mirror
        # that conservatively: never cross the next symbol and cap the gap.
        if (
            address >= declared_end
            and address - declared_end <= 0x1000
            and (next_start is None or address < next_start)
        ):
            return name
        return None


def decode_adr_target(word: int, pc: int) -> tuple[int, int, bool] | None:
    if (word & 0x1F000000) != 0x10000000:
        return None
    immlo = (word >> 29) & 0x3
    immhi = (word >> 5) & 0x7FFFF
    imm = sign_extend((immhi << 2) | immlo, 21)
    rd = word & 0x1F
    is_page = bool(word & 0x80000000)
    target = ((pc & ~0xFFF) + (imm << 12)) if is_page else (pc + imm)
    return rd, target, is_page


def decode_add_imm(word: int) -> tuple[int, int, int] | None:
    if (word & 0x7F000000) != 0x11000000:
        return None
    rd = word & 0x1F
    rn = (word >> 5) & 0x1F
    imm12 = (word >> 10) & 0xFFF
    shift = 12 if ((word >> 22) & 1) else 0
    return rd, rn, imm12 << shift


def decode_ldr_uimm64(word: int) -> tuple[int, int, int] | None:
    # LDR Xt, [Xn, #imm12 * 8]
    if (word & 0xFFC00000) != 0xF9400000:
        return None
    rt = word & 0x1F
    rn = (word >> 5) & 0x1F
    imm12 = (word >> 10) & 0xFFF
    return rt, rn, imm12 << 3


def feature_for(
    image: Elf64Image,
    symbol: Symbol,
    resolver: FunctionResolver,
) -> FunctionFeature:
    body = image.read_va(symbol.address, symbol.size) if symbol.size else None
    if not body:
        return FunctionFeature(
            name=symbol.name,
            address=symbol.address,
            size=symbol.size,
            body_hash=None,
            instruction_count=0,
            strings=(),
            calls=(),
            method=method_key(symbol.name),
            class_method=class_method_key(symbol.name),
            arity=argument_arity(symbol.name),
        )

    word_count = len(body) // 4
    normalized = bytearray()
    strings: set[str] = set()
    calls: set[str] = set()
    words = [
        struct.unpack_from("<I", body, index * 4)[0]
        for index in range(word_count)
    ]

    for index, word in enumerate(words):
        pc = symbol.address + index * 4
        normalized.extend(struct.pack("<I", normalize_aarch64_word(word)))

        if (word & 0xFC000000) == 0x94000000:  # BL
            imm26 = word & 0x03FFFFFF
            target = pc + (sign_extend(imm26, 26) << 2)
            callee = resolver.resolve(target)
            if callee:
                calls.add(canonical_cpp(callee))

        adr = decode_adr_target(word, pc)
        if adr:
            rd, target, is_page = adr
            if not is_page:
                value = image.cstring(target)
                if value:
                    strings.add(value)
            else:
                for look_ahead in range(index + 1, min(index + 6, word_count)):
                    next_word = words[look_ahead]
                    add = decode_add_imm(next_word)
                    if add:
                        add_rd, add_rn, add_imm = add
                        if add_rd == rd and add_rn == rd:
                            value = image.cstring(target + add_imm)
                            if value:
                                strings.add(value)
                            break
                    ldr = decode_ldr_uimm64(next_word)
                    if ldr:
                        _rt, ldr_rn, ldr_imm = ldr
                        if ldr_rn == rd:
                            raw_ptr = image.read_va(target + ldr_imm, 8)
                            if raw_ptr:
                                pointer = struct.unpack("<Q", raw_ptr)[0]
                                value = image.cstring(pointer)
                                if value:
                                    strings.add(value)
                            break

        if (word & 0x3B000000) == 0x18000000:  # LDR literal
            imm19 = (word >> 5) & 0x7FFFF
            literal = pc + (sign_extend(imm19, 19) << 2)
            raw_ptr = image.read_va(literal, 8)
            if raw_ptr:
                pointer = struct.unpack("<Q", raw_ptr)[0]
                value = image.cstring(pointer)
                if value:
                    strings.add(value)

    # Large UI strings/log templates are useful, but cap per-function evidence
    # deterministically so the artifact remains compact.
    kept_strings = tuple(sorted(strings, key=lambda value: (-len(value), value))[:16])
    kept_calls = tuple(sorted(calls)[:24])
    return FunctionFeature(
        name=symbol.name,
        address=symbol.address,
        size=symbol.size,
        body_hash=hashlib.sha256(normalized).hexdigest(),
        instruction_count=word_count,
        strings=kept_strings,
        calls=kept_calls,
        method=method_key(symbol.name),
        class_method=class_method_key(symbol.name),
        arity=argument_arity(symbol.name),
    )


def jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    a = set(left)
    b = set(right)
    if not a and not b:
        return 0.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def score_pair(global_row: FunctionFeature, jp_row: FunctionFeature) -> dict[str, Any]:
    body_exact = bool(
        global_row.body_hash
        and jp_row.body_hash
        and global_row.body_hash == jp_row.body_hash
    )
    if global_row.size and jp_row.size:
        size_similarity = min(global_row.size, jp_row.size) / max(
            global_row.size, jp_row.size
        )
    else:
        size_similarity = 0.0
    string_similarity = jaccard(global_row.strings, jp_row.strings)
    call_similarity = jaccard(global_row.calls, jp_row.calls)
    method_same = global_row.method == jp_row.method
    class_method_same = global_row.class_method == jp_row.class_method
    arity_same = (
        global_row.arity is not None
        and global_row.arity == jp_row.arity
    )

    score = min(
        1.0,
        (0.56 if body_exact else 0.0)
        + 0.12 * size_similarity
        + 0.10 * string_similarity
        + 0.10 * call_similarity
        + (0.05 if method_same else 0.0)
        + (0.04 if class_method_same else 0.0)
        + (0.03 if arity_same else 0.0),
    )
    signals = {
        "normalized_instruction_hash_exact": body_exact,
        "size_similarity": round(size_similarity, 6),
        "string_jaccard": round(string_similarity, 6),
        "call_neighborhood_jaccard": round(call_similarity, 6),
        "method_key_equal": method_same,
        "class_method_key_equal": class_method_same,
        "arity_equal": arity_same,
    }
    independent = sum(
        [
            body_exact,
            size_similarity >= 0.90,
            string_similarity > 0.0,
            call_similarity > 0.0,
            method_same or class_method_same,
            arity_same,
        ]
    )
    # Trivial getters/setters can have identical bodies across unrelated
    # classes. Never let body hash + size alone imply high lineage confidence.
    has_semantic_anchor = (
        class_method_same
        or string_similarity >= 0.25
        or call_similarity >= 0.25
    )
    if (
        class_method_same
        and body_exact
        and size_similarity >= 0.90
    ) or (
        class_method_same
        and size_similarity >= 0.80
        and string_similarity >= 0.25
        and call_similarity >= 0.25
    ):
        tier = "STRUCTURAL_HIGH"
    elif (
        has_semantic_anchor
        and size_similarity >= 0.70
        and independent >= 3
        and (
            body_exact
            or string_similarity >= 0.20
            or call_similarity >= 0.20
        )
    ):
        tier = "STRUCTURAL_MEDIUM"
    else:
        tier = "STRUCTURAL_LOW"
    return {
        "score": round(score, 6),
        "tier": tier,
        "independent_signal_count": independent,
        "signals": signals,
    }


def candidate_indexes(
    rows: list[FunctionFeature],
) -> dict[str, dict[Any, list[int]]]:
    index: dict[str, dict[Any, list[int]]] = {
        "body": defaultdict(list),
        "method_arity": defaultdict(list),
        "class_method": defaultdict(list),
        "string": defaultdict(list),
        "call": defaultdict(list),
    }
    for i, row in enumerate(rows):
        if row.body_hash:
            index["body"][row.body_hash].append(i)
        index["method_arity"][(row.method, row.arity)].append(i)
        index["class_method"][row.class_method].append(i)
        for value in row.strings:
            index["string"][value].append(i)
        for value in row.calls:
            index["call"][value].append(i)
    return index


def candidate_ids(
    row: FunctionFeature,
    index: dict[str, dict[Any, list[int]]],
) -> set[int]:
    result: set[int] = set()
    if row.body_hash:
        result.update(index["body"].get(row.body_hash, ()))

    method_bucket = index["method_arity"].get((row.method, row.arity), ())
    if len(method_bucket) <= 160:
        result.update(method_bucket)
    class_bucket = index["class_method"].get(row.class_method, ())
    if len(class_bucket) <= 160:
        result.update(class_bucket)

    for value in row.strings:
        bucket = index["string"].get(value, ())
        if len(bucket) <= 64:
            result.update(bucket)
    for value in row.calls:
        bucket = index["call"].get(value, ())
        if len(bucket) <= 64:
            result.update(bucket)
    return result


def compact_match_feature(row: FunctionFeature) -> dict[str, Any]:
    return {
        "name": row.name,
        "address_hex": f"0x{row.address:x}",
        "size": row.size,
        "normalized_instruction_sha256": row.body_hash,
        "string_refs": list(row.strings),
        "direct_calls": list(row.calls),
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    global_sha = sha256_file(args.global_binary)
    jp_sha = sha256_file(args.jp_binary)
    cache_sha = sha256_file(args.symbol_diff_cache)

    global_symbols, global_all, global_ranges = read_symbols(args.global_binary)
    jp_symbols, jp_all, jp_ranges = read_symbols(args.jp_binary)
    global_names = {row.name for row in global_symbols}
    jp_names = {row.name for row in jp_symbols}
    exact_names = sorted(global_names & jp_names)
    global_only_names = global_names - jp_names
    jp_only_names = jp_names - global_names

    global_symbol_by_name = {row.name: row for row in global_symbols}
    jp_symbol_by_name = {row.name: row for row in jp_symbols}
    global_image = Elf64Image(args.global_binary)
    jp_image = Elf64Image(args.jp_binary)
    global_resolver = FunctionResolver(global_all, global_ranges)
    jp_resolver = FunctionResolver(jp_all, jp_ranges)

    # Feature all defined lfs functions so exact-symbol matches can also report
    # whether normalized code changed, and unmatched functions can be ranked.
    global_features = {
        row.name: feature_for(global_image, row, global_resolver)
        for row in global_symbols
    }
    jp_features = {
        row.name: feature_for(jp_image, row, jp_resolver)
        for row in jp_symbols
    }

    exact_matches = []
    exact_body_identical = 0
    exact_body_changed = 0
    for name in exact_names:
        g = global_features[name]
        j = jp_features[name]
        body_identical = bool(
            g.body_hash and j.body_hash and g.body_hash == j.body_hash
        )
        if body_identical:
            exact_body_identical += 1
        elif g.body_hash and j.body_hash:
            exact_body_changed += 1
        exact_matches.append(
            {
                "global_name": name,
                "jp_name": name,
                "tier": "EXACT_SYMBOL_CORRESPONDENCE",
                "confidence": 1.0,
                "confidence_scope": "EXACT_SYMBOL_CORRESPONDENCE_ONLY",
                "behavioral_identity_claimed": False,
                "normalized_instruction_hash_identical": body_identical,
                "global_size": g.size,
                "jp_size": j.size,
            }
        )

    jp_unmatched = [
        jp_features[name]
        for name in sorted(jp_only_names)
    ]
    indexes = candidate_indexes(jp_unmatched)

    structural_rows = []
    unresolved = []
    provisional_targets: dict[str, list[int]] = defaultdict(list)

    for gname in sorted(global_only_names):
        g = global_features[gname]
        candidates = []
        for candidate_id in candidate_ids(g, indexes):
            j = jp_unmatched[candidate_id]
            scored = score_pair(g, j)
            candidates.append(
                {
                    "jp_name": j.name,
                    **scored,
                    "jp_feature": compact_match_feature(j),
                }
            )
        candidates.sort(
            key=lambda row: (
                -row["score"],
                row["jp_name"],
            )
        )
        top = candidates[:3]
        if not top:
            unresolved.append(
                {
                    "global_name": gname,
                    "reason": "NO_BOUNDED_STRUCTURAL_CANDIDATE",
                    "global_feature": compact_match_feature(g),
                }
            )
            continue

        margin = (
            top[0]["score"] - top[1]["score"]
            if len(top) > 1
            else top[0]["score"]
        )
        top_tier = top[0]["tier"]
        candidate = {
            "global_name": gname,
            "global_feature": compact_match_feature(g),
            "top_candidates": top,
            "top_score_margin": round(margin, 6),
            "provisional_resolution": (
                top_tier in {"STRUCTURAL_HIGH", "STRUCTURAL_MEDIUM"}
                and margin >= 0.03
            ),
            "exact_identity_claimed": False,
        }
        structural_rows.append(candidate)
        if candidate["provisional_resolution"]:
            provisional_targets[top[0]["jp_name"]].append(len(structural_rows) - 1)

    target_collisions = {
        target: indexes_list
        for target, indexes_list in provisional_targets.items()
        if len(indexes_list) > 1
    }
    collision_rows = []
    for target, row_indexes in sorted(target_collisions.items()):
        globals_for_target = [
            structural_rows[index]["global_name"]
            for index in row_indexes
        ]
        collision_rows.append(
            {
                "jp_name": target,
                "global_names": globals_for_target,
                "reason": "MULTIPLE_GLOBAL_FUNCTIONS_SHARE_PROVISIONAL_JP_TARGET",
            }
        )
        for index in row_indexes:
            structural_rows[index]["provisional_resolution"] = False
            structural_rows[index]["collision"] = target

    resolved_high = 0
    resolved_medium = 0
    ambiguous = 0
    low_only = 0
    structural_unresolved_names = []
    for row in structural_rows:
        top = row["top_candidates"][0]
        if row["provisional_resolution"]:
            if top["tier"] == "STRUCTURAL_HIGH":
                resolved_high += 1
            else:
                resolved_medium += 1
        else:
            structural_unresolved_names.append(row["global_name"])
            if row.get("collision") or row["top_score_margin"] < 0.03:
                ambiguous += 1
            elif top["tier"] == "STRUCTURAL_LOW":
                low_only += 1

    unresolved_names = sorted(
        {row["global_name"] for row in unresolved}
        | set(structural_unresolved_names)
    )

    broader_cache = json.loads(args.symbol_diff_cache.read_text())
    feature_counts = {
        "global_body_hashes": sum(
            row.body_hash is not None for row in global_features.values()
        ),
        "jp_body_hashes": sum(
            row.body_hash is not None for row in jp_features.values()
        ),
        "global_with_strings": sum(
            bool(row.strings) for row in global_features.values()
        ),
        "jp_with_strings": sum(
            bool(row.strings) for row in jp_features.values()
        ),
        "global_with_direct_calls": sum(
            bool(row.calls) for row in global_features.values()
        ),
        "jp_with_direct_calls": sum(
            bool(row.calls) for row in jp_features.values()
        ),
    }

    counts = {
        "global_defined_lfs_functions": len(global_symbols),
        "jp_defined_lfs_functions": len(jp_symbols),
        "exact_symbol_correspondences": len(exact_names),
        "global_function_only": len(global_only_names),
        "jp_function_only": len(jp_only_names),
        "exact_symbol_normalized_body_identical": exact_body_identical,
        "exact_symbol_normalized_body_changed": exact_body_changed,
        "structural_high_resolved": resolved_high,
        "structural_medium_resolved": resolved_medium,
        "structural_ambiguous": ambiguous,
        "structural_low_only": low_only,
        "unresolved_global_functions": len(unresolved_names),
        "target_collisions": len(collision_rows),
        **feature_counts,
    }

    return {
        "provenance": GLOBAL_PROVENANCE,
        "historical_authority": "Global 3.0.24 / 2017-05-25",
        "current_jp_role": "LINEAGE_REFERENCE_ONLY",
        "sources": {
            "global_binary": {
                "path": str(args.global_binary),
                "sha256": global_sha,
                "bytes": args.global_binary.stat().st_size,
            },
            "current_jp_binary": {
                "path": str(args.jp_binary),
                "sha256": jp_sha,
                "bytes": args.jp_binary.stat().st_size,
            },
            "cached_broader_lfs_symbol_diff": {
                "path": str(args.symbol_diff_cache),
                "sha256": cache_sha,
                "counts": {
                    "global_lfs_symbol_surface": broader_cache["global_lfs_count"],
                    "jp_lfs_symbol_surface": broader_cache["jp_lfs_count"],
                    "common_lfs_symbol_surface": broader_cache["common"],
                    "global_only_lfs_symbol_surface": broader_cache["global_only_count"],
                    "jp_only_lfs_symbol_surface": broader_cache["jp_only_count"],
                },
                "note": (
                    "Cached surface includes broader lfs symbols; this matcher "
                    "separately counts defined ELF FUNC symbols."
                ),
            },
        },
        "counts": counts,
        "matching_policy": {
            "exact_first": (
                "Exact demangled function names are paired first. Exact symbol "
                "correspondence does not claim normalized-body or behavioral identity."
            ),
            "normalized_instruction": (
                "AArch64 PC-relative branch/ADR/LDR literal immediates are masked "
                "before SHA-256 so body fingerprints are address-independent."
            ),
            "structural_features": [
                "normalized instruction SHA-256",
                "function byte size",
                "ASCII string references recovered from ADR/ADRP/LDR-literal patterns",
                "direct BL call-neighborhood resolved to exact symbols or bounded KnownSymbol+offset neighborhoods",
                "method/class-method/arity shape",
            ],
            "heuristic_ceiling": (
                "STRUCTURAL_HIGH/MEDIUM/LOW are lineage candidates only. "
                "Identical bodies across unrelated classes remain LOW; high "
                "confidence requires a semantic anchor. No heuristic is "
                "labeled exact identity or CONFIRMED ORIGINAL."
            ),
            "collision_policy": (
                "Low score-margin and many-to-one target collisions remain unresolved."
            ),
        },
        "exact_matches": exact_matches,
        "structural_candidates": structural_rows,
        "unresolved_global_function_names": unresolved_names,
        "target_collisions": collision_rows,
        "inventories": {
            "global": [
                global_features[row.name].compact()
                for row in global_symbols
            ],
            "current_jp": [
                jp_features[row.name].compact()
                for row in jp_symbols
            ],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--global-binary",
        type=Path,
        default=Path(
            "/home/ubuntu/logres/private/global-apk/3.0.24/"
            "libgame-arm64-v8a.so"
        ),
    )
    parser.add_argument(
        "--jp-binary",
        type=Path,
        default=Path("/home/ubuntu/logres/private/public-current-jp/libgame.so"),
    )
    parser.add_argument(
        "--symbol-diff-cache",
        type=Path,
        default=Path(
            "/home/ubuntu/logres/private/global-apk/3.0.24/re/reports/"
            "global-vs-current-jp-symbol-diff.json"
        ),
    )
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "counts": result["counts"],
                "global_sha256": result["sources"]["global_binary"]["sha256"],
                "jp_sha256": result["sources"]["current_jp_binary"]["sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
