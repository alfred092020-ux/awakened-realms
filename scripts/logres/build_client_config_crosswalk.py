#!/usr/bin/env python3
"""Build a structural Global↔Japanese Logres client config crosswalk.

Input is the committed client-config-index.json only. No private config string
values are read or emitted. Output records shared filenames, top-level key
overlap, Global-only keys, Japanese-only keys, hashes and evidence policy.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def build(index: dict) -> dict:
    grouped: dict[str, dict[str, dict]] = {}
    for item in index.get("configs", []):
        if not isinstance(item, dict):
            continue
        source = item.get("source")
        name = item.get("name")
        if source not in {"global", "japanese"} or not isinstance(name, str):
            continue
        grouped.setdefault(name, {})[source] = item

    shared = []
    global_only = []
    japanese_only = []
    for name in sorted(grouped):
        pair = grouped[name]
        g = pair.get("global")
        j = pair.get("japanese")
        if g and j:
            gkeys = set(g.get("topLevelKeys") or [])
            jkeys = set(j.get("topLevelKeys") or [])
            shared.append({
                "name": name,
                "global_sha256": g.get("sha256"),
                "japanese_sha256": j.get("sha256"),
                "shared_top_level_keys": sorted(gkeys & jkeys),
                "global_only_top_level_keys": sorted(gkeys - jkeys),
                "japanese_only_top_level_keys": sorted(jkeys - gkeys),
                "same_sha256": g.get("sha256") == j.get("sha256"),
                "player_facing_policy": (
                    "Prefer surviving Global English terminology for shared semantic keys; "
                    "Japanese-only extensions require separate evidence/localization."
                ),
            })
        elif g:
            global_only.append({
                "name": name,
                "sha256": g.get("sha256"),
                "topLevelKeys": sorted(g.get("topLevelKeys") or []),
            })
        elif j:
            japanese_only.append({
                "name": name,
                "sha256": j.get("sha256"),
                "topLevelKeys": sorted(j.get("topLevelKeys") or []),
            })

    return {
        "provenance": "COMMITTED_CLIENT_CONFIG_INDEX_STRUCTURAL_CROSSWALK",
        "evidence_classification": "CONFIRMED ORIGINAL",
        "policy": (
            "This crosswalk contains filenames, top-level key names and hashes only. "
            "It does not copy private string values. Shared keys support Global-first "
            "player-facing terminology; Japanese-only keys remain untranslated until "
            "evidence establishes an official or faithful English term."
        ),
        "shared_config_count": len(shared),
        "global_only_config_count": len(global_only),
        "japanese_only_config_count": len(japanese_only),
        "shared": shared,
        "global_only": global_only,
        "japanese_only": japanese_only,
    }


def self_test() -> None:
    sample = {
        "configs": [
            {"source":"global","name":"battle_texts.json","topLevelKeys":["skill","damage"],"sha256":"g"},
            {"source":"japanese","name":"battle_texts.json","topLevelKeys":["skill","damage","reserve"],"sha256":"j"},
            {"source":"global","name":"shop_text.json","topLevelKeys":["shop"],"sha256":"s"},
            {"source":"japanese","name":"new_feature.json","topLevelKeys":["new"],"sha256":"n"},
        ]
    }
    out = build(sample)
    assert out["shared_config_count"] == 1
    row = out["shared"][0]
    assert row["shared_top_level_keys"] == ["damage","skill"]
    assert row["japanese_only_top_level_keys"] == ["reserve"]
    assert out["global_only_config_count"] == 1
    assert out["japanese_only_config_count"] == 1
    print("Logres config localization crosswalk self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=Path("reference/logres/client-config-index.json"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    try:
        index = json.loads(args.index.read_text(encoding="utf-8"))
        result = build(index)
    except Exception as exc:
        print(f"crosswalk failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    text = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
