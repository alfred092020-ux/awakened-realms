#!/usr/bin/env python3
"""Inspect Logres LFLA protobuf-wire animation data without requiring its .proto schema.

The recovered LFLA files are protobuf messages. This script decodes the subset
needed for title reconstruction and can flatten a timeline's first visible
frame into leaf image transforms.

It never exports proprietary source code; it reports structural metadata,
resource references, and numeric transform evidence.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


class LflaDecodeError(ValueError):
    pass


@dataclass(frozen=True)
class WireValue:
    field: int
    wire: int
    value: int | bytes


def read_varint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        if offset >= len(data):
            raise LflaDecodeError("truncated varint")
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, offset
        shift += 7
        if shift > 70:
            raise LflaDecodeError("varint is too long")


def parse_wire(data: bytes) -> list[WireValue]:
    values: list[WireValue] = []
    offset = 0
    while offset < len(data):
        tag, offset = read_varint(data, offset)
        field = tag >> 3
        wire = tag & 7
        if field <= 0:
            raise LflaDecodeError("invalid protobuf field number")

        if wire == 0:
            value, offset = read_varint(data, offset)
            values.append(WireValue(field, wire, value))
        elif wire == 1:
            end = offset + 8
            if end > len(data):
                raise LflaDecodeError("truncated fixed64")
            values.append(WireValue(field, wire, data[offset:end]))
            offset = end
        elif wire == 2:
            size, offset = read_varint(data, offset)
            end = offset + size
            if end > len(data):
                raise LflaDecodeError("truncated length-delimited field")
            values.append(WireValue(field, wire, data[offset:end]))
            offset = end
        elif wire == 5:
            end = offset + 4
            if end > len(data):
                raise LflaDecodeError("truncated fixed32")
            values.append(WireValue(field, wire, data[offset:end]))
            offset = end
        else:
            raise LflaDecodeError(f"unsupported protobuf wire type {wire}")
    return values


def field_values(data: bytes, field: int, wire: int | None = None) -> list[WireValue]:
    return [
        item
        for item in parse_wire(data)
        if item.field == field and (wire is None or item.wire == wire)
    ]


def first_varint(data: bytes, field: int, default: int = 0) -> int:
    values = field_values(data, field, 0)
    return int(values[0].value) if values else default


def first_bytes(data: bytes, field: int) -> bytes | None:
    values = field_values(data, field, 2)
    return bytes(values[0].value) if values else None


def decode_text(data: bytes | None) -> str:
    if data is None:
        return ""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return ""
    if not text:
        return ""
    printable = sum(ch.isprintable() for ch in text)
    return text if printable / len(text) > 0.9 else ""


def fixed32_float(raw: bytes | None, default: float) -> float:
    if raw is None:
        return default
    if len(raw) != 4:
        raise LflaDecodeError("fixed32 value must be four bytes")
    value = struct.unpack("<f", raw)[0]
    if not math.isfinite(value):
        raise LflaDecodeError("non-finite float transform")
    return float(value)


def first_fixed32(data: bytes, field: int, default: float) -> float:
    values = field_values(data, field, 5)
    if not values:
        return default
    return fixed32_float(bytes(values[0].value), default)


@dataclass(frozen=True)
class Transform:
    x: float = 0.0
    y: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0

    def then(self, child: "Transform") -> "Transform":
        return Transform(
            x=self.x + child.x * self.scale_x,
            y=self.y + child.y * self.scale_y,
            scale_x=self.scale_x * child.scale_x,
            scale_y=self.scale_y * child.scale_y,
        )


def decode_instance(instance: bytes) -> tuple[str, Transform, int | None]:
    ref = decode_text(first_bytes(instance, 4))
    transform_bytes = first_bytes(instance, 5) or b""
    transform = Transform(
        x=first_fixed32(transform_bytes, 5, 0.0),
        y=first_fixed32(transform_bytes, 6, 0.0),
        scale_x=first_fixed32(transform_bytes, 1, 1.0),
        scale_y=first_fixed32(transform_bytes, 4, 1.0),
    )
    blend_mode = first_varint(instance, 6, -1)
    return ref, transform, None if blend_mode < 0 else blend_mode


def decode_layer(layer: bytes) -> dict[str, object]:
    name = decode_text(first_bytes(layer, 2))
    keyframes = []
    for entry in field_values(layer, 3, 2):
        keyframe = bytes(entry.value)
        keyframes.append(
            {
                "start": first_varint(keyframe, 2, 0),
                "duration": first_varint(keyframe, 3, 0),
                "flag": first_varint(keyframe, 4, 0),
                "instance": first_bytes(keyframe, 13),
            }
        )
    return {
        "name": name,
        "duration": first_varint(layer, 1, 0),
        "keyframes": keyframes,
    }


def decode_timeline(data: bytes) -> dict[str, object]:
    return {
        "name": decode_text(first_bytes(data, 1)),
        "layers": [
            decode_layer(bytes(entry.value))
            for entry in field_values(data, 2, 2)
        ],
    }


def choose_keyframe(layer: dict[str, object], time_ms: int) -> dict[str, object] | None:
    chosen = None
    for keyframe in layer["keyframes"]:  # type: ignore[index]
        start = int(keyframe["start"])  # type: ignore[index]
        duration = int(keyframe["duration"])  # type: ignore[index]
        end = start + max(duration, 1)
        if start <= time_ms < end:
            chosen = keyframe
            break
    return chosen


def flatten_timeline(
    timeline: dict[str, object],
    symbols: dict[str, dict[str, object]],
    resources: set[str],
    *,
    time_ms: int,
    parent: Transform = Transform(),
    stack: tuple[str, ...] = (),
) -> list[dict[str, object]]:
    leaves: list[dict[str, object]] = []
    for layer_index, layer in enumerate(timeline["layers"]):  # type: ignore[index]
        keyframe = choose_keyframe(layer, time_ms)
        if not keyframe:
            continue
        instance = keyframe.get("instance")
        if not isinstance(instance, (bytes, bytearray)):
            continue

        ref, local, blend_mode = decode_instance(bytes(instance))
        if not ref:
            continue
        combined = parent.then(local)

        if ref in symbols:
            if ref in stack:
                raise LflaDecodeError(f"recursive symbol cycle at {ref!r}")
            leaves.extend(
                flatten_timeline(
                    symbols[ref],
                    symbols,
                    resources,
                    time_ms=time_ms,
                    parent=combined,
                    stack=stack + (ref,),
                )
            )
            continue

        is_resource = ref in resources or ref.startswith("png/")
        leaves.append(
            {
                "ref": ref,
                "known_resource": is_resource,
                "layer": str(layer.get("name") or ""),
                "layer_index": layer_index,
                "x": round(combined.x, 5),
                "y": round(combined.y, 5),
                "scale_x": round(combined.scale_x, 6),
                "scale_y": round(combined.scale_y, 6),
                "blend_mode": blend_mode,
                "symbol_path": list(stack),
            }
        )
    return leaves


def inspect_lfla(data: bytes, time_ms: int = 0) -> dict[str, object]:
    root = parse_wire(data)
    width = first_varint(data, 1)
    height = first_varint(data, 2)
    duration = first_varint(data, 3)
    name = decode_text(first_bytes(data, 4))

    timeline_bytes = first_bytes(data, 5)
    if timeline_bytes is None:
        raise LflaDecodeError("LFLA has no root timeline")

    resources: set[str] = set()
    resource_records = []
    for entry in field_values(data, 6, 2):
        record = bytes(entry.value)
        original = decode_text(first_bytes(record, 1))
        runtime = decode_text(first_bytes(record, 3))
        if original:
            resources.add(original)
        if runtime:
            resources.add(runtime)
        resource_records.append({"original": original, "runtime": runtime})

    symbols: dict[str, dict[str, object]] = {}
    for entry in field_values(data, 7, 2):
        symbol = bytes(entry.value)
        symbol_name = decode_text(first_bytes(symbol, 1))
        symbol_timeline = first_bytes(symbol, 2)
        if symbol_name and symbol_timeline is not None:
            symbols[symbol_name] = decode_timeline(symbol_timeline)

    timeline = decode_timeline(timeline_bytes)
    leaves = flatten_timeline(
        timeline,
        symbols,
        resources,
        time_ms=time_ms,
    )

    return {
        "format": "PROTOBUF_WIRE_LFLA",
        "name": name,
        "width": width,
        "height": height,
        "duration": duration,
        "time": time_ms,
        "resource_count": len(resource_records),
        "symbol_count": len(symbols),
        "resources": resource_records,
        "visible_leaves": leaves,
    }


def encode_varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def field_varint(field: int, value: int) -> bytes:
    return encode_varint((field << 3) | 0) + encode_varint(value)


def field_bytes(field: int, value: bytes) -> bytes:
    return encode_varint((field << 3) | 2) + encode_varint(len(value)) + value


def field_fixed32(field: int, value: float) -> bytes:
    return encode_varint((field << 3) | 5) + struct.pack("<f", value)


def synthetic_lfla() -> bytes:
    leaf_transform = (
        field_fixed32(1, 1.0)
        + field_fixed32(4, 1.0)
        + field_fixed32(5, -10.0)
        + field_fixed32(6, -20.0)
    )
    leaf_instance = field_bytes(4, b"png/test.png") + field_bytes(5, leaf_transform)
    leaf_keyframe = (
        field_varint(1, 30000)
        + field_varint(3, 1000)
        + field_varint(4, 1)
        + field_bytes(13, leaf_instance)
    )
    leaf_layer = (
        field_varint(1, 1000)
        + field_bytes(2, b"leaf")
        + field_bytes(3, leaf_keyframe)
    )
    root_transform = (
        field_fixed32(1, 2.0)
        + field_fixed32(4, 2.0)
        + field_fixed32(5, 100.0)
        + field_fixed32(6, 200.0)
    )
    root_instance = field_bytes(4, b"symbol") + field_bytes(5, root_transform)
    root_keyframe = (
        field_varint(1, 30000)
        + field_varint(3, 1000)
        + field_varint(4, 1)
        + field_bytes(13, root_instance)
    )
    root_layer = (
        field_varint(1, 1000)
        + field_bytes(2, b"root")
        + field_bytes(3, root_keyframe)
    )
    root_timeline = field_bytes(1, b"") + field_bytes(2, root_layer)
    symbol_timeline = field_bytes(1, b"symbol") + field_bytes(2, leaf_layer)
    symbol = field_bytes(1, b"symbol") + field_bytes(2, symbol_timeline)
    resource = field_bytes(1, b"png/test.png") + field_bytes(3, b"png/test.png")
    return (
        field_varint(1, 720)
        + field_varint(2, 1280)
        + field_varint(3, 1000)
        + field_bytes(4, b"test")
        + field_bytes(5, root_timeline)
        + field_bytes(6, resource)
        + field_bytes(7, symbol)
        + field_varint(8, 30000)
    )


def self_test() -> dict[str, object]:
    result = inspect_lfla(synthetic_lfla())
    leaves = result["visible_leaves"]
    assert isinstance(leaves, list) and len(leaves) == 1
    leaf = leaves[0]
    assert leaf["ref"] == "png/test.png"
    assert leaf["x"] == 80.0
    assert leaf["y"] == 160.0
    assert leaf["scale_x"] == 2.0
    assert leaf["scale_y"] == 2.0
    return {
        "ok": True,
        "width": result["width"],
        "height": result["height"],
        "leaf": leaf,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lfla", nargs="?", type=Path)
    parser.add_argument("--time", type=int, default=0)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.self_test:
        result = self_test()
    else:
        if args.lfla is None:
            parser.error("lfla path is required unless --self-test is used")
        result = inspect_lfla(args.lfla.read_bytes(), time_ms=args.time)

    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
