#!/usr/bin/env python3
"""Hydrate recovered Logres title-effect images into the private runtime tree.

The source MBN remains private. This script writes only browser-readable
derivatives under gitignored public/__logres_ref paths and emits a provenance
summary with source/output hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import struct
import tempfile
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

from hydrate_private_assets import parse_mbn

TITLE_EFFECT_MBN_MEMBER = "files/cache/patch/gui/title/effect/png.mbn"
EXPECTED_MBN_SHA256 = (
    "73ae0bfa795f7d02f6286f18b6b8301d3cf607e14445f2318af81bb3b8a5a7d4"
)

# Keep this narrow: these are the title layers currently decoded/needed by the
# reconstruction, plus foreground pieces already proven by bg_c for the next step.
TITLE_EFFECT_ENTRIES = (
    "sky00.png",
    "cloud00.png",
    "cloud01.png",
    "field00.dds",
    "field01.dds",
    "player00.dds",
    "player01.dds",
    "player02.dds",
    "player03.dds",
    "flower00.dds",
    "flower01.dds",
    "grass00.dds",
    "grass01.dds",
    "grass02.dds",
    "efc00.dds",
    "efc01.dds",
    "bird00.dds",
    "bird01.dds",
    "bird02.dds",
    "bird03.dds",
    "logo00.dds",
    "logo01.png",
    "start00.dds",
    "start01.dds",
    "start02.dds",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def runtime_name(source_name: str) -> str:
    lower = source_name.lower()
    if lower.endswith(".dds"):
        return source_name + ".png"
    return source_name


def convert_entry(source_name: str, data: bytes) -> tuple[bytes, int, int]:
    lower = source_name.lower()
    if lower.endswith(".png"):
        image = Image.open(io.BytesIO(data))
        image.load()
        return data, image.width, image.height

    if lower.endswith(".dds"):
        image = Image.open(io.BytesIO(data)).convert("RGBA")
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue(), image.width, image.height

    raise ValueError(f"Unsupported title effect entry: {source_name}")


def hydrate_mbn_bytes(
    mbn: bytes,
    output_root: Path,
    *,
    expected_hash: str | None,
) -> dict[str, object]:
    actual_mbn_hash = sha256(mbn)
    if expected_hash is not None and actual_mbn_hash != expected_hash:
        raise ValueError(
            "Recovered title-effect MBN hash changed: "
            f"expected {expected_hash}, got {actual_mbn_hash}"
        )

    entries = parse_mbn(mbn)
    products: list[dict[str, object]] = []

    output_root.mkdir(parents=True, exist_ok=True)

    for source_name in TITLE_EFFECT_ENTRIES:
        if source_name not in entries:
            raise ValueError(
                f"Recovered title-effect MBN is missing required entry {source_name!r}"
            )

        source = entries[source_name]
        runtime, width, height = convert_entry(source_name, source)
        destination = output_root / runtime_name(source_name)
        destination.write_bytes(runtime)

        products.append(
            {
                "source_name": source_name,
                "runtime_name": destination.name,
                "source_sha256": sha256(source),
                "runtime_sha256": sha256(runtime),
                "width": width,
                "height": height,
                "bytes": len(runtime),
            }
        )

    return {
        "provenance": "RECOVERED_TITLE_EFFECT_PRIVATE_DERIVATIVE",
        "source_member": TITLE_EFFECT_MBN_MEMBER,
        "source_mbn_sha256": actual_mbn_hash,
        "cross_version_note": (
            "The inspected recovered archive member is byte-identical to the "
            "current-JP live title-effect package. Historical 2017 Global "
            "timeline identity is not asserted by this hydrator."
        ),
        "output_root": str(output_root),
        "products": products,
    }


def hydrate_archive(
    archive: Path,
    output_root: Path,
) -> dict[str, object]:
    with ZipFile(archive) as source:
        try:
            mbn = source.read(TITLE_EFFECT_MBN_MEMBER)
        except KeyError as exc:
            raise ValueError(
                f"Archive does not contain {TITLE_EFFECT_MBN_MEMBER!r}"
            ) from exc

    return hydrate_mbn_bytes(
        mbn,
        output_root,
        expected_hash=EXPECTED_MBN_SHA256,
    )


def _make_mbn(entries: dict[str, bytes]) -> bytes:
    manifest = []
    payload = bytearray()
    for name, data in entries.items():
        manifest.append(
            {
                "name": name,
                "size": len(data),
                "offset": len(payload),
                "compresstype": 0,
                "dst_size": len(data),
            }
        )
        payload.extend(data)

    encoded = json.dumps(manifest, separators=(",", ":")).encode("utf-8")
    return struct.pack("<II", 0, len(encoded)) + encoded + bytes(payload)


def self_test() -> dict[str, object]:
    # The production entry list is intentionally broad. Build a tiny MBN and
    # exercise conversion directly instead of pretending it is the real package.
    image = Image.new("RGBA", (2, 3), (10, 20, 30, 255))
    png_io = io.BytesIO()
    image.save(png_io, format="PNG")
    png = png_io.getvalue()

    converted, width, height = convert_entry("test.png", png)
    if converted != png or (width, height) != (2, 3):
        raise AssertionError("PNG passthrough self-test failed")

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.png"
        path.write_bytes(converted)
        if Image.open(path).size != (2, 3):
            raise AssertionError("Hydrated image self-test failed")

    parsed = parse_mbn(_make_mbn({"test.png": png}))
    if parsed["test.png"] != png:
        raise AssertionError("MBN parse self-test failed")

    return {
        "ok": True,
        "png_size": [width, height],
        "png_sha256": sha256(png),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", nargs="?", type=Path)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("public/__logres_ref/global/gui/title/effect/png"),
    )
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        result = self_test()
    else:
        if args.archive is None:
            parser.error("archive path is required unless --self-test is used")
        result = hydrate_archive(args.archive, args.output_root)

    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(encoded)
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
