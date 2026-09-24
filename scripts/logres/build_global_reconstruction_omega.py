#!/usr/bin/env python3
"""Build the deterministic OMEGA Logres reconstruction knowledge base.

The SQLite database unifies Global-first reconstruction facts, semantics,
protocols, resource/map lineage, state/behavior models, implementation links,
compiler packets, contradiction arbitration, consistency status and terminal
external ceilings.

No new historical fact is inferred here. The database is an indexed assembly of
existing evidence with canonical provenance grades and strict same-authority
claim-head conflict rejection.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
from typing import Any, Iterable

PROVENANCE = "OMEGA_DETERMINISTIC_GLOBAL_RECONSTRUCTION_KNOWLEDGE_BASE"

CANONICAL_GRADES = (
    "GLOBAL_DIRECT",
    "GLOBAL_BINARY_DERIVED",
    "GLOBAL_JP_IDENTICAL",
    "SAME_ERA_JP_CORROBORATED",
    "JP_LINEAGE_SUPPORTED",
    "IMPLEMENTATION_VERIFIED",
    "EXTERNAL_CEILING",
)
GRADE_RANK = {grade: index for index, grade in enumerate(CANONICAL_GRADES)}

GLOBAL_SCOPE = "GLOBAL_3_0_24_2017_05_25"
CURRENT_JP_SCOPE = "CURRENT_JP_2026_09_24"
IMPLEMENTATION_SCOPE = "RECONSTRUCTION_CANONICAL"

HEX64 = set("0123456789abcdef")


class OmegaError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def valid_sha256(value: str | None) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in HEX64 for char in value.lower())
    )


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise OmegaError(f"{path}: expected JSON object")
    return value


def repo_sha(repo: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        pragma journal_mode=OFF;
        pragma synchronous=OFF;
        pragma temp_store=MEMORY;
        pragma locking_mode=EXCLUSIVE;
        pragma foreign_keys=ON;
        pragma page_size=4096;
        pragma auto_vacuum=NONE;
        pragma application_id=1279545165;
        pragma user_version=1;

        create table metadata(
          key text primary key,
          value text not null
        ) without rowid;

        create table provenance_grades(
          grade text primary key,
          rank integer not null unique
        ) without rowid;

        create table artifacts(
          artifact_id text primary key,
          path text not null,
          sha256 text not null,
          bytes integer,
          provenance text,
          role text not null,
          unique(path,sha256)
        ) without rowid;

        create table claims(
          claim_id text primary key,
          claim_key text not null,
          domain text not null,
          version_scope text not null,
          provenance_grade text not null references provenance_grades(grade),
          authority_rank integer not null,
          payload_sha256 text not null,
          payload_json text not null,
          source_fact_id text,
          implementation_status text,
          historical_claim integer not null check(historical_claim in (0,1))
        ) without rowid;

        create table claim_heads(
          claim_key text not null,
          provenance_grade text not null references provenance_grades(grade),
          version_scope text not null,
          claim_id text not null references claims(claim_id),
          payload_sha256 text not null,
          primary key(claim_key,provenance_grade,version_scope)
        ) without rowid;

        create table claim_evidence(
          claim_id text not null references claims(claim_id),
          artifact_id text not null references artifacts(artifact_id),
          evidence_role text not null,
          evidence_path text not null,
          evidence_sha256 text not null,
          primary key(claim_id,artifact_id,evidence_role)
        ) without rowid;

        create table function_semantics(
          global_function text primary key,
          global_address_hex text,
          global_size integer,
          jp_name text,
          match_tier text,
          lineage_predicate text,
          match_score real,
          protocol_refs_json text not null,
          state_reads_json text not null,
          state_writes_json text not null,
          semantic_tags_json text not null,
          control_flow_json text not null,
          literals_json text not null,
          payload_sha256 text not null
        ) without rowid;

        create table protocol_messages(
          name text primary key,
          opcode_hex text,
          opcode_u32 integer,
          direction text,
          top_level_schema_evidence text,
          fields_json text not null,
          lineage_json text not null,
          payload_sha256 text not null
        ) without rowid;

        create table resource_nodes(
          node_id text primary key,
          kind text,
          provenance text,
          canonical_grade text references provenance_grades(grade),
          path text,
          payload_sha256 text not null,
          payload_json text not null
        ) without rowid;

        create table resource_edges(
          edge_id text primary key,
          src text,
          dst text,
          relation text,
          payload_sha256 text not null,
          payload_json text not null
        ) without rowid;

        create table maps(
          map_key text primary key,
          record_kind text not null,
          version_scope text not null,
          base_id text,
          provenance_grade text not null references provenance_grades(grade),
          path text,
          package_sha256 text,
          payload_sha256 text not null,
          payload_json text not null
        ) without rowid;

        create table state_transitions(
          transition_index integer primary key,
          from_state text not null,
          to_state text not null,
          message text,
          trigger text,
          guard text,
          action text,
          evidence text,
          bound_global_functions_json text not null,
          payload_sha256 text not null
        );

        create table behavior_rules(
          rule_key text primary key,
          payload_sha256 text not null,
          payload_json text not null
        ) without rowid;

        create table implementation_links(
          link_id text primary key,
          source_fact_id text not null,
          path text not null,
          link_kind text not null,
          file_sha256 text,
          exists_now integer not null check(exists_now in (0,1))
        ) without rowid;

        create table reconstruction_packets(
          packet_id text primary key,
          packet_fingerprint text not null,
          source_fact_id text,
          requested_claim_confidence text,
          file_scopes_json text not null,
          evidence_node_ids_json text not null,
          acceptance_tests_json text not null,
          do_not_infer_json text not null,
          payload_sha256 text not null,
          payload_json text not null
        ) without rowid;

        create table contradictions(
          task_id text primary key,
          status text not null,
          rationale text,
          winner_authorities_json text not null,
          winner_claims_json text not null,
          loser_claims_json text not null,
          external_ceilings_json text not null,
          payload_sha256 text not null
        ) without rowid;

        create table consistency_invariants(
          invariant_id text primary key,
          status text not null,
          severity text,
          statement text,
          details_json text not null
        ) without rowid;

        create table coverage(
          domain text not null,
          classification text not null,
          count integer not null,
          primary key(domain,classification)
        ) without rowid;

        create table external_ceilings(
          ceiling_id text primary key,
          text text not null,
          source_fact_id text not null
        ) without rowid;

        create index idx_claims_domain on claims(domain);
        create index idx_claims_grade on claims(provenance_grade);
        create index idx_claims_source_fact on claims(source_fact_id);
        create index idx_claim_evidence_artifact on claim_evidence(artifact_id);
        create index idx_impl_links_source_fact on implementation_links(source_fact_id);
        create index idx_resource_nodes_kind on resource_nodes(kind);
        create index idx_resource_edges_relation on resource_edges(relation);
        """
    )


