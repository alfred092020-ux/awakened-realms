#!/usr/bin/env python3
"""Hydrate one recovered Global Logres map candidate for private runtime diagnostics.

All outputs are private derivatives under a gitignored runtime tree. The script
never selects a tutorial map by itself and never changes gameplay flow.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile

from hydrate_private_assets import parse_astc_header, parse_mbn

MAP_ID = re.compile(r"^\d{3}_\d{3}_\d{5}$")
DEFAULT_MAP_ID = "002_000_00001"
DEFAULT_OUTPUT_ROOT = Path("public/__logres_ref/renderer-proof")
MAP_INFO_MEMBER = "files/cache/patch/map/info.mbn"

INFO_ENTRIES = (
    "chip_d.bin",
    "chip_r.bin",
    "object_d.bin",
    "object_r.bin",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_map_id(map_id: str) -> str:
    if not MAP_ID.fullmatch(map_id):
        raise ValueError(f"invalid Logres map id: {map_id}")
    return map_id


def decode_astc(
    astc: bytes,
    output: Path,
    *,
    profile: str,
    astcenc: str,
) -> None:
    mode = {
        "linear": "-dl",
        "srgb": "-ds",
    }.get(profile)
    if mode is None:
        raise ValueError("ASTC decode profile must be linear or srgb")

    executable = shutil.which(astcenc)
    if executable is None:
        raise ValueError(f"ASTC decoder not found: {astcenc}")

    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="logres-global-astc-") as temp:
        source = Path(temp) / "source.astc"
        source.write_bytes(astc)
        completed = subprocess.run(
            [executable, mode, str(source), str(output)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        if completed.returncode != 0 or not output.is_file():
            detail = completed.stdout.strip()
            raise ValueError(
                f"ASTC decode failed with exit {completed.returncode}: {detail}"
            )


def hydrate(
    archive: Path,
    map_id: str,
    output_root: Path,
    *,
    profile: str,
    astcenc: str,
) -> dict[str, object]:
    map_id = require_map_id(map_id)
    map_member = f"files/cache/patch/map/{map_id}.mbn"

    with ZipFile(archive) as source:
        try:
            map_mbn = source.read(map_member)
        except KeyError as exc:
            raise ValueError(
                f"Global archive does not contain {map_member}"
            ) from exc
        try:
            info_mbn = source.read(MAP_INFO_MEMBER)
        except KeyError as exc:
            raise ValueError(
                f"Global archive does not contain {MAP_INFO_MEMBER}"
            ) from exc

    map_entries = parse_mbn(map_mbn)
    info_entries = parse_mbn(info_mbn)

    map_name = f"{map_id}.map"
    chip_name = f"{map_id}_CHIP.astc"
    obj_name = f"{map_id}_OBJ.astc"

    for name in (map_name, chip_name, obj_name):
        if name not in map_entries:
            raise ValueError(f"Global map package is missing {name}")

    for name in INFO_ENTRIES:
        if name not in info_entries:
            raise ValueError(f"Global map-info package is missing {name}")

    try:
        map_payload = gzip.decompress(map_entries[map_name])
    except (OSError, EOFError) as exc:
        raise ValueError("Global map payload is not valid gzip") from exc

    chip_astc = map_entries[chip_name]
    obj_astc = map_entries[obj_name]
    chip_header = parse_astc_header(chip_astc)
    obj_header = parse_astc_header(obj_astc)

    target = output_root / map_id
    target.mkdir(parents=True, exist_ok=True)

    map_file = target / f"{map_id}.map.bin"
    chip_file = target / f"{map_id}_CHIP.png"
    obj_file = target / f"{map_id}_OBJ.png"

    map_file.write_bytes(map_payload)

    decode_astc(
        chip_astc,
        chip_file,
        profile=profile,
        astcenc=astcenc,
    )
    decode_astc(
        obj_astc,
        obj_file,
        profile=profile,
        astcenc=astcenc,
    )

    info_products: dict[str, object] = {}
    for name in INFO_ENTRIES:
        data = info_entries[name]
        destination = target / name
        destination.write_bytes(data)
        info_products[name] = {
            "bytes": len(data),
            "sha256": sha256(data),
            "relative_file": destination.name,
        }

    metadata = {
        "provenance": "RECOVERED_GLOBAL_CACHE_PRIVATE_DERIVATIVE",
        "evidence_classification": "CONFIRMED ORIGINAL SOURCE_BYTES",
        "role": "CANDIDATE_NOT_IDENTIFIED_TUTORIAL",
        "map_id": map_id,
        "source_members": [
            map_member,
            MAP_INFO_MEMBER,
        ],
        "map": {
            "bytes": len(map_payload),
            "sha256": sha256(map_payload),
            "relative_file": map_file.name,
        },
        "chip": {
            "source_format": "ASTC",
            "source_sha256": sha256(chip_astc),
            "width": chip_header.width,
            "height": chip_header.height,
            "block": [
                chip_header.block_x,
                chip_header.block_y,
                chip_header.block_z,
            ],
            "decode_profile": profile,
            "relative_file": chip_file.name,
        },
        "obj": {
            "source_format": "ASTC",
            "source_sha256": sha256(obj_astc),
            "width": obj_header.width,
            "height": obj_header.height,
            "block": [
                obj_header.block_x,
                obj_header.block_y,
                obj_header.block_z,
            ],
            "decode_profile": profile,
            "relative_file": obj_file.name,
        },
        "map_info": info_products,
        "color_policy": (
            "ASTC source blocks are preserved by hash. PNG is a private "
            f"{profile} diagnostic decode via astcenc. Original runtime "
            "linear/sRGB sampling remains UNRESOLVED."
        ),
    }

    metadata_file = target / "metadata.json"
    metadata_file.write_text(
        json.dumps(
            metadata,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return metadata


def self_test() -> None:
    assert require_map_id("002_000_00001") == "002_000_00001"
    for bad in (
        "../private",
        "2_0_1",
        "002_000_00001/",
        "002_000_0000x",
    ):
        try:
            require_map_id(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted invalid map id: {bad}")

    # Profile dispatch is tested without proprietary input.
    try:
        decode_astc(
            b"",
            Path("/tmp/logres-never-written.png"),
            profile="unknown",
            astcenc="astcenc",
        )
    except ValueError as exc:
        assert "profile" in str(exc)
    else:
        raise AssertionError("accepted invalid ASTC profile")

    print("Logres Global candidate hydrator self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", nargs="?", type=Path)
    parser.add_argument("--map-id", default=DEFAULT_MAP_ID)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
    )
    parser.add_argument(
        "--profile",
        choices=("linear", "srgb"),
        default="linear",
    )
    parser.add_argument(
        "--astcenc",
        default="astcenc",
    )
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

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
        result = hydrate(
            args.archive,
            args.map_id,
            args.output_root,
            profile=args.profile,
            astcenc=args.astcenc,
        )
    except (
        OSError,
        ValueError,
    ) as exc:
        print(
            f"Global candidate hydration failed: {exc}",
            file=sys.stderr,
        )
        return 1

    encoded = (
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    if args.summary:
        args.summary.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        args.summary.write_text(
            encoded,
            encoding="utf-8",
        )
    else:
        sys.stdout.write(
            encoded,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
