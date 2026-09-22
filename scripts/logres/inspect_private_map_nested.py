#!/usr/bin/env python3
"""Aggregate nested map wire evidence. Never export private blobs or source text."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import struct
from zipfile import ZipFile

from hydrate_private_assets import parse_mbn, parse_astc_header
from inspect_private_map_packages import MAP_PREFIX, parse_wire_message
from inspect_private_map_records import collect_field1_records

TERMS = (
    'tutorial', 'Tutorial', 'initial_view_scale', 'field_settings',
    'MapChip', 'MapObject', 'MapData', 'MapNode', '.proto',
    'CHIP', 'OBJ', 'quadtree', 'QuadTree', 'setCameraMask',
    'CameraFlag', 'GL_COMPRESSED_SRGB8_ALPHA8_ASTC',
    '001_000_00002', '001_000_00200', '001_000_00700',
    '002_000_00001', '002_000_00003',
)


def scan_blob(data):
    result = {}
    for term in TERMS:
        needle = term.encode('ascii')
        count = data.count(needle)
        if count:
            offsets = []
            start = 0
            for _ in range(min(count, 8)):
                start = data.find(needle, start)
                offsets.append(start)
                start += len(needle)
            result[term] = {'count': count, 'first_offsets': offsets}
    return result


def numeric_summary(values, dimensions):
    finite = [v for v in values if math.isfinite(v)]
    result = {
        'count': len(values), 'nonfinite_count': len(values) - len(finite),
        'min': min(finite) if finite else None,
        'max': max(finite) if finite else None,
        'unique_count': len(set(finite)),
        'zero_to_one_count': sum(0 <= v <= 1 for v in finite),
        'integer_count': sum(v == round(v) for v in finite),
        'top_values': Counter(finite).most_common(8),
    }
    # A small residual is evidence of a numeric relationship, not a UV label.
    result['scaled_integer_hits'] = {
        name: sum(abs(v * size - round(v * size)) <= 0.001 for v in finite)
        for name, size in dimensions.items()
    }
    return result


def profile_records(records, atlases, root_ranges):
    dimensions = {f'{name}.{axis}': size for name, sizes in atlases.items()
                  for axis, size in zip(('width', 'height'), sizes)}
    groups = defaultdict(list)
    opaque = Counter()
    relations = []

    def walk(data, path, depth):
        try:
            fields = parse_wire_message(data)
        except ValueError:
            opaque[path] += 1
            return
        if not fields:
            opaque[path] += 1
            return
        groups[path].append(fields)
        if depth < 6:
            for field in fields:
                if field.wire_type == 2:
                    walk(field.value, f'{path}/{field.number}', depth + 1)

    for raw in records:
        walk(raw, 'record', 0)
        fields = parse_wire_message(raw)
        values = {f.number: f.value for f in fields if f.wire_type == 0}
        if all(n in values for n in (1, 2, 3)):
            relations.append((values[1], values[2], values[3]))

    paths = {}
    for path, messages in sorted(groups.items()):
        fields_by_key = defaultdict(list)
        multiplicities = defaultdict(Counter)
        signatures = Counter()
        for fields in messages:
            counts = Counter(f'{f.number}:{f.wire_type}' for f in fields)
            signatures[','.join(sorted(counts))] += 1
            for key, count in counts.items():
                multiplicities[key][str(count)] += 1
            for field in fields:
                fields_by_key[f'{field.number}:{field.wire_type}'].append(field)
        summary = {}
        for key, fields in sorted(fields_by_key.items()):
            wire = fields[0].wire_type
            values = [f.value for f in fields]
            if wire == 0:
                summary[key] = {'varint': numeric_summary(values, {})}
            elif wire in (1, 5):
                integer, floating = ('Q', 'd') if wire == 1 else ('I', 'f')
                summary[key] = {
                    'u64' if wire == 1 else 'u32': numeric_summary(
                        [struct.unpack('<' + integer, v)[0] for v in values], {}),
                    'f64' if wire == 1 else 'f32': numeric_summary(
                        [struct.unpack('<' + floating, v)[0] for v in values], dimensions),
                }
            else:
                summary[key] = {'lengths': numeric_summary([len(v) for v in values], {})}
        paths[path] = {
            'messages': len(messages), 'field_set_signatures': dict(signatures),
            'multiplicities': {k: dict(v) for k, v in multiplicities.items()},
            'fields': summary,
        }
    pairs = [(a, b) for a, b, _ in relations]
    ids = [c for _, _, c in relations]
    return {
        'record_count': len(records), 'paths': paths,
        'opaque_length_fields': dict(opaque),
        'record_relations': {
            'eligible_records': len(relations),
            'unique_field1_field2_pairs': len(set(pairs)),
            'field3_unique_count': len(set(ids)),
            'field3_min': min(ids) if ids else None,
            'field3_max': max(ids) if ids else None,
            'within_root_3_4': sum(0 <= a < root_ranges[0] and 0 <= b < root_ranges[1]
                                      for a, b in pairs) if len(root_ranges) == 2 else None,
            'field3_equals_field2_times_root3_plus_field1': sum(
                c == b * root_ranges[0] + a for a, b, c in relations
            ) if root_ranges else None,
        },
    }


def inspect_archive(archive):
    packages = {}
    scan_hits = []
    inventory = Counter()
    skipped_large = 0
    with ZipFile(archive) as source:
        for info in sorted(source.infolist(), key=lambda i: i.filename):
            name = info.filename
            inventory[Path(name).suffix.lower() or '(none)'] += 1
            is_map = name.startswith(MAP_PREFIX) and name.endswith('.mbn') and Path(name).name[0].isdigit()
            # Bounded reads; images are not useful code/config scan candidates.
            candidate = Path(name).suffix.lower() in {'.lua', '.json', '.proto', '.so', '.dex', '.xml', '.txt', '.luac'}
            if not is_map and not candidate:
                continue
            if info.file_size > 128 * 1024 * 1024:
                skipped_large += 1
                continue
            data = source.read(info)
            if candidate:
                hits = scan_blob(data)
                if hits:
                    scan_hits.append({'member': name, 'sha256': hashlib.sha256(data).hexdigest(), 'hits': hits})
            if is_map:
                entries = parse_mbn(data)
                package_id = Path(name).stem
                required = [f'{package_id}{suffix}' for suffix in ('.map', '_CHIP.astc', '_OBJ.astc')]
                if not all(key in entries for key in required):
                    continue
                decoded = gzip.decompress(entries[required[0]])
                root = parse_wire_message(decoded)
                scalars = {f.number: f.value for f in root if f.wire_type == 0}
                tree = [f.value for f in root if f.number == 5 and f.wire_type == 2]
                if len(tree) != 1:
                    raise ValueError('expected one root field 5')
                headers = [parse_astc_header(entries[key]) for key in required[1:]]
                atlases = {key: [h.width, h.height] for key, h in zip(('CHIP', 'OBJ'), headers)}
                packages[package_id] = {
                    'map_sha256': hashlib.sha256(decoded).hexdigest(),
                    'root_varints': scalars, 'atlases': atlases,
                    **profile_records(collect_field1_records(tree[0]), atlases,
                                      [scalars[3], scalars[4]]),
                }
    return {
        'provenance': 'EXTRACTED_PRIVATE_CACHE_AGGREGATES',
        'semantics': 'Wire paths and numerical relationships only. Field meanings remain unproven.',
        'packages': packages, 'archive_suffix_counts': dict(inventory),
        'code_config_scan': scan_hits, 'skipped_large_members': skipped_large,
        'scan_scope': 'Direct archive members only; compressed MBN code/config not searched.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = inspect_archive(args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + '\n')
    print(f"Profiled {len(result['packages'])} packages; exported aggregate metadata only.")


if __name__ == '__main__':
    main()
