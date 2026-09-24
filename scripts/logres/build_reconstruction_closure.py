#!/usr/bin/env python3
"""Build exhaustive, bounded reconstruction closure over recovered Logres facts.

Global 3.0.24 is historical authority. Current-JP facts are lineage/reference
only unless an explicit identity predicate says otherwise. This script performs
no APK scan and creates no control-plane children; it emits bounded research
task candidates for canonical gaps and terminal records for external ceilings.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Iterable

PROVENANCE = "OMEGA_EXHAUSTIVE_RECONSTRUCTION_CLOSURE_WITH_TERMINAL_CEILINGS"

COVERED = "covered"
KNOWN_NOT_IMPLEMENTED = "evidence-known-not-implemented"
WEAKER_IMPLEMENTATION = "implementation-with-weaker-evidence"
EXTERNAL = "externally-unrecoverable"
UNRESOLVED = "unresolved"

GLOBAL_RESOURCE_PROVENANCE = {
    "CONFIRMED_ORIGINAL_GLOBAL_3_0_24_BOOTSTRAP",
    "RECOVERED_GLOBAL_TARGET_CACHE",
}
GLOBAL_MEMBER_PROVENANCE = {"GLOBAL_APK_MBN_MEMBER_CATALOG"}

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
MAP_ID_RE = re.compile(r"\b\d{3}_\d{3}_\d{5}\b")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected object")
    return value


def git_sha(repo: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def is_text_path(path: Path) -> bool:
    return path.suffix.lower() in {
        ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".txt", ".css", ".html",
    }


class RepoIndex:
    def __init__(self, repo: Path):
        self.repo = repo
        self.impl_text: dict[str, str] = {}
        self.test_text: dict[str, str] = {}
        self.impl_tokens: dict[str, set[str]] = defaultdict(set)
        self.test_tokens: dict[str, set[str]] = defaultdict(set)
        self._load()

    def _load(self) -> None:
        src = self.repo / "src"
        tests = self.repo / "tests"
        for root, destination, token_index in (
            (src, self.impl_text, self.impl_tokens),
            (tests, self.test_text, self.test_tokens),
        ):
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                if not path.is_file() or not is_text_path(path):
                    continue
                rel = path.relative_to(self.repo).as_posix()
                # Reverse/evidence modules prove knowledge, not gameplay
                # implementation. Excluding them prevents self-coverage.
                if rel.startswith("src/game/logres/reverse/"):
                    continue
                try:
                    text = path.read_text(errors="ignore")
                except OSError:
                    continue
                destination[rel] = text
                for token in set(TOKEN_RE.findall(text)):
                    token_index[token].add(rel)
                for token in set(MAP_ID_RE.findall(text)):
                    token_index[token].add(rel)

    @staticmethod
    def _refs_for_tokens(
        token_index: dict[str, set[str]],
        tokens: Iterable[str],
    ) -> list[str]:
        useful = [token for token in tokens if token and len(token) >= 3]
        if not useful:
            return []
        pools = [token_index.get(token, set()) for token in useful]
        if not pools or any(not pool for pool in pools):
            return []
        refs = set(pools[0])
        for pool in pools[1:]:
            refs.intersection_update(pool)
        return sorted(refs)

    def token_refs(self, tokens: Iterable[str]) -> tuple[list[str], list[str]]:
        tokens = list(dict.fromkeys(tokens))
        return (
            self._refs_for_tokens(self.impl_tokens, tokens),
            self._refs_for_tokens(self.test_tokens, tokens),
        )

    def exact_refs(self, literal: str) -> tuple[list[str], list[str]]:
        if not literal:
            return [], []
        return (
            sorted(path for path, text in self.impl_text.items() if literal in text),
            sorted(path for path, text in self.test_text.items() if literal in text),
        )


def cpp_short_class(name: str) -> str:
    tail = name.rsplit("::", 1)[-1]
    return tail.split("<", 1)[0].strip()


def method_base(name: str) -> str:
    raw = name.split("(", 1)[0].strip().rsplit("::", 1)[-1]
    if raw.startswith("operator"):
        return ""
    return raw.replace("~", "")


def function_class_method(name: str) -> tuple[str, str]:
    head = name.split("(", 1)[0].strip()
    if "::" not in head:
        return "", head
    klass, method = head.rsplit("::", 1)
    return klass, method.replace("~", "")


def classify(
    *,
    authority: str,
    implementation_refs: list[str],
    external: bool = False,
    unresolved: bool = False,
) -> str:
    if external:
        return EXTERNAL
    if authority == "WEAKER_LINEAGE":
        return WEAKER_IMPLEMENTATION if implementation_refs else UNRESOLVED
    if unresolved:
        return WEAKER_IMPLEMENTATION if implementation_refs else UNRESOLVED
    return COVERED if implementation_refs else KNOWN_NOT_IMPLEMENTED


def fact(
    *,
    fact_id: str,
    domain: str,
    authority: str,
    classification: str,
    implementation_refs: list[str],
    test_refs: list[str],
    evidence: dict[str, Any],
    semantic_resolution: str | None = None,
) -> dict[str, Any]:
    row = {
        "id": fact_id,
        "domain": domain,
        "authority": authority,
        "classification": classification,
        "implementation_refs": implementation_refs,
        "test_refs": test_refs,
        "evidence": evidence,
    }
    if semantic_resolution is not None:
        row["semantic_resolution"] = semantic_resolution
    return row


def build(args: argparse.Namespace) -> dict[str, Any]:
    complete = load(args.completeness)
    methods = load(args.method_catalog)
    semantic = load(args.semantic_lift)
    protocol = load(args.protocol_schema)
    resources = load(args.resource_graph)
    maps = load(args.map_genealogy)
    state = load(args.state_machine)
    binder = load(args.asset_binder)
    differential = load(args.differential)
    repo_index = RepoIndex(args.repo)

    lfs_records = complete["lfs_records"]
    if len(lfs_records) != 2372:
        raise RuntimeError(f"expected 2372 lfs classes, got {len(lfs_records)}")
    method_total = sum(len(value) for value in methods.values())
    if method_total != 19467:
        raise RuntimeError(f"expected 19467 lfs methods, got {method_total}")
    if set(methods) != {row["class"] for row in lfs_records}:
        raise RuntimeError("lfs class catalog and method catalog differ")

    message_catalog = complete["gmcl"]["message_catalog"]
    constructor_types = complete["gmcl"]["constructor_types"]
    if len(message_catalog) != 631:
        raise RuntimeError(f"expected 631 messages, got {len(message_catalog)}")
    if len(constructor_types) != 533:
        raise RuntimeError(f"expected 533 constructor types, got {len(constructor_types)}")

    high_semantic_classes: Counter[str] = Counter()
    high_semantic_methods: set[tuple[str, str]] = set()
    for row in semantic["function_semantics"]:
        klass, method = function_class_method(row["global_function"])
        if klass:
            high_semantic_classes[klass] += 1
            high_semantic_methods.add((klass, method))

    medium_semantic_methods: set[tuple[str, str]] = set()
    for row in semantic["medium_lineage_candidates"]:
        klass, method = function_class_method(row["global_name"])
        if klass:
            medium_semantic_methods.add((klass, method))

    records: list[dict[str, Any]] = []

    # 2,372 classes.
    for row in sorted(lfs_records, key=lambda item: item["class"]):
        class_name = row["class"]
        short = cpp_short_class(class_name)
        impl, tests = repo_index.token_refs([short])
        semantic_count = high_semantic_classes.get(class_name, 0)
        records.append(fact(
            fact_id=f"class:{class_name}",
            domain="lfs_class",
            authority="CONFIRMED_GLOBAL_3_0_24_STATIC_CLIENT",
            classification=classify(
                authority="STRONG_GLOBAL",
                implementation_refs=impl,
            ),
            implementation_refs=impl,
            test_refs=tests,
            semantic_resolution=(
                "HIGH_CONFIDENCE_FUNCTION_SEMANTICS_PRESENT"
                if semantic_count
                else "STATIC_EXISTENCE_ONLY"
            ),
            evidence={
                "class": class_name,
                "category": row["category"],
                "evidence_owner": row["evidence_owner"],
                "method_count": row["method_count"],
                "high_confidence_semantic_function_count": semantic_count,
            },
        ))

    # 19,467 methods.
    for class_name in sorted(methods):
        class_short = cpp_short_class(class_name)
        for method_name in methods[class_name]:
            base = method_base(method_name)
            tokens = [class_short] + ([base] if base and base != class_short else [])
            impl, tests = repo_index.token_refs(tokens)
            key = (class_name, base)
            if key in high_semantic_methods:
                semantic_resolution = "HIGH_CONFIDENCE_FUNCTION_SEMANTICS_PRESENT"
            elif key in medium_semantic_methods:
                semantic_resolution = "MEDIUM_LINEAGE_CANDIDATE_ONLY"
            else:
                semantic_resolution = "STATIC_METHOD_EXISTENCE_ONLY"
            records.append(fact(
                fact_id=f"method:{class_name}::{method_name}",
                domain="lfs_method",
                authority="CONFIRMED_GLOBAL_3_0_24_STATIC_CLIENT",
                classification=classify(
                    authority="STRONG_GLOBAL",
                    implementation_refs=impl,
                ),
                implementation_refs=impl,
                test_refs=tests,
                semantic_resolution=semantic_resolution,
                evidence={
                    "class": class_name,
                    "method": method_name,
                },
            ))

    # 631 protocol messages.
    semantic_protocols = {
        ref["name"]
        for row in semantic["function_semantics"]
        for ref in row.get("protocol_references", [])
    }
    protocol_by_name = {row["name"]: row for row in protocol["messages"]}
    for item in sorted(message_catalog, key=lambda row: row["name"]):
        name = item["name"]
        impl, tests = repo_index.token_refs([name])
        schema = protocol_by_name.get(name, {})
        records.append(fact(
            fact_id=f"protocol:{name}",
            domain="protocol_message",
            authority="CONFIRMED_GLOBAL_3_0_24_PROTOCOL_ID",
            classification=classify(
                authority="STRONG_GLOBAL",
                implementation_refs=impl,
            ),
            implementation_refs=impl,
            test_refs=tests,
            semantic_resolution=(
                "BOUND_TO_GLOBAL_NATIVE_FUNCTION"
                if name in semantic_protocols
                else "PROTOCOL_SCHEMA_ONLY"
            ),
            evidence={
                "name": name,
                "id": item["id"],
                "hex": item["hex"],
                "direction": schema.get("direction"),
                "top_level_schema_evidence": schema.get("top_level_schema_evidence"),
            },
        ))

    # 533 constructor/types.
    for type_name in sorted(constructor_types):
        short = type_name.rsplit("::", 1)[-1]
        impl, tests = repo_index.token_refs([short])
        records.append(fact(
            fact_id=f"protocol-type:{type_name}",
            domain="protocol_constructor_type",
            authority="CONFIRMED_GLOBAL_3_0_24_CONSTRUCTOR_SURFACE",
            classification=classify(
                authority="STRONG_GLOBAL",
                implementation_refs=impl,
            ),
            implementation_refs=impl,
            test_refs=tests,
            evidence={"type": type_name},
        ))

    # Direct Global resources: 27 bootstrap + 14 recovered cache = 41.
    global_resource_nodes = [
        node for node in resources["nodes"]
        if node.get("kind") == "resource"
        and node.get("provenance") in GLOBAL_RESOURCE_PROVENANCE
    ]
    for node in sorted(global_resource_nodes, key=lambda item: item["id"]):
        literal = node.get("path") or ""
        impl, tests = repo_index.exact_refs(literal)
        records.append(fact(
            fact_id=node["id"],
            domain="global_resource",
            authority=node["provenance"],
            classification=classify(
                authority="STRONG_GLOBAL",
                implementation_refs=impl,
            ),
            implementation_refs=impl,
            test_refs=tests,
            evidence={
                key: node.get(key)
                for key in ("path", "size", "sha1", "sha256", "lineage_grade", "surface")
            },
        ))

    # Global bootstrap package members.
    global_members = [
        node for node in resources["nodes"]
        if node.get("kind") == "package_member"
        and node.get("provenance") in GLOBAL_MEMBER_PROVENANCE
    ]
    for node in sorted(global_members, key=lambda item: item["id"]):
        entry = node.get("entry") or ""
        package = node.get("package") or ""
        impl, tests = repo_index.exact_refs(entry)
        package_impl_refs, package_test_refs = repo_index.exact_refs(package)
        records.append(fact(
            fact_id=node["id"],
            domain="global_package_member",
            authority="CONFIRMED_GLOBAL_APK_MBN_MEMBER",
            classification=classify(
                authority="STRONG_GLOBAL",
                implementation_refs=impl,
            ),
            implementation_refs=impl,
            test_refs=tests,
            evidence={
                **{
                    key: node.get(key)
                    for key in ("package", "entry", "size", "sha256", "suffix")
                },
                "package_level_implementation_refs": package_impl_refs,
                "package_level_test_refs": package_test_refs,
                "coverage_rule": "member coverage requires the member entry itself; package-only references do not cover every member",
            },
        ))

    # Native resource path expectations are Global facts, but do not prove that
    # every formatted concrete ID existed historically.
    native_patterns = [
        node for node in resources["nodes"]
        if node.get("kind") == "native_resource_pattern"
        and node.get("provenance") == "GLOBAL_NATIVE_RESOURCE_PATH_LITERAL"
    ]
    for node in sorted(native_patterns, key=lambda item: item["id"]):
        pattern = node.get("pattern") or ""
        impl, tests = repo_index.exact_refs(pattern)
        records.append(fact(
            fact_id=node["id"],
            domain="global_native_resource_pattern",
            authority="CONFIRMED_GLOBAL_NATIVE_RESOURCE_PATH_LITERAL",
            classification=classify(
                authority="STRONG_GLOBAL",
                implementation_refs=impl,
            ),
            implementation_refs=impl,
            test_refs=tests,
            evidence={"pattern": pattern},
        ))

    # Changed-path lineage candidates stay weak by definition.
    for item in sorted(
        binder.get("changed_lineage_candidates", []),
        key=lambda row: row["global_path"],
    ):
        literal = item["global_path"]
        impl, tests = repo_index.exact_refs(literal)
        records.append(fact(
            fact_id=f"resource-lineage:{literal}",
            domain="resource_lineage_candidate",
            authority="CURRENT_JP_LINEAGE_REFERENCE_ONLY",
            classification=classify(
                authority="WEAKER_LINEAGE",
                implementation_refs=impl,
            ),
            implementation_refs=impl,
            test_refs=tests,
            semantic_resolution="BYTES_CHANGED_DO_NOT_BACKPORT",
            evidence=item,
        ))

    # Direct Global map package.
    for item in sorted(maps["global_packages"], key=lambda row: row["base_id"]):
        base_id = item["base_id"]
        path = item["path"]
        impl_id, tests_id = repo_index.token_refs([base_id])
        impl_path, tests_path = repo_index.exact_refs(path)
        impl = sorted(set(impl_id + impl_path))
        tests = sorted(set(tests_id + tests_path))
        records.append(fact(
            fact_id=f"global-map:{base_id}",
            domain="global_map_package",
            authority="RECOVERED_GLOBAL_CACHE",
            classification=classify(
                authority="STRONG_GLOBAL",
                implementation_refs=impl,
            ),
            implementation_refs=impl,
            test_refs=tests,
            evidence={
                "base_id": base_id,
                "path": path,
                "package_sha256": item["package_sha256"],
                "terrain": item.get("terrain"),
            },
        ))

    # Current-JP map inventory is useful lineage/reference only.
    for item in sorted(
        maps["jp_packages"],
        key=lambda row: (row["base_id"], row["category"], row["variant"], row["path"]),
    ):
        base_id = item["base_id"]
        impl, tests = repo_index.token_refs([base_id])
        records.append(fact(
            fact_id=f"jp-map-lineage:{item['path']}",
            domain="jp_map_lineage_reference",
            authority="CURRENT_JP_LINEAGE_REFERENCE_ONLY",
            classification=classify(
                authority="WEAKER_LINEAGE",
                implementation_refs=impl,
            ),
            implementation_refs=impl,
            test_refs=tests,
            semantic_resolution="NOT_HISTORICAL_GLOBAL_WITHOUT_PREDICATE",
            evidence={
                "base_id": base_id,
                "path": item["path"],
                "category": item["category"],
                "variant": item["variant"],
                "package_sha256": item["package_sha256"],
            },
        ))

    # 28 critical client transitions.
    semantic_transition = {
        row["transition_index"]: row
        for row in semantic["state_transition_coverage"]
    }
    for index, transition in enumerate(state["transitions"]):
        semantic_row = semantic_transition.get(index, {})
        impl_set: set[str] = set()
        test_set: set[str] = set()

        # A protocol transition is cross-linked only by the exact Global
        # message token. Generic prose in action/trigger text never counts.
        message = transition.get("message")
        if message:
            impl_refs, test_refs = repo_index.token_refs([message])
            impl_set.update(impl_refs)
            test_set.update(test_refs)

        # For non-message/client-local transitions, only directly bound Global
        # functions may establish an implementation cross-link.
        for function_name in semantic_row.get("bound_global_functions", []):
            klass, method = function_class_method(function_name)
            class_short = cpp_short_class(klass) if klass else ""
            method_short = method_base(method)
            tokens = [class_short] + (
                [method_short]
                if method_short and method_short != class_short
                else []
            )
            impl_refs, test_refs = repo_index.token_refs(tokens)
            impl_set.update(impl_refs)
            test_set.update(test_refs)

        impl = sorted(impl_set)
        tests = sorted(test_set)
        records.append(fact(
            fact_id=f"state-transition:{index}",
            domain="critical_state_transition",
            authority="CONFIRMED_GLOBAL_3_0_24_CLIENT_STATE_MACHINE",
            classification=classify(
                authority="STRONG_GLOBAL",
                implementation_refs=impl,
            ),
            implementation_refs=impl,
            test_refs=tests,
            semantic_resolution=(
                "BOUND_TO_GLOBAL_NATIVE_FUNCTION"
                if semantic_row.get("bound")
                else "NO_DIRECT_FUNCTION_BINDING"
            ),
            evidence={
                "index": index,
                "from": transition["from"],
                "to": transition["to"],
                "message": transition.get("message"),
                "trigger": transition.get("trigger"),
                "guard": transition.get("guard"),
                "action": transition.get("action"),
                "source_evidence": transition.get("evidence"),
                "bound_global_functions": semantic_row.get("bound_global_functions", []),
            },
        ))

    # External evidence ceilings are terminal facts, never recursive blockers.
    for index, ceiling in enumerate(complete["evidence_ceilings"]):
        records.append(fact(
            fact_id=f"external-ceiling:{index:02d}",
            domain="external_evidence_ceiling",
            authority="EXPLICIT_COMPLETENESS_LEDGER_CEILING",
            classification=EXTERNAL,
            implementation_refs=[],
            test_refs=[],
            semantic_resolution="TERMINAL_EXTERNAL_FACT",
            evidence={
                "text": ceiling,
                "terminal": True,
                "generate_research_child": False,
            },
        ))

    domain_counts: dict[str, Counter[str]] = defaultdict(Counter)
    total_classifications: Counter[str] = Counter()
    for row in records:
        domain_counts[row["domain"]][row["classification"]] += 1
        total_classifications[row["classification"]] += 1

    unbound_transitions = [
        row for row in semantic["state_transition_coverage"]
        if not row.get("bound")
    ]
    unresolved_functions = semantic["unresolved"]["global_function_names"]
    pattern_bound = binder["counts"].get("direct_global_patterns_bound", 0)
    pattern_total = binder["counts"].get("native_resource_patterns", len(native_patterns))

    canonical_gaps = [
        {
            "gap_key": "native-semantic-unresolved",
            "status": "RESEARCHABLE_BOUNDED",
            "count": len(unresolved_functions),
            "sample": unresolved_functions[:25],
            "research_task": {
                "suggested_id": "GAP-NATIVE-SEMANTICS-001",
                "scope": "Rank unresolved Global functions by direct critical-state/protocol/resource connectivity, then inspect only the bounded highest-impact set.",
                "max_new_children_for_gap": 1,
            },
        },
        {
            "gap_key": "critical-transition-function-binding",
            "status": "RESEARCHABLE_BOUNDED",
            "count": len(unbound_transitions),
            "sample": [row["transition_index"] for row in unbound_transitions[:25]],
            "research_task": {
                "suggested_id": "GAP-CRITICAL-TRANSITION-BINDING-001",
                "scope": "Resolve direct Global function bindings for currently unbound critical-loop state transitions using indexed native evidence only.",
                "max_new_children_for_gap": 1,
            },
        },
        {
            "gap_key": "native-resource-pattern-binding",
            "status": "RESEARCHABLE_BOUNDED",
            "count": max(0, pattern_total - pattern_bound),
            "sample": [],
            "research_task": {
                "suggested_id": "GAP-NATIVE-RESOURCE-BINDING-001",
                "scope": "Bind only Global native resource patterns that intersect critical-loop semantic functions or recovered Global packages.",
                "max_new_children_for_gap": 1,
            },
        },
        {
            "gap_key": "historical-runtime-server-and-remote-assets",
            "status": "TERMINAL_EXTERNAL_CEILING",
            "count": len(complete["evidence_ceilings"]),
            "sample": complete["evidence_ceilings"],
            "research_task": None,
        },
    ]

    # Exactly one candidate per canonical researchable gap, never recursive.
    research_candidates = [
        {
            **row["research_task"],
            "gap_key": row["gap_key"],
            "source_task": "GJP-EVIDENCE-CLOSURE-001",
            "parent_prefix_allowed": True,
            "forbidden_parent_prefixes": ["AUTO-RE-", "UNBLOCK-"],
            "auto_create": False,
            "auto_merge": False,
        }
        for row in canonical_gaps
        if row["status"] == "RESEARCHABLE_BOUNDED" and row["research_task"]
    ]
    if len({row["gap_key"] for row in research_candidates}) != len(research_candidates):
        raise RuntimeError("duplicate research candidate for canonical gap")

    expected_domain_totals = {
        "lfs_class": 2372,
        "lfs_method": 19467,
        "protocol_message": 631,
        "protocol_constructor_type": 533,
        "global_resource": len(global_resource_nodes),
        "global_package_member": len(global_members),
        "global_native_resource_pattern": len(native_patterns),
        "resource_lineage_candidate": len(binder.get("changed_lineage_candidates", [])),
        "global_map_package": len(maps["global_packages"]),
        "jp_map_lineage_reference": len(maps["jp_packages"]),
        "critical_state_transition": len(state["transitions"]),
        "external_evidence_ceiling": len(complete["evidence_ceilings"]),
    }
    actual_domain_totals = Counter(row["domain"] for row in records)
    if dict(actual_domain_totals) != expected_domain_totals:
        raise RuntimeError(
            f"domain total mismatch expected={expected_domain_totals} actual={dict(actual_domain_totals)}"
        )

    facts_sha256 = hashlib.sha256(
        json.dumps(
            records,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()

    core = {
        "facts_sha256": facts_sha256,
        "source_hashes": {
            "completeness": sha256_file(args.completeness),
            "method_catalog": sha256_file(args.method_catalog),
            "semantic_lift": sha256_file(args.semantic_lift),
            "protocol_schema": sha256_file(args.protocol_schema),
            "resource_graph": sha256_file(args.resource_graph),
            "map_genealogy": sha256_file(args.map_genealogy),
            "state_machine": sha256_file(args.state_machine),
            "asset_binder": sha256_file(args.asset_binder),
            "differential": sha256_file(args.differential),
        },
        "repo_base_sha": git_sha(args.repo),
        "domain_totals": expected_domain_totals,
        "classification_totals": dict(sorted(total_classifications.items())),
        "canonical_gaps": canonical_gaps,
    }
    closure_id = hashlib.sha256(
        json.dumps(core, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    return {
        "provenance": PROVENANCE,
        "closure_id": closure_id,
        "facts_sha256": facts_sha256,
        "historical_authority": "Global 3.0.24 / 2017-05-25",
        "current_jp_role": "LINEAGE_REFERENCE_ONLY",
        "repo_base_sha": core["repo_base_sha"],
        "sources": {
            name: {"path": str(getattr(args, name)), "sha256": digest}
            for name, digest in core["source_hashes"].items()
        },
        "coverage": {
            "facts_total": len(records),
            "domain_totals": expected_domain_totals,
            "classification_totals": dict(sorted(total_classifications.items())),
            "domain_classifications": {
                domain: dict(sorted(counter.items()))
                for domain, counter in sorted(domain_counts.items())
            },
            "required_exact_counts": {
                "lfs_classes": 2372,
                "lfs_methods": 19467,
                "protocol_messages": 631,
                "protocol_constructor_types": 533,
                "critical_state_transitions": len(state["transitions"]),
            },
            "differential_snapshot": differential["counts"],
        },
        "facts": records,
        "canonical_gaps": canonical_gaps,
        "research_task_candidates": research_candidates,
        "policy": {
            "implementation_crosslink": (
                "Only non-reverse src/ files count as gameplay implementation. "
                "Reverse/evidence modules do not self-satisfy implementation coverage."
            ),
            "tests": "tests/ references are tracked independently from implementation.",
            "global": "Direct Global static/client facts retain Global authority even when semantic behavior is incomplete.",
            "jp": "Current-JP-only maps/resources remain weaker lineage references and never backfill Global.",
            "external": "Documented external ceilings are terminal facts and generate no research children.",
            "recursion": "At most one candidate is emitted per canonical gap; AUTO-RE/UNBLOCK parents are forbidden.",
            "automation": "Research candidates are advisory only: no automatic task creation, merge or deployment occurs here.",
        },
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    root = Path("/home/ubuntu/logres/artifacts")
    p.add_argument("--repo", type=Path, default=Path.cwd())
    p.add_argument("--completeness", type=Path, default=root / "global-3024-completeness-ledger-20260924.json")
    p.add_argument("--method-catalog", type=Path, default=Path("/home/ubuntu/logres/private/global-apk/3.0.24/re/reports/lfs-class-methods.json"))
    p.add_argument("--semantic-lift", type=Path, default=root / "global-jp-semantic-lift-20260924.json")
    p.add_argument("--protocol-schema", type=Path, default=root / "global-jp-protocol-schema-20260924.json")
    p.add_argument("--resource-graph", type=Path, default=root / "global-jp-resource-semantic-graph-20260924.json")
    p.add_argument("--map-genealogy", type=Path, default=root / "global-jp-map-genealogy-20260924.json")
    p.add_argument("--state-machine", type=Path, default=root / "global-3024-state-machine-20260924.json")
    p.add_argument("--asset-binder", type=Path, default=root / "global-asset-behavior-bindings-20260924.json")
    p.add_argument("--differential", type=Path, default=root / "global3024-differential-emulator-20260924.json")
    p.add_argument("--output", type=Path, required=True)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    result = build(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "closure_id": result["closure_id"],
        "facts_total": result["coverage"]["facts_total"],
        "domain_totals": result["coverage"]["domain_totals"],
        "classification_totals": result["coverage"]["classification_totals"],
        "research_candidates": len(result["research_task_candidates"]),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
