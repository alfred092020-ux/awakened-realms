#!/usr/bin/env python3
"""Inspect pixel-format metadata of DDS atlases paired with live Logres maps.

Exports DDS header fields, mask signatures and aggregate counts only.
No texture pixels, payload bytes, decoded images, map geometry or source text
are exported.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import struct
import sys
import tempfile

from hydrate_private_assets import parse_mbn

CACHE_NAME = "jp-live-patch-cache"
MAX_SAMPLES = 300

DDPF_ALPHAPIXELS = 0x1
DDPF_ALPHA = 0x2
DDPF_FOURCC = 0x4
DDPF_RGB = 0x40
DDPF_YUV = 0x200
DDPF_LUMINANCE = 0x20000


def _hex(value: int) -> str:
    return f"0x{value:08x}"


def _flag_names(flags: int) -> list[str]:
    known = (
        (DDPF_ALPHAPIXELS, "ALPHAPIXELS"),
        (DDPF_ALPHA, "ALPHA"),
        (DDPF_FOURCC, "FOURCC"),
        (DDPF_RGB, "RGB"),
        (DDPF_YUV, "YUV"),
        (DDPF_LUMINANCE, "LUMINANCE"),
    )
    return [name for bit, name in known if flags & bit]


def _single_byte_index(mask: int) -> int | None:
    for index in range(4):
        if mask == (0xFF << (index * 8)):
            return index
    return None


def byte_channel_order(bit_count: int, masks: dict[str, int]) -> str | None:
    if bit_count != 32:
        return None
    positions = {}
    for channel in ("R", "G", "B", "A"):
        mask = masks[channel]
        if channel == "A" and mask == 0:
            continue
        index = _single_byte_index(mask)
        if index is None or index in positions:
            return None
        positions[index] = channel
    if len(positions) not in (3, 4):
        return None
    return "".join(positions.get(index, "X") for index in range(4))


def parse_dds_header(data: bytes) -> dict[str, object]:
    if len(data) < 128 or data[:4] != b"DDS ":
        raise ValueError("not-dds")
    if struct.unpack_from("<I", data, 4)[0] != 124:
        raise ValueError("unsupported-dds-header")
    if struct.unpack_from("<I", data, 76)[0] != 32:
        raise ValueError("unsupported-dds-pixel-format")

    flags = struct.unpack_from("<I", data, 8)[0]
    height = struct.unpack_from("<I", data, 12)[0]
    width = struct.unpack_from("<I", data, 16)[0]
    pitch_or_linear = struct.unpack_from("<I", data, 20)[0]
    depth = struct.unpack_from("<I", data, 24)[0]
    mip_count = struct.unpack_from("<I", data, 28)[0]

    pf_flags = struct.unpack_from("<I", data, 80)[0]
    fourcc_raw = data[84:88]
    bit_count = struct.unpack_from("<I", data, 88)[0]
    masks = {
        "R": struct.unpack_from("<I", data, 92)[0],
        "G": struct.unpack_from("<I", data, 96)[0],
        "B": struct.unpack_from("<I", data, 100)[0],
        "A": struct.unpack_from("<I", data, 104)[0],
    }
    caps = struct.unpack_from("<I", data, 108)[0]
    caps2 = struct.unpack_from("<I", data, 112)[0]

    fourcc = "".join(chr(b) if 32 <= b <= 126 else f"\\x{b:02x}" for b in fourcc_raw)
    dx10 = None
    if fourcc_raw == b"DX10":
        if len(data) < 148:
            raise ValueError("truncated-dx10")
        dx10 = {
            "dxgi_format": struct.unpack_from("<I", data, 128)[0],
            "resource_dimension": struct.unpack_from("<I", data, 132)[0],
            "misc_flag": _hex(struct.unpack_from("<I", data, 136)[0]),
            "array_size": struct.unpack_from("<I", data, 140)[0],
            "misc_flags2": _hex(struct.unpack_from("<I", data, 144)[0]),
        }

    return {
        "width": width,
        "height": height,
        "header_flags": _hex(flags),
        "pitch_or_linear_size": pitch_or_linear,
        "depth": depth,
        "mip_map_count": mip_count,
        "pixel_format_flags": _hex(pf_flags),
        "pixel_format_flag_names": _flag_names(pf_flags),
        "fourcc": fourcc,
        "rgb_bit_count": bit_count,
        "masks": {key: _hex(value) for key, value in masks.items()},
        "byte_channel_order_little_endian": byte_channel_order(bit_count, masks),
        "caps": _hex(caps),
        "caps2": _hex(caps2),
        "dx10": dx10,
    }


def inspect(anchor: Path) -> dict[str, object]:
    map_root = anchor.resolve().parent / CACHE_NAME / "map"
    if not map_root.is_dir():
        raise ValueError("live map cache not found")

    formats = Counter()
    orders = Counter()
    bit_counts = Counter()
    pf_flags = Counter()
    mip_counts = Counter()
    samples = []
    errors = []
    texture_count = 0
    package_count = 0

    for package in sorted(map_root.glob("*__ans.mbn")):
        package_count += 1
        try:
            entries = parse_mbn(package.read_bytes())
        except Exception as exc:
            errors.append({"package": package.name, "reason": "parse-" + type(exc).__name__})
            continue

        for entry, data in sorted(entries.items()):
            if Path(entry).suffix.lower() != ".dds":
                continue
            if not (entry.endswith("_CHIP.dds") or entry.endswith("_OBJ.dds")):
                continue
            texture_count += 1
            try:
                header = parse_dds_header(data)
            except Exception as exc:
                errors.append({"package": package.name, "entry": entry, "reason": type(exc).__name__ + ":" + str(exc)})
                continue

            formats.update([header["fourcc"]])
            orders.update([header["byte_channel_order_little_endian"] or "(unresolved)"])
            bit_counts.update([str(header["rgb_bit_count"])])
            pf_flags.update([header["pixel_format_flags"]])
            mip_counts.update([str(header["mip_map_count"])])

            if len(samples) < MAX_SAMPLES:
                samples.append({
                    "package": package.name,
                    "entry": entry,
                    "header": header,
                })

    return {
        "provenance": "PUBLIC_LIVE_JP_MAP_DDS_HEADER_METADATA",
        "policy": (
            "DDS header metadata only. Byte channel order is derived solely from "
            "32-bit byte-aligned channel masks. It does not prove color space, "
            "premultiplication, shader sampling or pixel equivalence with ASTC."
        ),
        "ans_package_count": package_count,
        "dds_texture_count": texture_count,
        "fourcc_distribution": dict(formats.most_common()),
        "byte_channel_order_distribution": dict(orders.most_common()),
        "rgb_bit_count_distribution": dict(bit_counts.most_common()),
        "pixel_format_flags_distribution": dict(pf_flags.most_common()),
        "mip_map_count_distribution": dict(mip_counts.most_common()),
        "samples": samples,
        "errors": errors[:200],
    }


def make_dds(
    *,
    width: int,
    height: int,
    pf_flags: int,
    bit_count: int,
    r: int,
    g: int,
    b: int,
    a: int,
    fourcc: bytes = b"\x00\x00\x00\x00",
) -> bytes:
    data = bytearray(128)
    data[:4] = b"DDS "
    struct.pack_into("<I", data, 4, 124)
    struct.pack_into("<I", data, 8, 0x100F)
    struct.pack_into("<I", data, 12, height)
    struct.pack_into("<I", data, 16, width)
    struct.pack_into("<I", data, 20, width * max(1, bit_count // 8))
    struct.pack_into("<I", data, 76, 32)
    struct.pack_into("<I", data, 80, pf_flags)
    data[84:88] = fourcc
    struct.pack_into("<I", data, 88, bit_count)
    struct.pack_into("<IIII", data, 92, r, g, b, a)
    struct.pack_into("<I", data, 108, 0x1000)
    return bytes(data)


def self_test() -> None:
    bgra = make_dds(
        width=10, height=20,
        pf_flags=DDPF_RGB | DDPF_ALPHAPIXELS,
        bit_count=32,
        r=0x00FF0000, g=0x0000FF00, b=0x000000FF, a=0xFF000000,
    )
    rgba = make_dds(
        width=30, height=40,
        pf_flags=DDPF_RGB | DDPF_ALPHAPIXELS,
        bit_count=32,
        r=0x000000FF, g=0x0000FF00, b=0x00FF0000, a=0xFF000000,
    )
    h1 = parse_dds_header(bgra)
    h2 = parse_dds_header(rgba)
    assert h1["byte_channel_order_little_endian"] == "BGRA"
    assert h2["byte_channel_order_little_endian"] == "RGBA"
    assert h1["pixel_format_flag_names"] == ["ALPHAPIXELS", "RGB"]
    assert h1["width"] == 10 and h1["height"] == 20
    print("Logres live map DDS format inspector self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchor", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0
    if not args.anchor:
        print("--anchor required", file=sys.stderr)
        return 2

    try:
        result = inspect(args.anchor)
    except Exception as exc:
        print(f"inspect failed: {type(exc).__name__}: {exc}", file=sys.stderr)
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