def register_artifact(
    conn: sqlite3.Connection,
    path: Path,
    *,
    expected_sha256: str | None = None,
    provenance: str | None = None,
    role: str,
) -> str:
    if not path.is_file():
        raise OmegaError(f"required evidence path does not exist: {path}")
    digest = sha256_file(path)
    if expected_sha256 and digest != expected_sha256:
        raise OmegaError(
            f"artifact hash mismatch for {path}: expected={expected_sha256} actual={digest}"
        )
    artifact_id = f"sha256:{digest}"
    conn.execute(
        """insert or ignore into artifacts(
             artifact_id,path,sha256,bytes,provenance,role
           ) values(?,?,?,?,?,?)""",
        (
            artifact_id,
            str(path),
            digest,
            path.stat().st_size,
            provenance,
            role,
        ),
    )
    return artifact_id


def register_virtual_artifact(
    conn: sqlite3.Connection,
    *,
    path: str,
    digest: str,
    provenance: str | None,
    role: str,
) -> str:
    if not valid_sha256(digest):
        raise OmegaError(f"invalid virtual artifact hash for {path}: {digest}")
    artifact_id = f"sha256:{digest}"
    conn.execute(
        """insert or ignore into artifacts(
             artifact_id,path,sha256,bytes,provenance,role
           ) values(?,?,?,?,?,?)""",
        (artifact_id, path, digest, None, provenance, role),
    )
    return artifact_id


def add_claim_evidence(
    conn: sqlite3.Connection,
    claim_id: str,
    artifact_id: str,
    role: str,
) -> None:
    row = conn.execute(
        "select path,sha256 from artifacts where artifact_id=?",
        (artifact_id,),
    ).fetchone()
    if row is None:
        raise OmegaError(f"unknown artifact_id {artifact_id}")
    conn.execute(
        """insert or ignore into claim_evidence(
             claim_id,artifact_id,evidence_role,evidence_path,evidence_sha256
           ) values(?,?,?,?,?)""",
        (claim_id, artifact_id, role, row[0], row[1]),
    )


def insert_claim(
    conn: sqlite3.Connection,
    *,
    claim_id: str,
    claim_key: str,
    domain: str,
    version_scope: str,
    provenance_grade: str,
    payload: Any,
    source_fact_id: str | None,
    implementation_status: str | None,
    historical_claim: bool,
    evidence_artifacts: Iterable[tuple[str, str]],
) -> str:
    if provenance_grade not in GRADE_RANK:
        raise OmegaError(f"noncanonical provenance grade: {provenance_grade}")
    payload_json = canonical_json(payload)
    payload_sha = sha256_bytes(payload_json.encode("utf-8"))

    head = conn.execute(
        """select claim_id,payload_sha256 from claim_heads
            where claim_key=? and provenance_grade=? and version_scope=?""",
        (claim_key, provenance_grade, version_scope),
    ).fetchone()
    if head is not None:
        if head[1] != payload_sha:
            raise OmegaError(
                "same-authority contradiction rejected: "
                f"claim_key={claim_key} grade={provenance_grade} "
                f"scope={version_scope} existing={head[1]} incoming={payload_sha}"
            )
        existing_id = str(head[0])
        for artifact_id, role in evidence_artifacts:
            add_claim_evidence(conn, existing_id, artifact_id, role)
        return existing_id

    conn.execute(
        """insert into claims(
             claim_id,claim_key,domain,version_scope,provenance_grade,
             authority_rank,payload_sha256,payload_json,source_fact_id,
             implementation_status,historical_claim
           ) values(?,?,?,?,?,?,?,?,?,?,?)""",
        (
            claim_id,
            claim_key,
            domain,
            version_scope,
            provenance_grade,
            GRADE_RANK[provenance_grade],
            payload_sha,
            payload_json,
            source_fact_id,
            implementation_status,
            1 if historical_claim else 0,
        ),
    )
    conn.execute(
        """insert into claim_heads(
             claim_key,provenance_grade,version_scope,claim_id,payload_sha256
           ) values(?,?,?,?,?)""",
        (
            claim_key,
            provenance_grade,
            version_scope,
            claim_id,
            payload_sha,
        ),
    )
    for artifact_id, role in evidence_artifacts:
        add_claim_evidence(conn, claim_id, artifact_id, role)
    return claim_id


