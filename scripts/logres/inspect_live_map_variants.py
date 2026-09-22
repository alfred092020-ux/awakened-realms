#!/usr/bin/env python3
"""Compare live Logres map ASTC packages with paired __ans DDS packages.

Exports hashes, formats, dimensions and pair-equivalence metadata only.
No texture bytes, decoded pixels, geometry or source content are exported.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile

from hydrate_private_assets import _make_synthetic_mbn, parse_astc_header, parse_mbn

CACHE_NAME = "jp-live-patch-cache"
MAX_SAMPLES = 300


def dds_header(data: bytes) -> dict[str, object]:
    if len(data) < 128 or data[:4] != b"DDS ":
        raise ValueError("not-dds")
    size = struct.unpack_from("<I", data, 4)[0]
    if size != 124:
        raise ValueError("unsupported-dds-header")
    height = struct.unpack_from("<I", data, 12)[0]
    width = struct.unpack_from("<I", data, 16)[0]
    pf_size = struct.unpack_from("<I", data, 76)[0]
    if pf_size != 32:
        raise ValueError("unsupported-dds-pixel-format")
    fourcc = data[84:88]
    dx10 = None
    if fourcc == b"DX10":
        if len(data) < 148:
            raise ValueError("truncated-dds-dx10")
        dxgi_format = struct.unpack_from("<I", data, 128)[0]
        resource_dimension = struct.unpack_from("<I", data, 132)[0]
        array_size = struct.unpack_from("<I", data, 140)[0]
        dx10 = {
            "dxgi_format": dxgi_format,
            "resource_dimension": resource_dimension,
            "array_size": array_size,
        }
    return {
        "width": width,
        "height": height,
        "fourcc": fourcc.decode("latin-1"),
        "dx10": dx10,
    }


def inspect(anchor: Path) -> dict[str, object]:
    root = anchor.resolve().parent / CACHE_NAME / "map"
    if not root.is_dir():
        raise ValueError("live map cache not found")

    base_packages = {
        path.stem: path
        for path in root.glob("*.mbn")
        if not path.stem.endswith("__ans")
    }
    ans_packages = {
        path.stem[:-5]: path
        for path in root.glob("*__ans.mbn")
    }

    pairs = []
    missing_ans = []
    errors = []
    map_equal = 0
    atlas_dimension_match = 0
    astc_blocks = Counter()
    dds_formats = Counter()

    for map_id, base_path in sorted(base_packages.items()):
        ans_path = ans_packages.get(map_id)
        if ans_path is None:
            missing_ans.append(map_id)
            continue

        try:
            base_entries = parse_mbn(base_path.read_bytes())
            ans_entries = parse_mbn(ans_path.read_bytes())
            map_name = map_id + ".map"
            chip_astc_name = map_id + "_CHIP.astc"
            obj_astc_name = map_id + "_OBJ.astc"
            chip_dds_name = map_id + "_CHIP.dds"
            obj_dds_name = map_id + "_OBJ.dds"
            required = (
                (base_entries, map_name),
                (base_entries, chip_astc_name),
                (base_entries, obj_astc_name),
                (ans_entries, map_name),
                (ans_entries, chip_dds_name),
                (ans_entries, obj_dds_name),
            )
            if not all(name in entries for entries, name in required):
                raise ValueError("missing-expected-entry")

            base_map = gzip.decompress(base_entries[map_name])
            ans_map = gzip.decompress(ans_entries[map_name])
            same_map = base_map == ans_map
            if same_map:
                map_equal += 1

            chip_astc = parse_astc_header(base_entries[chip_astc_name])
            obj_astc = parse_astc_header(base_entries[obj_astc_name])
            chip_dds = dds_header(ans_entries[chip_dds_name])
            obj_dds = dds_header(ans_entries[obj_dds_name])

            chip_dims_match = (chip_astc.width, chip_astc.height) == (chip_dds["width"], chip_dds["height"])
            obj_dims_match = (obj_astc.width, obj_astc.height) == (obj_dds["width"], obj_dds["height"])
            if chip_dims_match and obj_dims_match:
                atlas_dimension_match += 1

            astc_blocks.update([
                f"{chip_astc.block_x}x{chip_astc.block_y}x{chip_astc.block_z}",
                f"{obj_astc.block_x}x{obj_astc.block_y}x{obj_astc.block_z}",
            ])
            dds_formats.update([
                f"{chip_dds['fourcc']}:{(chip_dds['dx10'] or {}).get('dxgi_format')}",
                f"{obj_dds['fourcc']}:{(obj_dds['dx10'] or {}).get('dxgi_format')}",
            ])

            if len(pairs) < MAX_SAMPLES:
                pairs.append({
                    "map_id": map_id,
                    "map_payload_equal": same_map,
                    "map_sha256": hashlib.sha256(base_map).hexdigest(),
                    "chip": {
                        "astc": {
                            "width": chip_astc.width,
                            "height": chip_astc.height,
                            "block": [chip_astc.block_x, chip_astc.block_y, chip_astc.block_z],
                        },
                        "dds": chip_dds,
                        "dimension_match": chip_dims_match,
                    },
                    "obj": {
                        "astc": {
                            "width": obj_astc.width,
                            "height": obj_astc.height,
                            "block": [obj_astc.block_x, obj_astc.block_y, obj_astc.block_z],
                        },
                        "dds": obj_dds,
                        "dimension_match": obj_dims_match,
                    },
                })
        except Exception as exc:
            errors.append({"map_id": map_id, "reason": type(exc).__name__ + ":" + str(exc)})

    paired_count = len(set(base_packages) & set(ans_packages))
    return {
        "provenance": "PUBLIC_LIVE_JP_MAP_VARIANT_METADATA",
        "policy": (
            "Hashes, compressed texture headers and dimensions only. Matching map "
            "payloads/dimensions prove package correspondence, not pixel identity, "
            "sampling color space, shader behavior or tutorial selection."
        ),
        "base_package_count": len(base_packages),
        "ans_package_count": len(ans_packages),
        "paired_package_count": paired_count,
        "map_payload_equal_count": map_equal,
        "atlas_dimension_match_count": atlas_dimension_match,
        "astc_block_distribution": dict(astc_blocks.most_common()),
        "dds_format_distribution": dict(dds_formats.most_common()),
        "missing_ans_count": len(missing_ans),
        "missing_ans_samples": missing_ans[:100],
        "pair_samples": pairs,
        "errors": errors[:200],
    }


def make_astc(width: int, height: int) -> bytes:
    return (
        bytes.fromhex("13aba15c")
        + bytes([6, 6, 1])
        + width.to_bytes(3, "little")
        + height.to_bytes(3, "little")
        + (1).to_bytes(3, "little")
        + bytes(((width + 5) // 6) * ((height + 5) // 6) * 16)
    )


def make_dds(width: int, height: int, fourcc: bytes = b"DXT5") -> bytes:
    data = bytearray(128)
    data[:4] = b"DDS "
    struct.pack_into("<I", data, 4, 124)
    struct.pack_into("<I", data, 12, height)
    struct.pack_into("<I", data, 16, width)
    struct.pack_into("<I", data, 76, 32)
    data[84:88] = fourcc
    return bytes(data)


def make_multi(entries: dict[str, bytes]) -> bytes:
    import zlib
    manifest = []
    body = bytearray()
    for name, content in entries.items():
        stored = zlib.compress(content)
        manifest.append({
            "name": name,
            "size": len(stored),
            "offset": len(body),
            "compresstype": 1,
            "dst_size": len(content),
        })
        body.extend(stored)
    raw = json.dumps(manifest, separators=(",", ":")).encode()
    return struct.pack("<II", 0, len(raw)) + raw + body


def self_test() -> None:
    import zlib
    map_id = "001_000_00001"
    raw_map = b"map-protobuf"
    gz_map = gzip.compress(raw_map)
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        anchor = root / "private.zip"
        anchor.write_bytes(b"x")
        maps = root / CACHE_NAME / "map"
        maps.mkdir(parents=True)
        (maps / f"{map_id}.mbn").write_bytes(make_multi({
            f"{map_id}.map": gz_map,
            f"{map_id}_CHIP.astc": make_astc(720, 1280),
            f"{map_id}_OBJ.astc": make_astc(512, 512),
        }))
        (maps / f"{map_id}__ans.mbn").write_bytes(make_multi({
            f"{map_id}.map": gz_map,
            f"{map_id}_CHIP.dds": make_dds(720, 1280),
            f"{map_id}_OBJ.dds": make_dds(512, 512),
        }))
        result = inspect(anchor)
        if result["paired_package_count"] != 1:
            raise AssertionError("pair not found")
        if result["map_payload_equal_count"] != 1:
            raise AssertionError("map payload pair mismatch")
        if result["atlas_dimension_match_count"] != 1:
            raise AssertionError("atlas dimensions mismatch")
    print("Logres live map variant inspector self-test: PASS")


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
