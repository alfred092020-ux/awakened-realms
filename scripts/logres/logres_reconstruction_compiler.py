#!/usr/bin/env python3
"""Compile strong recovered Logres facts into bounded implementation packets.

This is an advisory/dry-run compiler. It reads the exhaustive closure artifact
and the provenance knowledge graph. It never writes task state, commits, merges,
deploys, or main.

Every packet is constrained to RECONSTRUCTED implementation confidence even
when its source evidence is CONFIRMED ORIGINAL. That distinction prevents a
reconstructed implementation from being mislabeled as original client code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterable

CLOSURE_PROVENANCE = (
    "OMEGA_EXHAUSTIVE_RECONSTRUCTION_CLOSURE_WITH_TERMINAL_CEILINGS"
)
SOURCE_TASK = "GJP-EVIDENCE-CLOSURE-001"
IMPLEMENTATION_CONFIDENCE = "RECONSTRUCTED"
HARD_PACKET_LIMIT = 50

CONFIDENCE_SCORE = {
    "CONFIRMED ORIGINAL": 1.00,
    "CONFIRMED": 1.00,
    "HIGH": 0.90,
    "SUPPORTED INFERENCE": 0.72,
    "INFERENCE": 0.72,
    "MEDIUM": 0.62,
    "RECONSTRUCTED": 0.58,
    "VERSION SENSITIVE": 0.45,
    "VERSION_SENSITIVE": 0.45,
    "LOW": 0.28,
    "UNRESOLVED": 0.10,
}

STRONG_GLOBAL_AUTHORITY_PREFIXES = (
    "CONFIRMED_GLOBAL_",
    "CONFIRMED_ORIGINAL_GLOBAL_",
    "RECOVERED_GLOBAL_",
)

ACTIONABLE_DOMAINS = {
    "critical_state_transition",
    "protocol_message",
    "global_map_package",
    "global_resource",
    "global_package_member",
    "lfs_class",
    "lfs_method",
}

DOMAIN_PRIORITY = {
    "critical_state_transition": 1000,
    "global_map_package": 950,
    "protocol_message": 900,
    "global_resource": 820,
    "global_package_member": 760,
    "lfs_method": 700,
    "lfs_class": 680,
}

CATEGORY_SCOPE = {
    "battle": "src/game/logres/battle/",
    "combat_misc": "src/game/logres/battle/",
    "field_world": "src/game/logres/field/",
    "boot_scene": "src/game/logres/onboarding/",
    "avatar_profile": "src/game/logres/onboarding/",
    "ui_gui": "src/game/logres/ui/",
    "network_protocol": "src/game/logres/protocol/",
    "quest_mission": "src/game/logres/systems/",
    "items_equipment": "src/game/logres/systems/",
    "jobs_progression": "src/game/logres/systems/",
    "social_clan_party_chat_mail": "src/game/logres/systems/",
    "economy_shop_gacha": "src/game/logres/systems/",
    "patch_update": "src/game/logres/patch/",
    "presentation_resources": "src/game/logres/assets/",
}

UNIVERSAL_DO_NOT_INFER = (
    "Do not infer retired-server validation, persistence, matchmaking, economy, "
    "dynamic event decisions, or payload values not present in the evidence.",
    "Do not use current-JP-only behavior or resources as historical Global truth "
    "without an explicit identity predicate.",
    "Do not describe reconstructed implementation code as CONFIRMED ORIGINAL or "
    "byte-identical original code.",
    "Do not broaden the packet beyond its listed evidence IDs and file scopes.",
)

RECURSIVE_PREFIXES = ("AUTO-RE-", "UNBLOCK-")


class CompilerError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_closure(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise CompilerError("closure must be a JSON object")
    if payload.get("provenance") != CLOSURE_PROVENANCE:
        raise CompilerError("input is not an OMEGA reconstruction closure")
    facts = payload.get("facts")
    if not isinstance(facts, list):
        raise CompilerError("closure facts must be a list")

    claimed = payload.get("facts_sha256")
    actual = hashlib.sha256(
        canonical_json(facts).encode("utf-8")
    ).hexdigest()
    if claimed != actual:
        raise CompilerError(
            f"closure fact hash mismatch: expected={claimed} actual={actual}"
        )
    return payload


def open_graph_readonly(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    required = {"knowledge_nodes", "knowledge_edges"}
    tables = {
        row[0]
        for row in conn.execute(
            "select name from sqlite_master where type='table'"
        )
    }
    missing = required - tables
    if missing:
        conn.close()
        raise CompilerError(
            f"provenance graph is missing tables: {sorted(missing)}"
        )
    return conn


def graph_provenance_bundle(
    conn: sqlite3.Connection,
    *,
    closure_path: Path,
    closure_sha256: str,
    closure_sources: dict[str, Any],
) -> dict[str, Any]:
    artifact_id = f"artifact:{closure_sha256}"
    artifact = conn.execute(
        """select node_id,kind,label,provenance,confidence,artifact_path,
                  artifact_sha
             from knowledge_nodes
            where node_id=?""",
        (artifact_id,),
    ).fetchone()
    if artifact is None:
        raise CompilerError(
            f"closure artifact node is absent from provenance graph: {artifact_id}"
        )
    if float(artifact["confidence"] or 0) < 0.90:
        raise CompilerError("closure artifact graph confidence is below 0.90")
    if str(artifact["artifact_sha"] or "") != closure_sha256:
        raise CompilerError("closure graph node hash disagrees with file hash")

    claim_rows = list(
        conn.execute(
            """select claim.node_id,claim.kind,claim.label,claim.provenance,
                      claim.confidence,claim.artifact_sha
                 from knowledge_edges evidence
                 join knowledge_nodes claim on claim.node_id=evidence.dst
                 join knowledge_edges supports
                   on supports.src=claim.node_id
                  and supports.relation='supports'
                where evidence.src=?
                  and evidence.relation='evidence_for'
                  and supports.dst=?
                order by claim.confidence desc,claim.node_id""",
            (artifact_id, f"task:{SOURCE_TASK}"),
        )
    )
    confirmed_claims = [
        row for row in claim_rows
        if float(row["confidence"] or 0) >= 0.90
    ]
    if not confirmed_claims:
        raise CompilerError(
            "no >=0.90 provenance claim links the closure artifact to its source task"
        )

    commit_rows = list(
        conn.execute(
            """select kn.node_id,kn.kind,kn.label,kn.provenance,
                      kn.confidence
                 from knowledge_edges produced
                 join knowledge_nodes kn on kn.node_id=produced.dst
                where produced.src=?
                  and produced.relation='produced'
                order by kn.confidence desc,kn.node_id""",
            (f"task:{SOURCE_TASK}",),
        )
    )

    source_artifact_nodes: dict[str, dict[str, Any]] = {}
    for source_name, source in closure_sources.items():
        if not isinstance(source, dict):
            continue
        digest = source.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            continue
        row = conn.execute(
            """select node_id,kind,label,provenance,confidence,artifact_sha
                 from knowledge_nodes
                where node_id=?""",
            (f"artifact:{digest}",),
        ).fetchone()
        if row is not None:
            source_artifact_nodes[str(source_name)] = dict(row)

    core_nodes = [
        dict(artifact),
        *[dict(row) for row in confirmed_claims],
        {
            "node_id": f"task:{SOURCE_TASK}",
            "kind": "task",
            "label": SOURCE_TASK,
            "provenance": "CONTROL_PLANE",
            "confidence": 1.0,
        },
        *[dict(row) for row in commit_rows],
    ]
    deduped = {}
    for row in core_nodes:
        deduped[row["node_id"]] = row

    return {
        "closure_path": str(closure_path),
        "closure_sha256": closure_sha256,
        "source_task_id": SOURCE_TASK,
        "core_graph_nodes": [
            deduped[key] for key in sorted(deduped)
        ],
        "source_graph_nodes": {
            key: source_artifact_nodes[key]
            for key in sorted(source_artifact_nodes)
        },
    }


def is_strong_global_fact(fact: dict[str, Any]) -> bool:
    authority = str(fact.get("authority") or "")
    return authority.startswith(STRONG_GLOBAL_AUTHORITY_PREFIXES)


def fact_actionability(
    fact: dict[str, Any],
) -> tuple[bool, str]:
    if fact.get("classification") != "evidence-known-not-implemented":
        return False, "classification is not evidence-known-not-implemented"
    if fact.get("domain") not in ACTIONABLE_DOMAINS:
        return False, "domain is not implementation-actionable"
    if not is_strong_global_fact(fact):
        return False, "authority is not direct/confirmed Global evidence"

    domain = fact["domain"]
    semantic = str(fact.get("semantic_resolution") or "")
    evidence = fact.get("evidence") or {}

    if domain in {"lfs_class", "lfs_method"}:
        if semantic != "HIGH_CONFIDENCE_FUNCTION_SEMANTICS_PRESENT":
            return False, "static class/method existence lacks high-confidence semantics"

    if domain == "protocol_message":
        if not evidence.get("top_level_schema_evidence"):
            return False, "protocol ID exists but top-level schema is unresolved"

    if domain == "global_package_member":
        if not evidence.get("sha256"):
            return False, "package member lacks exact content hash"

    if domain == "global_map_package":
        if not evidence.get("package_sha256"):
            return False, "map package lacks exact package hash"

    return True, "eligible"


def packet_priority(fact: dict[str, Any]) -> int:
    base = DOMAIN_PRIORITY.get(str(fact.get("domain")), 0)
    semantic = str(fact.get("semantic_resolution") or "")
    if semantic == "BOUND_TO_GLOBAL_NATIVE_FUNCTION":
        base += 50
    if semantic == "HIGH_CONFIDENCE_FUNCTION_SEMANTICS_PRESENT":
        base += 35

    evidence = fact.get("evidence") or {}
    text = " ".join(
        str(evidence.get(key) or "")
        for key in ("message", "from", "to", "path", "class", "method")
    ).upper()
    for token, bonus in (
        ("BATTLE_ENTRY", 80),
        ("CHARACTER", 70),
        ("ACCOUNT", 60),
        ("FIELD", 55),
        ("BATTLE", 50),
        ("QUEST", 35),
        ("REWARD", 35),
    ):
        if token in text:
            base += bonus
            break
    return base


def slug(value: str, limit: int = 52) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return normalized[:limit].rstrip("-") or "fact"


def scope_for_state_transition(evidence: dict[str, Any]) -> list[str]:
    text = " ".join(
        str(evidence.get(key) or "")
        for key in ("message", "from", "to", "trigger", "action")
    ).upper()
    if "BATTLE_ENTRY" in text or "ENCOUNTER" in text:
        return [
            "src/game/logres/encounter/",
            "src/game/logres/field/controllers/",
        ]
    if "BATTLE" in text or "REWARD" in text:
        return ["src/game/logres/battle/"]
    if any(token in text for token in ("FIELD", "AREA_", "CHAR_MOVE", "WARP", "NPC")):
        return ["src/game/logres/field/"]
    if any(token in text for token in ("TITLE", "ACCOUNT", "CHARACTER", "WORLD", "TERMS", "PREBEGIN")):
        return ["src/game/logres/onboarding/"]
    return ["src/game/logres/systems/"]


def scope_for_protocol(evidence: dict[str, Any]) -> list[str]:
    name = str(evidence.get("name") or "").upper()
    scopes = ["src/game/logres/protocol/"]
    if "BATTLE_ENTRY" in name or "ENCOUNTER" in name:
        scopes.append("src/game/logres/encounter/")
    elif "BATTLE" in name:
        scopes.append("src/game/logres/battle/")
    elif any(token in name for token in ("CHAR_MOVE", "AREA_", "FIELD_", "WARP", "WEATHER")):
        scopes.append("src/game/logres/field/")
    elif any(token in name for token in ("ACCOUNT", "CHARACTER", "WORLD")):
        scopes.append("src/game/logres/onboarding/")
    elif "QUEST" in name or "ITEM" in name or "GIFT" in name:
        scopes.append("src/game/logres/systems/")
    return scopes[:2]


def scopes_for_fact(fact: dict[str, Any]) -> list[str]:
    domain = fact["domain"]
    evidence = fact.get("evidence") or {}

    if domain == "critical_state_transition":
        scopes = scope_for_state_transition(evidence)
    elif domain == "protocol_message":
        scopes = scope_for_protocol(evidence)
    elif domain == "global_map_package":
        scopes = ["src/game/logres/field/", "src/game/logres/assets/"]
    elif domain in {"global_resource", "global_package_member"}:
        path = str(
            evidence.get("path")
            or evidence.get("package")
            or evidence.get("entry")
            or ""
        ).lower()
        if "battle" in path:
            scopes = ["src/game/logres/battle/", "src/game/logres/assets/"]
        elif path.startswith("map") or ".map" in path:
            scopes = ["src/game/logres/field/", "src/game/logres/assets/"]
        elif "characreate" in path:
            scopes = ["src/game/logres/onboarding/", "src/game/logres/assets/"]
        elif path.startswith("gui") or "title" in path:
            scopes = ["src/game/logres/ui/", "src/game/logres/assets/"]
        else:
            scopes = ["src/game/logres/assets/"]
    elif domain in {"lfs_class", "lfs_method"}:
        category = str(evidence.get("category") or "")
        scope = CATEGORY_SCOPE.get(category)
        if scope is None:
            raise CompilerError(
                f"no bounded implementation scope for category {category!r}"
            )
        scopes = [scope]
    else:
        raise CompilerError(f"unsupported actionable domain: {domain}")

    packet_stub = slug(fact["id"], 42)
    test_scope = f"tests/LogresCompiled_{packet_stub}.test.ts"
    return [*dict.fromkeys(scopes), test_scope]


def domain_do_not_infer(fact: dict[str, Any]) -> list[str]:
    domain = fact["domain"]
    extra = []
    if domain in {"protocol_message", "critical_state_transition"}:
        extra.append(
            "Do not invent the retired server's validation, response outcome, "
            "ordering decisions, or payload fields beyond the cited client evidence."
        )
    if domain in {"global_resource", "global_package_member"}:
        extra.append(
            "Do not infer runtime semantics merely from resource/package presence; "
            "wire only behavior independently supported by evidence."
        )
    if domain == "global_map_package":
        extra.append(
            "Do not infer a historical field-name/area assignment for the recovered "
            "static map package unless a direct Global crosswalk is cited."
        )
    if domain in {"lfs_class", "lfs_method"}:
        extra.append(
            "Do not infer behavior from symbol existence alone; implement only the "
            "high-confidence semantic predicates carried by this fact."
        )
    return [*UNIVERSAL_DO_NOT_INFER, *extra]


def acceptance_for_fact(fact: dict[str, Any]) -> list[str]:
    domain = fact["domain"]
    evidence = fact.get("evidence") or {}
    checks = [
        f"Implement only closure fact {fact['id']} at RECONSTRUCTED implementation confidence.",
        "Add focused deterministic Vitest coverage under the packet's exact test scope.",
        "Preserve all do-not-infer constraints and provenance labels in code/tests.",
        "Run the focused tests plus logres-gate fast before handoff.",
    ]
    if domain == "critical_state_transition":
        checks.insert(
            1,
            f"Preserve client transition {evidence.get('from')} -> "
            f"{evidence.get('to')} and its cited trigger/message/guard exactly.",
        )
    elif domain == "protocol_message":
        checks.insert(
            1,
            f"Preserve Global message {evidence.get('name')} "
            f"({evidence.get('hex') or evidence.get('id')}) and only its recovered top-level schema.",
        )
    elif domain == "global_map_package":
        checks.insert(
            1,
            f"Use recovered map package {evidence.get('base_id')} only with exact package hash {evidence.get('package_sha256')}.",
        )
    elif domain in {"global_resource", "global_package_member"}:
        checks.insert(
            1,
            "Verify the exact recovered resource/member identity or content hash before wiring it into runtime behavior.",
        )
    elif domain in {"lfs_class", "lfs_method"}:
        checks.insert(
            1,
            "Use the linked high-confidence Global semantic record; do not reconstruct behavior from the symbol name alone.",
        )
    return checks


def claim_text(fact: dict[str, Any]) -> str:
    domain = fact["domain"]
    evidence = fact.get("evidence") or {}
    if domain == "critical_state_transition":
        return (
            f"Reconstruct client transition {evidence.get('from')} -> "
            f"{evidence.get('to')} from closure fact {fact['id']}."
        )
    if domain == "protocol_message":
        return (
            f"Reconstruct the client-side surface for Global protocol message "
            f"{evidence.get('name')} from closure fact {fact['id']}."
        )
    if domain == "global_map_package":
        return (
            f"Integrate recovered Global map package {evidence.get('base_id')} "
            f"without adding unsupported historical area semantics."
        )
    if domain in {"global_resource", "global_package_member"}:
        label = evidence.get("path") or evidence.get("entry") or fact["id"]
        return f"Integrate recovered Global resource evidence {label} within bounded runtime scope."
    return f"Implement the high-confidence Global semantic surface represented by {fact['id']}."


def validate_requested_confidence(
    requested: str,
    *,
    source_graph_confidence: float,
) -> None:
    requested = requested.upper()
    if requested != IMPLEMENTATION_CONFIDENCE:
        raise CompilerError(
            "implementation packets must request RECONSTRUCTED confidence; "
            "CONFIRMED ORIGINAL describes evidence, not newly written code"
        )
    if source_graph_confidence < 0.90:
        raise CompilerError(
            "source provenance confidence is below the compiler's 0.90 implementation threshold"
        )


def relevant_graph_nodes(
    fact: dict[str, Any],
    graph_bundle: dict[str, Any],
) -> list[dict[str, Any]]:
    domain = str(fact.get("domain") or "")
    evidence = fact.get("evidence") or {}
    source_keys: list[str] = []

    if domain == "critical_state_transition":
        source_keys = ["state_machine"]
        if fact.get("semantic_resolution") == "BOUND_TO_GLOBAL_NATIVE_FUNCTION":
            source_keys.append("semantic_lift")
        if evidence.get("message"):
            source_keys.append("protocol_schema")
    elif domain == "protocol_message":
        source_keys = ["protocol_schema", "semantic_lift"]
    elif domain == "global_map_package":
        source_keys = ["map_genealogy", "asset_binder"]
    elif domain in {"global_resource", "global_package_member"}:
        source_keys = ["resource_graph", "asset_binder", "completeness"]
    elif domain in {"lfs_class", "lfs_method"}:
        source_keys = ["completeness", "method_catalog", "semantic_lift"]

    rows = list(graph_bundle["core_graph_nodes"])
    source_nodes = graph_bundle.get("source_graph_nodes") or {}
    for key in source_keys:
        row = source_nodes.get(key)
        if row is not None:
            rows.append(row)

    deduped = {row["node_id"]: row for row in rows}
    return [deduped[key] for key in sorted(deduped)]


def build_packet(
    fact: dict[str, Any],
    *,
    graph_bundle: dict[str, Any],
    requested_confidence: str,
) -> dict[str, Any]:
    eligible, reason = fact_actionability(fact)
    if not eligible:
        raise CompilerError(f"{fact.get('id')}: {reason}")

    graph_nodes = relevant_graph_nodes(fact, graph_bundle)
    graph_confidence = max(
        float(row.get("confidence") or 0)
        for row in graph_nodes
        if row.get("kind") in {"artifact", "claim"}
    )
    validate_requested_confidence(
        requested_confidence,
        source_graph_confidence=graph_confidence,
    )

    evidence_nodes = [
        {
            "id": f"closure-fact:{fact['id']}",
            "kind": "closure_fact",
            "authority": fact["authority"],
            "classification": fact["classification"],
        },
        *[
            {
                "id": row["node_id"],
                "kind": row.get("kind"),
                "provenance": row.get("provenance"),
                "confidence": row.get("confidence"),
            }
            for row in graph_nodes
        ],
    ]
    evidence_node_ids = sorted(
        {row["id"] for row in evidence_nodes}
    )

    payload_core = {
        "source_fact_ids": [fact["id"]],
        "requested_claim_confidence": requested_confidence,
        "allowed_confidence_grades": [IMPLEMENTATION_CONFIDENCE],
        "evidence_node_ids": evidence_node_ids,
        "file_scopes": scopes_for_fact(fact),
        "claim": claim_text(fact),
    }
    fingerprint = hashlib.sha256(
        canonical_json(payload_core).encode("utf-8")
    ).hexdigest()

    return {
        "schema": "logres-reconstruction-packet-v1",
        "packet_id": (
            f"RECON-{slug(fact['domain'], 18).upper()}-"
            f"{fingerprint[:12].upper()}"
        ),
        "packet_fingerprint": fingerprint,
        "work_type": "implementation",
        "source_task_id": SOURCE_TASK,
        "claim": payload_core["claim"],
        "requested_claim_confidence": requested_confidence,
        "source_evidence_authority": fact["authority"],
        "source_fact_classification": fact["classification"],
        "allowed_confidence_grades": [IMPLEMENTATION_CONFIDENCE],
        "evidence_node_ids": evidence_node_ids,
        "evidence_nodes": evidence_nodes,
        "source_fact_ids": [fact["id"]],
        "source_fact": {
            "id": fact["id"],
            "domain": fact["domain"],
            "authority": fact["authority"],
            "semantic_resolution": fact.get("semantic_resolution"),
            "evidence": fact.get("evidence"),
        },
        "evidence_predicates": [
            "source closure classification == evidence-known-not-implemented",
            "source authority is direct/confirmed Global evidence",
            "source provenance graph has >=0.90 closure support",
            "requested implementation confidence == RECONSTRUCTED",
            "no current-JP-only or external/unresolved predicate is promoted",
        ],
        "file_scopes": payload_core["file_scopes"],
        "acceptance_tests": acceptance_for_fact(fact),
        "do_not_infer": domain_do_not_infer(fact),
        "automation": {
            "create_task": False,
            "write_code": False,
            "commit": False,
            "merge": False,
            "deploy": False,
            "modify_main": False,
        },
        "integration_authority": (
            "Existing serialized Logres Lead integration/preflight remains authoritative."
        ),
    }


def validate_packet(packet: dict[str, Any]) -> list[str]:
    errors = []
    if packet.get("schema") != "logres-reconstruction-packet-v1":
        errors.append("unsupported packet schema")
    if packet.get("work_type") != "implementation":
        errors.append("packet work_type must be implementation")
    if packet.get("source_task_id", "").startswith(RECURSIVE_PREFIXES):
        errors.append("recursive AUTO-RE/UNBLOCK source task is forbidden")
    if packet.get("requested_claim_confidence") != IMPLEMENTATION_CONFIDENCE:
        errors.append("implementation confidence promotion is forbidden")
    if packet.get("allowed_confidence_grades") != [IMPLEMENTATION_CONFIDENCE]:
        errors.append("allowed confidence grades must be exactly [RECONSTRUCTED]")
    authority = str(packet.get("source_evidence_authority") or "")
    if not authority.startswith(STRONG_GLOBAL_AUTHORITY_PREFIXES):
        errors.append("packet source authority is weaker than a Global implementation predicate")
    if packet.get("source_fact_classification") != "evidence-known-not-implemented":
        errors.append("packet source fact is not an evidence-known implementation gap")
    for key in ("evidence_node_ids", "file_scopes", "acceptance_tests", "do_not_infer"):
        if not packet.get(key):
            errors.append(f"packet requires non-empty {key}")
    automation = packet.get("automation") or {}
    if any(bool(value) for value in automation.values()):
        errors.append("reconstruction packet exposes an automatic mutation action")

    fingerprint_core = {
        "source_fact_ids": packet.get("source_fact_ids"),
        "requested_claim_confidence": packet.get("requested_claim_confidence"),
        "allowed_confidence_grades": packet.get("allowed_confidence_grades"),
        "evidence_node_ids": packet.get("evidence_node_ids"),
        "file_scopes": packet.get("file_scopes"),
        "claim": packet.get("claim"),
    }
    expected = hashlib.sha256(
        canonical_json(fingerprint_core).encode("utf-8")
    ).hexdigest()
    if packet.get("packet_fingerprint") != expected:
        errors.append("packet fingerprint mismatch")
    return errors


def compile_packets(
    closure: dict[str, Any],
    graph_bundle: dict[str, Any],
    *,
    requested_confidence: str = IMPLEMENTATION_CONFIDENCE,
    fact_ids: set[str] | None = None,
    domains: set[str] | None = None,
    limit: int = 12,
) -> dict[str, Any]:
    if limit < 1 or limit > HARD_PACKET_LIMIT:
        raise CompilerError(
            f"limit must be between 1 and {HARD_PACKET_LIMIT}"
        )

    selected = []
    rejected = []
    found_fact_ids = set()
    class_categories = {
        str(fact.get("evidence", {}).get("class") or ""): str(
            fact.get("evidence", {}).get("category") or ""
        )
        for fact in closure["facts"]
        if fact.get("domain") == "lfs_class"
    }

    for fact in closure["facts"]:
        fact_id = str(fact.get("id") or "")
        if fact_ids is not None and fact_id not in fact_ids:
            continue
        if fact_ids is not None:
            found_fact_ids.add(fact_id)
        if domains is not None and fact.get("domain") not in domains:
            continue

        eligible, reason = fact_actionability(fact)
        if not eligible:
            if fact_ids is not None:
                rejected.append({"fact_id": fact_id, "reason": reason})
            continue

        packet_fact = fact
        if fact.get("domain") == "lfs_method":
            evidence = dict(fact.get("evidence") or {})
            category = class_categories.get(str(evidence.get("class") or ""))
            if not category or category not in CATEGORY_SCOPE:
                if fact_ids is not None:
                    rejected.append({
                        "fact_id": fact_id,
                        "reason": "no bounded category scope for semantic method",
                    })
                continue
            evidence["category"] = category
            packet_fact = {**fact, "evidence": evidence}
        selected.append(packet_fact)

    if fact_ids is not None:
        missing = sorted(fact_ids - found_fact_ids)
        if missing:
            raise CompilerError(f"unknown closure fact IDs: {missing}")
        if rejected:
            raise CompilerError(
                "requested facts are not implementation-eligible: "
                + canonical_json(rejected)
            )

    selected.sort(
        key=lambda fact: (
            -packet_priority(fact),
            str(fact["domain"]),
            str(fact["id"]),
        )
    )
    selected = selected[:limit]

    packets = [
        build_packet(
            fact,
            graph_bundle=graph_bundle,
            requested_confidence=requested_confidence,
        )
        for fact in selected
    ]
    packet_errors = {
        packet["packet_id"]: errors
        for packet in packets
        if (errors := validate_packet(packet))
    }
    if packet_errors:
        raise CompilerError(
            "generated packet validation failed: "
            + canonical_json(packet_errors)
        )

    output_core = {
        "closure_id": closure["closure_id"],
        "closure_facts_sha256": closure["facts_sha256"],
        "requested_confidence": requested_confidence,
        "packet_fingerprints": [
            packet["packet_fingerprint"] for packet in packets
        ],
    }
    compiler_run_id = hashlib.sha256(
        canonical_json(output_core).encode("utf-8")
    ).hexdigest()

    return {
        "schema": "logres-reconstruction-compiler-output-v1",
        "provenance": "OMEGA_BOUNDED_RECONSTRUCTION_PACKET_COMPILER",
        "compiler_run_id": compiler_run_id,
        "closure_id": closure["closure_id"],
        "closure_facts_sha256": closure["facts_sha256"],
        "historical_authority": closure["historical_authority"],
        "current_jp_role": closure["current_jp_role"],
        "knowledge_graph": graph_bundle,
        "selection": {
            "requested_confidence": requested_confidence,
            "domains": sorted(domains) if domains else None,
            "fact_ids": sorted(fact_ids) if fact_ids else None,
            "limit": limit,
            "eligible_seen": len(selected),
        },
        "packets": packets,
        "counts": {
            "packets": len(packets),
            "critical_state_transition_packets": sum(
                packet["source_fact"]["domain"] == "critical_state_transition"
                for packet in packets
            ),
        },
        "automation": {
            "control_db_writes": False,
            "task_creation": False,
            "code_writes": False,
            "commit": False,
            "merge": False,
            "deploy": False,
            "modify_main": False,
        },
        "policy": {
            "implementation_confidence": (
                "New implementation is always RECONSTRUCTED even when source "
                "evidence is CONFIRMED ORIGINAL."
            ),
            "weak_evidence": (
                "JP-only, version-sensitive, external and unresolved facts "
                "cannot produce Global implementation packets."
            ),
            "recursive_research": (
                "Compiler produces implementation packets only and rejects "
                "AUTO-RE/UNBLOCK recursion."
            ),
            "integration": (
                "Packet output is advisory; Lead serialized preflight/integration "
                "remains the only merge path."
            ),
        },
    }


def parse_csv(values: list[str] | None) -> set[str] | None:
    if not values:
        return None
    result = set()
    for value in values:
        result.update(item.strip() for item in value.split(",") if item.strip())
    return result or None


def compile_command(args: argparse.Namespace) -> int:
    closure = load_closure(args.closure)
    closure_sha = sha256_file(args.closure)
    conn = open_graph_readonly(args.database)
    try:
        graph_bundle = graph_provenance_bundle(
            conn,
            closure_path=args.closure,
            closure_sha256=closure_sha,
            closure_sources=closure.get("sources", {}),
        )
        output = compile_packets(
            closure,
            graph_bundle,
            requested_confidence=args.requested_confidence,
            fact_ids=parse_csv(args.fact_id),
            domains=parse_csv(args.domain),
            limit=args.limit,
        )
    finally:
        conn.close()

    text = json.dumps(output, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")
    return 0


def validate_command(args: argparse.Namespace) -> int:
    value = json.loads(args.packet.read_text())
    packets = value.get("packets") if isinstance(value, dict) else None
    if packets is None:
        packets = [value]
    if not isinstance(packets, list):
        raise CompilerError("packet input must contain a packets list or one packet object")
    errors = {
        str(packet.get("packet_id") or index): validate_packet(packet)
        for index, packet in enumerate(packets)
        if isinstance(packet, dict)
        and validate_packet(packet)
    }
    if errors:
        print(json.dumps({"status": "REJECTED", "errors": errors}, indent=2, sort_keys=True))
        return 2
    print(json.dumps({"status": "PASS", "packets": len(packets)}, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    root = Path("/home/ubuntu/logres")
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    compile_p = sub.add_parser("compile")
    compile_p.add_argument(
        "--closure",
        type=Path,
        default=root / "artifacts/global-reconstruction-closure-20260924.json",
    )
    compile_p.add_argument(
        "--database",
        type=Path,
        default=root / "control/control.sqlite",
    )
    compile_p.add_argument("--output", type=Path)
    compile_p.add_argument("--limit", type=int, default=12)
    compile_p.add_argument("--domain", action="append")
    compile_p.add_argument("--fact-id", action="append")
    compile_p.add_argument(
        "--requested-confidence",
        default=IMPLEMENTATION_CONFIDENCE,
    )
    compile_p.set_defaults(func=compile_command)

    validate_p = sub.add_parser("validate")
    validate_p.add_argument("packet", type=Path)
    validate_p.set_defaults(func=validate_command)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (CompilerError, OSError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(json.dumps({
            "status": "REJECTED",
            "error": type(exc).__name__,
            "message": str(exc),
        }, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
