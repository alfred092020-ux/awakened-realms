#!/usr/bin/env python3
"""Validate derived Global 3.0.24 bootstrap-asset catalogs and emit metadata only.

This tool consumes already-derived reports. It does not open the APK, MBN
packages, or any private asset payload. Output contains paths/types/sizes and
decoder metadata only, never proprietary file bytes.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Iterable

AUDIO_SUFFIXES = frozenset({
    ".aac",
    ".caf",
    ".flac",
    ".m4a",
    ".mp3",
    ".ogg",
    ".opus",
    ".wav",
})

A4R4G4B4_SIGNATURE = (
    "RGB16:R00000f00:G000000f0:B0000000f:A0000f000"
)
A1R5G5B5_SIGNATURE = (
    "RGB16:R00007c00:G000003e0:B0000001f:A00008000"
)

EXPECTED_MEMBER_COUNTS = {
    ".json": 74,
    ".lua": 22,
    ".png": 193,
    ".dds": 155,
    ".bss": 2,
    ".lfla": 15,
}


class CatalogError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        raise CatalogError(f"Could not read JSON catalog {path}: {exc}") from exc


def require_list(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise CatalogError(f"{label} must be a list")
    if not all(isinstance(entry, dict) for entry in value):
        raise CatalogError(f"{label} must contain objects only")
    return value


def decoder_error_count(value: Any, label: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        if value < 0:
            raise CatalogError(f"{label} error count cannot be negative")
        return value

    if isinstance(value, list):
        return len(value)

    raise CatalogError(
        f"{label} errors must be an integer count or an error list"
    )


def catalog_key(entry: dict[str, Any]) -> tuple[str, str]:
    package = str(entry.get("package", "")).strip()
    name = str(entry.get("entry", "")).strip()
    if not package or not name:
        raise CatalogError("Catalog entries require package and entry")
    return package, name


def summarize(
    members_raw: Any,
    lfla_raw: Any,
    dds_raw: Any,
    source_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    members = require_list(members_raw, "member catalog")

    if not isinstance(lfla_raw, dict):
        raise CatalogError("LFLA catalog must be an object")
    if not isinstance(dds_raw, dict):
        raise CatalogError("DDS catalog must be an object")

    lfla_files = require_list(lfla_raw.get("files"), "LFLA files")
    dds_files = require_list(dds_raw.get("files"), "DDS files")

    lfla_errors = decoder_error_count(
        lfla_raw.get("errors"),
        "LFLA decoder",
    )
    dds_errors = decoder_error_count(
        dds_raw.get("errors"),
        "DDS decoder",
    )
    if lfla_errors != 0:
        raise CatalogError(f"LFLA decoder errors must be zero, got {lfla_errors}")
    if dds_errors != 0:
        raise CatalogError(f"DDS decoder errors must be zero, got {dds_errors}")

    member_index: dict[tuple[str, str], dict[str, Any]] = {}
    suffix_counts: collections.Counter[str] = collections.Counter()
    packages: set[str] = set()
    audio_members: list[dict[str, Any]] = []

    normalized_members: list[dict[str, Any]] = []
    for entry in members:
        key = catalog_key(entry)
        if key in member_index:
            raise CatalogError(f"Duplicate member catalog entry: {key}")

        suffix = str(entry.get("suffix", "")).lower()
        size = entry.get("size")
        if not isinstance(size, int) or size < 0:
            raise CatalogError(f"Invalid member size for {key}: {size!r}")

        normalized = {
            "package": key[0],
            "entry": key[1],
            "suffix": suffix,
            "size": size,
            "file_type": str(entry.get("file_type", "")),
        }
        member_index[key] = normalized
        normalized_members.append(normalized)
        suffix_counts[suffix] += 1
        packages.add(key[0])

        if suffix in AUDIO_SUFFIXES:
            audio_members.append(normalized)

    lfla_index: dict[tuple[str, str], dict[str, Any]] = {}
    title_canvas_count = 0
    patch_character_canvas_count = 0
    lfla_durations: set[int] = set()

    for entry in lfla_files:
        key = catalog_key(entry)
        member = member_index.get(key)
        if member is None or member["suffix"] != ".lfla":
            raise CatalogError(f"LFLA catalog entry missing from member catalog: {key}")
        if key in lfla_index:
            raise CatalogError(f"Duplicate LFLA catalog entry: {key}")

        width = entry.get("width")
        height = entry.get("height")
        duration = entry.get("duration")
        if not all(isinstance(value, int) and value >= 0 for value in (width, height, duration)):
            raise CatalogError(f"Invalid LFLA geometry/timing for {key}")

        if (width, height) == (720, 1280):
            title_canvas_count += 1
        if (width, height) == (152, 128):
            patch_character_canvas_count += 1

        lfla_durations.add(duration)
        lfla_index[key] = {
            "package": key[0],
            "entry": key[1],
            "size": member["size"],
            "document_name": entry.get("name"),
            "width": width,
            "height": height,
            "duration": duration,
            "resource_count": entry.get("resource_count"),
            "symbol_count": entry.get("symbol_count"),
            "resources": entry.get("resources", []),
            "visible_leaves_at_0": entry.get("visible_leaves_at_0", []),
        }

    dds_index: dict[tuple[str, str], dict[str, Any]] = {}
    dds_formats: collections.Counter[str] = collections.Counter()
    dds_max_area: tuple[int, int, str, str] | None = None

    for entry in dds_files:
        key = catalog_key(entry)
        member = member_index.get(key)
        if member is None or member["suffix"] != ".dds":
            raise CatalogError(f"DDS catalog entry missing from member catalog: {key}")
        if key in dds_index:
            raise CatalogError(f"Duplicate DDS catalog entry: {key}")

        width = entry.get("width")
        height = entry.get("height")
        signature = str(entry.get("format_signature", ""))
        if not isinstance(width, int) or width <= 0 or not isinstance(height, int) or height <= 0:
            raise CatalogError(f"Invalid DDS dimensions for {key}")

        dds_formats[signature] += 1
        candidate = (width * height, width, height, key[0], key[1])
        if dds_max_area is None or candidate[0] > dds_max_area[0] * dds_max_area[1]:
            dds_max_area = (width, height, key[0], key[1])

        dds_index[key] = {
            "package": key[0],
            "entry": key[1],
            "size": member["size"],
            "width": width,
            "height": height,
            "pitch": entry.get("pitch"),
            "bit_count": entry.get("bit_count"),
            "pixel_format_flags": entry.get("pixel_format_flags"),
            "format_signature": signature,
        }

    if len(lfla_index) != suffix_counts[".lfla"]:
        raise CatalogError(
            f"LFLA coverage mismatch: decoded={len(lfla_index)} members={suffix_counts['.lfla']}"
        )
    if len(dds_index) != suffix_counts[".dds"]:
        raise CatalogError(
            f"DDS coverage mismatch: decoded={len(dds_index)} members={suffix_counts['.dds']}"
        )

    bss_members = [
        member
        for member in normalized_members
        if member["suffix"] == ".bss"
    ]

    normalized_members.sort(key=lambda value: (value["package"], value["entry"]))

    result: dict[str, Any] = {
        "schema": "logres-global-3024-bootstrap-assets-v1",
        "provenance": "CONFIRMED_ORIGINAL_GLOBAL_3_0_24_PACKAGED_ASSET_METADATA",
        "packages": len(packages),
        "members": len(normalized_members),
        "package_names": sorted(packages),
        "member_types": dict(sorted(suffix_counts.items())),
        "member_catalog": normalized_members,
        "lfla": {
            "files": len(lfla_index),
            "errors": 0,
            "title_canvas_720x1280": title_canvas_count,
            "patch_character_canvas_152x128": patch_character_canvas_count,
            "durations": sorted(lfla_durations),
            "catalog": [
                lfla_index[key]
                for key in sorted(lfla_index)
            ],
        },
        "dds": {
            "files": len(dds_index),
            "errors": 0,
            "a4r4g4b4": dds_formats[A4R4G4B4_SIGNATURE],
            "a1r5g5b5": dds_formats[A1R5G5B5_SIGNATURE],
            "other_formats": {
                signature: count
                for signature, count in sorted(dds_formats.items())
                if signature not in {
                    A4R4G4B4_SIGNATURE,
                    A1R5G5B5_SIGNATURE,
                }
            },
            "max_dimensions": (
                list(dds_max_area)
                if dds_max_area is not None
                else None
            ),
            "catalog": [
                dds_index[key]
                for key in sorted(dds_index)
            ],
        },
        "bss": {
            "files": len(bss_members),
            "classification": "SPRITE_SHEET_METADATA_NOT_AUDIO",
            "entries": [
                f"{entry['package']}/{entry['entry']}"
                for entry in bss_members
            ],
        },
        "audio": {
            "packaged_bootstrap_files": len(audio_members),
            "entries": [
                f"{entry['package']}/{entry['entry']}"
                for entry in audio_members
            ],
            "finding": "NO_PACKAGED_AUDIO_IN_BOOTSTRAP_MBN_CORPUS",
        },
    }

    if source_summary is not None:
        expected_packages = source_summary.get("packages")
        expected_members = source_summary.get("members")
        expected_types = source_summary.get("member_types")

        if expected_packages != result["packages"]:
            raise CatalogError(
                f"Package count disagrees with source summary: {result['packages']} != {expected_packages}"
            )
        if expected_members != result["members"]:
            raise CatalogError(
                f"Member count disagrees with source summary: {result['members']} != {expected_members}"
            )
        if expected_types != result["member_types"]:
            raise CatalogError(
                f"Member type counts disagree with source summary: {result['member_types']} != {expected_types}"
            )

        expected_lfla = source_summary.get("lfla", {})
        expected_dds = source_summary.get("dds", {})
        if expected_lfla.get("files") != result["lfla"]["files"]:
            raise CatalogError("LFLA file count disagrees with source summary")
        if expected_lfla.get("errors") != 0:
            raise CatalogError("Source summary reports LFLA decoder errors")
        if expected_dds.get("files") != result["dds"]["files"]:
            raise CatalogError("DDS file count disagrees with source summary")
        if expected_dds.get("errors") != 0:
            raise CatalogError("Source summary reports DDS decoder errors")

        result["source"] = source_summary.get("source")
        result["native_loaders"] = source_summary.get("native_loaders")
        result["json_tables"] = source_summary.get("json_tables")
        result["validated_against_source_summary"] = True

    return result


def self_test() -> dict[str, Any]:
    members = [
        {"package": "a.mbn", "entry": "x.json", "suffix": ".json", "size": 1, "file_type": "JSON"},
        {"package": "a.mbn", "entry": "x.lua", "suffix": ".lua", "size": 2, "file_type": "Lua"},
        {"package": "a.mbn", "entry": "x.png", "suffix": ".png", "size": 3, "file_type": "PNG"},
        {"package": "a.mbn", "entry": "x.lfla", "suffix": ".lfla", "size": 4, "file_type": "data"},
        {"package": "b.mbn", "entry": "x.dds", "suffix": ".dds", "size": 5, "file_type": "DDS"},
        {"package": "b.mbn", "entry": "x.bss", "suffix": ".bss", "size": 6, "file_type": "data"},
    ]
    lfla = {
        "files": [{
            "package": "a.mbn",
            "entry": "x.lfla",
            "width": 720,
            "height": 1280,
            "duration": 30000,
            "name": "x",
            "resource_count": 0,
            "symbol_count": 0,
        }],
        "errors": 0,
    }
    dds = {
        "files": [{
            "package": "b.mbn",
            "entry": "x.dds",
            "width": 16,
            "height": 16,
            "pitch": 32,
            "bit_count": 16,
            "pixel_format_flags": 65,
            "format_signature": A4R4G4B4_SIGNATURE,
        }],
        "errors": 0,
    }

    result = summarize(members, lfla, dds)
    assert result["packages"] == 2
    assert result["members"] == 6
    assert result["lfla"]["files"] == 1
    assert result["dds"]["a4r4g4b4"] == 1
    assert result["audio"]["packaged_bootstrap_files"] == 0
    assert result["bss"]["classification"] == "SPRITE_SHEET_METADATA_NOT_AUDIO"

    return {
        "ok": True,
        "packages": result["packages"],
        "members": result["members"],
        "audio": result["audio"]["packaged_bootstrap_files"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--members", type=Path)
    parser.add_argument("--lfla", type=Path)
    parser.add_argument("--dds", type=Path)
    parser.add_argument("--source-summary", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        result = self_test()
    else:
        missing = [
            name
            for name, value in {
                "--members": args.members,
                "--lfla": args.lfla,
                "--dds": args.dds,
            }.items()
            if value is None
        ]
        if missing:
            parser.error(f"required unless --self-test: {', '.join(missing)}")

        result = summarize(
            read_json(args.members),
            read_json(args.lfla),
            read_json(args.dds),
            (
                read_json(args.source_summary)
                if args.source_summary is not None
                else None
            ),
        )

    encoded = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
