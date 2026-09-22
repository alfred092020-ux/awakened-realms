#!/usr/bin/env python3
"""Inspect recovered private Logres standard map packages without semantic guessing."""

from __future__ import annotations

import argparse
import gzip
import json
import struct
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from hydrate_private_assets import (
    parse_astc_header,
    parse_mbn,
    sha256,
)

MAP_PREFIX = "files/cache/patch/map/"


@dataclass(frozen=True)
class WireField:
    number: int
    wire_type: int
    value: int | bytes


def read_varint(
    data: bytes,
    offset: int,
) -> tuple[int, int]:
    value = 0
    shift = 0

    while True:
        if offset >= len(data):
            raise ValueError(
                "truncated protobuf varint"
            )

        byte = data[offset]
        offset += 1
        value |= (
            byte & 0x7F
        ) << shift

        if (
            byte &
            0x80
        ) == 0:
            return value, offset

        shift += 7
        if shift > 63:
            raise ValueError(
                "protobuf varint exceeds 64 bits"
            )


def parse_wire_message(
    data: bytes,
) -> list[WireField]:
    fields: list[WireField] = []
    offset = 0

    while offset < len(data):
        key, offset = read_varint(
            data,
            offset,
        )
        number = key >> 3
        wire_type = key & 7

        if number == 0:
            raise ValueError(
                "protobuf field number 0 is invalid"
            )

        if wire_type == 0:
            value, offset = read_varint(
                data,
                offset,
            )
        elif wire_type == 1:
            end = offset + 8
            if end > len(data):
                raise ValueError(
                    "truncated fixed64 field"
                )
            value = data[offset:end]
            offset = end
        elif wire_type == 2:
            size, offset = read_varint(
                data,
                offset,
            )
            end = offset + size
            if end > len(data):
                raise ValueError(
                    "truncated length-delimited field"
                )
            value = data[offset:end]
            offset = end
        elif wire_type == 5:
            end = offset + 4
            if end > len(data):
                raise ValueError(
                    "truncated fixed32 field"
                )
            value = data[offset:end]
            offset = end
        else:
            raise ValueError(
                f"unsupported protobuf wire type {wire_type}"
            )

        fields.append(
            WireField(
                number,
                wire_type,
                value,
            )
        )

    return fields


def fixed32_float4_candidate(
    data: bytes,
) -> list[float] | None:
    try:
        fields = parse_wire_message(
            data,
        )
    except ValueError:
        return None

    signature = [
        (
            field.number,
            field.wire_type,
        )
        for field in fields
    ]

    if signature != [
        (1, 5),
        (2, 5),
        (3, 5),
        (4, 5),
    ]:
        return None

    return [
        struct.unpack(
            "<f",
            field.value,
        )[0]
        for field in fields
        if isinstance(
            field.value,
            bytes,
        )
    ]


def summarize_field5_tree(
    data: bytes,
) -> dict[str, dict[str, int]]:
    depths: dict[
        int,
        dict[str, int],
    ] = defaultdict(
        lambda: {
            "nodes": 0,
            "field2_children": 0,
            "field1_records": 0,
            "field3_float4_candidates": 0,
        }
    )

    def walk(
        message: bytes,
        depth: int,
    ) -> None:
        fields = parse_wire_message(
            message,
        )
        item = depths[depth]
        item["nodes"] += 1

        children: list[bytes] = []

        for field in fields:
            if (
                field.number == 1 and
                field.wire_type == 2
            ):
                item[
                    "field1_records"
                ] += 1
            elif (
                field.number == 2 and
                field.wire_type == 2
            ):
                assert isinstance(
                    field.value,
                    bytes,
                )
                children.append(
                    field.value
                )
            elif (
                field.number == 3 and
                field.wire_type == 2
            ):
                assert isinstance(
                    field.value,
                    bytes,
                )
                if (
                    fixed32_float4_candidate(
                        field.value
                    )
                    is not None
                ):
                    item[
                        "field3_float4_candidates"
                    ] += 1

        item[
            "field2_children"
        ] += len(children)

        for child in children:
            walk(
                child,
                depth + 1,
            )

    walk(
        data,
        0,
    )

    return {
        str(depth):
            depths[depth]
        for depth in
        sorted(depths)
    }


