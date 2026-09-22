#!/usr/bin/env python3
"""Inspect opaque terminal records inside recovered private Logres map packages."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any
from zipfile import ZipFile

from hydrate_private_assets import parse_astc_header, parse_mbn
from inspect_private_map_packages import (
    MAP_PREFIX,
    WireField,
    parse_wire_message,
)

SAMPLE_LIMIT = 3
TOP_VALUE_LIMIT = 12


def wire_signature(fields: list[WireField]) -> str:
    return ",".join(
        f"{field.number}:{field.wire_type}"
        for field in fields
    )


def collect_field1_records(tree: bytes) -> list[bytes]:
    records: list[bytes] = []

    def walk(message: bytes) -> None:
        fields = parse_wire_message(message)
        for field in fields:
            if (
                field.number == 1
                and field.wire_type == 2
                and isinstance(field.value, bytes)
            ):
                records.append(field.value)
            elif (
                field.number == 2
                and field.wire_type == 2
                and isinstance(field.value, bytes)
            ):
                walk(field.value)

    walk(tree)
    return records


def nested_signature(data: bytes) -> str | None:
    if not data:
        return None
    try:
        fields = parse_wire_message(data)
    except ValueError:
        return None
    if not fields:
        return None
    return wire_signature(fields)


def printable_preview(data: bytes) -> str | None:
    if not data:
        return None
    printable = sum(
        1
        for byte in data
        if byte in (9, 10, 13) or 32 <= byte <= 126
    )
    if printable / len(data) < 0.9:
        return None
    return data[:80].decode("ascii", errors="replace")


def field_sample(field: WireField) -> dict[str, Any]:
    if field.wire_type == 0:
        assert isinstance(field.value, int)
        return {
            "field": field.number,
            "wire_type": 0,
            "varint": field.value,
        }

    assert isinstance(field.value, bytes)
    if field.wire_type == 5:
        value = field.value
        return {
            "field": field.number,
            "wire_type": 5,
            "u32": struct.unpack("<I", value)[0],
            "f32": struct.unpack("<f", value)[0],
            "hex": value.hex(),
        }
    if field.wire_type == 1:
        value = field.value
        return {
            "field": field.number,
            "wire_type": 1,
            "u64": struct.unpack("<Q", value)[0],
            "f64": struct.unpack("<d", value)[0],
            "hex": value.hex(),
        }

    assert field.wire_type == 2
    value = field.value
    result: dict[str, Any] = {
        "field": field.number,
        "wire_type": 2,
        "byte_length": len(value),
        "hex_prefix": value[:32].hex(),
    }
    text = printable_preview(value)
    if text is not None:
        result["ascii_preview"] = text
    nested = nested_signature(value)
    if nested is not None:
        result["nested_wire_signature_candidate"] = nested
    return result


def range_hits(
    values: list[float],
    chip_width: int,
    chip_height: int,
    obj_width: int,
    obj_height: int,
) -> dict[str, int]:
    finite = [
        value
        for value in values
        if math.isfinite(value)
    ]
    return {
        "finite_count": len(finite),
        "zero_to_one": sum(0.0 <= value <= 1.0 for value in finite),
        "zero_to_chip_width": sum(
            0.0 <= value <= chip_width for value in finite
        ),
        "zero_to_chip_height": sum(
            0.0 <= value <= chip_height for value in finite
        ),
        "zero_to_obj_width": sum(
            0.0 <= value <= obj_width for value in finite
        ),
        "zero_to_obj_height": sum(
            0.0 <= value <= obj_height for value in finite
        ),
    }


def summarize_signature(
    records: list[tuple[bytes, list[WireField]]],
    chip_width: int,
    chip_height: int,
    obj_width: int,
    obj_height: int,
) -> dict[str, Any]:
    sizes = [len(raw) for raw, _ in records]
    field_stats: dict[str, dict[str, Any]] = {}

    grouped: dict[
        tuple[int, int],
        list[WireField],
    ] = defaultdict(list)
    for _, fields in records:
        for field in fields:
            grouped[(field.number, field.wire_type)].append(field)

    for (number, wire_type), fields in sorted(grouped.items()):
        key = f"{number}:{wire_type}"
        if wire_type == 0:
            values = [
                int(field.value)
                for field in fields
                if isinstance(field.value, int)
            ]
            counts = Counter(values)
            field_stats[key] = {
                "occurrences": len(values),
                "min": min(values),
                "max": max(values),
                "unique_count": len(counts),
                "top_values": [
                    {"value": value, "count": count}
                    for value, count in counts.most_common(TOP_VALUE_LIMIT)
                ],
                "numeric_range_hits": range_hits(
                    [float(value) for value in values],
                    chip_width,
                    chip_height,
                    obj_width,
                    obj_height,
                ),
            }
        elif wire_type == 5:
            raw_values = [
                field.value
                for field in fields
                if isinstance(field.value, bytes)
            ]
            u32 = [struct.unpack("<I", value)[0] for value in raw_values]
            f32 = [struct.unpack("<f", value)[0] for value in raw_values]
            finite_f32 = [value for value in f32 if math.isfinite(value)]
            field_stats[key] = {
                "occurrences": len(raw_values),
                "u32_min": min(u32),
                "u32_max": max(u32),
                "f32_finite_count": len(finite_f32),
                "f32_min": min(finite_f32) if finite_f32 else None,
                "f32_max": max(finite_f32) if finite_f32 else None,
                "f32_numeric_range_hits": range_hits(
                    finite_f32,
                    chip_width,
                    chip_height,
                    obj_width,
                    obj_height,
                ),
            }
        elif wire_type == 1:
            raw_values = [
                field.value
                for field in fields
                if isinstance(field.value, bytes)
            ]
            u64 = [struct.unpack("<Q", value)[0] for value in raw_values]
            f64 = [struct.unpack("<d", value)[0] for value in raw_values]
            finite_f64 = [value for value in f64 if math.isfinite(value)]
            field_stats[key] = {
                "occurrences": len(raw_values),
                "u64_min": min(u64),
                "u64_max": max(u64),
                "f64_finite_count": len(finite_f64),
                "f64_min": min(finite_f64) if finite_f64 else None,
                "f64_max": max(finite_f64) if finite_f64 else None,
            }
        else:
            blobs = [
                field.value
                for field in fields
                if isinstance(field.value, bytes)
            ]
            lengths = [len(value) for value in blobs]
            nested = Counter(
                signature
                for value in blobs
                if (signature := nested_signature(value)) is not None
            )
            ascii_values = [
                preview
                for value in blobs
                if (preview := printable_preview(value)) is not None
            ]
            field_stats[key] = {
                "occurrences": len(blobs),
                "byte_length_min": min(lengths),
                "byte_length_max": max(lengths),
                "byte_length_unique_count": len(set(lengths)),
                "nested_wire_signature_candidates": [
                    {"signature": signature, "count": count}
                    for signature, count in nested.most_common(TOP_VALUE_LIMIT)
                ],
                "ascii_preview_samples": ascii_values[:SAMPLE_LIMIT],
            }

    return {
        "count": len(records),
        "record_bytes_min": min(sizes),
        "record_bytes_max": max(sizes),
        "record_bytes_mean": round(mean(sizes), 3),
        "fields": field_stats,
        "samples": [
            {
                "record_bytes": len(raw),
                "hex_prefix": raw[:64].hex(),
                "fields": [field_sample(field) for field in fields],
            }
            for raw, fields in records[:SAMPLE_LIMIT]
        ],
    }


def inspect_package(member: str, mbn: bytes) -> dict[str, Any] | None:
    package_id = Path(member).stem
    entries = parse_mbn(mbn)
    map_name = f"{package_id}.map"
    chip_name = f"{package_id}_CHIP.astc"
    obj_name = f"{package_id}_OBJ.astc"
    if not all(name in entries for name in (map_name, chip_name, obj_name)):
        return None

    decoded_map = gzip.decompress(entries[map_name])
    root = parse_wire_message(decoded_map)
    field5_values = [
        field.value
        for field in root
        if (
            field.number == 5
            and field.wire_type == 2
            and isinstance(field.value, bytes)
        )
    ]
    if len(field5_values) != 1:
        raise ValueError(
            f"{map_name} expected exactly one length-delimited root field 5"
        )

    chip = parse_astc_header(entries[chip_name])
    obj = parse_astc_header(entries[obj_name])
    raw_records = collect_field1_records(field5_values[0])

    parsed: dict[str, list[tuple[bytes, list[WireField]]]] = defaultdict(list)
    parse_errors: list[bytes] = []
    for raw in raw_records:
        try:
            fields = parse_wire_message(raw)
        except ValueError:
            parse_errors.append(raw)
            continue
        parsed[wire_signature(fields)].append((raw, fields))

    return {
        "package_member": member,
        "terminal_record_count": len(raw_records),
        "parsed_record_count": sum(len(items) for items in parsed.values()),
        "parse_error_count": len(parse_errors),
        "parse_error_hex_prefix_samples": [
            raw[:64].hex() for raw in parse_errors[:SAMPLE_LIMIT]
        ],
        "atlas_dimensions": {
            "CHIP": [chip.width, chip.height],
            "OBJ": [obj.width, obj.height],
        },
        "wire_signature_count": len(parsed),
        "wire_signatures": {
            signature: summarize_signature(
                records,
                chip.width,
                chip.height,
                obj.width,
                obj.height,
            )
            for signature, records in sorted(
                parsed.items(),
                key=lambda item: (-len(item[1]), item[0]),
            )
        },
    }


def inspect_archive(archive: Path) -> dict[str, Any]:
    packages: dict[str, Any] = {}
    with ZipFile(archive) as source:
        for member in sorted(source.namelist()):
            if (
                not member.startswith(MAP_PREFIX)
                or not member.endswith(".mbn")
            ):
                continue
            basename = Path(member).name
            if not basename or not basename[0].isdigit():
                continue
            package = inspect_package(member, source.read(member))
            if package is not None:
                packages[Path(member).stem] = package

    return {
        "provenance": "EXTRACTED_PRIVATE_CACHE_METADATA",
        "semantic_policy": (
            "Terminal field1 payloads are treated as opaque protobuf-style "
            "records. Numeric and nested interpretations are candidates only; "
            "no tile/object/position/UV meaning is asserted here."
        ),
        "package_count": len(packages),
        "packages": packages,
    }


def _enc_varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _field_varint(number: int, value: int) -> bytes:
    return _enc_varint(number << 3) + _enc_varint(value)


def _field_bytes(number: int, value: bytes) -> bytes:
    return (
        _enc_varint((number << 3) | 2)
        + _enc_varint(len(value))
        + value
    )


def _field_fixed32(number: int, value: float) -> bytes:
    return _enc_varint((number << 3) | 5) + struct.pack("<f", value)


def self_test() -> None:
    record_a = (
        _field_varint(1, 7)
        + _field_fixed32(2, 12.5)
        + _field_bytes(3, b"abc")
    )
    record_b = (
        _field_varint(1, 9)
        + _field_fixed32(2, 24.0)
        + _field_bytes(3, b"xyz")
    )
    leaf = _field_bytes(1, record_a) + _field_bytes(1, record_b)
    tree = _field_bytes(2, leaf)

    records = collect_field1_records(tree)
    if records != [record_a, record_b]:
        raise AssertionError("terminal record collection failed")

    parsed = [parse_wire_message(record) for record in records]
    signature = wire_signature(parsed[0])
    if signature != "1:0,2:5,3:2":
        raise AssertionError(f"unexpected signature: {signature}")

    summary = summarize_signature(
        list(zip(records, parsed)),
        100,
        200,
        300,
        400,
    )
    if summary["count"] != 2:
        raise AssertionError("signature count failed")
    if summary["fields"]["1:0"]["min"] != 7:
        raise AssertionError("varint summary failed")
    if summary["fields"]["2:5"]["f32_max"] != 24.0:
        raise AssertionError("fixed32 summary failed")
    if summary["fields"]["3:2"]["ascii_preview_samples"] != ["abc", "xyz"]:
        raise AssertionError("length-delimited summary failed")

    print("Logres private map terminal record inspector self-test: PASS")


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
        print(
            "archive argument is required unless --self-test is used",
            file=sys.stderr,
        )
        return 2

    try:
        result = inspect_archive(args.archive)
    except (OSError, ValueError) as exc:
        print(f"Logres map record inspection failed: {exc}", file=sys.stderr)
        return 1

    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        sys.stdout.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
