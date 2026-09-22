#!/usr/bin/env python3
"""Decode evidenced map messages privately; CLI exports aggregate validation only."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import struct
from zipfile import ZipFile

from hydrate_private_assets import parse_mbn
from inspect_private_map_packages import MAP_PREFIX, parse_wire_message

# Names/numbers: Global ELF constants in reference/logres/global-map-schema-constants.json.
# Wire types and cardinalities: all five recovered Japanese maps, corroborated by
# Global FieldVertex/FieldQuadTreeStream signatures. These are not server values.
SCHEMA = {
    'Root': {1: ('Version', 0), 2: ('UpdateDate', 0), 3: ('Width', 0), 4: ('Height', 0),
             5: ('QuadTreeRoot', 'QuadTree'), 6: ('FieldQuadUnitRow', 0), 7: ('FieldQuadUnitCol', 0)},
    'QuadTree': {1: ('Grids', 'Grid', True), 2: ('QuadTrees', 'QuadTree', True), 3: ('BoundingBox', 'BoundingBox')},
    'BoundingBox': {1: ('OriginX', 5), 2: ('OriginY', 5), 3: ('SizeX', 5), 4: ('SizeY', 5)},
    'Grid': {1: ('Col', 0), 2: ('Row', 0), 3: ('DepthOrder', 0), 4: ('Prohibition', 0),
             5: ('Attribute', 0), 6: ('PathwayIndex', 0), 7: ('BorderID', 0),
             8: ('BlendAdjacence', 0), 9: ('ColorIndex', 0), 10: ('Chips', 'Chip', True),
             11: ('Obj', 'Object', True), 12: ('ObjAnimated', 'ObjectAnimated', True)},
    'Chip': {1: ('Id', 0), 2: ('Height', 0), 3: ('ShadowID', 0),
             4: ('ShadowAlpha', 5), 5: ('Vertices', 'Vertex', True)},
    'Object': {1: ('Id', 0), 2: ('DepthOrder', 0), 3: ('Vertices', 'Vertex', True)},
    'ObjectAnimated': {1: ('Id', 0), 2: ('DepthOrder', 0)},
    'Vertex': {1: ('VertexPos', 'VertexPos'), 2: ('UvPoses', 'UVPos', True)},
    'VertexPos': {1: ('PosX', 5), 2: ('PosY', 5)},
    'UVPos': {1: ('UvX', 5), 2: ('UvY', 5)},
}


def decode_message(data, name, depth=0):
    if depth > 64:
        raise ValueError('map nesting exceeds 64 levels')
    result = {}
    for field in parse_wire_message(data):
        spec = SCHEMA[name].get(field.number)
        if spec is None:
            result.setdefault('_unknown_fields', []).append(f'{field.number}:{field.wire_type}')
            continue
        label, kind, *repeated = spec
        expected_wire = 2 if isinstance(kind, str) else kind
        if field.wire_type != expected_wire:
            raise ValueError(f'{name}.{label}: unexpected wire type {field.wire_type}')
        if isinstance(kind, str):
            value = decode_message(field.value, kind, depth + 1)
        elif kind == 5:
            value = struct.unpack('<f', field.value)[0]
            if not math.isfinite(value):
                raise ValueError(f'{name}.{label}: nonfinite geometry')
        else:
            value = field.value
        if repeated:
            result.setdefault(label, []).append(value)
        elif label in result:
            # Inspection deliberately flags variants instead of silently applying
            # protobuf last-value/merge semantics to unexamined content.
            raise ValueError(f'{name}.{label}: duplicate singular field')
        else:
            result[label] = value
    return result


def summarize_root(root):
    counters = Counter()
    uv_counts = Counter()
    unknown = Counter()
    coordinates = set()
    depths = set()

    def unknowns(item, path):
        if isinstance(item, dict):
            for value in item.get('_unknown_fields', []):
                unknown[f'{path}/{value}'] += 1
            for key, value in item.items():
                unknowns(value, f'{path}/{key}')
        elif isinstance(item, list):
            for value in item:
                unknowns(value, path)

    def walk(tree):
        counters['quadtree_count'] += 1
        for grid in tree.get('Grids', []):
            counters['grid_count'] += 1
            coordinates.add((grid.get('Col'), grid.get('Row')))
            depths.add(grid.get('DepthOrder'))
            for label in ('Chips', 'Obj', 'ObjAnimated'):
                for entity in grid.get(label, []):
                    counters[label] += 1
                    for vertex in entity.get('Vertices', []):
                        counters[label + '_vertices'] += 1
                        uv_counts[f'{label}:{len(vertex.get("UvPoses", []))}'] += 1
        for child in tree.get('QuadTrees', []):
            walk(child)

    unknowns(root, 'Root')
    if 'QuadTreeRoot' in root:
        walk(root['QuadTreeRoot'])
    return {**counters, 'unique_col_row_count': len(coordinates),
            'unique_depth_order_count': len(depths), 'uv_pose_counts': dict(uv_counts),
            'unknown_fields': dict(unknown),
            'root': {k: v for k, v in root.items() if isinstance(v, int)}}


def inspect_archive(archive):
    packages = {}
    with ZipFile(archive) as z:
        for member in sorted(z.namelist()):
            if not member.startswith(MAP_PREFIX) or not member.endswith('.mbn') or not Path(member).name[0].isdigit():
                continue
            entries = parse_mbn(z.read(member))
            key = Path(member).stem
            if key + '.map' not in entries:
                continue
            data = gzip.decompress(entries[key + '.map'])
            packages[key] = {'map_sha256': hashlib.sha256(data).hexdigest(),
                             **summarize_root(decode_message(data, 'Root'))}
    return {'provenance': 'GLOBAL_SCHEMA_VALIDATED_AGAINST_PRIVATE_JAPANESE_CACHE', 'packages': packages}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = inspect_archive(args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + '\n')
    print(f"Decoded {len(result['packages'])} maps with Global schema; no geometry exported.")


if __name__ == '__main__':
    main()
