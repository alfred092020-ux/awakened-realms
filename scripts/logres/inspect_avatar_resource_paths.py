#!/usr/bin/env python3
"""Inspect and hydrate a conservative Logres player-avatar field reference.

This tool reconstructs one static field-avatar reference per gender from:
- current-JP motion/anm/anm_001.mbn, entry anm_001_m_wat_000.lfla
- current-JP avatar/bod_001_m.mbn / bod_001_f.mbn

The output is NOT asserted to be the historical 2017 Global starter appearance.
It intentionally uses unequipped base-body resources so no equipment identity is
invented. The female body is applied to the shared humanoid motion skeleton as
SUPPORTED INFERENCE because the dedicated f_wat authoring file is not a clean
runtime pose.

Private source packages remain private. Hydrated PNG derivatives are written
only under gitignored runtime paths.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image

from hydrate_private_assets import parse_mbn
import flatten_title_lfla as lfla


MOTION_MBN = Path("motion/anm/anm_001.mbn")
MOTION_ENTRY = "anm_001_m_wat_000.lfla"
BODY_TEMPLATE = "avatar/bod_001_{sex}.mbn"

REFERENCE_BODY_ID = "bod_001"
REFERENCE_HEAD_VARIANT = 1

HEAD_LAYER_SUFFIXES = (
    "hat_001",
    "fac_001",
    "eya_000",
    "moa_000",
    "eba_000",
    "haf_001",
)

SYMBOL_TO_BODY_SUFFIX = {
    "Arm_up_000": "aru_000",
    "Arm_hnc_000": "hnc_000",
    "Upper_000": "upr_000",
    "Lower_000": "low_000",
    "Leg_dw_001": "lgd_001",
    "Foot_001": "fot_001",
    "Leg_up_001": "lgu_001",
    "Arm_up_002": "aru_002",
    "Arm_hnc_002": "hnc_002",
}

IGNORED_MOTION_SYMBOLS = (
    "Weapon_100",
    "Skirt_000",
    "Back_000",
    "Hair_bk2_001",
    "Shadow",
)


class AvatarHydrationError(ValueError):
    pass


@dataclass(frozen=True)
class Matrix2D:
    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    tx: float = 0.0
    ty: float = 0.0

    def then(self, child: "Matrix2D") -> "Matrix2D":
        return Matrix2D(
            a=self.a * child.a + self.c * child.b,
            b=self.b * child.a + self.d * child.b,
            c=self.a * child.c + self.c * child.d,
            d=self.b * child.c + self.d * child.d,
            tx=self.a * child.tx + self.c * child.ty + self.tx,
            ty=self.b * child.tx + self.d * child.ty + self.ty,
        )

    def inverse(self) -> "Matrix2D":
        determinant = self.a * self.d - self.b * self.c
        if abs(determinant) < 1e-9:
            raise AvatarHydrationError("Non-invertible avatar affine matrix")

        return Matrix2D(
            a=self.d / determinant,
            b=-self.b / determinant,
            c=-self.c / determinant,
            d=self.a / determinant,
            tx=(self.c * self.ty - self.d * self.tx) / determinant,
            ty=(self.b * self.tx - self.a * self.ty) / determinant,
        )


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def first_fixed32(
    message: bytes,
    field: int,
    default: float,
) -> float:
    values = lfla.field_values(message, field, 5)
    if not values:
        return default
    value = lfla.fixed32_float(bytes(values[0].value), default)
    if not math.isfinite(value):
        raise AvatarHydrationError("Non-finite avatar transform")
    return float(value)


def matrix_from_instance(instance: bytes) -> Matrix2D:
    matrix = lfla.first_bytes(instance, 5) or b""
    return Matrix2D(
        a=first_fixed32(matrix, 1, 1.0),
        b=first_fixed32(matrix, 2, 0.0),
        c=first_fixed32(matrix, 3, 0.0),
        d=first_fixed32(matrix, 4, 1.0),
        tx=first_fixed32(matrix, 5, 0.0),
        ty=first_fixed32(matrix, 6, 0.0),
    )


def decode_motion_leaves(
    data: bytes,
) -> list[tuple[str, Matrix2D, tuple[str, ...]]]:
    timeline_bytes = lfla.first_bytes(data, 5)
    if timeline_bytes is None:
        raise AvatarHydrationError("Motion LFLA has no root timeline")

    symbols: dict[str, dict[str, object]] = {}
    for entry in lfla.field_values(data, 7, 2):
        symbol = bytes(entry.value)
        name = lfla.decode_text(lfla.first_bytes(symbol, 1))
        nested = lfla.first_bytes(symbol, 2)
        if name and nested is not None:
            symbols[name] = lfla.decode_timeline(nested)

    def flatten(
        timeline: dict[str, object],
        parent: Matrix2D = Matrix2D(),
        stack: tuple[str, ...] = (),
    ) -> list[tuple[str, Matrix2D, tuple[str, ...]]]:
        leaves: list[tuple[str, Matrix2D, tuple[str, ...]]] = []

        for layer in timeline["layers"]:  # type: ignore[index]
            keyframe = lfla.choose_keyframe(layer, 0)
            if not keyframe:
                continue

            raw_instance = keyframe.get("instance")
            if not isinstance(raw_instance, (bytes, bytearray)):
                continue

            instance = bytes(raw_instance)
            reference, _, _ = lfla.decode_instance(instance)
            if not reference:
                continue

            combined = parent.then(
                matrix_from_instance(instance),
            )

            if reference in symbols:
                if reference in stack:
                    raise AvatarHydrationError(
                        f"Recursive avatar symbol cycle at {reference!r}",
                    )

                leaves.extend(
                    flatten(
                        symbols[reference],
                        combined,
                        stack + (reference,),
                    )
                )
            else:
                leaves.append(
                    (
                        reference,
                        combined,
                        stack,
                    )
                )

        return leaves

    return flatten(
        lfla.decode_timeline(timeline_bytes),
    )


def padded_body_part(
    entries: dict[str, bytes],
    stem: str,
) -> Image.Image:
    metadata_name = stem + ".json"
    if metadata_name not in entries:
        raise AvatarHydrationError(
            f"Body package is missing metadata {metadata_name!r}",
        )

    metadata = json.loads(
        entries[metadata_name].decode(
            "utf-8-sig",
        )
    )

    image_name = metadata["image"]
    if image_name not in entries:
        raise AvatarHydrationError(
            f"Body package is missing image {image_name!r}",
        )

    raw = Image.open(
        io.BytesIO(
            entries[image_name],
        )
    ).convert("RGBA")

    original = metadata["originalSize"]
    offset = metadata["offset"]
    width = int(original["width"])
    height = int(original["height"])

    canvas = Image.new(
        "RGBA",
        (width, height),
        (0, 0, 0, 0),
    )
    canvas.alpha_composite(
        raw,
        (
            int(offset["x"]),
            int(offset["y"]),
        ),
    )
    return canvas


def compose_reference_head(
    entries: dict[str, bytes],
    sex: str,
) -> Image.Image:
    head = Image.new(
        "RGBA",
        (72, 64),
        (0, 0, 0, 0),
    )

    for suffix in HEAD_LAYER_SUFFIXES:
        stem = f"bod_001_{sex}_{suffix}"
        part = padded_body_part(
            entries,
            stem,
        )

        if part.size != head.size:
            raise AvatarHydrationError(
                f"Head part {stem!r} expected 72x64 canvas, got {part.size}",
            )

        head.alpha_composite(
            part,
            (0, 0),
        )

    return head


def build_part_mapping(
    entries: dict[str, bytes],
    sex: str,
) -> dict[str, Image.Image]:
    mapping = {
        symbol: padded_body_part(
            entries,
            f"bod_001_{sex}_{suffix}",
        )
        for symbol, suffix in
        SYMBOL_TO_BODY_SUFFIX.items()
    }

    mapping["Face_ceo_001"] = (
        compose_reference_head(
            entries,
            sex,
        )
    )

    return mapping


def warp_part(
    source: Image.Image,
    matrix: Matrix2D,
    stage_size: tuple[int, int],
) -> Image.Image:
    inverse = matrix.inverse()

    return source.transform(
        stage_size,
        Image.Transform.AFFINE,
        (
            inverse.a,
            inverse.c,
            inverse.tx,
            inverse.b,
            inverse.d,
            inverse.ty,
        ),
        resample=Image.Resampling.BICUBIC,
    )


def compose_reference_avatar(
    motion: bytes,
    body_entries: dict[str, bytes],
    sex: str,
) -> tuple[Image.Image, dict[str, object]]:
    stage_size = (
        lfla.first_varint(
            motion,
            1,
            800,
        ),
        lfla.first_varint(
            motion,
            2,
            600,
        ),
    )

    leaves = decode_motion_leaves(
        motion,
    )
    mapping = build_part_mapping(
        body_entries,
        sex,
    )

    stage = Image.new(
        "RGBA",
        stage_size,
        (0, 0, 0, 0),
    )

    used_symbols: list[str] = []
    skipped_symbols: list[str] = []

    # The LFLA timeline stores front-most visual layers first. Reversing the
    # leaf sequence reproduces the native back-to-front stacking order for
    # this recovered humanoid wait skeleton.
    for _, matrix, stack in reversed(
        leaves,
    ):
        symbol = (
            stack[-1]
            if stack
            else ""
        )

        source = mapping.get(
            symbol,
        )

        if source is None:
            if (
                symbol and
                symbol not in
                skipped_symbols
            ):
                skipped_symbols.append(
                    symbol,
                )
            continue

        stage = Image.alpha_composite(
            stage,
            warp_part(
                source,
                matrix,
                stage_size,
            ),
        )

        if symbol not in used_symbols:
            used_symbols.append(
                symbol,
            )

    bounds = stage.getbbox()
    if bounds is None:
        raise AvatarHydrationError(
            "Reference avatar composition produced no visible pixels",
        )

    cropped = stage.crop(
        bounds,
    )

    return (
        cropped,
        {
            "stage_size":
                list(stage_size),
            "crop_bounds":
                list(bounds),
            "output_size":
                list(cropped.size),
            "used_symbols":
                sorted(used_symbols),
            "ignored_symbols":
                sorted(skipped_symbols),
        },
    )


def hydrate_reference_avatars(
    patch_root: Path,
    output_root: Path,
) -> dict[str, object]:
    motion_path = (
        patch_root /
        MOTION_MBN
    )
    if not motion_path.exists():
        raise AvatarHydrationError(
            f"Missing motion package: {motion_path}",
        )

    motion_package = parse_mbn(
        motion_path.read_bytes(),
    )
    if MOTION_ENTRY not in motion_package:
        raise AvatarHydrationError(
            f"Motion package is missing {MOTION_ENTRY!r}",
        )

    motion = motion_package[
        MOTION_ENTRY
    ]

    output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    products: list[dict[str, object]] = []

    for sex in (
        "m",
        "f",
    ):
        body_path = (
            patch_root /
            BODY_TEMPLATE.format(
                sex=sex,
            )
        )

        if not body_path.exists():
            raise AvatarHydrationError(
                f"Missing body package: {body_path}",
            )

        body_bytes = body_path.read_bytes()
        body_entries = parse_mbn(
            body_bytes,
        )

        image, composition = (
            compose_reference_avatar(
                motion,
                body_entries,
                sex,
            )
        )

        output_name = (
            f"player_avatar_reference_{sex}.png"
        )
        destination = (
            output_root /
            output_name
        )

        buffer = io.BytesIO()
        image.save(
            buffer,
            format="PNG",
        )
        output_bytes = (
            buffer.getvalue()
        )
        destination.write_bytes(
            output_bytes,
        )

        products.append({
            "sex":
                sex,
            "runtime_name":
                output_name,
            "body_package":
                str(
                    BODY_TEMPLATE.format(
                        sex=sex,
                    )
                ),
            "body_package_sha256":
                sha256(
                    body_bytes,
                ),
            "body_selection":
                "RECONSTRUCTED_CURRENT_JP_REFERENCE_BOD_001",
            "motion_package":
                str(
                    MOTION_MBN,
                ),
            "motion_entry":
                MOTION_ENTRY,
            "motion_entry_sha256":
                sha256(
                    motion,
                ),
            "motion_application":
                (
                    "CONFIRMED_CURRENT_JP_RESOURCE"
                    if sex == "m"
                    else
                    "SUPPORTED_INFERENCE_SHARED_HUMANOID_SKELETON"
                ),
            "historical_global_body_id":
                "UNRESOLVED",
            "historical_global_equipment_ids":
                "UNRESOLVED",
            "runtime_sha256":
                sha256(
                    output_bytes,
                ),
            "composition":
                composition,
        })

    return {
        "provenance":
            "RECOVERED_CURRENT_JP_PRIVATE_DERIVATIVE",
        "purpose":
            "FIELD_PLAYER_REFERENCE_PRESENTATION",
        "reference_body_id":
            REFERENCE_BODY_ID,
        "reference_equipment":
            "NONE",
        "historical_global_appearance":
            "UNRESOLVED",
        "head_variant_selection":
            "RECONSTRUCTED_REFERENCE_SELECTION",
        "products":
            products,
    }


def self_test() -> dict[str, object]:
    parent = Matrix2D(
        a=2.0,
        d=2.0,
        tx=10.0,
        ty=20.0,
    )
    child = Matrix2D(
        tx=3.0,
        ty=4.0,
    )
    combined = parent.then(
        child,
    )

    if (
        combined.tx,
        combined.ty,
    ) != (
        16.0,
        28.0,
    ):
        raise AssertionError(
            "Affine composition self-test failed",
        )

    inverse = combined.inverse()
    roundtrip = combined.then(
        inverse,
    )

    values = (
        roundtrip.a,
        roundtrip.b,
        roundtrip.c,
        roundtrip.d,
        roundtrip.tx,
        roundtrip.ty,
    )

    expected = (
        1.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
    )

    if any(
        abs(actual - wanted) >
        1e-6
        for actual, wanted in
        zip(
            values,
            expected,
        )
    ):
        raise AssertionError(
            "Affine inversion self-test failed",
        )

    return {
        "ok":
            True,
        "reference_body_id":
            REFERENCE_BODY_ID,
        "motion_entry":
            MOTION_ENTRY,
        "historical_global_appearance":
            "UNRESOLVED",
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
    )
    parser.add_argument(
        "patch_root",
        nargs="?",
        type=Path,
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(
            "public/__logres_ref/current-jp/player-avatar-reference",
        ),
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
        result = self_test()
    else:
        if args.patch_root is None:
            parser.error(
                "patch_root is required unless --self-test is used",
            )

        result = hydrate_reference_avatars(
            args.patch_root,
            args.output_root,
        )

    encoded = (
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
            allow_nan=False,
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
        )
    else:
        print(
            encoded,
            end="",
        )


if __name__ == "__main__":
    main()