def canonical_grade_for_fact(fact: dict[str, Any]) -> tuple[str, str, bool]:
    domain = str(fact.get("domain") or "")
    authority = str(fact.get("authority") or "")
    classification = str(fact.get("classification") or "")

    if classification == "externally-unrecoverable":
        return "EXTERNAL_CEILING", GLOBAL_SCOPE, False
    if authority == "CURRENT_JP_LINEAGE_REFERENCE_ONLY":
        return "JP_LINEAGE_SUPPORTED", CURRENT_JP_SCOPE, False
    if domain in {
        "lfs_class",
        "lfs_method",
        "protocol_constructor_type",
        "global_native_resource_pattern",
    }:
        return "GLOBAL_BINARY_DERIVED", GLOBAL_SCOPE, True
    if authority.startswith("CONFIRMED_GLOBAL_") or authority.startswith(
        "RECOVERED_GLOBAL_"
    ):
        return "GLOBAL_DIRECT", GLOBAL_SCOPE, True
    if authority.startswith("CONFIRMED_ORIGINAL_GLOBAL_"):
        return "GLOBAL_DIRECT", GLOBAL_SCOPE, True
    raise OmegaError(
        f"closure fact lacks canonical provenance mapping: {fact.get('id')} {authority}"
    )


def source_keys_for_fact(fact: dict[str, Any]) -> list[str]:
    domain = str(fact.get("domain") or "")
    semantic = str(fact.get("semantic_resolution") or "")
    if domain == "lfs_class":
        return ["completeness", "method_catalog", "semantic_lift"]
    if domain == "lfs_method":
        keys = ["method_catalog"]
        if semantic == "HIGH_CONFIDENCE_FUNCTION_SEMANTICS_PRESENT":
            keys.append("semantic_lift")
        return keys
    if domain in {"protocol_message", "protocol_constructor_type"}:
        return ["protocol_schema"]
    if domain in {
        "global_resource",
        "global_package_member",
        "global_native_resource_pattern",
        "resource_lineage_candidate",
    }:
        return ["resource_graph", "asset_binder"]
    if domain in {"global_map_package", "jp_map_lineage_reference"}:
        return ["map_genealogy", "asset_binder"]
    if domain == "critical_state_transition":
        keys = ["state_machine"]
        if semantic == "BOUND_TO_GLOBAL_NATIVE_FUNCTION":
            keys.append("semantic_lift")
        return keys
    if domain == "external_evidence_ceiling":
        return ["completeness"]
    return ["completeness"]


def add_source_artifacts(
    conn: sqlite3.Connection,
    closure: dict[str, Any],
) -> dict[str, str]:
    result = {}
    for key, source in sorted(closure.get("sources", {}).items()):
        if not isinstance(source, dict):
            continue
        path = source.get("path")
        digest = source.get("sha256")
        if not isinstance(path, str) or not isinstance(digest, str):
            continue
        p = Path(path)
        if p.is_file():
            result[key] = register_artifact(
                conn,
                p,
                expected_sha256=digest,
                provenance="CLOSURE_SOURCE",
                role=f"closure_source:{key}",
            )
        else:
            result[key] = register_virtual_artifact(
                conn,
                path=path,
                digest=digest,
                provenance="CLOSURE_SOURCE_UNMOUNTED",
                role=f"closure_source:{key}",
            )
    return result


def insert_closure_claims(
    conn: sqlite3.Connection,
    *,
    closure: dict[str, Any],
    closure_artifact_id: str,
    source_artifacts: dict[str, str],
    repo: Path,
) -> None:
    id_counts = Counter(str(fact["id"]) for fact in closure["facts"])
    for fact_id, count in sorted(id_counts.items()):
        if count <= 1:
            continue
        domains = {
            str(fact.get("domain") or "")
            for fact in closure["facts"]
            if str(fact["id"]) == fact_id
        }
        if domains != {"resource_lineage_candidate"}:
            raise OmegaError(
                "duplicate closure fact ID is only allowed for explicit "
                f"multi-valued resource lineage candidates: {fact_id} domains={sorted(domains)}"
            )

    def fact_sort_key(row: dict[str, Any]) -> tuple[str, str]:
        return (
            str(row["id"]),
            sha256_bytes(canonical_json(row).encode("utf-8")),
        )

    for fact in sorted(closure["facts"], key=fact_sort_key):
        fact_id = str(fact["id"])
        payload_sha = sha256_bytes(canonical_json(fact).encode("utf-8"))
        if id_counts[fact_id] > 1:
            global_node = str(
                (fact.get("evidence") or {}).get("global_resource_node")
                or payload_sha[:16]
            )
            fact_instance_id = f"{fact_id}#{global_node}"
            fact_claim_key = f"fact:{fact_id}:{global_node}"
        else:
            fact_instance_id = fact_id
            fact_claim_key = f"fact:{fact_id}"

        grade, scope, historical = canonical_grade_for_fact(fact)
        evidence = [(closure_artifact_id, "closure_fact")]
        for key in source_keys_for_fact(fact):
            artifact_id = source_artifacts.get(key)
            if artifact_id:
                evidence.append((artifact_id, f"source:{key}"))

        insert_claim(
            conn,
            claim_id=f"fact:{fact_instance_id}",
            claim_key=fact_claim_key,
            domain=str(fact["domain"]),
            version_scope=scope,
            provenance_grade=grade,
            payload=fact,
            source_fact_id=fact_instance_id,
            implementation_status=str(fact.get("classification") or ""),
            historical_claim=historical,
            evidence_artifacts=evidence,
        )

        if grade == "EXTERNAL_CEILING":
            text = str((fact.get("evidence") or {}).get("text") or "")
            conn.execute(
                """insert into external_ceilings(ceiling_id,text,source_fact_id)
                   values(?,?,?)""",
                (f"ceiling:{fact_instance_id}", text, fact_instance_id),
            )

        implementation_refs = sorted(
            set(
                list(fact.get("implementation_refs") or [])
                + list(fact.get("test_refs") or [])
            )
        )
        for rel in implementation_refs:
            path = repo / rel
            exists = path.is_file()
            digest = sha256_file(path) if exists else None
            link_kind = (
                "test"
                if rel.startswith("tests/")
                else "implementation"
            )
            link_id = sha256_bytes(
                f"{fact_instance_id}|{link_kind}|{rel}".encode()
            )
            conn.execute(
                """insert into implementation_links(
                     link_id,source_fact_id,path,link_kind,file_sha256,exists_now
                   ) values(?,?,?,?,?,?)""",
                (
                    link_id,
                    fact_instance_id,
                    rel,
                    link_kind,
                    digest,
                    1 if exists else 0,
                ),
            )

        if implementation_refs:
            code_evidence: list[tuple[str, str]] = [
                (closure_artifact_id, "implementation_link_source")
            ]
            current_files = []
            for rel in implementation_refs:
                path = repo / rel
                if not path.is_file():
                    continue
                artifact_id = register_artifact(
                    conn,
                    path,
                    provenance="CURRENT_CANONICAL_RECONSTRUCTION",
                    role="implementation_or_test",
                )
                code_evidence.append((artifact_id, "current_file"))
                current_files.append(
                    {
                        "path": rel,
                        "sha256": sha256_file(path),
                        "kind": (
                            "test" if rel.startswith("tests/") else "implementation"
                        ),
                    }
                )

            insert_claim(
                conn,
                claim_id=f"implementation:{fact_instance_id}",
                claim_key=f"implementation:{fact_instance_id}",
                domain="implementation_link",
                version_scope=IMPLEMENTATION_SCOPE,
                provenance_grade="IMPLEMENTATION_VERIFIED",
                payload={
                    "source_fact_id": fact_instance_id,
                    "closure_classification": fact.get("classification"),
                    "files": current_files,
                    "historical_authority_grade": grade,
                    "historical_truth_promoted": False,
                },
                source_fact_id=fact_instance_id,
                implementation_status="CURRENT_FILE_HASH_VERIFIED",
                historical_claim=False,
                evidence_artifacts=code_evidence,
            )


