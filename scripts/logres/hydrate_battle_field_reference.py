#!/usr/bin/env python3
"""Hydrate one evidence-bounded Logres battle-field reference from live JP cache."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

from PIL import Image

SOURCE_RELATIVE = Path("battle/field/bfd_002_001__ans.mbn")
SOURCE_SHA256 = "f8727a721eee46effe16036a2bcfabb4a9cc178dc1b119f65933b0efc365a6b8"
ENTRY_NAME = "bfd_002_001.dds"
ENTRY_SHA256 = "cc34e618235b49e77431079f2a8cace73936c87a4abaabf04fbd2bbab1f80f62"
OUTPUT_RELATIVE = Path("current-jp/battle-field/bfd_002_001.png")
EXPECTED_SIZE = (720, 1280)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_single_entry_mbn(data: bytes) -> tuple[str, bytes]:
    if len(data) < 8:
        raise ValueError("MBN is shorter than its fixed header")

    reserved, manifest_size = struct.unpack_from("<II", data, 0)
    if reserved != 0:
        raise ValueError(f"Unexpected MBN reserved value {reserved}")
    manifest_end = 8 + manifest_size
    if manifest_end > len(data):
        raise ValueError("MBN manifest extends past end of file")

    manifest = json.loads(data[8:manifest_end].decode("utf-8"))
    if not isinstance(manifest, list) or len(manifest) != 1:
        raise ValueError("Expected a single-entry battle-field MBN")

    record = manifest[0]
    name = record.get("name")
    size = record.get("size")
    offset = record.get("offset")
    compression = record.get("compresstype", 0)
    destination_size = record.get("dst_size")

    if not isinstance(name, str) or not isinstance(size, int) or not isinstance(offset, int):
        raise ValueError("Battle-field MBN record is malformed")

    stored = data[manifest_end + offset : manifest_end + offset + size]
    if compression == 0:
        unpacked = stored
    elif compression == 1:
        unpacked = zlib.decompress(stored)
    else:
        raise ValueError(f"Unsupported MBN compression type {compression}")

    if destination_size is not None and len(unpacked) != destination_size:
        raise ValueError("Battle-field payload size mismatch")

    return name, unpacked
def hydrate(cache_root: Path, public_root: Path) -> dict[str, object]:
    source = cache_root / SOURCE_RELATIVE
    source_bytes = source.read_bytes()

    if sha256(source_bytes) != SOURCE_SHA256:
        raise ValueError("Recovered bfd_002_001 package hash changed")

    entry_name, dds = parse_single_entry_mbn(source_bytes)
    if entry_name != ENTRY_NAME:
        raise ValueError(f"Unexpected battle-field entry {entry_name!r}")
    if sha256(dds) != ENTRY_SHA256:
        raise ValueError("Recovered bfd_002_001 DDS hash changed")

    output = public_root / OUTPUT_RELATIVE
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_dds = output.with_suffix(".dds.tmp")
    temporary_dds.write_bytes(dds)

    try:
        with Image.open(temporary_dds) as image:
            if image.size != EXPECTED_SIZE:
                raise ValueError(f"Unexpected battle-field dimensions {image.size}")
            image.convert("RGBA").save(output, format="PNG", optimize=True)
    finally:
        temporary_dds.unlink(missing_ok=True)

    return {
        "source": str(source),
        "source_sha256": SOURCE_SHA256,
        "entry": ENTRY_NAME,
        "entry_sha256": ENTRY_SHA256,
        "output": str(output),
        "output_sha256": sha256(output.read_bytes()),
        "dimensions": list(EXPECTED_SIZE),
        "provenance": {
            "resource_family": "CONFIRMED_GLOBAL_BOUTBG_BFD_PATTERN",
            "asset_bytes": "CONFIRMED_CURRENT_JP_RESOURCE",
            "tutorial_candidate": "SUPPORTED_INFERENCE_CURRENT_JP_BFD_002_001",
            "historical_global_tutorial_bfd_id": "UNRESOLVED",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=Path("/home/ubuntu/logres/private/jp-live-patch-cache"),
    )
    parser.add_argument(
        "--public-root",
        type=Path,
        default=Path("public/__logres_ref"),
    )
    args = parser.parse_args()

    try:
        result = hydrate(args.cache_root, args.public_root)
    except (OSError, ValueError, json.JSONDecodeError, zlib.error) as exc:
        print(f"battle-field hydration failed: {exc}")
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
