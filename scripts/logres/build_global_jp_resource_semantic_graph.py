#!/usr/bin/env python3
"""Build the OMEGA Global/JP semantic resource graph from indexed evidence.

This compiler does not rescan native binaries or download patch assets. It
fuses previously verified genealogy, map, package-member, source-path and
native-resource-string evidence into a queryable graph with explicit edge
provenance.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
from typing import Any


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def norm_path(value: str) -> str:
    value = value.strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value


def semantic_systems(path: str) -> list[str]:
    p = norm_path(path)
    low = p.lower()
    tags: set[str] = set()
    top = p.split("/", 1)[0] if "/" in p else "(root)"
    if top != "(root)":
        tags.add(top.lower())

    rules = [
        ("battle", ("battle", "gui/battle", "motion/battle", "bout")),
        ("field", ("map/", "field_", "field/", "minimap", "encount")),
        ("onboarding", ("characreate", "charactermake", "world_select", "title")),
        ("avatar", ("avatar/", "hair/", "face_", "character/")),
        ("quest", ("quest", "mission")),
        ("items_equipment", ("equipment", "item/", "inventory", "fusion", "garage")),
        ("gacha", ("gacha", "lotitem")),
        ("chat_social", ("gui/chat", "chat_", "friend", "community")),
        ("clan", ("clan",)),
        ("sixth_sense", ("sixth_sense", "sixthsense")),
        ("event", ("event_", "event/", "eventpoint", "event_point")),
        ("audio", ("sound/", ".ogg", ".wav")),
        ("animation", ("motion/", ".lfla", ".bss")),
        ("renderer", ("shader/", "palette/", "graphicsettings/", "texture")),
        ("weather", ("weather",)),
        ("narrative_skit", ("skitevent/", "skit")),
        ("platform_ui", ("gui/",)),
    ]
    for tag, needles in rules:
        if any(needle in low for needle in needles):
            tags.add(tag)

    if p.startswith("json_resource/"):
        stem = Path(p).stem.lower()
        for tag, needles in rules:
            if any(needle.strip("/_.") in stem for needle in needles):
                tags.add(tag)
        tags.add("configuration_text")
    return sorted(tags)


ID_RE = re.compile(r"(?<!\d)(\d{3}(?:_\d{3}){1,3})(?!\d)")


def logical_ids(path: str) -> list[str]:
    return sorted(set(ID_RE.findall(path)))


class Graph:
    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, Any]] = []
        self._edge_keys: set[tuple[str, str, str, str]] = set()

    def node(self, node_id: str, kind: str, **attrs: Any) -> str:
        existing = self.nodes.get(node_id)
        payload = {"id": node_id, "kind": kind, **attrs}
        if existing is None:
            self.nodes[node_id] = payload
        else:
            for key, value in payload.items():
                if key in ("id", "kind"):
                    continue
                if key not in existing or existing[key] in (None, [], {}):
                    existing[key] = value
        return node_id

    def edge(
        self,
        source: str,
        relation: str,
        target: str,
        provenance: str,
        **attrs: Any,
    ) -> None:
        key = (source, relation, target, provenance)
        if key in self._edge_keys:
            return
        self._edge_keys.add(key)
        self.edges.append(
            {
                "source": source,
                "relation": relation,
                "target": target,
                "provenance": provenance,
                **attrs,
            }
        )


def resource_node_id(surface: str, path: str) -> str:
    return f"resource:{surface}:{norm_path(path)}"


def add_resource_semantics(
    graph: Graph,
    node_id: str,
    path: str,
    system_to_resource: dict[str, set[str]],
    resource_to_system: dict[str, set[str]],
) -> None:
    for system in semantic_systems(path):
        sys_id = graph.node(
            f"system:{system}",
            "semantic_system",
            name=system,
            provenance="DETERMINISTIC_PATH_TAXONOMY",
        )
        graph.edge(
            node_id,
            "CLASSIFIED_AS_SYSTEM",
            sys_id,
            "DETERMINISTIC_PATH_TAXONOMY",
        )
        system_to_resource[system].add(node_id)
        resource_to_system[node_id].add(system)
    for logical_id in logical_ids(path):
        lid = graph.node(
            f"logical-id:{logical_id}",
            "logical_resource_id",
            value=logical_id,
            provenance="PATH_LITERAL",
        )
        graph.edge(node_id, "HAS_LOGICAL_ID", lid, "PATH_LITERAL")


def build(args: argparse.Namespace) -> dict[str, Any]:
    genealogy = json.loads(args.resource_genealogy.read_text())
    maps = json.loads(args.map_genealogy.read_text())
    members = json.loads(args.global_mbn_members.read_text())
    source_paths = json.loads(args.source_paths.read_text())
    source_modules = json.loads(args.source_modules.read_text())
    native_resource_paths = [
        norm_path(line)
        for line in args.resource_path_catalog.read_text(errors="replace").splitlines()
        if line.strip()
    ]

    graph = Graph()
    system_to_resource: dict[str, set[str]] = defaultdict(set)
    resource_to_system: dict[str, set[str]] = defaultdict(set)
    path_index: dict[str, list[str]] = defaultdict(list)

    native_lib = graph.node(
        "binary:global-3.0.24-libgame",
        "native_binary",
        version="3.0.24",
        provenance="CONFIRMED_ORIGINAL_GLOBAL_3_0_24",
    )

    # Full current JP manifest.
    for row in genealogy["jp_manifest"]:
        node = graph.node(
            resource_node_id("jp-current", row["path"]),
            "resource",
            surface="current_jp_public_patch",
            path=row["path"],
            sha1=row["sha1"],
            size=row["size"],
            timestamp=row["timestamp"],
            genealogy_relation=row["genealogy_relation"],
            historical_global_presence=(
                True if row["genealogy_relation"] == "EXACT_GLOBAL_LINEAGE"
                else None
            ),
        )
        path_index[row["path"]].append(node)
        add_resource_semantics(
            graph, node, row["path"], system_to_resource, resource_to_system
        )

    # Original Global bootstrap and recovered Global cache surfaces.
    for surface, key in (
        ("global-bootstrap", "global_bootstrap_lineage"),
        ("global-cache", "recovered_global_cache_lineage"),
    ):
        for row in genealogy[key]:
            node = graph.node(
                resource_node_id(surface, row["path"]),
                "resource",
                surface=surface,
                path=row["path"],
                sha1=row["sha1"],
                sha256=row.get("sha256"),
                size=row["size"],
                timestamp=row.get("timestamp"),
                lineage_grade=row["lineage_grade"],
                provenance=(
                    "CONFIRMED_ORIGINAL_GLOBAL_3_0_24_BOOTSTRAP"
                    if surface == "global-bootstrap"
                    else "RECOVERED_GLOBAL_TARGET_CACHE"
                ),
            )
            path_index[row["path"]].append(node)
            add_resource_semantics(
                graph, node, row["path"], system_to_resource, resource_to_system
            )

    # Exact and changed lineage edges.
    for edge in genealogy["exact_identity_edges"]:
        src_surface = (
            "global-bootstrap"
            if edge["global_source"] == "GLOBAL_3_0_24_BOOTSTRAP_FILELIST"
            else "global-cache"
        )
        src = resource_node_id(src_surface, edge["global_path"])
        dst = resource_node_id("jp-current", edge["jp_path"])
        graph.edge(
            src,
            "EXACT_BYTES_LINEAGE",
            dst,
            "GLOBAL_JP_IDENTICAL_MANIFEST_HASH_AND_SIZE",
            sha1=edge["sha1"],
            size=edge["size"],
            same_path=edge["same_path"],
        )
    for edge in genealogy["same_path_changed_edges"]:
        src_surface = (
            "global-bootstrap"
            if edge["global_source"] == "GLOBAL_3_0_24_BOOTSTRAP_FILELIST"
            else "global-cache"
        )
        src = resource_node_id(src_surface, edge["path"])
        dst = resource_node_id("jp-current", edge["path"])
        graph.edge(
            src,
            "SAME_PATH_CHANGED_LINEAGE",
            dst,
            "PATH_CONTINUITY_ONLY_BYTES_CHANGED",
            global_sha1=edge["global_sha1"],
            jp_sha1=edge["jp_sha1"],
            timestamp_lineage=edge.get("timestamp_lineage"),
        )

    # Global APK bootstrap package membership.
    package_nodes: dict[str, str] = {}
    for row in members:
        package = norm_path(row["package"])
        package_id = resource_node_id("global-bootstrap", package)
        if package_id not in graph.nodes:
            package_id = graph.node(
                f"package:global-bootstrap:{package}",
                "resource_package",
                surface="global-bootstrap",
                path=package,
                provenance="GLOBAL_APK_MBN_MEMBER_CATALOG",
            )
            add_resource_semantics(
                graph, package_id, package, system_to_resource, resource_to_system
            )
        package_nodes[package] = package_id
        member_id = graph.node(
            f"member:global-bootstrap:{package}::{row['entry']}",
            "package_member",
            package=package,
            entry=row["entry"],
            suffix=row.get("suffix"),
            size=row["size"],
            sha256=row.get("sha256"),
            provenance="GLOBAL_APK_MBN_MEMBER_CATALOG",
        )
        graph.edge(
            package_id,
            "PACKAGE_CONTAINS_MEMBER",
            member_id,
            "GLOBAL_APK_MBN_MEMBER_CATALOG",
        )
        add_resource_semantics(
            graph,
            member_id,
            f"{package}/{row['entry']}",
            system_to_resource,
            resource_to_system,
        )

    # Current-JP map package members and atlas-use edges from decoded map genealogy.
    for package in maps["jp_packages"]:
        if package["category"] != "terrain":
            continue
        jp_path = f"map/{package['path']}"
        package_id = resource_node_id("jp-current", jp_path)
        if package_id not in graph.nodes:
            package_id = graph.node(
                package_id,
                "resource",
                surface="current_jp_map_cache",
                path=jp_path,
                sha256=package["package_sha256"],
                size=package["package_bytes"],
                provenance="CURRENT_JP_MAP_GENEALOGY",
            )
            add_resource_semantics(
                graph, package_id, jp_path, system_to_resource, resource_to_system
            )
        map_id = graph.node(
            f"map:{package['base_id']}:{package['variant']}",
            "map",
            base_id=package["base_id"],
            variant=package["variant"],
            structure_fingerprint=package["terrain"]["structure_fingerprint"],
            collision_fingerprint=package["terrain"]["collision_fingerprint"],
            provenance="CURRENT_JP_MAP_GENEALOGY",
        )
        graph.edge(
            map_id,
            "PACKAGED_AS",
            package_id,
            "CURRENT_JP_MAP_GENEALOGY",
        )
        graph.edge(
            map_id,
            "CLASSIFIED_AS_SYSTEM",
            graph.node(
                "system:field",
                "semantic_system",
                name="field",
                provenance="DETERMINISTIC_PATH_TAXONOMY",
            ),
            "DETERMINISTIC_PATH_TAXONOMY",
        )
        for atlas_kind, atlas_rows in (
            ("MAP_USES_CHIP_ATLAS", package["terrain"]["chip_atlas"]),
            ("MAP_USES_OBJECT_ATLAS", package["terrain"]["object_atlas"]),
        ):
            for atlas in atlas_rows:
                member_id = graph.node(
                    f"member:jp-current:{jp_path}::{atlas['entry']}",
                    "package_member",
                    package=jp_path,
                    entry=atlas["entry"],
                    size=atlas["size"],
                    sha256=atlas["sha256"],
                    encoding=atlas["encoding"],
                    provenance="CURRENT_JP_MAP_GENEALOGY",
                )
                graph.edge(
                    package_id,
                    "PACKAGE_CONTAINS_MEMBER",
                    member_id,
                    "CURRENT_JP_MAP_GENEALOGY",
                )
                graph.edge(
                    map_id,
                    atlas_kind,
                    member_id,
                    "CURRENT_JP_MAP_GENEALOGY",
                )

    # Native resource path references. Exact paths connect to known versioned
    # resources; format strings remain explicit pattern nodes.
    native_exact_links = 0
    native_pattern_nodes = 0
    for path in sorted(set(native_resource_paths)):
        candidates = path_index.get(path, [])
        is_pattern = "%" in path or "{" in path or "*" in path
        if candidates and not is_pattern:
            for target in candidates:
                graph.edge(
                    native_lib,
                    "NATIVE_REFERENCES_RESOURCE",
                    target,
                    "GLOBAL_NATIVE_RESOURCE_PATH_LITERAL",
                    literal=path,
                )
                native_exact_links += 1
        else:
            pattern_id = graph.node(
                f"native-resource-pattern:{path}",
                "native_resource_pattern",
                pattern=path,
                provenance="GLOBAL_NATIVE_RESOURCE_PATH_LITERAL",
            )
            graph.edge(
                native_lib,
                "NATIVE_REFERENCES_PATTERN",
                pattern_id,
                "GLOBAL_NATIVE_RESOURCE_PATH_LITERAL",
            )
            add_resource_semantics(
                graph,
                pattern_id,
                path,
                system_to_resource,
                resource_to_system,
            )
            native_pattern_nodes += 1

    # Original source paths and source-module taxonomy.
    source_module_counts = {name: count for name, count in source_modules}
    source_nodes = 0
    for raw_path in source_paths:
        marker = "/client/game/src/"
        short = raw_path.split(marker, 1)[1] if marker in raw_path else raw_path
        module = short.split("/", 1)[0] if "/" in short else "other"
        source_id = graph.node(
            f"source:{short}",
            "original_source_path",
            path=raw_path,
            short_path=short,
            module=module,
            provenance="GLOBAL_NATIVE_SOURCE_PATH_LITERAL",
        )
        module_id = graph.node(
            f"source-module:{module}",
            "source_module",
            name=module,
            expected_path_count=source_module_counts.get(module),
            provenance="GLOBAL_SOURCE_MODULE_CATALOG",
        )
        graph.edge(
            source_id,
            "BELONGS_TO_SOURCE_MODULE",
            module_id,
            "GLOBAL_NATIVE_SOURCE_PATH_LITERAL",
        )
        source_nodes += 1

    node_counts = Counter(node["kind"] for node in graph.nodes.values())
    edge_counts = Counter(edge["relation"] for edge in graph.edges)

    query = {
        "resource_to_system": {
            key: sorted(value) for key, value in sorted(resource_to_system.items())
        },
        "system_to_resource": {
            key: sorted(value) for key, value in sorted(system_to_resource.items())
        },
        "path_to_resource_nodes": {
            key: sorted(value) for key, value in sorted(path_index.items())
        },
    }

    return {
        "provenance": "OMEGA_SEMANTIC_RESOURCE_GRAPH_WITH_EXPLICIT_EDGE_AUTHORITY",
        "sources": {
            "resource_genealogy": {
                "path": str(args.resource_genealogy),
                "sha256": sha256_file(args.resource_genealogy),
            },
            "map_genealogy": {
                "path": str(args.map_genealogy),
                "sha256": sha256_file(args.map_genealogy),
            },
            "global_mbn_members": {
                "path": str(args.global_mbn_members),
                "sha256": sha256_file(args.global_mbn_members),
            },
            "source_paths": {
                "path": str(args.source_paths),
                "sha256": sha256_file(args.source_paths),
            },
            "source_modules": {
                "path": str(args.source_modules),
                "sha256": sha256_file(args.source_modules),
            },
            "resource_path_catalog": {
                "path": str(args.resource_path_catalog),
                "sha256": sha256_file(args.resource_path_catalog),
            },
        },
        "counts": {
            "nodes": len(graph.nodes),
            "edges": len(graph.edges),
            "node_kinds": dict(sorted(node_counts.items())),
            "edge_relations": dict(sorted(edge_counts.items())),
            "systems": len(system_to_resource),
            "native_resource_path_literals": len(set(native_resource_paths)),
            "native_exact_resource_links": native_exact_links,
            "native_pattern_nodes": native_pattern_nodes,
            "global_package_members": len(members),
            "source_paths": source_nodes,
        },
        "nodes": sorted(graph.nodes.values(), key=lambda row: row["id"]),
        "edges": sorted(
            graph.edges,
            key=lambda row: (
                row["source"], row["relation"], row["target"], row["provenance"]
            ),
        ),
        "query": query,
        "policy": {
            "exact_bytes": (
                "Exact resource identity is a byte-continuity claim only."
            ),
            "path_changed": (
                "Same-path changed bytes are ancestry evidence, not identity."
            ),
            "native_reference": (
                "A Global native string literal proves client reference to a path/pattern, "
                "not ownership by a specific function unless separately recovered."
            ),
            "system_taxonomy": (
                "System labels are deterministic query taxonomy and do not upgrade historical behavior confidence."
            ),
            "jp_only": (
                "JP-only resources stay current-JP facts and cannot establish historical Global presence."
            ),
        },
        "unresolved": [
            "Native resource literals with format placeholders are retained as patterns unless an exact expansion is independently proven.",
            "Original source-path module membership does not by itself identify every resource's owning C++ function.",
            "Remote Global resources absent from recovered evidence remain external ceilings even if similarly named JP resources exist.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    reports = Path("/home/ubuntu/logres/private/global-apk/3.0.24/re/reports")
    parser.add_argument(
        "--resource-genealogy",
        type=Path,
        default=Path(
            "/home/ubuntu/logres/artifacts/global-jp-resource-genealogy-20260924.json"
        ),
    )
    parser.add_argument(
        "--map-genealogy",
        type=Path,
        default=Path(
            "/home/ubuntu/logres/artifacts/global-jp-map-genealogy-20260924.json"
        ),
    )
    parser.add_argument(
        "--global-mbn-members",
        type=Path,
        default=reports / "global-apk-mbn-members.json",
    )
    parser.add_argument(
        "--source-paths",
        type=Path,
        default=reports / "global-source-paths.json",
    )
    parser.add_argument(
        "--source-modules",
        type=Path,
        default=reports / "global-source-modules.json",
    )
    parser.add_argument(
        "--resource-path-catalog",
        type=Path,
        default=reports / "resource-path-catalog.txt",
    )
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    print(json.dumps(result["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
