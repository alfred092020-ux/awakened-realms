#!/usr/bin/env python3
"""Hydrate a narrow set of recovered Global Logres tutorial HUD assets.

Original client bytes are read from the owner's private recovered cache archive.
Only PNG derivatives and metadata are written to the gitignored runtime tree.
No tutorial map identity is selected by this tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import struct
import subprocess
import sys
import tempfile
from zipfile import ZipFile

from hydrate_global_renderer_candidate import decode_astc
from hydrate_private_assets import parse_astc_header, parse_mbn

DEFAULT_OUTPUT_ROOT = Path("public/__logres_ref/global/tutorial-hud")

PACKAGE_ASSETS: dict[str, tuple[str, ...]] = {
    "files/cache/patch/gui/HUD.mbn": (
        "field_underbar.dds",
        "field_parameter.dds",
        "field_parameter02.astc",
        "field_parameter_icon.png",
        "field_chatbutton.dds",
        "field_menu.dds",
        "field_menu_cover.dds",
        "field_telop.dds",
        "field_chatparts02.dds",
        "field_chatparts02on.dds",
        "field_chatparts02_yajirushi.dds",
    ),
    "files/cache/patch/motion/telop/png.mbn": (
        "quest_start.dds",
        "quest_start_w00.dds",
        "quest_start_w01.dds",
        "quest_bg00.dds",
        "quest_bg00a.dds",
        "quest_bg00b.dds",
        "quest_bg00c.dds",
    ),
}

PACKAGE_DIRS = {
    "files/cache/patch/gui/HUD.mbn": "hud",
    "files/cache/patch/motion/telop/png.mbn": "telop",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_output_name(name: str) -> str:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
        raise ValueError(f"unsafe tutorial HUD entry name: {name}")
    stem = Path(name).stem
    if not stem:
        raise ValueError(f"invalid tutorial HUD entry name: {name}")
    return stem + ".png"


def parse_dds_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 128 or data[:4] != b"DDS ":
        raise ValueError("DDS payload is missing its fixed header")
    height = struct.unpack_from("<I", data, 12)[0]
    width = struct.unpack_from("<I", data, 16)[0]
    if width <= 0 or height <= 0:
        raise ValueError("DDS payload has zero-sized dimensions")
    return width, height


def parse_png_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("PNG payload is missing a valid signature")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if width <= 0 or height <= 0:
        raise ValueError("PNG payload has zero-sized dimensions")
    return width, height


def decode_dds(data: bytes, output: Path, *, converter: str) -> None:
    executable = shutil.which(converter)
    if executable is None:
        raise ValueError(f"DDS converter not found: {converter}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="logres-global-hud-dds-") as temp:
        source = Path(temp) / "source.dds"
        source.write_bytes(data)
        completed = subprocess.run(
            [executable, str(source), str(output)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    if completed.returncode != 0 or not output.is_file():
        detail = completed.stdout.strip()
        raise ValueError(
            f"DDS decode failed with exit {completed.returncode}: {detail}"
        )


def hydrate(
    archive: Path,
    output_root: Path,
    *,
    astc_profile: str,
    astcenc: str,
    dds_converter: str,
) -> dict[str, object]:
    output_root.mkdir(parents=True, exist_ok=True)
    products: list[dict[str, object]] = []

    with ZipFile(archive) as source:
        for member, wanted in PACKAGE_ASSETS.items():
            try:
                package = source.read(member)
            except KeyError as exc:
                raise ValueError(
                    f"Global archive does not contain required HUD package {member}"
                ) from exc

            entries = parse_mbn(package)
            package_dir = PACKAGE_DIRS[member]

            for entry_name in wanted:
                try:
                    payload = entries[entry_name]
                except KeyError as exc:
                    raise ValueError(
                        f"HUD package {member} is missing required entry {entry_name}"
                    ) from exc

                output_name = safe_output_name(entry_name)
                destination = output_root / package_dir / output_name
                source_format = Path(entry_name).suffix.lower().lstrip(".")

                if source_format == "dds":
                    width, height = parse_dds_dimensions(payload)
                    decode_dds(
                        payload,
                        destination,
                        converter=dds_converter,
                    )
                    decode_policy = "ImageMagick DDS decode to private PNG"
                elif source_format == "astc":
                    header = parse_astc_header(payload)
                    width, height = header.width, header.height
                    decode_astc(
                        payload,
                        destination,
                        profile=astc_profile,
                        astcenc=astcenc,
                    )
                    decode_policy = (
                        f"astcenc {astc_profile} decode to private PNG; "
                        "original runtime color-space sampling remains UNRESOLVED"
                    )
                elif source_format == "png":
                    width, height = parse_png_dimensions(payload)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(payload)
                    decode_policy = "lossless original PNG copy into private runtime"
                else:
                    raise ValueError(
                        f"unsupported tutorial HUD source format: {entry_name}"
                    )

                if not destination.is_file() or destination.stat().st_size <= 0:
                    raise ValueError(f"tutorial HUD output was not created: {destination}")

                products.append(
                    {
                        "source_member": member,
                        "entry": entry_name,
                        "source_format": source_format.upper(),
                        "source_sha256": sha256(payload),
                        "width": width,
                        "height": height,
                        "relative_file": str(
                            Path(package_dir) / output_name
                        ).replace("\\", "/"),
                        "decode_policy": decode_policy,
                    }
                )

    metadata = {
        "provenance": "RECOVERED_GLOBAL_CACHE_PRIVATE_DERIVATIVE",
        "evidence_classification": "CONFIRMED ORIGINAL SOURCE BYTES",
        "role": "TUTORIAL_HUD_ASSET_CANDIDATES",
        "map_identity": "UNRESOLVED",
        "design_reference": {
            "width": 720,
            "height": 1280,
            "source": "Recovered Global MainHUD.lua / field_hud_footer.lua layout coordinates",
        },
        "products": products,
    }

    metadata_path = output_root / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return metadata


def self_test() -> None:
    if len({name for names in PACKAGE_ASSETS.values() for name in names}) != sum(
        len(names) for names in PACKAGE_ASSETS.values()
    ):
        raise AssertionError("tutorial HUD asset list contains duplicate entry names")

    for member, entries in PACKAGE_ASSETS.items():
        if member not in PACKAGE_DIRS:
            raise AssertionError("tutorial HUD package is missing an output directory")
        for name in entries:
            safe_output_name(name)

    dds = bytearray(128)
    dds[:4] = b"DDS "
    struct.pack_into("<I", dds, 12, 66)
    struct.pack_into("<I", dds, 16, 410)
    if parse_dds_dimensions(bytes(dds)) != (410, 66):
        raise AssertionError("synthetic DDS dimension parse failed")

    png = (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\x0dIHDR"
        + (28).to_bytes(4, "big")
        + (36).to_bytes(4, "big")
    )
    if parse_png_dimensions(png) != (28, 36):
        raise AssertionError("synthetic PNG dimension parse failed")

    try:
        safe_output_name("../secret.dds")
    except ValueError:
        pass
    else:
        raise AssertionError("unsafe HUD entry path was accepted")

    print("Logres Global tutorial HUD hydrator self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", nargs="?", type=Path)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--profile", choices=("linear", "srgb"), default="linear")
    parser.add_argument("--astcenc", default="astcenc")
    parser.add_argument("--dds-converter", default="convert")
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
            args.output_root,
            astc_profile=args.profile,
            astcenc=args.astcenc,
            dds_converter=args.dds_converter,
        )
    except (OSError, ValueError) as exc:
        print(f"Global tutorial HUD hydration failed: {exc}", file=sys.stderr)
        return 1

    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(encoded, encoding="utf-8")
    else:
        sys.stdout.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