def insert_global_jp_identity_claims(
    conn: sqlite3.Connection,
    *,
    binder: dict[str, Any],
    binder_artifact_id: str,
    maps: dict[str, Any],
    map_artifact_id: str,
) -> None:
    for index, row in enumerate(
        sorted(
            binder.get("concrete_global_exact_lineage", []),
            key=lambda item: canonical_json(item),
        )
    ):
        global_path = str(row.get("global_path") or row.get("path") or f"row-{index}")
        insert_claim(
            conn,
            claim_id=f"lineage:resource:{index:05d}",
            claim_key=f"lineage:resource:{global_path}",
            domain="resource_identity_lineage",
            version_scope=f"{GLOBAL_SCOPE}<->{CURRENT_JP_SCOPE}",
            provenance_grade="GLOBAL_JP_IDENTICAL",
            payload=row,
            source_fact_id=None,
            implementation_status=None,
            historical_claim=False,
            evidence_artifacts=[(binder_artifact_id, "exact_lineage_predicate")],
        )

    for index, row in enumerate(
        sorted(
            maps.get("global_to_jp", []),
            key=lambda item: str(item.get("base_id") or ""),
        )
    ):
        if not (
            row.get("package_byte_identical_to_jp_base")
            and row.get("map_payload_identical_to_jp_base")
            and row.get("structure_identical_to_jp_base")
        ):
            continue
        base_id = str(row.get("base_id") or index)
        insert_claim(
            conn,
            claim_id=f"lineage:map:{base_id}",
            claim_key=f"lineage:map:{base_id}",
            domain="map_identity_lineage",
            version_scope=f"{GLOBAL_SCOPE}<->{CURRENT_JP_SCOPE}",
            provenance_grade="GLOBAL_JP_IDENTICAL",
            payload=row,
            source_fact_id=None,
            implementation_status=None,
            historical_claim=False,
            evidence_artifacts=[(map_artifact_id, "exact_map_lineage_predicate")],
        )


