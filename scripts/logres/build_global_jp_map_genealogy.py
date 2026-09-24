#!/usr/bin/env python3
"""Build a provenance-safe Global 3.0.24 -> current-JP map genealogy database.

The tool consumes already recovered local evidence. It does not download remote
assets. Global remains authoritative; JP is used only for byte/structure lineage.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from decode_private_map import decode_message
from hydrate_private_assets import parse_mbn

TERRAIN_RE = re.compile(r"^(\d{3}_\d{3}_\d{5})(__ans)?$")
MAP_ID_RE = re.compile(r"^\d{3}_\d{3}_\d{5}$")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    )


def classify_package(relative: Path) -> tuple[str, str, str]:
    stem = relative.stem
    if relative.parts and relative.parts[0] == "background":
        base = stem[:-5] if stem.endswith("__ans") else stem
        return "background", base, "ans" if stem.endswith("__ans") else "base"
    if relative.parts and relative.parts[0] == "object":
        return "object", stem, "base"
    if relative.parts and relative.parts[0] == "clan_room":
        return "clan_room", stem, "base"
    match = TERRAIN_RE.match(stem)
    if match:
        return "terrain", match.group(1), "ans" if match.group(2) else "base"
    return "other", stem, "base"


def walk_grids(tree: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    grids: list[dict[str, Any]] = []
    tree_count = 0

    def walk(node: dict[str, Any]) -> None:
        nonlocal tree_count
        tree_count += 1
        grids.extend(node.get("Grids", []))
        for child in node.get("QuadTrees", []):
            walk(child)

    walk(tree)
    return grids, tree_count


def counter_json(values: list[Any]) -> dict[str, int]:
    counts = Counter(values)
    return {
        "null" if key is None else str(key): count
        for key, count in sorted(counts.items(), key=lambda item: str(item[0]))
    }


def terrain_profile(entries: dict[str, bytes], base_id: str) -> dict[str, Any]:
    map_name = f"{base_id}.map"
    if map_name not in entries:
        raise ValueError(f"terrain package missing {map_name}")
    raw_map_member = entries[map_name]
    decoded = gzip.decompress(raw_map_member)
    root = decode_message(decoded, "Root")
    if "QuadTreeRoot" not in root:
        raise ValueError(f"{base_id}: missing QuadTreeRoot")
    grids, quadtree_count = walk_grids(root["QuadTreeRoot"])

    collision = {
        "prohibition": counter_json([grid.get("Prohibition") for grid in grids]),
        "attribute": counter_json([grid.get("Attribute") for grid in grids]),
        "pathway_index": counter_json([grid.get("PathwayIndex") for grid in grids]),
        "border_id": counter_json([grid.get("BorderID") for grid in grids]),
        "blend_adjacence": counter_json([grid.get("BlendAdjacence") for grid in grids]),
        "color_index": counter_json([grid.get("ColorIndex") for grid in grids]),
    }

    structure_rows = []
    for grid in sorted(
        grids,
        key=lambda item: (
            -1 if item.get("Row") is None else item.get("Row"),
            -1 if item.get("Col") is None else item.get("Col"),
            -1 if item.get("DepthOrder") is None else item.get("DepthOrder"),
        ),
    ):
        structure_rows.append(
            [
                grid.get("Col"),
                grid.get("Row"),
                grid.get("DepthOrder"),
                grid.get("Prohibition"),
                grid.get("Attribute"),
                grid.get("PathwayIndex"),
                grid.get("BorderID"),
                len(grid.get("Chips", [])),
                len(grid.get("Obj", [])),
                len(grid.get("ObjAnimated", [])),
            ]
        )

    chip_entries = sorted(
        name for name in entries
        if name.startswith(base_id + "_CHIP.")
    )
    obj_entries = sorted(
        name for name in entries
        if name.startswith(base_id + "_OBJ.")
    )
    chip = [
        {
            "entry": name,
            "encoding": Path(name).suffix.lower().lstrip("."),
            "size": len(entries[name]),
            "sha256": sha256_bytes(entries[name]),
        }
        for name in chip_entries
    ]
    obj = [
        {
            "entry": name,
            "encoding": Path(name).suffix.lower().lstrip("."),
            "size": len(entries[name]),
            "sha256": sha256_bytes(entries[name]),
        }
        for name in obj_entries
    ]

    counts = {
        "grid_count": len(grids),
        "quadtree_count": quadtree_count,
        "chip_count": sum(len(grid.get("Chips", [])) for grid in grids),
        "object_count": sum(len(grid.get("Obj", [])) for grid in grids),
        "animated_object_count": sum(
            len(grid.get("ObjAnimated", [])) for grid in grids
        ),
    }
    root_shape = {
        "version": root.get("Version"),
        "update_date": root.get("UpdateDate"),
        "width": root.get("Width"),
        "height": root.get("Height"),
        "field_quad_unit_row": root.get("FieldQuadUnitRow"),
        "field_quad_unit_col": root.get("FieldQuadUnitCol"),
    }

    atlas_identity = {
        "chip": [item["sha256"] for item in chip],
        "obj": [item["sha256"] for item in obj],
    }
    return {
        "map_member_compressed_sha256": sha256_bytes(raw_map_member),
        "map_payload_sha256": sha256_bytes(decoded),
        "map_payload_bytes": len(decoded),
        "root": root_shape,
        "counts": counts,
        "collision": collision,
        "structure_fingerprint": stable_hash(
            {
                "root": {
                    key: value
                    for key, value in root_shape.items()
                    if key != "update_date"
                },
                "rows": structure_rows,
            }
        ),
        "collision_fingerprint": stable_hash(collision),
        "atlas_identity_fingerprint": stable_hash(atlas_identity),
        "chip_atlas": chip,
        "object_atlas": obj,
        "region_semantics": {
            "explicit_region_id_field": False,
            "note": (
                "Recovered static map schema exposes Prohibition, Attribute, "
                "PathwayIndex and BorderID per grid. No field named RegionID is "
                "present in the static map schema; do not rename these fields to RegionID."
            ),
        },
    }


def inspect_package(path: Path, relative: Path, provenance: str) -> dict[str, Any]:
    data = path.read_bytes()
    category, base_id, variant = classify_package(relative)
    entries = parse_mbn(data)
    entry_rows = [
        {
            "name": name,
            "size": len(value),
            "sha256": sha256_bytes(value),
        }
        for name, value in sorted(entries.items())
    ]
    result: dict[str, Any] = {
        "path": relative.as_posix(),
        "category": category,
        "base_id": base_id,
        "variant": variant,
        "provenance": provenance,
        "package_bytes": len(data),
        "package_sha256": sha256_bytes(data),
        "entry_count": len(entry_rows),
        "entries": entry_rows,
    }
    if category == "terrain":
        result["terrain"] = terrain_profile(entries, base_id)
    return result


def _inspect_job(job: tuple[str, str, str]) -> dict[str, Any]:
    root_text, path_text, provenance = job
    root = Path(root_text)
    path = Path(path_text)
    return inspect_package(path, path.relative_to(root), provenance)


def inventory_tree(
    root: Path,
    provenance: str,
    workers: int = 1,
) -> list[dict[str, Any]]:
    paths = sorted(root.rglob("*.mbn"))
    jobs = [(str(root), str(path), provenance) for path in paths]
    if workers <= 1 or len(jobs) <= 1:
        return [_inspect_job(job) for job in jobs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_inspect_job, jobs, chunksize=4))


def normalized_global_path(path: str) -> str:
    name = Path(path).name
    if MAP_ID_RE.match(Path(name).stem):
        return name
    return path


def cluster_indices(
    packages: list[dict[str, Any]], field_getter
) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for package in packages:
        value = field_getter(package)
        if value:
            groups[value].append(package["path"])
    return {
        key: sorted(paths)
        for key, paths in groups.items()
        if len(paths) > 1
    }


def terrain_lookup(packages: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    result = {}
    for package in packages:
        if package["category"] == "terrain":
            result[(package["base_id"], package["variant"])] = package
    return result


def compare_millennium_tree(jp_lookup: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    one = jp_lookup.get(("002_000_00001", "base"))
    eight = jp_lookup.get(("002_000_00008", "base"))
    if not one or not eight:
        return {"status": "missing_required_candidate"}
    one_t = one["terrain"]
    eight_t = eight["terrain"]
    same_chip = (
        [x["sha256"] for x in one_t["chip_atlas"]]
        == [x["sha256"] for x in eight_t["chip_atlas"]]
    )
    same_obj = (
        [x["sha256"] for x in one_t["object_atlas"]]
        == [x["sha256"] for x in eight_t["object_atlas"]]
    )
    return {
        "status": "analyzed",
        "candidate_002_000_00001": {
            "package_sha256": one["package_sha256"],
            "map_payload_sha256": one_t["map_payload_sha256"],
            "structure_fingerprint": one_t["structure_fingerprint"],
            "collision": one_t["collision"],
            "counts": one_t["counts"],
        },
        "candidate_002_000_00008": {
            "package_sha256": eight["package_sha256"],
            "map_payload_sha256": eight_t["map_payload_sha256"],
            "structure_fingerprint": eight_t["structure_fingerprint"],
            "collision": eight_t["collision"],
            "counts": eight_t["counts"],
        },
        "same_chip_atlas_bytes": same_chip,
        "same_object_atlas_bytes": same_obj,
        "same_map_payload": (
            one_t["map_payload_sha256"] == eight_t["map_payload_sha256"]
        ),
        "same_structure_fingerprint": (
            one_t["structure_fingerprint"] == eight_t["structure_fingerprint"]
        ),
        "interpretation": (
            "002_000_00001 and 002_000_00008 share the same texture atlases "
            "but have different decompressed .map payloads and collision/structure. "
            "Texture-only image matching cannot uniquely identify the terrain map."
        ),
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    jp = inventory_tree(args.jp_map_root, "CURRENT_JP_PUBLIC_PATCH_CACHE", args.workers)
    global_all = inventory_tree(args.global_map_root, "RECOVERED_GLOBAL_CACHE", args.workers)
    global_maps = [
        package
        for package in global_all
        if package["category"] == "terrain"
    ]

    jp_counts = Counter(package["category"] for package in jp)
    jp_variants = Counter(
        package["variant"] for package in jp
        if package["category"] == "terrain"
    )
    jp_lookup = terrain_lookup(jp)

    global_to_jp = []
    for package in global_maps:
        current = jp_lookup.get((package["base_id"], "base"))
        ans = jp_lookup.get((package["base_id"], "ans"))
        relation = {
            "global_path": package["path"],
            "base_id": package["base_id"],
            "global_package_sha256": package["package_sha256"],
            "current_jp_base_path": current["path"] if current else None,
            "current_jp_ans_path": ans["path"] if ans else None,
            "package_byte_identical_to_jp_base": bool(
                current
                and package["package_sha256"] == current["package_sha256"]
            ),
            "map_payload_identical_to_jp_base": bool(
                current
                and package["terrain"]["map_payload_sha256"]
                == current["terrain"]["map_payload_sha256"]
            ),
            "map_payload_identical_to_jp_ans": bool(
                ans
                and package["terrain"]["map_payload_sha256"]
                == ans["terrain"]["map_payload_sha256"]
            ),
            "structure_identical_to_jp_base": bool(
                current
                and package["terrain"]["structure_fingerprint"]
                == current["terrain"]["structure_fingerprint"]
            ),
        }
        if relation["package_byte_identical_to_jp_base"]:
            relation["lineage_grade"] = "GLOBAL_JP_IDENTICAL"
        elif relation["map_payload_identical_to_jp_base"]:
            relation["lineage_grade"] = "GLOBAL_GEOMETRY_IDENTICAL"
        elif relation["structure_identical_to_jp_base"]:
            relation["lineage_grade"] = "JP_LINEAGE_SUPPORTED"
        else:
            relation["lineage_grade"] = "UNRESOLVED"
        global_to_jp.append(relation)

    terrain = [
        package for package in jp
        if package["category"] == "terrain"
    ]
    exact_map_clusters = cluster_indices(
        terrain,
        lambda package: package["terrain"]["map_payload_sha256"],
    )
    structure_clusters = cluster_indices(
        terrain,
        lambda package: package["terrain"]["structure_fingerprint"],
    )
    atlas_clusters = cluster_indices(
        [
            package
            for package in terrain
            if package["variant"] == "base"
        ],
        lambda package: package["terrain"]["atlas_identity_fingerprint"],
    )

    family_counts = Counter()
    for package in terrain:
        parts = package["base_id"].split("_")
        family_counts["_".join(parts[:2])] += 1

    return {
        "provenance": (
            "GLOBAL_AUTHORITY_WITH_CURRENT_JP_BYTE_AND_STRUCTURE_LINEAGE"
        ),
        "source": {
            "global_map_root": str(args.global_map_root),
            "jp_map_root": str(args.jp_map_root),
        },
        "inventory": {
            "jp_map_related_packages": len(jp),
            "jp_categories": dict(sorted(jp_counts.items())),
            "jp_terrain_variants": dict(sorted(jp_variants.items())),
            "recovered_global_map_packages": len(global_maps),
            "jp_terrain_family_counts": dict(sorted(family_counts.items())),
        },
        "global_to_jp": global_to_jp,
        "clusters": {
            "exact_map_payload_reuse": exact_map_clusters,
            "structural_reuse": structure_clusters,
            "base_atlas_reuse": atlas_clusters,
        },
        "millennium_tree": compare_millennium_tree(jp_lookup),
        "jp_packages": jp,
        "global_packages": global_maps,
        "confidence_policy": {
            "GLOBAL_JP_IDENTICAL": (
                "Exact package bytes match between recovered Global and current JP."
            ),
            "GLOBAL_GEOMETRY_IDENTICAL": (
                "Decompressed map payload matches; texture encoding/package may differ."
            ),
            "JP_LINEAGE_SUPPORTED": (
                "Structural fingerprint matches without exact Global byte identity."
            ),
            "UNRESOLVED": (
                "No identity predicate sufficient to transfer current-JP map facts backward."
            ),
        },
        "unresolved": [
            "Human-readable historical Global field names are server/runtime data and are not embedded in static map packages.",
            "Recovered static map schema contains no explicit field named RegionID; RegionID must not be inferred from Attribute, BorderID or PathwayIndex.",
            "Current-JP-only maps cannot be promoted to historical Global presence without Global-era package, manifest, payload or equivalent primary evidence.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--jp-map-root",
        type=Path,
        default=Path("/home/ubuntu/logres/private/jp-live-patch-cache/map"),
    )
    parser.add_argument(
        "--global-map-root",
        type=Path,
        default=Path("/home/ubuntu/logres/private/global-target"),
    )
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        "Global/JP map genealogy: "
        f"JP={result['inventory']['jp_map_related_packages']} "
        f"Global={result['inventory']['recovered_global_map_packages']} "
        f"terrain={result['inventory']['jp_categories'].get('terrain', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