def astc_fact(
    data: bytes,
) -> dict[str, Any]:
    header = parse_astc_header(
        data,
    )

    return {
        "block": [
            header.block_x,
            header.block_y,
            header.block_z,
        ],
        "width":
            header.width,
        "height":
            header.height,
        "depth":
            header.depth,
        "bytes":
            len(data),
        "sha256":
            sha256(data),
    }


def inspect_standard_map_package(
    member: str,
    mbn: bytes,
) -> dict[str, Any] | None:
    package_id = Path(
        member
    ).stem

    entries = parse_mbn(
        mbn,
    )

    map_name = (
        f"{package_id}.map"
    )
    chip_name = (
        f"{package_id}_CHIP.astc"
    )
    obj_name = (
        f"{package_id}_OBJ.astc"
    )

    required = (
        map_name,
        chip_name,
        obj_name,
    )

    if not all(
        name in entries
        for name in required
    ):
        return None

    compressed_map = entries[
        map_name
    ]

    try:
        decoded_map = gzip.decompress(
            compressed_map,
        )
    except OSError as exc:
        raise ValueError(
            f"{map_name} is not valid gzip data"
        ) from exc

    root = parse_wire_message(
        decoded_map,
    )

    root_field5 = [
        field.value
        for field in root
        if (
            field.number == 5 and
            field.wire_type == 2 and
            isinstance(
                field.value,
                bytes,
            )
        )
    ]

    if len(
        root_field5
    ) != 1:
        raise ValueError(
            f"{map_name} expected exactly one "
            "length-delimited root field 5"
        )

    field5 = root_field5[0]
    field5_fields = (
        parse_wire_message(
            field5,
        )
    )

    field5_float4 = [
        fixed32_float4_candidate(
            field.value
        )
        for field in field5_fields
        if (
            field.number == 3 and
            field.wire_type == 2 and
            isinstance(
                field.value,
                bytes,
            )
        )
    ]

    field5_float4 = [
        value
        for value in field5_float4
        if value is not None
    ]

    root_summary: list[dict[str, Any]] = []

    for field in root:
        if field.wire_type == 0:
            assert isinstance(
                field.value,
                int,
            )
            value: int | dict[str, int] = field.value
        else:
            assert isinstance(
                field.value,
                bytes,
            )
            value = {
                "byte_length":
                    len(
                        field.value
                    ),
            }

        root_summary.append({
            "field":
                field.number,
            "wire_type":
                field.wire_type,
            "value":
                value,
        })

    return {
        "package_member":
            member,
        "map": {
            "gzip_bytes":
                len(
                    compressed_map
                ),
            "gzip_sha256":
                sha256(
                    compressed_map
                ),
            "decoded_bytes":
                len(
                    decoded_map
                ),
            "decoded_sha256":
                sha256(
                    decoded_map
                ),
            "root_fields":
                root_summary,
            "field5": {
                "byte_length":
                    len(
                        field5
                    ),
                "field2_child_count":
                    sum(
                        1
                        for field
                        in field5_fields
                        if (
                            field.number ==
                                2 and
                            field.wire_type ==
                                2
                        )
                    ),
                "field3_fixed32_float4_candidates":
                    field5_float4,
                "recursive_wire_counts":
                    summarize_field5_tree(
                        field5
                    ),
            },
        },
        "textures": {
            chip_name:
                astc_fact(
                    entries[
                        chip_name
                    ]
                ),
            obj_name:
                astc_fact(
                    entries[
                        obj_name
                    ]
                ),
        },
    }


def inspect_archive(
    archive: Path,
) -> dict[str, Any]:
    packages: dict[str, Any] = {}

    with ZipFile(
        archive
    ) as source:
        for member in sorted(
            source.namelist()
        ):
            if (
                not member.startswith(
                    MAP_PREFIX
                ) or
                not member.endswith(
                    ".mbn"
                )
            ):
                continue

            basename = Path(
                member
            ).name

            if (
                not basename or
                not basename[0]
                    .isdigit()
            ):
                continue

            package = (
                inspect_standard_map_package(
                    member,
                    source.read(
                        member
                    ),
                )
            )

            if package is not None:
                packages[
                    Path(
                        member
                    ).stem
                ] = package

    return {
        "provenance":
            "EXTRACTED_PRIVATE_CACHE_METADATA",
        "semantic_policy":
            (
                "Protobuf fields remain numeric. "
                "field3 fixed32 x4 values are "
                "recorded only as float candidates; "
                "no tile/object/quadtree meaning is "
                "asserted without schema evidence."
            ),
        "package_count":
            len(packages),
        "packages":
            packages,
    }