def insert_function_semantics(
    conn: sqlite3.Connection,
    semantic: dict[str, Any],
) -> None:
    for row in sorted(
        semantic["function_semantics"],
        key=lambda item: item["global_function"],
    ):
        jp = row.get("jp_lineage") or {}
        payload_json = canonical_json(row)
        conn.execute(
            """insert into function_semantics(
                 global_function,global_address_hex,global_size,jp_name,
                 match_tier,lineage_predicate,match_score,protocol_refs_json,
                 state_reads_json,state_writes_json,semantic_tags_json,
                 control_flow_json,literals_json,payload_sha256
               ) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                row["global_function"],
                row.get("global_address_hex"),
                row.get("global_size"),
                jp.get("jp_name"),
                jp.get("match_tier"),
                jp.get("lineage_predicate"),
                jp.get("match_score"),
                canonical_json(row.get("protocol_references", [])),
                canonical_json(row.get("state_reads", [])),
                canonical_json(row.get("state_writes", [])),
                canonical_json(row.get("semantic_tags", [])),
                canonical_json(row.get("control_flow", {})),
                canonical_json(row.get("literals", {})),
                sha256_bytes(payload_json.encode()),
            ),
        )


def insert_protocols(conn: sqlite3.Connection, protocol: dict[str, Any]) -> None:
    for row in sorted(protocol["messages"], key=lambda item: item["name"]):
        payload_json = canonical_json(row)
        conn.execute(
            """insert into protocol_messages(
                 name,opcode_hex,opcode_u32,direction,top_level_schema_evidence,
                 fields_json,lineage_json,payload_sha256
               ) values(?,?,?,?,?,?,?,?)""",
            (
                row["name"],
                row.get("opcode_hex"),
                row.get("opcode_u32"),
                row.get("direction"),
                row.get("top_level_schema_evidence"),
                canonical_json(row.get("fields", [])),
                canonical_json(row.get("lineage", {})),
                sha256_bytes(payload_json.encode()),
            ),
        )


def resource_grade(node: dict[str, Any]) -> str:
    provenance = str(node.get("provenance") or "")
    if provenance.startswith("GLOBAL_") or provenance.startswith(
        "CONFIRMED_ORIGINAL_GLOBAL"
    ):
        return "GLOBAL_DIRECT"
    if provenance == "RECOVERED_GLOBAL_TARGET_CACHE":
        return "GLOBAL_DIRECT"
    if "CURRENT_JP" in provenance or provenance.startswith("JP_"):
        return "JP_LINEAGE_SUPPORTED"
    return "GLOBAL_BINARY_DERIVED"


def insert_resources(
    conn: sqlite3.Connection,
    resource_graph: dict[str, Any],
) -> None:
    for row in sorted(resource_graph["nodes"], key=lambda item: item["id"]):
        payload_json = canonical_json(row)
        conn.execute(
            """insert into resource_nodes(
                 node_id,kind,provenance,canonical_grade,path,
                 payload_sha256,payload_json
               ) values(?,?,?,?,?,?,?)""",
            (
                row["id"],
                row.get("kind"),
                row.get("provenance"),
                resource_grade(row),
                row.get("path"),
                sha256_bytes(payload_json.encode()),
                payload_json,
            ),
        )
    for index, row in enumerate(
        sorted(
            resource_graph["edges"],
            key=lambda item: (
                str(item.get("src") or ""),
                str(item.get("dst") or ""),
                str(item.get("relation") or ""),
                canonical_json(item),
            ),
        )
    ):
        payload_json = canonical_json(row)
        edge_id = str(row.get("id") or sha256_bytes(
            f"{index}|{payload_json}".encode()
        ))
        conn.execute(
            """insert into resource_edges(
                 edge_id,src,dst,relation,payload_sha256,payload_json
               ) values(?,?,?,?,?,?)""",
            (
                edge_id,
                row.get("src"),
                row.get("dst"),
                row.get("relation"),
                sha256_bytes(payload_json.encode()),
                payload_json,
            ),
        )


def insert_maps(conn: sqlite3.Connection, maps: dict[str, Any]) -> None:
    records = []
    for row in maps.get("global_packages", []):
        records.append(
            (
                f"global:{row['path']}",
                "global_package",
                GLOBAL_SCOPE,
                row.get("base_id"),
                "GLOBAL_DIRECT",
                row.get("path"),
                row.get("package_sha256"),
                row,
            )
        )
    for row in maps.get("jp_packages", []):
        records.append(
            (
                f"jp:{row['path']}",
                "jp_lineage_reference",
                CURRENT_JP_SCOPE,
                row.get("base_id"),
                "JP_LINEAGE_SUPPORTED",
                row.get("path"),
                row.get("package_sha256"),
                row,
            )
        )
    for row in maps.get("global_to_jp", []):
        grade = (
            "GLOBAL_JP_IDENTICAL"
            if row.get("package_byte_identical_to_jp_base")
            and row.get("map_payload_identical_to_jp_base")
            and row.get("structure_identical_to_jp_base")
            else "JP_LINEAGE_SUPPORTED"
        )
        records.append(
            (
                f"lineage:{row.get('base_id')}",
                "global_to_jp_lineage",
                f"{GLOBAL_SCOPE}<->{CURRENT_JP_SCOPE}",
                row.get("base_id"),
                grade,
                row.get("global_path"),
                row.get("global_package_sha256"),
                row,
            )
        )

    for (
        key,
        record_kind,
        scope,
        base_id,
        grade,
        path,
        package_sha,
        row,
    ) in sorted(records, key=lambda value: value[0]):
        payload_json = canonical_json(row)
        conn.execute(
            """insert into maps(
                 map_key,record_kind,version_scope,base_id,provenance_grade,
                 path,package_sha256,payload_sha256,payload_json
               ) values(?,?,?,?,?,?,?,?,?)""",
            (
                key,
                record_kind,
                scope,
                base_id,
                grade,
                path,
                package_sha,
                sha256_bytes(payload_json.encode()),
                payload_json,
            ),
        )


def insert_state_transitions(
    conn: sqlite3.Connection,
    state: dict[str, Any],
    semantic: dict[str, Any],
) -> None:
    bound = {
        int(row["transition_index"]): row.get("bound_global_functions", [])
        for row in semantic.get("state_transition_coverage", [])
    }
    for index, row in enumerate(state["transitions"]):
        payload_json = canonical_json(row)
        conn.execute(
            """insert into state_transitions(
                 transition_index,from_state,to_state,message,trigger,guard,
                 action,evidence,bound_global_functions_json,payload_sha256
               ) values(?,?,?,?,?,?,?,?,?,?)""",
            (
                index,
                row["from"],
                row["to"],
                row.get("message"),
                row.get("trigger"),
                row.get("guard"),
                row.get("action"),
                row.get("evidence"),
                canonical_json(bound.get(index, [])),
                sha256_bytes(payload_json.encode()),
            ),
        )


def insert_behavior_rules(
    conn: sqlite3.Connection,
    behavior: dict[str, Any],
) -> None:
    for key, value in sorted(behavior.get("exact_rules", {}).items()):
        payload_json = canonical_json(value)
        conn.execute(
            """insert into behavior_rules(rule_key,payload_sha256,payload_json)
               values(?,?,?)""",
            (key, sha256_bytes(payload_json.encode()), payload_json),
        )
    for index, value in enumerate(behavior.get("guardrails", [])):
        payload_json = canonical_json(value)
        conn.execute(
            """insert into behavior_rules(rule_key,payload_sha256,payload_json)
               values(?,?,?)""",
            (
                f"guardrail:{index:02d}",
                sha256_bytes(payload_json.encode()),
                payload_json,
            ),
        )


def insert_packets(conn: sqlite3.Connection, packets: dict[str, Any]) -> None:
    for row in sorted(packets["packets"], key=lambda item: item["packet_id"]):
        payload_json = canonical_json(row)
        source_ids = row.get("source_fact_ids") or []
        conn.execute(
            """insert into reconstruction_packets(
                 packet_id,packet_fingerprint,source_fact_id,
                 requested_claim_confidence,file_scopes_json,
                 evidence_node_ids_json,acceptance_tests_json,
                 do_not_infer_json,payload_sha256,payload_json
               ) values(?,?,?,?,?,?,?,?,?,?)""",
            (
                row["packet_id"],
                row["packet_fingerprint"],
                source_ids[0] if source_ids else None,
                row.get("requested_claim_confidence"),
                canonical_json(row.get("file_scopes", [])),
                canonical_json(row.get("evidence_node_ids", [])),
                canonical_json(row.get("acceptance_tests", [])),
                canonical_json(row.get("do_not_infer", [])),
                sha256_bytes(payload_json.encode()),
                payload_json,
            ),
        )


def insert_contradictions(
    conn: sqlite3.Connection,
    arbiter: dict[str, Any],
) -> None:
    for row in sorted(arbiter["results"], key=lambda item: item["task_id"]):
        payload_json = canonical_json(row)
        winner_authorities = sorted(
            {
                str(claim.get("authority") or "")
                for claim in row.get("winner_claims", [])
                if claim.get("authority")
            }
        )
        conn.execute(
            """insert into contradictions(
                 task_id,status,rationale,winner_authorities_json,
                 winner_claims_json,loser_claims_json,external_ceilings_json,
                 payload_sha256
               ) values(?,?,?,?,?,?,?,?)""",
            (
                row["task_id"],
                row["status"],
                row.get("rationale"),
                canonical_json(winner_authorities),
                canonical_json(row.get("winner_claims", [])),
                canonical_json(row.get("loser_claims", [])),
                canonical_json(row.get("external_ceilings", [])),
                sha256_bytes(payload_json.encode()),
            ),
        )


def insert_consistency(
    conn: sqlite3.Connection,
    certificate: dict[str, Any],
) -> None:
    for row in sorted(
        certificate["invariants"],
        key=lambda item: item["id"],
    ):
        conn.execute(
            """insert into consistency_invariants(
                 invariant_id,status,severity,statement,details_json
               ) values(?,?,?,?,?)""",
            (
                row["id"],
                row["status"],
                row.get("severity"),
                row.get("statement"),
                canonical_json(row.get("details")),
            ),
        )


def insert_coverage(conn: sqlite3.Connection, closure: dict[str, Any]) -> None:
    for domain, classes in sorted(
        closure["coverage"]["domain_classifications"].items()
    ):
        for classification, count in sorted(classes.items()):
            conn.execute(
                """insert into coverage(domain,classification,count)
                   values(?,?,?)""",
                (domain, classification, int(count)),
            )


def assert_integrity(
    conn: sqlite3.Connection,
    *,
    closure: dict[str, Any],
    protocol: dict[str, Any],
    semantic: dict[str, Any],
    resource_graph: dict[str, Any],
    state: dict[str, Any],
    packets: dict[str, Any],
    arbiter: dict[str, Any],
    certificate: dict[str, Any],
) -> dict[str, Any]:
    expected = {
        "claims_min": len(closure["facts"]),
        "function_semantics": len(semantic["function_semantics"]),
        "protocol_messages": len(protocol["messages"]),
        "resource_nodes": len(resource_graph["nodes"]),
        "resource_edges": len(resource_graph["edges"]),
        "state_transitions": len(state["transitions"]),
        "reconstruction_packets": len(packets["packets"]),
        "contradictions": len(arbiter["results"]),
        "consistency_invariants": len(certificate["invariants"]),
        "external_ceilings": closure["coverage"]["domain_totals"][
            "external_evidence_ceiling"
        ],
    }
    actual = {}
    for table in (
        "claims",
        "claim_heads",
        "claim_evidence",
        "function_semantics",
        "protocol_messages",
        "resource_nodes",
        "resource_edges",
        "maps",
        "state_transitions",
        "behavior_rules",
        "implementation_links",
        "reconstruction_packets",
        "contradictions",
        "consistency_invariants",
        "coverage",
        "external_ceilings",
    ):
        actual[table] = int(
            conn.execute(f"select count(*) from {table}").fetchone()[0]
        )

    if actual["claims"] < expected["claims_min"]:
        raise OmegaError("OMEGA lost closure claims")
    for key in (
        "function_semantics",
        "protocol_messages",
        "resource_nodes",
        "resource_edges",
        "state_transitions",
        "reconstruction_packets",
        "contradictions",
        "consistency_invariants",
        "external_ceilings",
    ):
        if actual[key] != expected[key]:
            raise OmegaError(
                f"OMEGA table count mismatch {key}: "
                f"expected={expected[key]} actual={actual[key]}"
            )

    missing_evidence = int(
        conn.execute(
            """select count(*)
                 from claims c
                where not exists(
                      select 1 from claim_evidence e
                       where e.claim_id=c.claim_id
                )"""
        ).fetchone()[0]
    )
    if missing_evidence:
        raise OmegaError(
            f"{missing_evidence} material claims lack evidence path/hash"
        )

    conflicting_heads = int(
        conn.execute(
            """select count(*) from (
                 select claim_key,provenance_grade,version_scope,
                        count(distinct payload_sha256) n
                   from claims
                  group by claim_key,provenance_grade,version_scope
                 having n>1
               )"""
        ).fetchone()[0]
    )
    if conflicting_heads:
        raise OmegaError(
            f"{conflicting_heads} same-authority claim conflicts escaped rejection"
        )

    failed_invariants = int(
        conn.execute(
            "select count(*) from consistency_invariants where status!='PASS'"
        ).fetchone()[0]
    )
    if failed_invariants:
        raise OmegaError(
            f"consistency certificate contains {failed_invariants} failed invariants"
        )

    grade_counts = {
        row[0]: int(row[1])
        for row in conn.execute(
            """select provenance_grade,count(*)
                 from claims
                group by provenance_grade
                order by authority_rank"""
        )
    }
    return {
        "table_counts": actual,
        "grade_counts": grade_counts,
        "missing_claim_evidence": missing_evidence,
        "same_authority_conflicts": conflicting_heads,
        "failed_consistency_invariants": failed_invariants,
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    sources = {
        "closure": (args.closure, "OMEGA closure"),
        "packets": (args.packets, "reconstruction compiler packets"),
        "semantic": (args.semantic_lift, "Global semantic lift"),
        "behavior": (args.behavior_twin, "Global behavior twin"),
        "binder": (args.asset_binder, "asset-behavior binder"),
        "resource": (args.resource_graph, "resource semantic graph"),
        "maps": (args.map_genealogy, "map genealogy"),
        "protocol": (args.protocol_schema, "protocol schema"),
        "state": (args.state_machine, "critical state machine"),
        "arbiter": (args.contradiction_arbiter, "contradiction arbiter"),
        "consistency": (args.consistency_certificate, "consistency certificate"),
    }
    loaded = {key: load_json(path) for key, (path, _) in sources.items()}
    closure = loaded["closure"]
    packets = loaded["packets"]
    semantic = loaded["semantic"]
    behavior = loaded["behavior"]
    binder = loaded["binder"]
    resource_graph = loaded["resource"]
    maps = loaded["maps"]
    protocol = loaded["protocol"]
    state = loaded["state"]
    arbiter = loaded["arbiter"]
    certificate = loaded["consistency"]

    if closure.get("provenance") != (
        "OMEGA_EXHAUSTIVE_RECONSTRUCTION_CLOSURE_WITH_TERMINAL_CEILINGS"
    ):
        raise OmegaError("closure provenance mismatch")
    if behavior.get("historical_facts_created") is not False:
        raise OmegaError("behavior twin unexpectedly creates historical facts")
    if certificate.get("status") != "PASS":
        raise OmegaError("consistency certificate is not PASS")
    if int(certificate["invariant_counts"]["failed"]) != 0:
        raise OmegaError("consistency certificate has failed invariants")

    arbiter_order = [
        grade for grade in arbiter.get("authority_order", [])
        if grade != "SPECULATION_OR_UNRESOLVED"
    ]
    if arbiter_order != list(CANONICAL_GRADES[:-2]) + ["IMPLEMENTATION_VERIFIED"]:
        # The historical arbiter predates EXTERNAL_CEILING as a claim grade.
        expected_prefix = [
            "GLOBAL_DIRECT",
            "GLOBAL_BINARY_DERIVED",
            "GLOBAL_JP_IDENTICAL",
            "SAME_ERA_JP_CORROBORATED",
            "JP_LINEAGE_SUPPORTED",
            "IMPLEMENTATION_VERIFIED",
        ]
        if arbiter_order != expected_prefix:
            raise OmegaError(
                f"arbiter authority order changed: {arbiter_order}"
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.output.unlink(missing_ok=True)

    conn = sqlite3.connect(args.output)
    try:
        init_schema(conn)
        conn.executemany(
            "insert into provenance_grades(grade,rank) values(?,?)",
            [(grade, rank) for grade, rank in GRADE_RANK.items()],
        )

        artifact_ids = {}
        for key, (path, role) in sorted(sources.items()):
            artifact_ids[key] = register_artifact(
                conn,
                path,
                provenance=str(loaded[key].get("provenance") or ""),
                role=role,
            )
        source_artifacts = add_source_artifacts(conn, closure)

        metadata = {
            "provenance": PROVENANCE,
            "historical_authority": "Global 3.0.24 / 2017-05-25",
            "current_jp_role": "LINEAGE_REFERENCE_ONLY",
            "repo_sha": repo_sha(args.repo),
            "closure_id": str(closure["closure_id"]),
            "closure_facts_sha256": str(closure["facts_sha256"]),
            "compiler_run_id": str(packets["compiler_run_id"]),
            "consistency_certificate_id": str(certificate["certificate_id"]),
            "consistency_status": str(certificate["status"]),
            "creates_new_historical_facts": "false",
            "retired_server_internals_claimed": "false",
        }
        conn.executemany(
            "insert into metadata(key,value) values(?,?)",
            sorted(metadata.items()),
        )

        insert_closure_claims(
            conn,
            closure=closure,
            closure_artifact_id=artifact_ids["closure"],
            source_artifacts=source_artifacts,
            repo=args.repo,
        )
        insert_global_jp_identity_claims(
            conn,
            binder=binder,
            binder_artifact_id=artifact_ids["binder"],
            maps=maps,
            map_artifact_id=artifact_ids["maps"],
        )
        insert_function_semantics(conn, semantic)
        insert_protocols(conn, protocol)
        insert_resources(conn, resource_graph)
        insert_maps(conn, maps)
        insert_state_transitions(conn, state, semantic)
        insert_behavior_rules(conn, behavior)
        insert_packets(conn, packets)
        insert_contradictions(conn, arbiter)
        insert_consistency(conn, certificate)
        insert_coverage(conn, closure)

        integrity = assert_integrity(
            conn,
            closure=closure,
            protocol=protocol,
            semantic=semantic,
            resource_graph=resource_graph,
            state=state,
            packets=packets,
            arbiter=arbiter,
            certificate=certificate,
        )

        conn.commit()
        conn.execute("vacuum")
        conn.commit()
    finally:
        conn.close()

    db_sha = sha256_file(args.output)
    db_bytes = args.output.stat().st_size

    manifest_core = {
        "provenance": PROVENANCE,
        "database": {
            "path": str(args.output),
            "sha256": db_sha,
            "bytes": db_bytes,
        },
        "repo_sha": repo_sha(args.repo),
        "closure_id": closure["closure_id"],
        "closure_facts_sha256": closure["facts_sha256"],
        "compiler_run_id": packets["compiler_run_id"],
        "canonical_provenance_grades": list(CANONICAL_GRADES),
        "integrity": integrity,
        "coverage": closure["coverage"],
        "external_evidence_ceilings": [
            row["text"]
            for row in load_external_ceilings(args.output)
        ],
        "contradiction_arbiter": {
            "status_counts": arbiter["counts"]["status_counts"],
            "unresolved_tasks": arbiter["counts"]["unresolved_tasks"],
            "creates_new_facts": arbiter["creates_new_facts"],
        },
        "consistency_certificate": {
            "id": certificate["certificate_id"],
            "status": certificate["status"],
            "invariant_counts": certificate["invariant_counts"],
        },
        "sources": {
            key: {
                "path": str(path),
                "sha256": sha256_file(path),
                "role": role,
            }
            for key, (path, role) in sorted(sources.items())
        },
        "policy": {
            "global_authority": (
                "Global 3.0.24 remains historical authority. JP evidence is "
                "lineage/reference unless an explicit identity predicate exists."
            ),
            "claim_evidence": (
                "Every material claim has at least one exact evidence path/hash."
            ),
            "conflicts": (
                "A second differing payload at the same claim key, provenance "
                "grade and version scope aborts the build instead of coexisting."
            ),
            "implementation": (
                "IMPLEMENTATION_VERIFIED claims bind to exact current source/test "
                "file SHA-256 values and do not promote historical truth."
            ),
            "external": (
                "External evidence ceilings are terminal constraints, not missing "
                "facts to be fabricated."
            ),
        },
    }
    omega_id = sha256_bytes(
        canonical_json(manifest_core).encode("utf-8")
    )
    manifest = {
        **manifest_core,
        "omega_id": omega_id,
    }
    args.manifest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    print(
        json.dumps(
            {
                "omega_id": omega_id,
                "database_sha256": db_sha,
                "database_bytes": db_bytes,
                "manifest_sha256": sha256_file(args.manifest),
                "claims": integrity["table_counts"]["claims"],
                "claim_evidence": integrity["table_counts"]["claim_evidence"],
                "grade_counts": integrity["grade_counts"],
            },
            sort_keys=True,
        )
    )
    return manifest


def load_external_ceilings(database: Path) -> list[dict[str, Any]]:
    conn = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [
            dict(row)
            for row in conn.execute(
                "select ceiling_id,text,source_fact_id from external_ceilings order by ceiling_id"
            )
        ]
    finally:
        conn.close()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    root = Path("/home/ubuntu/logres/artifacts")
    p.add_argument("--repo", type=Path, default=Path.cwd())
    p.add_argument("--closure", type=Path, default=root / "global-reconstruction-closure-20260924.json")
    p.add_argument("--packets", type=Path, default=root / "logres-reconstruction-packets-20260924.json")
    p.add_argument("--semantic-lift", type=Path, default=root / "global-jp-semantic-lift-20260924.json")
    p.add_argument("--behavior-twin", type=Path, default=root / "global3024-behavior-twin-20260924.json")
    p.add_argument("--asset-binder", type=Path, default=root / "global-asset-behavior-bindings-20260924.json")
    p.add_argument("--resource-graph", type=Path, default=root / "global-jp-resource-semantic-graph-20260924.json")
    p.add_argument("--map-genealogy", type=Path, default=root / "global-jp-map-genealogy-20260924.json")
    p.add_argument("--protocol-schema", type=Path, default=root / "global-jp-protocol-schema-20260924.json")
    p.add_argument("--state-machine", type=Path, default=root / "global-3024-state-machine-20260924.json")
    p.add_argument("--contradiction-arbiter", type=Path, default=root / "global-contradiction-arbiter-20260924.json")
    p.add_argument("--consistency-certificate", type=Path, default=root / "logres-reconstruction-consistency-certificate-20260924.json")
    p.add_argument("--output", type=Path, default=root / "global-reconstruction-omega-20260924.sqlite")
    p.add_argument("--manifest", type=Path, default=root / "global-reconstruction-omega-20260924.json")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    try:
        build(args)
        return 0
    except (OmegaError, OSError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "status": "REJECTED",
                    "error": type(exc).__name__,
                    "message": str(exc),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
