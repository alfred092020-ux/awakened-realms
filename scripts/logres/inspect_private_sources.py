#!/usr/bin/env python3
"""Find source/schema evidence inside MBNs without exporting private source text."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
from zipfile import ZipFile

from hydrate_private_assets import parse_mbn
from inspect_private_map_nested import scan_blob

SOURCE_SUFFIXES = {'.lua', '.luac', '.json', '.proto', '.so', '.dex', '.xml', '.txt', '.bin'}
RESOURCE_ID = re.compile(r'\d{3}_\d{3}_\d{5}\Z')
SETTING_KEYS = {'initial_view_scale', 'default_background_image'}


def json_evidence(value):
    refs = []
    settings = []

    def walk(item, pointer, key):
        if isinstance(item, dict):
            for k, v in sorted(item.items()):
                escaped = k.replace('~', '~0').replace('/', '~1')
                walk(v, pointer + '/' + escaped, k)
        elif isinstance(item, list):
            for i, v in enumerate(item):
                walk(v, pointer + '/' + str(i), key)
        elif isinstance(item, str) and RESOURCE_ID.fullmatch(item):
            refs.append({'pointer': pointer, 'resource_id': item})
        elif key in SETTING_KEYS and isinstance(item, (str, int, float)):
            settings.append({'pointer': pointer, 'value': item})

    walk(value, '', '')
    return {'resource_id_candidates': refs[:200], 'resource_id_candidate_count': len(refs),
            'semantic_policy': 'The same ID syntax is used for maps, audio, effects and other resources. Context must establish the type.',
            'settings': settings[:50]}


def source_evidence(container, name, data):
    suffix = Path(name).suffix.lower()
    result = {'container': container, 'entry': name, 'size': len(data),
              'sha256': hashlib.sha256(data).hexdigest(), 'hits': scan_blob(data)}
    if data.startswith(b'\x1bLua'):
        result['format'] = 'lua-bytecode'
    elif data.startswith(b'\x1bLJ'):
        result['format'] = 'luajit-bytecode'
    elif data.startswith(b'\x7fELF'):
        result['format'] = 'elf'
    elif data.startswith(b'dex\n'):
        result['format'] = 'dex'
    else:
        result['format'] = 'unclassified'
    if suffix == '.json':
        try:
            result['json_evidence'] = json_evidence(json.loads(data))
            result['format'] = 'json'
        except (ValueError, UnicodeDecodeError):
            result['json_parse_failed'] = True
    return result


def inspect_sources(archive):
    sources = []
    inventory = Counter()
    errors = []
    relevant_packages = []
    with ZipFile(archive) as z:
        for info in sorted(z.infolist(), key=lambda item: item.filename):
            suffix = Path(info.filename).suffix.lower()
            if suffix == '.mbn':
                try:
                    with z.open(info) as handle:
                        header = handle.read(8)
                        if len(header) != 8:
                            raise ValueError('short header')
                        reserved, size = struct.unpack('<II', header)
                        if reserved != 0 or size > 8 * 1024 * 1024:
                            raise ValueError('invalid manifest header')
                        manifest = json.loads(handle.read(size))
                    names = [entry['name'] for entry in manifest]
                    for name in names:
                        inventory[Path(name).suffix.lower() or '(none)'] += 1
                    candidates = [name for name in names if Path(name).suffix.lower() in SOURCE_SUFFIXES]
                    if candidates:
                        if info.file_size > 128 * 1024 * 1024:
                            errors.append({'member': info.filename, 'reason': 'source package exceeds scan bound'})
                            continue
                        entries = parse_mbn(z.read(info))
                        for name in candidates:
                            sources.append(source_evidence(info.filename, name, entries[name]))
                    if any(term in info.filename.lower() for term in ('tutorial', 'field', 'shader', 'system', 'script')):
                        relevant_packages.append({'member': info.filename, 'entries': names[:40]})
                except (ValueError, KeyError, TypeError, struct.error) as exc:
                    errors.append({'member': info.filename, 'reason': type(exc).__name__})
            elif suffix in SOURCE_SUFFIXES and info.file_size <= 128 * 1024 * 1024:
                sources.append(source_evidence(None, info.filename, z.read(info)))
    return {
        'provenance': 'EXTRACTED_PRIVATE_CACHE_SOURCE_METADATA',
        'scope': 'Direct source candidates and source entries in MBN manifests; no raw source exported.',
        'mbn_entry_suffix_counts': dict(inventory), 'sources': sources,
        'relevant_package_names': relevant_packages, 'errors': errors,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = inspect_sources(args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + '\n')
    print(f"Inspected {len(result['sources'])} source candidates; {len(result['errors'])} explicit scan errors.")


if __name__ == '__main__':
    main()
