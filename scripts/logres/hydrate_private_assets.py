#!/usr/bin/env python3
"""Hydrate private Logres runtime assets from the owner's recovered cache archive.

This tool intentionally writes only to gitignored private/runtime paths. It does not
put original Logres binaries into the public repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from zipfile import ZipFile

ASTC_MAGIC = 0x5CA1AB13
KTX_IDENTIFIER = b"\xABKTX 11\xBB\r\n\x1A\n"
KTX_ENDIANNESS = 0x04030201
GL_RGBA = 0x1908
GL_COMPRESSED_RGBA_ASTC_6X6_KHR = 0x93B4
GL_COMPRESSED_SRGB8_ALPHA8_ASTC_6X6_KHR = 0x93D4

DEFAULT_MBN_MEMBER = "files/cache/patch/map/background/mbg_002_001.mbn"
DEFAULT_ASTC_ENTRY = "mbg_002_001.astc"
DEFAULT_OUTPUT_DIR = Path(
    "public/__logres_ref/japanese/map/background/mbg_002_001"
)
EXPECTED_ASTC_SHA256 = (
    "74b9111b485d124722c5c3d6f4ff9cb5e95b95438fb25a31eff4cf4d63c74482"
)


@dataclass(frozen=True)
class AstcHeader:
    block_x: int
    block_y: int
    block_z: int
    width: int
    height: int
    depth: int


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _u24(data: bytes) -> int:
    if len(data) != 3:
        raise ValueError("u24 requires exactly three bytes")
    return data[0] | (data[1] << 8) | (data[2] << 16)


def parse_astc_header(data: bytes) -> AstcHeader:
    if len(data) < 16:
        raise ValueError("ASTC payload is shorter than its 16-byte header")

    magic = struct.unpack_from("<I", data, 0)[0]
    if magic != ASTC_MAGIC:
        raise ValueError(f"Unexpected ASTC magic 0x{magic:08x}")

    header = AstcHeader(
        block_x=data[4],
        block_y=data[5],
        block_z=data[6],
        width=_u24(data[7:10]),
        height=_u24(data[10:13]),
        depth=_u24(data[13:16]),
    )

    if min(
        header.block_x,
        header.block_y,
        header.block_z,
        header.width,
        header.height,
        header.depth,
    ) <= 0:
        raise ValueError("ASTC header contains a zero-sized dimension")

    blocks_x = (header.width + header.block_x - 1) // header.block_x
    blocks_y = (header.height + header.block_y - 1) // header.block_y
    blocks_z = (header.depth + header.block_z - 1) // header.block_z
    expected_size = 16 + blocks_x * blocks_y * blocks_z * 16

    if len(data) != expected_size:
        raise ValueError(
            f"ASTC byte length mismatch: expected {expected_size}, got {len(data)}"
        )

    return header


def parse_mbn(data: bytes) -> dict[str, bytes]:
    if len(data) < 8:
        raise ValueError("MBN is shorter than its fixed header")

    reserved, manifest_size = struct.unpack_from("<II", data, 0)
    if reserved != 0:
        raise ValueError(f"Unexpected MBN reserved value {reserved}")

    manifest_end = 8 + manifest_size
    if manifest_end > len(data):
        raise ValueError("MBN manifest extends past end of file")

    try:
        manifest = json.loads(data[8:manifest_end].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("MBN manifest is not valid UTF-8 JSON") from exc

    if not isinstance(manifest, list):
        raise ValueError("MBN manifest root must be an array")

    payload = data[manifest_end:]
    extracted: dict[str, bytes] = {}

    for record in manifest:
        if not isinstance(record, dict):
            raise ValueError("MBN manifest contains a non-object record")

        name = record.get("name")
        size = record.get("size")
        offset = record.get("offset")
        compression = record.get("compresstype", 0)
        destination_size = record.get("dst_size")

        if not isinstance(name, str) or not name:
            raise ValueError("MBN record is missing a valid name")
        if not isinstance(size, int) or size < 0:
            raise ValueError(f"MBN record {name!r} has an invalid size")
        if not isinstance(offset, int) or offset < 0:
            raise ValueError(f"MBN record {name!r} has an invalid offset")
        if offset + size > len(payload):
            raise ValueError(f"MBN record {name!r} extends past payload")

        stored = payload[offset : offset + size]
        if compression == 0:
            unpacked = stored
        elif compression == 1:
            try:
                unpacked = zlib.decompress(stored)
            except zlib.error as exc:
                raise ValueError(
                    f"MBN record {name!r} failed zlib decompression"
                ) from exc
        else:
            raise ValueError(
                f"MBN record {name!r} uses unsupported compression type {compression}"
            )

        if destination_size is not None:
            if not isinstance(destination_size, int) or destination_size < 0:
                raise ValueError(f"MBN record {name!r} has an invalid dst_size")
            if len(unpacked) != destination_size:
                raise ValueError(
                    f"MBN record {name!r} size mismatch: "
                    f"expected {destination_size}, got {len(unpacked)}"
                )

        if name in extracted:
            raise ValueError(f"Duplicate MBN record name {name!r}")
        extracted[name] = unpacked

    return extracted


def wrap_astc_as_ktx1(astc: bytes, profile: str) -> bytes:
    header = parse_astc_header(astc)
    if (header.block_x, header.block_y, header.block_z) != (6, 6, 1):
        raise ValueError(
            "KTX wrapper currently permits only the recovered 6x6x1 ASTC layout"
        )

    if profile == "linear":
        internal_format = GL_COMPRESSED_RGBA_ASTC_6X6_KHR
    elif profile == "srgb":
        internal_format = GL_COMPRESSED_SRGB8_ALPHA8_ASTC_6X6_KHR
    else:
        raise ValueError("KTX profile must be either 'linear' or 'srgb'")

    compressed_blocks = astc[16:]
    ktx_header = KTX_IDENTIFIER + struct.pack(
        "<13I",
        KTX_ENDIANNESS,
        0,
        1,
        0,
        internal_format,
        GL_RGBA,
        header.width,
        header.height,
        0,
        0,
        1,
        1,
        0,
    )

    return ktx_header + struct.pack("<I", len(compressed_blocks)) + compressed_blocks


def hydrate(
    archive: Path,
    output_dir: Path,
    profiles: Iterable[str],
) -> dict[str, object]:
    with ZipFile(archive) as source_zip:
        try:
            mbn = source_zip.read(DEFAULT_MBN_MEMBER)
        except KeyError as exc:
            raise ValueError(
                f"Archive does not contain required member {DEFAULT_MBN_MEMBER!r}"
            ) from exc

    entries = parse_mbn(mbn)
    try:
        astc = entries[DEFAULT_ASTC_ENTRY]
    except KeyError as exc:
        raise ValueError(
            f"Recovered MBN does not contain {DEFAULT_ASTC_ENTRY!r}"
        ) from exc

    header = parse_astc_header(astc)
    if (header.width, header.height, header.depth) != (720, 1280, 1):
        raise ValueError(
            "Recovered default field background dimensions changed: "
            f"{header.width}x{header.height}x{header.depth}"
        )

    actual_hash = sha256(astc)
    if actual_hash != EXPECTED_ASTC_SHA256:
        raise ValueError(
            "Recovered default field ASTC hash differs from inspected evidence: "
            f"{actual_hash}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    astc_path = output_dir / DEFAULT_ASTC_ENTRY
    astc_path.write_bytes(astc)

    products: dict[str, object] = {
        "source": DEFAULT_MBN_MEMBER,
        "entry": DEFAULT_ASTC_ENTRY,
        "astc": {
            "path": str(astc_path),
            "sha256": actual_hash,
            "width": header.width,
            "height": header.height,
            "block": [header.block_x, header.block_y, header.block_z],
        },
        "ktx": {},
    }

    for profile in profiles:
        ktx = wrap_astc_as_ktx1(astc, profile)
        ktx_path = output_dir / f"mbg_002_001.{profile}.ktx"
        ktx_path.write_bytes(ktx)
        products["ktx"][profile] = {
            "path": str(ktx_path),
            "sha256": sha256(ktx),
        }

    return products


def _make_synthetic_astc(width: int = 12, height: int = 12) -> bytes:
    header = (
        struct.pack("<I", ASTC_MAGIC)
        + bytes((6, 6, 1))
        + width.to_bytes(3, "little")
        + height.to_bytes(3, "little")
        + (1).to_bytes(3, "little")
    )
    blocks = ((width + 5) // 6) * ((height + 5) // 6)
    return header + bytes((index % 251 for index in range(blocks * 16)))


def _make_synthetic_mbn(name: str, content: bytes) -> bytes:
    stored = zlib.compress(content)
    manifest = json.dumps(
        [
            {
                "name": name,
                "size": len(stored),
                "offset": 0,
                "compresstype": 1,
                "dst_size": len(content),
            }
        ],
        separators=(",", ":"),
    ).encode("utf-8")
    return struct.pack("<II", 0, len(manifest)) + manifest + stored


def self_test() -> None:
    astc = _make_synthetic_astc()
    parsed = parse_mbn(_make_synthetic_mbn(DEFAULT_ASTC_ENTRY, astc))
    if parsed[DEFAULT_ASTC_ENTRY] != astc:
        raise AssertionError("Synthetic MBN round-trip failed")

    header = parse_astc_header(astc)
    if (header.width, header.height, header.block_x, header.block_y) != (
        12,
        12,
        6,
        6,
    ):
        raise AssertionError("Synthetic ASTC header parse failed")

    for profile, expected_format in (
        ("linear", GL_COMPRESSED_RGBA_ASTC_6X6_KHR),
        ("srgb", GL_COMPRESSED_SRGB8_ALPHA8_ASTC_6X6_KHR),
    ):
        ktx = wrap_astc_as_ktx1(astc, profile)
        if not ktx.startswith(KTX_IDENTIFIER):
            raise AssertionError("KTX identifier mismatch")
        internal_format = struct.unpack_from("<I", ktx, 28)[0]
        if internal_format != expected_format:
            raise AssertionError(f"KTX internal format mismatch for {profile}")
        image_size = struct.unpack_from("<I", ktx, 64)[0]
        if image_size != len(astc) - 16:
            raise AssertionError("KTX imageSize mismatch")
        if ktx[68:] != astc[16:]:
            raise AssertionError("KTX wrapper altered ASTC compressed blocks")

    print("Logres private asset hydrator self-test: PASS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Recover the original default Logres field ASTC from the owner's "
            "split-cache archive and create lossless KTX wrappers."
        )
    )
    parser.add_argument(
        "archive",
        nargs="?",
        type=Path,
        help="joined cache ZIP, for example /mnt/data/files.joined.zip",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="gitignored private runtime destination",
    )
    parser.add_argument(
        "--ktx-profile",
        choices=("linear", "srgb", "both", "none"),
        default="both",
        help=(
            "KTX color interpretation. 'both' preserves both explicit variants "
            "until original-client color-space evidence selects one."
        ),
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run parser/wrapper tests using synthetic non-proprietary data",
    )
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

    if args.ktx_profile == "both":
        profiles = ("linear", "srgb")
    elif args.ktx_profile == "none":
        profiles = ()
    else:
        profiles = (args.ktx_profile,)

    try:
        products = hydrate(args.archive, args.output_dir, profiles)
    except (OSError, ValueError) as exc:
        print(f"Logres private asset hydration failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(products, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
