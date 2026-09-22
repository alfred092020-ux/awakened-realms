#!/usr/bin/env python3
"""Profile renderer-relevant facts from evidenced Logres map messages.

The CLI exports aggregate statistics only. It never exports recovered geometry,
textures, source text, or other private client payloads.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
from zipfile import ZipFile

from decode_private_map import decode_message
from hydrate_private_assets import parse_astc_header, parse_mbn
from inspect_private_map_packages import MAP_PREFIX


def top(counter, limit=16):
    return [
        {"value": value, "count": count}
        for value, count in counter.most_common(limit)
    ]


def scalar_summary(values):
    finite = [value for value in values if isinstance(value, (int, float)) and math.isfinite(value)]
    return {
        "count": len(values),
        "finite_count": len(finite),
        "min": min(finite) if finite else None,
        "max": max(finite) if finite else None,
        "unique_count": len(set(finite)),
        "top_values": top(Counter(finite)),
    }


def collect_grids(tree):
    grids = list(tree.get("Grids", []))
    for child in tree.get("QuadTrees", []):
        grids.extend(collect_grids(child))
    return grids


def entity_profile(grids, label, atlas_width, atlas_height):
    entities = []
    for grid in grids:
        entities.extend(grid.get(label, []))

    vertex_counts = Counter()
    uv_pattern_counts = Counter()
    ids = Counter()
    depth_orders = []
    pos_x = []
    pos_y = []
    uv_x = []
    uv_y = []
    bbox_widths = Counter()
    bbox_heights = Counter()
    uv_pixel_x_hits = 0
    uv_pixel_y_hits = 0
    uv_total = 0
    strip_triangle_count = 0

    chip_heights = []
    shadow_ids = Counter()
    shadow_alpha = []

    for entity in entities:
        vertices = entity.get("Vertices", [])
        vertex_counts[len(vertices)] += 1
        strip_triangle_count += max(0, len(vertices) - 2)
        ids[entity.get("Id")] += 1

        if "DepthOrder" in entity:
            depth_orders.append(entity["DepthOrder"])
        if label == "Chips":
            if "Height" in entity:
                chip_heights.append(entity["Height"])
            if "ShadowID" in entity:
                shadow_ids[entity["ShadowID"]] += 1
            if "ShadowAlpha" in entity:
                shadow_alpha.append(entity["ShadowAlpha"])

        pattern = tuple(len(vertex.get("UvPoses", [])) for vertex in vertices)
        uv_pattern_counts[pattern] += 1

        entity_x = []
        entity_y = []
        for vertex in vertices:
            position = vertex.get("VertexPos", {})
            if "PosX" in position:
                pos_x.append(position["PosX"])
                entity_x.append(position["PosX"])
            if "PosY" in position:
                pos_y.append(position["PosY"])
                entity_y.append(position["PosY"])

            for uv in vertex.get("UvPoses", []):
                x = uv.get("UvX")
                y = uv.get("UvY")
                if x is not None:
                    uv_x.append(x)
                    if abs(x * atlas_width - round(x * atlas_width)) <= 0.001:
                        uv_pixel_x_hits += 1
                if y is not None:
                    uv_y.append(y)
                    if abs(y * atlas_height - round(y * atlas_height)) <= 0.001:
                        uv_pixel_y_hits += 1
                if x is not None and y is not None:
                    uv_total += 1

        if entity_x:
            bbox_widths[max(entity_x) - min(entity_x)] += 1
        if entity_y:
            bbox_heights[max(entity_y) - min(entity_y)] += 1

    result = {
        "entity_count": len(entities),
        "id_unique_count": len(ids),
        "top_ids": top(ids),
        "vertices_per_entity": top(vertex_counts),
        "uv_pose_pattern_per_entity": [
            {"pattern": list(pattern), "count": count}
            for pattern, count in uv_pattern_counts.most_common(16)
        ],
        "triangle_strip_triangle_count_candidate": strip_triangle_count,
        "position_x": scalar_summary(pos_x),
        "position_y": scalar_summary(pos_y),
        "bbox_widths": top(bbox_widths),
        "bbox_heights": top(bbox_heights),
        "uv_x": scalar_summary(uv_x),
        "uv_y": scalar_summary(uv_y),
        "uv_pair_count": uv_total,
        "uv_pixel_grid_hits": {
            "x": uv_pixel_x_hits,
            "y": uv_pixel_y_hits,
        },
    }

    if depth_orders:
        result["depth_order"] = scalar_summary(depth_orders)
    if label == "Chips":
        result["height"] = scalar_summary(chip_heights)
        result["shadow_id"] = {
            "count": sum(shadow_ids.values()),
            "unique_count": len(shadow_ids),
            "top_values": top(shadow_ids),
        }
        result["shadow_alpha"] = scalar_summary(shadow_alpha)

    return result


def profile_root(root, chip_size, obj_size):
    tree = root.get("QuadTreeRoot", {})
    grids = collect_grids(tree)
    width = root.get("Width")
    height = root.get("Height")

    cols = [grid.get("Col") for grid in grids if "Col" in grid]
    rows = [grid.get("Row") for grid in grids if "Row" in grid]
    depths = [grid.get("DepthOrder") for grid in grids if "DepthOrder" in grid]

    simple_depth_hits = {}
    if isinstance(width, int) and isinstance(height, int):
        formulas = {
            "row_times_width_plus_col": lambda c, r: r * width + c,
            "col_times_height_plus_row": lambda c, r: c * height + r,
            "row_plus_col": lambda c, r: r + c,
            "row_minus_col": lambda c, r: r - c,
        }
        for name, formula in formulas.items():
            simple_depth_hits[name] = sum(
                1 for grid in grids
                if all(key in grid for key in ("Col", "Row", "DepthOrder"))
                and grid["DepthOrder"] == formula(grid["Col"], grid["Row"])
            )

    grid_fields = {}
    for field in (
        "Prohibition",
        "Attribute",
        "PathwayIndex",
        "BorderID",
        "BlendAdjacence",
        "ColorIndex",
    ):
        values = [grid[field] for grid in grids if field in grid]
        grid_fields[field] = {
            "present_count": len(values),
            "summary": scalar_summary(values),
        }

    return {
        "root": {
            key: root.get(key)
            for key in (
                "Version",
                "UpdateDate",
                "Width",
                "Height",
                "FieldQuadUnitRow",
                "FieldQuadUnitCol",
            )
        },
        "grid": {
            "count": len(grids),
            "col": scalar_summary(cols),
            "row": scalar_summary(rows),
            "depth_order": scalar_summary(depths),
            "unique_col_row_count": len(set(zip(cols, rows))),
            "simple_depth_formula_exact_hits": simple_depth_hits,
            "fields": grid_fields,
        },
        "atlases": {
            "CHIP": list(chip_size),
            "OBJ": list(obj_size),
        },
        "entities": {
            "Chips": entity_profile(
                grids, "Chips", chip_size[0], chip_size[1]
            ),
            "Obj": entity_profile(
                grids, "Obj", obj_size[0], obj_size[1]
            ),
            "ObjAnimated": entity_profile(
                grids, "ObjAnimated", obj_size[0], obj_size[1]
            ),
        },
    }


def inspect_archive(archive):
    packages = {}
    with ZipFile(archive) as source:
        for member in sorted(source.namelist()):
            if (
                not member.startswith(MAP_PREFIX)
                or not member.endswith(".mbn")
                or not Path(member).name[0].isdigit()
            ):
                continue

            package_id = Path(member).stem
            entries = parse_mbn(source.read(member))
            map_name = f"{package_id}.map"
            chip_name = f"{package_id}_CHIP.astc"
            obj_name = f"{package_id}_OBJ.astc"
            if not all(name in entries for name in (map_name, chip_name, obj_name)):
                continue

            decoded = gzip.decompress(entries[map_name])
            chip = parse_astc_header(entries[chip_name])
            obj = parse_astc_header(entries[obj_name])
            root = decode_message(decoded, "Root")

            packages[package_id] = {
                "map_sha256": hashlib.sha256(decoded).hexdigest(),
                **profile_root(
                    root,
                    (chip.width, chip.height),
                    (obj.width, obj.height),
                ),
            }

    return {
        "provenance": "GLOBAL_SCHEMA_PRIVATE_RENDER_AGGREGATES",
        "semantic_policy": (
            "Schema labels are evidence-backed. TRIANGLE_STRIP triangle totals "
            "are arithmetic candidates only; animation timing, texture orientation, "
            "batching, and color space remain unproven."
        ),
        "packages": packages,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    result = inspect_archive(args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Profiled renderer aggregates for {len(result['packages'])} maps; "
        "no private geometry exported."
    )


if __name__ == "__main__":
    main()
