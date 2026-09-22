#!/usr/bin/env python3
"""Privately hydrate one authentic live Logres map for renderer-proof runtime use.

The default target is 001_000_00002 because its schema/geometry has already been
validated extensively. This is a RENDERER PROOF map only; it is not evidence of
the tutorial/start map.

Private derivatives are written beside the private archive under
logres-renderer-proof/ and are never intended for Git. A bounded JSON summary
may be exported separately.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import zlib

from hydrate_private_assets import parse_mbn

CACHE_NAME = "jp-live-patch-cache"
DEFAULT_MAP_ID = "001_000_00002"
OUTPUT_DIR_NAME = "logres-renderer-proof"

DDPF_ALPHAPIXELS = 0x1
DDPF_RGB = 0x40
EXPECTED_PF_FLAGS = DDPF_ALPHAPIXELS | DDPF_RGB
EXPECTED_MASKS = {
    "R": 0x0F00,
    "G": 0x00F0,
    "B": 0x000F,
    "A": 0xF000,
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_a4r4g4b4_dds(data: bytes) -> tuple[int, int, bytes]:
    if len(data) < 128 or data[:4] != b"DDS ":
        raise ValueError("not-dds")
    if struct.unpack_from("<I", data, 4)[0] != 124:
        raise ValueError("unsupported-dds-header")
    width = struct.unpack_from("<I", data, 16)[0]
    height = struct.unpack_from("<I", data, 12)[0]
    pitch = struct.unpack_from("<I", data, 20)[0]
    if width <= 0 or height <= 0:
        raise ValueError("invalid-dds-dimensions")
    if struct.unpack_from("<I", data, 76)[0] != 32:
        raise ValueError("unsupported-dds-pixel-format-header")

    pf_flags = struct.unpack_from("<I", data, 80)[0]
    fourcc = data[84:88]
    bit_count = struct.unpack_from("<I", data, 88)[0]
    masks = {
        "R": struct.unpack_from("<I", data, 92)[0],
        "G": struct.unpack_from("<I", data, 96)[0],
        "B": struct.unpack_from("<I", data, 100)[0],
        "A": struct.unpack_from("<I", data, 104)[0],
    }
    if pf_flags != EXPECTED_PF_FLAGS:
        raise ValueError(f"unexpected-dds-flags-0x{pf_flags:08x}")
    if fourcc != b"\x00\x00\x00\x00":
        raise ValueError("unexpected-dds-fourcc")
    if bit_count != 16:
        raise ValueError(f"unexpected-dds-bit-count-{bit_count}")
    if masks != EXPECTED_MASKS:
        raise ValueError("unexpected-dds-channel-masks")
    if pitch != width * 2:
        raise ValueError("unexpected-dds-pitch")

    required = 128 + pitch * height
    if len(data) < required:
        raise ValueError("truncated-dds-pixels")
    pixels = data[128:required]
    return width, height, pixels


def expand_a4r4g4b4(pixels: bytes, width: int, height: int) -> bytes:
    expected = width * height * 2
    if len(pixels) != expected:
        raise ValueError("unexpected-a4r4g4b4-pixel-length")
    rgba = bytearray(width * height * 4)
    out = 0
    for offset in range(0, len(pixels), 2):
        value = pixels[offset] | (pixels[offset + 1] << 8)
        alpha = ((value >> 12) & 0xF) * 17
        red = ((value >> 8) & 0xF) * 17
        green = ((value >> 4) & 0xF) * 17
        blue = (value & 0xF) * 17
        rgba[out:out + 4] = bytes((red, green, blue, alpha))
        out += 4
    return bytes(rgba)


def _chunk(name: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + name
        + payload
        + struct.pack(">I", zlib.crc32(name + payload) & 0xFFFFFFFF)
    )


def rgba_png(width: int, height: int, rgba: bytes) -> bytes:
    if width <= 0 or height <= 0:
        raise ValueError("invalid-png-dimensions")
    if len(rgba) != width * height * 4:
        raise ValueError("invalid-rgba-length")
    stride = width * 4
    scanlines = bytearray()
    for row in range(height):
        scanlines.append(0)
        start = row * stride
        scanlines.extend(rgba[start:start + stride])
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(bytes(scanlines), 9))
        + _chunk(b"IEND", b"")
    )


def decode_dds_to_png(data: bytes) -> tuple[int, int, bytes]:
    width, height, pixels = parse_a4r4g4b4_dds(data)
    return width, height, rgba_png(width, height, expand_a4r4g4b4(pixels, width, height))


def hydrate(anchor: Path, map_id: str, output_root: Path | None = None) -> dict[str, object]:
    cache = anchor.resolve().parent / CACHE_NAME / "map"
    normal_path = cache / f"{map_id}.mbn"
    ans_path = cache / f"{map_id}__ans.mbn"
    if not normal_path.is_file():
        raise ValueError("normal map package not found")
    if not ans_path.is_file():
        raise ValueError("__ans map package not found")

    normal = parse_mbn(normal_path.read_bytes())
    ans = parse_mbn(ans_path.read_bytes())

    map_name = f"{map_id}.map"
    chip_name = f"{map_id}_CHIP.dds"
    obj_name = f"{map_id}_OBJ.dds"
    for entries, name in ((normal, map_name), (ans, map_name), (ans, chip_name), (ans, obj_name)):
        if name not in entries:
            raise ValueError(f"missing expected entry: {name}")

    normal_map = gzip.decompress(normal[map_name])
    ans_map = gzip.decompress(ans[map_name])
    if normal_map != ans_map:
        raise ValueError("normal/__ans map payload mismatch")

    chip_w, chip_h, chip_png = decode_dds_to_png(ans[chip_name])
    obj_w, obj_h, obj_png = decode_dds_to_png(ans[obj_name])

    root = output_root or (anchor.resolve().parent / OUTPUT_DIR_NAME)
    target = root / map_id
    target.mkdir(parents=True, exist_ok=True)

    map_file = target / f"{map_id}.map.bin"
    chip_file = target / f"{map_id}_CHIP.png"
    obj_file = target / f"{map_id}_OBJ.png"
    meta_file = target / "metadata.json"

    map_file.write_bytes(normal_map)
    chip_file.write_bytes(chip_png)
    obj_file.write_bytes(obj_png)

    metadata = {
        "provenance": "PUBLIC_LIVE_JP_RENDERER_PROOF_PRIVATE_DERIVATIVE",
        "evidence_classification": "CONFIRMED ORIGINAL",
        "role": "RENDERER_PROOF_NOT_TUTORIAL_MAP",
        "map_id": map_id,
        "source_packages": [normal_path.name, ans_path.name],
        "map": {
            "bytes": len(normal_map),
            "sha256": sha256(normal_map),
            "relative_file": map_file.name,
        },
        "chip": {
            "width": chip_w,
            "height": chip_h,
            "source_format": "DDS A4R4G4B4",
            "derived_format": "PNG RGBA8 nibble expansion",
            "source_sha256": sha256(ans[chip_name]),
            "derived_sha256": sha256(chip_png),
            "relative_file": chip_file.name,
        },
        "obj": {
            "width": obj_w,
            "height": obj_h,
            "source_format": "DDS A4R4G4B4",
            "derived_format": "PNG RGBA8 nibble expansion",
            "source_sha256": sha256(ans[obj_name]),
            "derived_sha256": sha256(obj_png),
            "relative_file": obj_file.name,
        },
        "orientation_policy": (
            "DDS row order is preserved exactly. Vertical texture orientation remains "
            "UNRESOLVED until renderer/native evidence establishes the sampling transform."
        ),
        "color_policy": (
            "4-bit channel values are expanded exactly by multiplying each nibble by 17. "
            "No gamma/color-space conversion or premultiplication is applied."
        ),
    }
    meta_file.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metadata


def make_dds(width: int, height: int, values: list[int]) -> bytes:
    if len(values) != width * height:
        raise ValueError("synthetic pixel count")
    data = bytearray(128 + width * height * 2)
    data[:4] = b"DDS "
    struct.pack_into("<I", data, 4, 124)
    struct.pack_into("<I", data, 8, 0x100F)
    struct.pack_into("<I", data, 12, height)
    struct.pack_into("<I", data, 16, width)
    struct.pack_into("<I", data, 20, width * 2)
    struct.pack_into("<I", data, 24, 1)
    struct.pack_into("<I", data, 76, 32)
    struct.pack_into("<I", data, 80, EXPECTED_PF_FLAGS)
    struct.pack_into("<I", data, 88, 16)
    struct.pack_into("<IIII", data, 92, EXPECTED_MASKS["R"], EXPECTED_MASKS["G"], EXPECTED_MASKS["B"], EXPECTED_MASKS["A"])
    struct.pack_into("<I", data, 108, 0x1000)
    for index, value in enumerate(values):
        struct.pack_into("<H", data, 128 + index * 2, value)
    return bytes(data)


def self_test() -> None:
    dds = make_dds(2, 1, [0xF123, 0x048F])
    width, height, pixels = parse_a4r4g4b4_dds(dds)
    assert (width, height) == (2, 1)
    rgba = expand_a4r4g4b4(pixels, width, height)
    assert rgba == bytes((17, 34, 51, 255, 68, 136, 255, 0))
    png = rgba_png(width, height, rgba)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert b"IHDR" in png and b"IDAT" in png and png.endswith(b"IEND\xaeB\x60\x82")
    print("Logres live renderer-proof hydration self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchor", type=Path)
    parser.add_argument("--map-id", default=DEFAULT_MAP_ID)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0
    if not args.anchor:
        print("--anchor required", file=sys.stderr)
        return 2

    try:
        result = hydrate(args.anchor, args.map_id, args.output_root)
    except Exception as exc:
        print(f"hydration failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(encoded, encoding="utf-8")
    else:
        sys.stdout.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
