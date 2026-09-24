#!/usr/bin/env python3
"""Offline Global Logres 3.0.24 GmCl / oneup protocol twin.

This module never opens sockets. It models only wire behavior recovered from
the original Global 3.0.24 native client. Current-JP evidence is not required
for encoding/decoding.

Confirmed Global transport order:
    GmCl payload -> SplitToContract -> Compressor -> Packetize -> TCP

SplitToContract:
    uint32 LE ContractId
    uint32 LE nested Buffer length
    nested Buffer bytes

Compressor:
    byte 0x00 + raw bytes                         (input < 0x401)
    byte 0x01 + Snappy RawCompress(input)         (input >= 0x401)

Packetize:
    byte 0x01
    uint32 LE sequence
    base-128 varuint payload length
    payload bytes

The fixture compiler accounts for all 631 recovered GmCl procedures. Exact
payload bytes are emitted only where every top-level field has directly
supported Global serialization. Other procedures remain deterministic
schema fixtures with positional field names and explicit unresolved types.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.util
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
from typing import Any, Iterable

GMCL_CONTRACT_ID = 0x31318435
PACKET_MARKER = 0x01
COMPRESS_THRESHOLD = 0x401

DIRECT_PRIMITIVES = {
    "int32", "uint32", "float32", "bool", "string",
    "int64", "uint64", "int16", "uint16", "uint8", "char8",
}

UID2_TYPES = {
    "t_CUID", "t_AreaUID", "t_GridCoord", "t_FieldUID", "t_WarpUID",
    "t_SymbolUID", "t_QuestUID", "t_BoutCharUID", "t_ItemUID",
    "t_BattleSystemUID", "t_BoutSystemUID", "ObjectUID",
}

FLOAT2_TYPES = {"t_MapPos"}
UID4_TYPES = {"t_SkillUID"}
KNOWN_ARRAY_TYPES = {
    "t_arrGridCoord": "t_GridCoord",
    "t_arrBoutCharUID": "t_BoutCharUID",
}

CRITICAL_REPLAY = [
    ("client", "C_GMCL_ACCOUNT_LOGIN_REQ"),
    ("server", "C_GMCL_ACCOUNT_LOGIN_REQ_Response"),
    ("client", "C_GMCL_CHAR_CREATE_REQ"),
    ("server", "C_GMCL_CHAR_CREATE_REQ_Response"),
    ("client", "C_GMCL_CHAR_LOGIN_REQ"),
    ("server", "C_GMCL_CHAR_LOGIN_REQ_Response"),
    ("client", "C_GMCL_FIELD_SELECT_REQ"),
    ("server", "S_GMCL_FIELD_SELECT_REQ"),
    ("client", "C_GMCL_FIELD_INFO_REQ"),
    ("server", "C_GMCL_FIELD_INFO_REQ_Response"),
    ("client", "C_GMCL_ZONEIN_REQ"),
    ("server", "C_GMCL_ZONEIN_REQ_Response"),
    ("server", "S_GMCL_AREA_ENTER"),
    ("client", "C_GMCL_CHAR_MOVE_REQ"),
    ("server", "S_GMCL_CHAR_MOVE_REQ"),
    ("server", "S_GMCL_NPC_APPEAR"),
    ("server", "S_GMCL_ENEMY_APPEAR"),
    ("client", "C_GMCL_CHAR_TALK_REQ"),
    ("server", "C_GMCL_CHAR_TALK_REQ_Response"),
    ("client", "C_GMCL_BATTLE_ENTRY_REQ"),
    ("server", "C_GMCL_BATTLE_ENTRY_REQ_Response"),
    ("server", "S_GMCL_BATTLE_INITIALIZE"),
    ("server", "S_GMCL_BATTLE_BOUT_INITIALIZE"),
    ("client", "C_GMCL_BATTLE_USE_SKILL_REQ"),
    ("server", "C_GMCL_BATTLE_USE_SKILL_REQ_Response"),
    ("server", "S_GMCL_BATTLE_BOUT_EVENT_DROP"),
    ("server", "S_GMCL_BATTLE_RESULT"),
    ("server", "S_GMCL_ITEM_INFO"),
    ("server", "S_GMCL_QUEST_INFO_STATE_RESULT"),
    ("server", "S_GMCL_QUEST_INFO_STATE_RETURN"),
]


class WireError(ValueError):
    pass


class UnknownWireType(WireError):
    pass


class Writer:
    def __init__(self) -> None:
        self.data = bytearray()

    def u8(self, value: int) -> None:
        self.data += struct.pack("<B", value & 0xFF)

    def i16(self, value: int) -> None:
        self.data += struct.pack("<h", value)

    def u16(self, value: int) -> None:
        self.data += struct.pack("<H", value & 0xFFFF)

    def i32(self, value: int) -> None:
        self.data += struct.pack("<i", value)

    def u32(self, value: int) -> None:
        self.data += struct.pack("<I", value & 0xFFFFFFFF)

    def i64(self, value: int) -> None:
        self.data += struct.pack("<q", value)

    def u64(self, value: int) -> None:
        self.data += struct.pack("<Q", value & 0xFFFFFFFFFFFFFFFF)

    def f32(self, value: float) -> None:
        self.data += struct.pack("<f", float(value))

    def bool8(self, value: bool) -> None:
        self.u8(1 if value else 0)

    def string(self, value: str) -> None:
        encoded = value.encode("utf-8")
        self.u32(len(encoded))
        self.data += encoded

    def raw(self, value: bytes) -> None:
        self.data += value

    def bytes(self) -> bytes:
        return bytes(self.data)


class Reader:
    def __init__(self, value: bytes) -> None:
        self.value = value
        self.offset = 0

    def take(self, size: int) -> bytes:
        if size < 0 or self.offset + size > len(self.value):
            raise WireError("truncated")
        result = self.value[self.offset:self.offset + size]
        self.offset += size
        return result

    def u8(self) -> int:
        return struct.unpack("<B", self.take(1))[0]

    def u32(self) -> int:
        return struct.unpack("<I", self.take(4))[0]

    def done(self) -> bool:
        return self.offset == len(self.value)


class Snappy:
    """ctypes wrapper for the system libsnappy C API; no network/package install."""

    SNAPPY_OK = 0

    def __init__(self) -> None:
        name = ctypes.util.find_library("snappy")
        if not name:
            raise RuntimeError("libsnappy not available")
        self.lib = ctypes.CDLL(name)
        c_size = ctypes.c_size_t
        self.lib.snappy_max_compressed_length.argtypes = [c_size]
        self.lib.snappy_max_compressed_length.restype = c_size
        self.lib.snappy_compress.argtypes = [
            ctypes.c_char_p, c_size, ctypes.c_void_p, ctypes.POINTER(c_size)
        ]
        self.lib.snappy_compress.restype = ctypes.c_int
        self.lib.snappy_uncompressed_length.argtypes = [
            ctypes.c_char_p, c_size, ctypes.POINTER(c_size)
        ]
        self.lib.snappy_uncompressed_length.restype = ctypes.c_int
        self.lib.snappy_uncompress.argtypes = [
            ctypes.c_char_p, c_size, ctypes.c_void_p, ctypes.POINTER(c_size)
        ]
        self.lib.snappy_uncompress.restype = ctypes.c_int

    def compress(self, value: bytes) -> bytes:
        maximum = int(self.lib.snappy_max_compressed_length(len(value)))
        out = ctypes.create_string_buffer(maximum)
        out_len = ctypes.c_size_t(maximum)
        status = self.lib.snappy_compress(
            value, len(value), out, ctypes.byref(out_len)
        )
        if status != self.SNAPPY_OK:
            raise WireError(f"snappy_compress failed: {status}")
        return out.raw[:out_len.value]

    def decompress(self, value: bytes) -> bytes:
        out_len = ctypes.c_size_t()
        status = self.lib.snappy_uncompressed_length(
            value, len(value), ctypes.byref(out_len)
        )
        if status != self.SNAPPY_OK:
            raise WireError(f"invalid snappy stream: {status}")
        out = ctypes.create_string_buffer(out_len.value)
        actual = ctypes.c_size_t(out_len.value)
        status = self.lib.snappy_uncompress(
            value, len(value), out, ctypes.byref(actual)
        )
        if status != self.SNAPPY_OK:
            raise WireError(f"snappy_uncompress failed: {status}")
        return out.raw[:actual.value]


_SNAPPY: Snappy | None = None


def snappy() -> Snappy:
    global _SNAPPY
    if _SNAPPY is None:
        _SNAPPY = Snappy()
    return _SNAPPY


def encode_varuint(value: int) -> bytes:
    if value < 0 or value > 0xFFFFFFFF:
        raise WireError("Packetize length outside uint32")
    out = bytearray()
    while True:
        part = value & 0x7F
        value >>= 7
        if value:
            out.append(part | 0x80)
        else:
            out.append(part)
            return bytes(out)


def decode_varuint(reader: Reader) -> int:
    value = 0
    shift = 0
    for _ in range(5):
        part = reader.u8()
        value |= (part & 0x7F) << shift
        if not part & 0x80:
            return value
        shift += 7
    raise WireError("Packetize varuint exceeds five bytes")


def split_to_contract(payload: bytes, contract_id: int = GMCL_CONTRACT_ID) -> bytes:
    # Global SplitToContract::transferForward writes ContractId raw32, then
    # Buffer::push<Buffer>, whose serializer is uint32 byte length + bytes.
    return (
        struct.pack("<II", contract_id & 0xFFFFFFFF, len(payload))
        + payload
    )


def unsplit_contract(value: bytes) -> tuple[int, bytes]:
    reader = Reader(value)
    contract_id = reader.u32()
    nested_length = reader.u32()
    payload = reader.take(nested_length)
    if not reader.done():
        raise WireError("trailing bytes after nested contract Buffer")
    return contract_id, payload


def compressor_forward(value: bytes) -> bytes:
    if len(value) < COMPRESS_THRESHOLD:
        return b"\x00" + value
    return b"\x01" + snappy().compress(value)


def compressor_backward(value: bytes) -> bytes:
    if not value:
        raise WireError("missing Compressor flag")
    flag, body = value[0], value[1:]
    if flag == 0:
        return body
    return snappy().decompress(body)


def packetize(value: bytes, sequence: int) -> bytes:
    return (
        bytes([PACKET_MARKER])
        + struct.pack("<I", sequence & 0xFFFFFFFF)
        + encode_varuint(len(value))
        + value
    )


def unpacketize(frame: bytes) -> tuple[int, int, bytes]:
    reader = Reader(frame)
    marker = reader.u8()
    sequence = reader.u32()
    length = decode_varuint(reader)
    payload = reader.take(length)
    if not reader.done():
        raise WireError("trailing bytes after Packetize payload")
    return marker, sequence, payload


def encode_wire(procedure_payload: bytes, sequence: int) -> bytes:
    return packetize(
        compressor_forward(split_to_contract(procedure_payload)),
        sequence,
    )


def decode_wire(frame: bytes) -> tuple[int, int, bytes]:
    marker, sequence, compressed = unpacketize(frame)
    contract_id, payload = unsplit_contract(compressor_backward(compressed))
    if marker != PACKET_MARKER:
        raise WireError(f"unexpected Packetize marker: {marker:#x}")
    if contract_id != GMCL_CONTRACT_ID:
        raise WireError(f"unexpected contract: {contract_id:#x}")
    return marker, sequence, payload


def positional_default(type_name: str, index: int) -> Any:
    """Deterministic positional fixture value; never claims semantic meaning."""
    if type_name in {"int32", "int16", "int64"}:
        return index + 1
    if type_name in {"uint32", "uint16", "uint64", "uint8", "char8"}:
        return index + 1
    if type_name == "float32":
        return float(index + 1)
    if type_name == "bool":
        return bool(index % 2)
    if type_name == "string":
        return f"field_{index:03d}"
    if type_name in UID2_TYPES:
        return [index + 1, index + 101]
    if type_name in FLOAT2_TYPES:
        return [float(index + 1), float(index + 2)]
    if type_name in UID4_TYPES:
        return [index + 1, index + 2, index + 3, index + 4]
    if type_name == "t_BattleRequestHeader":
        return [[index + 1, index + 2], [index + 3, index + 4]]
    if type_name == "t_BattleSkillInfo":
        return [
            [index + 1, index + 2, index + 3, index + 4],
            index + 5,
            index + 6,
        ]
    if type_name in KNOWN_ARRAY_TYPES:
        # Empty arrays prove the direct count prefix without inventing elements.
        return []
    return {"opaque_type": type_name, "field_index": index}


def encode_known_type(writer: Writer, type_name: str, value: Any) -> None:
    if type_name == "int32":
        writer.i32(int(value))
    elif type_name == "uint32":
        writer.u32(int(value))
    elif type_name == "int16":
        writer.i16(int(value))
    elif type_name == "uint16":
        writer.u16(int(value))
    elif type_name in {"uint8", "char8"}:
        writer.u8(int(value))
    elif type_name == "int64":
        writer.i64(int(value))
    elif type_name == "uint64":
        writer.u64(int(value))
    elif type_name == "float32":
        writer.f32(float(value))
    elif type_name == "bool":
        writer.bool8(bool(value))
    elif type_name == "string":
        writer.string(str(value))
    elif type_name in UID2_TYPES:
        if len(value) != 2:
            raise WireError(f"{type_name} fixture must have two fields")
        writer.u32(int(value[0]))
        writer.u32(int(value[1]))
    elif type_name in FLOAT2_TYPES:
        if len(value) != 2:
            raise WireError(f"{type_name} fixture must have two fields")
        writer.f32(float(value[0]))
        writer.f32(float(value[1]))
    elif type_name in UID4_TYPES:
        if len(value) != 4:
            raise WireError(f"{type_name} fixture must have four fields")
        for part in value:
            writer.u32(int(part))
    elif type_name == "t_BattleRequestHeader":
        encode_known_type(writer, "t_BattleSystemUID", value[0])
        encode_known_type(writer, "t_BoutSystemUID", value[1])
    elif type_name == "t_BattleSkillInfo":
        encode_known_type(writer, "t_SkillUID", value[0])
        writer.u32(int(value[1]))
        writer.u32(int(value[2]))
    elif type_name in KNOWN_ARRAY_TYPES:
        element_type = KNOWN_ARRAY_TYPES[type_name]
        writer.u32(len(value))
        for item in value:
            encode_known_type(writer, element_type, item)
    else:
        raise UnknownWireType(type_name)


def encode_message_fixture(message: dict[str, Any]) -> dict[str, Any]:
    values = []
    unresolved = []
    writer = Writer()
    writer.u32(message["opcode_u32"])

    for field in message["fields"]:
        type_name = field["normalized_type"]
        index = field["index"]
        value = positional_default(type_name, index)
        values.append({
            "name": f"field_{index:03d}",
            "type": type_name,
            "value": value,
            "source_evidence": field["evidence"],
        })
        try:
            encode_known_type(writer, type_name, value)
        except UnknownWireType:
            unresolved.append({
                "name": f"field_{index:03d}",
                "type": type_name,
                "reason": "NO_DIRECT_GLOBAL_WIRE_ENCODER_IN_OFFLINE_TWIN",
            })

    exact = not unresolved
    return {
        "name": message["name"],
        "opcode_u32": message["opcode_u32"],
        "opcode_hex": message["opcode_hex"],
        "direction": message["direction"],
        "fields": values,
        "payload_encoding_status": (
            "GLOBAL_DIRECT_EXACT_TOP_LEVEL_FIXTURE" if exact
            else "SCHEMA_FIXTURE_WIRE_BODY_PARTIAL"
        ),
        "procedure_payload_hex": writer.bytes().hex() if exact else None,
        "procedure_payload_bytes": len(writer.bytes()) if exact else None,
        "unresolved_wire_fields": unresolved,
    }


def build_replay(
    fixtures_by_name: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    replay = []
    sequence = 1
    for actor, name in CRITICAL_REPLAY:
        fixture = fixtures_by_name.get(name)
        if fixture is None:
            replay.append({
                "actor": actor,
                "message": name,
                "status": "MISSING_RECOVERED_MESSAGE",
            })
            continue
        event = {
            "actor": actor,
            "message": name,
            "opcode_hex": fixture["opcode_hex"],
            "schema_status": fixture["payload_encoding_status"],
        }
        if actor == "client" and fixture["procedure_payload_hex"] is not None:
            payload = bytes.fromhex(fixture["procedure_payload_hex"])
            frame = encode_wire(payload, sequence)
            marker, decoded_sequence, decoded_payload = decode_wire(frame)
            if decoded_payload != payload or decoded_sequence != sequence:
                raise AssertionError("offline wire round-trip failed")
            event.update({
                "status": "OFFLINE_EXACT_REQUEST_FRAME",
                "sequence": sequence,
                "packet_marker": marker,
                "wire_hex": frame.hex(),
                "wire_sha256": hashlib.sha256(frame).hexdigest(),
            })
            sequence += 1
        elif actor == "server":
            event.update({
                "status": "SERVER_AUTHORITY_STUB",
                "stub_policy": (
                    "Schema/opcode are recovered Global facts; authoritative "
                    "server validation/state values are intentionally supplied "
                    "by deterministic offline test fixtures, not inferred."
                ),
            })
        else:
            event["status"] = "OFFLINE_SCHEMA_ONLY_REQUEST"
        replay.append(event)
    return replay


def build_artifact(schema_path: Path) -> dict[str, Any]:
    schema = json.loads(schema_path.read_text())
    fixtures = [
        encode_message_fixture(message)
        for message in schema["messages"]
    ]
    fixtures_by_name = {row["name"]: row for row in fixtures}
    counts: dict[str, int] = {}
    for fixture in fixtures:
        key = fixture["payload_encoding_status"]
        counts[key] = counts.get(key, 0) + 1

    # Transport self-checks include both the raw and Snappy paths.
    raw_payload = struct.pack("<I", 0x740A055C) + b"global-offline"
    raw_frame = encode_wire(raw_payload, 7)
    _, seq_raw, decoded_raw = decode_wire(raw_frame)
    if seq_raw != 7 or decoded_raw != raw_payload:
        raise AssertionError("raw transport self-test failed")

    large_payload = struct.pack("<I", 0x740A055C) + (b"A" * 0x500)
    compressed_frame = encode_wire(large_payload, 8)
    _, seq_compressed, decoded_compressed = decode_wire(compressed_frame)
    if seq_compressed != 8 or decoded_compressed != large_payload:
        raise AssertionError("Snappy transport self-test failed")

    replay = build_replay(fixtures_by_name)
    exact_client_replay = sum(
        row.get("status") == "OFFLINE_EXACT_REQUEST_FRAME"
        for row in replay
    )
    server_stubs = sum(
        row.get("status") == "SERVER_AUTHORITY_STUB"
        for row in replay
    )

    return {
        "provenance": "CONFIRMED_GLOBAL_3_0_24_OFFLINE_PROTOCOL_TWIN",
        "network_policy": "NO_SOCKET_OR_REMOTE_SERVER_ACCESS",
        "source_schema": {
            "path": str(schema_path),
            "sha256": hashlib.sha256(schema_path.read_bytes()).hexdigest(),
        },
        "wire": {
            "gmcl_function_id": "uint32 little-endian first field",
            "split_to_contract": {
                "contract_id": f"0x{GMCL_CONTRACT_ID:08x}",
                "format": "uint32_le contractId + uint32_le nestedBufferLength + nestedBufferBytes",
                "evidence": (
                    "Global SplitToContract::transferForward plus "
                    "Buffer::push<Buffer>; reverse strips uint32 ContractId "
                    "then Buffer::pop<Buffer>."
                ),
            },
            "compressor": {
                "threshold": COMPRESS_THRESHOLD,
                "raw": "0x00 + raw bytes",
                "compressed": "0x01 + Snappy RawCompress bytes",
                "evidence": (
                    "Global Compressor::transferForward/backward; backward "
                    "removes one flag byte then RawUncompresses when nonzero."
                ),
            },
            "packetize": {
                "marker": PACKET_MARKER,
                "format": "0x01 + uint32_le sequence + base128_varuint length + payload",
                "max_length_varuint_bytes": 5,
            },
            "encryption_checkpoint": False,
        },
        "direct_global_serializers": {
            "primitive": [
                "int32", "uint32", "float32", "bool8",
                "string=u32 byte length + bytes",
            ],
            "structs": sorted(
                UID2_TYPES | FLOAT2_TYPES | UID4_TYPES
                | {"t_BattleRequestHeader", "t_BattleSkillInfo"}
            ),
            "arrays": {
                key: f"uint32 count + repeated {value}"
                for key, value in sorted(KNOWN_ARRAY_TYPES.items())
            },
        },
        "fixture_counts": {
            "total_messages": len(fixtures),
            **dict(sorted(counts.items())),
        },
        "fixtures": fixtures,
        "critical_offline_replay": replay,
        "critical_replay_counts": {
            "events": len(replay),
            "exact_client_request_frames": exact_client_replay,
            "server_authority_stubs": server_stubs,
        },
        "transport_self_tests": {
            "raw_frame_sha256": hashlib.sha256(raw_frame).hexdigest(),
            "compressed_frame_sha256": hashlib.sha256(compressed_frame).hexdigest(),
            "raw_roundtrip": True,
            "snappy_roundtrip": True,
        },
        "ceilings": [
            "Unknown nested/composite serializers remain schema fixtures until direct Global Buffer push/pop evidence is indexed.",
            "Server validation, persistence, matchmaking, economy decisions and dynamic values are represented by explicit offline authority stubs.",
            "Offline replay proves recovered client wire/framing behavior; it does not recreate retired production server state.",
        ],
    }


def self_test() -> None:
    for value in (0, 1, 0x7F, 0x80, 0x3FFF, 0x4000, 0xFFFFFFFF):
        encoded = encode_varuint(value)
        reader = Reader(encoded)
        decoded = decode_varuint(reader)
        assert decoded == value and reader.done()

    payload = b"abc"
    split = split_to_contract(payload)
    assert split[:8] == struct.pack("<II", GMCL_CONTRACT_ID, 3)
    assert unsplit_contract(split) == (GMCL_CONTRACT_ID, payload)
    assert compressor_backward(compressor_forward(payload)) == payload

    large = b"x" * 0x500
    encoded = compressor_forward(large)
    assert encoded[0] == 1
    assert compressor_backward(encoded) == large

    frame = packetize(b"payload", 0x10203040)
    marker, sequence, body = unpacketize(frame)
    assert marker == 1 and sequence == 0x10203040 and body == b"payload"

    # Directly recovered Global primitive formats.
    writer = Writer()
    writer.u32(3)
    writer.string("abc")
    writer.bool8(True)
    writer.f32(1.5)
    assert writer.bytes() == (
        b"\x03\x00\x00\x00"
        b"\x03\x00\x00\x00abc"
        b"\x01"
        + struct.pack("<f", 1.5)
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(
            "/home/ubuntu/logres/artifacts/global-jp-protocol-schema-20260924.json"
        ),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        self_test()
        print("GLOBAL3024_PROTOCOL_TWIN_SELF_TEST PASS")
    if args.output:
        result = build_artifact(args.schema)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n"
        )
        print(json.dumps({
            "fixture_counts": result["fixture_counts"],
            "critical_replay_counts": result["critical_replay_counts"],
        }, sort_keys=True))
    if not args.self_test and not args.output:
        raise SystemExit("specify --self-test and/or --output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
