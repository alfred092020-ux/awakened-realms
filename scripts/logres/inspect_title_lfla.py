#!/usr/bin/env python3
"""Extract narrow title-layout evidence from Logres LFLA protobuf-wire data."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent),
)

from hydrate_private_assets import parse_mbn


class ParseError(ValueError):
    pass


def read_varint(
    data: bytes,
    offset: int,
) -> tuple[int, int]:
    value = 0
    shift = 0

    while offset < len(data):
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift

        if not byte & 0x80:
            return value, offset

        shift += 7

        if shift > 70:
            raise ParseError(
                'varint exceeds supported width',
            )

    raise ParseError(
        'truncated varint',
    )


def parse_message(
    data: bytes,
) -> dict[int, list[tuple[int, Any]]]:
    result: dict[
        int,
        list[tuple[int, Any]],
    ] = {}

    offset = 0

    while offset < len(data):
        tag, offset = read_varint(
            data,
            offset,
        )

        field = tag >> 3
        wire = tag & 7

        if field <= 0:
            raise ParseError(
                'invalid protobuf field',
            )

        if wire == 0:
            value, offset = read_varint(
                data,
                offset,
            )
        elif wire == 1:
            if offset + 8 > len(data):
                raise ParseError(
                    'truncated fixed64',
                )

            value = data[
                offset:
                offset + 8
            ]

            offset += 8
        elif wire == 2:
            size, offset = read_varint(
                data,
                offset,
            )

            end = offset + size

            if end > len(data):
                raise ParseError(
                    'truncated length field',
                )

            value = data[
                offset:end
            ]

            offset = end
        elif wire == 5:
            if offset + 4 > len(data):
                raise ParseError(
                    'truncated fixed32',
                )

            value = data[
                offset:
                offset + 4
            ]

            offset += 4
        else:
            raise ParseError(
                f'unsupported protobuf wire type {wire}',
            )

        result.setdefault(
            field,
            [],
        ).append(
            (
                wire,
                value,
            ),
        )

    return result


def first_varint(
    message: dict[int, list[tuple[int, Any]]],
    field: int,
) -> int:
    wire, value = message[field][0]

    if wire != 0:
        raise ParseError(
            f'field {field} is not varint',
        )

    return int(value)


def first_bytes(
    message: dict[int, list[tuple[int, Any]]],
    field: int,
) -> bytes:
    wire, value = message[field][0]

    if wire != 2:
        raise ParseError(
            f'field {field} is not bytes',
        )

    return bytes(value)


def first_text(
    message: dict[int, list[tuple[int, Any]]],
    field: int,
) -> str:
    return first_bytes(
        message,
        field,
    ).decode(
        'utf-8',
    )


def first_float32(
    message: dict[int, list[tuple[int, Any]]],
    field: int,
) -> float:
    wire, value = message[field][0]

    if wire != 5:
        raise ParseError(
            f'field {field} is not fixed32',
        )

    return struct.unpack(
        '<f',
        bytes(value),
    )[0]


def nested(
    message: dict[int, list[tuple[int, Any]]],
    field: int,
    index: int = 0,
) -> dict[int, list[tuple[int, Any]]]:
    wire, value = message[field][index]

    if wire != 2:
        raise ParseError(
            f'field {field} is not nested bytes',
        )

    return parse_message(
        bytes(value),
    )


def transform_from_instance(
    instance: dict[int, list[tuple[int, Any]]],
) -> dict[str, float]:
    transform = nested(
        instance,
        5,
    )

    return {
        'scale_x':
            first_float32(
                transform,
                1,
            ),

        'scale_y':
            first_float32(
                transform,
                4,
            ),

        'x':
            first_float32(
                transform,
                5,
            ),

        'y':
            first_float32(
                transform,
                6,
            ),
    }


def inspect_idle_logo(
    data: bytes,
) -> dict[str, Any]:
    root = parse_message(
        data,
    )

    stage = nested(
        root,
        5,
    )

    root_layer = nested(
        stage,
        2,
    )

    root_timeline = nested(
        root_layer,
        3,
    )

    root_instance = nested(
        root_timeline,
        13,
    )

    assets = []

    for index in range(
        len(
            root.get(
                6,
                [],
            ),
        ),
    ):
        asset = nested(
            root,
            6,
            index,
        )

        assets.append(
            first_text(
                asset,
                1,
            ),
        )

    logo00_symbol = None

    for index in range(
        len(
            root.get(
                7,
                [],
            ),
        ),
    ):
        symbol = nested(
            root,
            7,
            index,
        )

        if (
            first_text(
                symbol,
                1,
            ) ==
            'logo00'
        ):
            logo00_symbol = symbol
            break

    if logo00_symbol is None:
        raise ParseError(
            'logo00 symbol missing',
        )

    symbol_timeline = nested(
        logo00_symbol,
        2,
    )

    symbol_layer = nested(
        symbol_timeline,
        2,
    )

    symbol_frame = nested(
        symbol_layer,
        3,
    )

    symbol_instance = nested(
        symbol_frame,
        13,
    )

    return {
        'format':
            'LFLA_PROTOBUF_WIRE',

        'sha256':
            hashlib.sha256(
                data,
            ).hexdigest(),

        'design_width':
            first_varint(
                root,
                1,
            ),

        'design_height':
            first_varint(
                root,
                2,
            ),

        'duration_units':
            first_varint(
                root,
                3,
            ),

        'animation_name':
            first_text(
                root,
                4,
            ),

        'root_layer_name':
            first_text(
                root_layer,
                2,
            ),

        'root_transform':
            transform_from_instance(
                root_instance,
            ),

        'asset_refs':
            assets,

        'logo00_symbol_transform':
            transform_from_instance(
                symbol_instance,
            ),

        'evidence':
            'CONFIRMED_CURRENT_JP_NATIVE',
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
    )

    parser.add_argument(
        'mbn',
        type=Path,
    )

    parser.add_argument(
        '--entry',
        default='logo_b.lfla',
    )

    parser.add_argument(
        '--output',
        type=Path,
    )

    args = parser.parse_args()

    entries = parse_mbn(
        args.mbn.read_bytes(),
    )

    if args.entry not in entries:
        raise SystemExit(
            f'missing MBN entry: {args.entry}',
        )

    result = inspect_idle_logo(
        entries[
            args.entry
        ],
    )

    rendered = (
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) +
        '\n'
    )

    if args.output:
        args.output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        args.output.write_text(
            rendered,
        )
    else:
        print(
            rendered,
            end='',
        )


if __name__ == '__main__':
    main()
