#!/usr/bin/env python3
"""Hydrate narrow current-JP tutorial-field visual references.

This tool intentionally does not claim historical Global resource identity.
It extracts:
- the current-JP tutorial tap-hand artwork, whose behavior is independently
  visible in Global launch footage;
- the current-JP base green-jelly field idle frames used as a visual candidate
  for the Global tutorial Green Jell.

Outputs remain under the gitignored private runtime tree.
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

from hydrate_private_assets import parse_mbn

DEFAULT_OUTPUT_ROOT = Path(
    "public/__logres_ref/current-jp/tutorial-field"
)

TUTORIAL_PACKAGE = Path(
    "gui/tutorial.mbn"
)

ENEMY_MOTION_PACKAGE = Path(
    "motion/enm/enm_001_000/png.mbn"
)

POINTER_ENTRY = "tutorial_parts02.dds"

ENEMY_IDLE_ENTRIES = tuple(
    f"enm_001_000_000_wat_990_{index:03d}.png"
    for index in range(4)
)


def sha256(
    data: bytes,
) -> str:
    return hashlib.sha256(
        data,
    ).hexdigest()


def parse_dds_dimensions(
    data: bytes,
) -> tuple[int, int]:
    if (
        len(data) < 128 or
        data[:4] != b"DDS "
    ):
        raise ValueError(
            "invalid DDS payload",
        )

    height = struct.unpack_from(
        "<I",
        data,
        12,
    )[0]

    width = struct.unpack_from(
        "<I",
        data,
        16,
    )[0]

    if (
        width <= 0 or
        height <= 0
    ):
        raise ValueError(
            "invalid DDS dimensions",
        )

    return (
        width,
        height,
    )


def parse_png_dimensions(
    data: bytes,
) -> tuple[int, int]:
    if (
        len(data) < 24 or
        data[:8] !=
        b"\x89PNG\r\n\x1a\n"
    ):
        raise ValueError(
            "invalid PNG payload",
        )

    width = int.from_bytes(
        data[16:20],
        "big",
    )

    height = int.from_bytes(
        data[20:24],
        "big",
    )

    if (
        width <= 0 or
        height <= 0
    ):
        raise ValueError(
            "invalid PNG dimensions",
        )

    return (
        width,
        height,
    )


def safe_entry_name(
    name: str,
) -> str:
    path = PurePosixPath(
        name,
    )

    if (
        path.is_absolute() or
        ".." in path.parts or
        len(path.parts) != 1
    ):
        raise ValueError(
            f"unsafe MBN entry: {name}",
        )

    return name


def decode_dds(
    data: bytes,
    output: Path,
    *,
    converter: str,
) -> None:
    executable = shutil.which(
        converter,
    )

    if executable is None:
        raise ValueError(
            f"DDS converter not found: {converter}",
        )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with tempfile.TemporaryDirectory(
        prefix="logres-tutorial-pointer-",
    ) as temp:
        source = (
            Path(temp) /
            "source.dds"
        )

        source.write_bytes(
            data,
        )

        completed = subprocess.run(
            [
                executable,
                str(source),
                str(output),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )

    if (
        completed.returncode != 0 or
        not output.is_file() or
        output.stat().st_size <= 0
    ):
        raise ValueError(
            "DDS conversion failed: " +
            completed.stdout.strip(),
        )


def hydrate(
    cache_root: Path,
    output_root: Path,
    *,
    dds_converter: str,
) -> dict[str, object]:
    tutorial_path = (
        cache_root /
        TUTORIAL_PACKAGE
    )

    motion_path = (
        cache_root /
        ENEMY_MOTION_PACKAGE
    )

    if not tutorial_path.is_file():
        raise ValueError(
            f"missing tutorial package: {tutorial_path}",
        )

    if not motion_path.is_file():
        raise ValueError(
            f"missing enemy motion package: {motion_path}",
        )

    tutorial_entries = parse_mbn(
        tutorial_path.read_bytes(),
    )

    motion_entries = parse_mbn(
        motion_path.read_bytes(),
    )

    safe_entry_name(
        POINTER_ENTRY,
    )

    try:
        pointer_bytes = (
            tutorial_entries[
                POINTER_ENTRY
            ]
        )
    except KeyError as exc:
        raise ValueError(
            f"tutorial package missing {POINTER_ENTRY}",
        ) from exc

    pointer_width, pointer_height = (
        parse_dds_dimensions(
            pointer_bytes,
        )
    )

    output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    pointer_output = (
        output_root /
        "tutorial_pointer_tap.png"
    )

    decode_dds(
        pointer_bytes,
        pointer_output,
        converter=dds_converter,
    )

    products: list[
        dict[str, object]
    ] = [
        {
            "role":
                "TUTORIAL_TAP_POINTER",

            "source_package":
                str(
                    TUTORIAL_PACKAGE,
                ).replace(
                    "\\",
                    "/",
                ),

            "source_entry":
                POINTER_ENTRY,

            "source_sha256":
                sha256(
                    pointer_bytes,
                ),

            "width":
                pointer_width,

            "height":
                pointer_height,

            "relative_file":
                pointer_output.name,

            "source_classification":
                "CONFIRMED_CURRENT_JP_NATIVE_SOURCE_BYTES",

            "global_behavior_evidence":
                "CONFIRMED_GLOBAL_VIDEO_HAND_PROMPT",

            "global_artwork_application":
                "SUPPORTED_INFERENCE",
        },
    ]

    for (
        index,
        entry_name,
    ) in enumerate(
        ENEMY_IDLE_ENTRIES,
    ):
        safe_entry_name(
            entry_name,
        )

        try:
            payload = (
                motion_entries[
                    entry_name
                ]
            )
        except KeyError as exc:
            raise ValueError(
                f"enemy motion package missing {entry_name}",
            ) from exc

        width, height = (
            parse_png_dimensions(
                payload,
            )
        )

        destination = (
            output_root /
            f"green_jell_idle_{index}.png"
        )

        destination.write_bytes(
            payload,
        )

        products.append(
            {
                "role":
                    "GREEN_JELL_FIELD_IDLE_FRAME",

                "frame_index":
                    index,

                "current_jp_resource_family":
                    "enm_001_000_000",

                "source_package":
                    str(
                        ENEMY_MOTION_PACKAGE,
                    ).replace(
                        "\\",
                        "/",
                    ),

                "source_entry":
                    entry_name,

                "source_sha256":
                    sha256(
                        payload,
                    ),

                "width":
                    width,

                "height":
                    height,

                "relative_file":
                    destination.name,

                "source_classification":
                    "CONFIRMED_CURRENT_JP_NATIVE_SOURCE_BYTES",

                "global_enemy_behavior":
                    "CONFIRMED_GLOBAL_GREEN_JELL_TUTORIAL",

                "historical_global_internal_id":
                    "UNRESOLVED",

                "global_visual_application":
                    "SUPPORTED_INFERENCE",
            },
        )

    metadata = {
        "provenance":
            "CURRENT_JP_PRIVATE_RUNTIME_DERIVATIVE",

        "purpose":
            "TUTORIAL_FIELD_PRESENTATION_REFERENCE",

        "do_not_conflate":
            [
                "Current-JP enm_001_000_000 is not claimed as the historical Global 2017 enemy ID.",
                "Current-JP tutorial_parts02 artwork is not independently proven byte-identical to Global.",
                "Global footage confirms Green Jell tutorial behavior and a hand prompt, not these internal resource IDs.",
            ],

        "products":
            products,
    }

    (
        output_root /
        "metadata.json"
    ).write_text(
        json.dumps(
            metadata,
            indent=2,
            sort_keys=True,
        ) +
        "\n",
        encoding="utf-8",
    )

    return metadata


def self_test() -> None:
    dds = bytearray(
        128,
    )

    dds[:4] = b"DDS "

    struct.pack_into(
        "<I",
        dds,
        12,
        192,
    )

    struct.pack_into(
        "<I",
        dds,
        16,
        118,
    )

    if (
        parse_dds_dimensions(
            bytes(
                dds,
            ),
        ) !=
        (
            118,
            192,
        )
    ):
        raise AssertionError(
            "DDS dimension self-test failed",
        )

    png = (
        b"\x89PNG\r\n\x1a\n" +
        b"\x00\x00\x00\x0dIHDR" +
        (
            70
        ).to_bytes(
            4,
            "big",
        ) +
        (
            52
        ).to_bytes(
            4,
            "big",
        )
    )

    if (
        parse_png_dimensions(
            png,
        ) !=
        (
            70,
            52,
        )
    ):
        raise AssertionError(
            "PNG dimension self-test failed",
        )

    try:
        safe_entry_name(
            "../secret.png",
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "unsafe entry accepted",
        )

    print(
        "Logres tutorial-field presentation hydrator self-test: PASS",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
    )

    parser.add_argument(
        "cache_root",
        nargs="?",
        type=Path,
    )

    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
    )

    parser.add_argument(
        "--dds-converter",
        default="convert",
    )

    parser.add_argument(
        "--summary",
        type=Path,
    )

    parser.add_argument(
        "--self-test",
        action="store_true",
    )

    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    if args.cache_root is None:
        print(
            "cache_root is required unless --self-test is used",
            file=sys.stderr,
        )

        return 2

    try:
        result = hydrate(
            args.cache_root,
            args.output_root,
            dds_converter=
                args.dds_converter,
        )
    except (
        OSError,
        ValueError,
    ) as exc:
        print(
            f"tutorial-field hydration failed: {exc}",
            file=sys.stderr,
        )

        return 1

    encoded = (
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        ) +
        "\n"
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
    raise SystemExit(
        main(),
    )