def _encode_varint(
    value: int,
) -> bytes:
    output = bytearray()

    while True:
        byte = value & 0x7F
        value >>= 7

        if value:
            output.append(
                byte |
                0x80
            )
        else:
            output.append(
                byte
            )
            return bytes(
                output
            )


def _field_varint(
    number: int,
    value: int,
) -> bytes:
    return (
        _encode_varint(
            number << 3
        ) +
        _encode_varint(
            value
        )
    )


def _field_bytes(
    number: int,
    value: bytes,
) -> bytes:
    return (
        _encode_varint(
            (
                number <<
                3
            ) |
            2
        ) +
        _encode_varint(
            len(
                value
            )
        ) +
        value
    )


def _float4(
    values:
        tuple[
            float,
            float,
            float,
            float,
        ],
) -> bytes:
    return b"".join(
        (
            _encode_varint(
                (
                    number <<
                    3
                ) |
                5
            ) +
            struct.pack(
                "<f",
                value,
            )
        )
        for (
            number,
            value,
        )
        in enumerate(
            values,
            start=1,
        )
    )


def self_test() -> None:
    bounds = _float4(
        (
            -1.0,
            -2.0,
            3.0,
            4.0,
        )
    )

    leaf = (
        _field_bytes(
            1,
            b"opaque-record",
        ) +
        _field_bytes(
            3,
            bounds,
        )
    )

    tree = (
        b"".join(
            _field_bytes(
                2,
                leaf,
            )
            for _ in range(
                4
            )
        ) +
        _field_bytes(
            3,
            bounds,
        )
    )

    root = (
        _field_varint(
            1,
            1,
        ) +
        _field_varint(
            2,
            123,
        ) +
        _field_varint(
            3,
            120,
        ) +
        _field_varint(
            4,
            120,
        ) +
        _field_bytes(
            5,
            tree,
        ) +
        _field_varint(
            6,
            8,
        ) +
        _field_varint(
            7,
            8,
        )
    )

    fields = parse_wire_message(
        root,
    )

    if [
        (
            field.number,
            field.wire_type,
        )
        for field in fields
    ] != [
        (1, 0),
        (2, 0),
        (3, 0),
        (4, 0),
        (5, 2),
        (6, 0),
        (7, 0),
    ]:
        raise AssertionError(
            "root wire signature "
            "self-test failed"
        )

    candidate = (
        fixed32_float4_candidate(
            bounds
        )
    )

    if candidate != [
        -1.0,
        -2.0,
        3.0,
        4.0,
    ]:
        raise AssertionError(
            "fixed32 float candidate "
            "self-test failed"
        )

    counts = (
        summarize_field5_tree(
            tree
        )
    )

    expected = {
        "0": {
            "nodes": 1,
            "field2_children": 4,
            "field1_records": 0,
            "field3_float4_candidates": 1,
        },
        "1": {
            "nodes": 4,
            "field2_children": 0,
            "field1_records": 4,
            "field3_float4_candidates": 4,
        },
    }

    if counts != expected:
        raise AssertionError(
            "tree summary self-test "
            f"failed: {counts!r}"
        )

    try:
        parse_wire_message(
            b"\x0a\x05abc"
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "truncated length-delimited "
            "field was accepted"
        )

    print(
        "Logres private map package "
        "inspector self-test: PASS"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
    )

    parser.add_argument(
        "archive",
        nargs="?",
        type=Path,
    )

    parser.add_argument(
        "--output",
        type=Path,
    )

    parser.add_argument(
        "--self-test",
        action="store_true",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.self_test:
        self_test()
        return 0

    if args.archive is None:
        print(
            "archive argument is required "
            "unless --self-test is used",
            file=sys.stderr,
        )
        return 2

    try:
        result = inspect_archive(
            args.archive,
        )
    except (
        OSError,
        ValueError,
    ) as exc:
        print(
            "Logres map package "
            f"inspection failed: {exc}",
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

    if args.output:
        args.output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        args.output.write_text(
            encoded,
            encoding="utf-8",
        )
    else:
        sys.stdout.write(
            encoded
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
