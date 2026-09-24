#!/usr/bin/env python3
"""Read-only authoritative query kernel for reconstructed Logres truth.

The kernel queries the deterministic OMEGA SQLite knowledge base and enriches
exact evidence hashes from the live provenance graph. It returns the strongest
supported claim without collapsing version scopes, exposes contradictions and
terminal evidence ceilings, and fails closed on unsupported confidence
promotion or current-JP substitution for historical Global truth.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterable

PROVENANCE = "MUIUE_AUTHORITATIVE_LOGRES_TRUTH_KERNEL"
SCHEMA = "logres-truth-kernel-v1"

GLOBAL_SCOPE = "GLOBAL_3_0_24_2017_05_25"
CURRENT_JP_SCOPE = "CURRENT_JP_2026_09_24"
IMPLEMENTATION_SCOPE = "RECONSTRUCTION_CANONICAL"

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

GLOBAL_ELIGIBLE_GRADES = {
    "GLOBAL_DIRECT",
    "GLOBAL_BINARY_DERIVED",
    "GLOBAL_JP_IDENTICAL",
    "SAME_ERA_JP_CORROBORATED",
}

TARGETS = ("global", "current-jp", "implementation", "any")
QUERY_MODES = ("claim", "fact", "search")
TOKEN_RE = re.compile(r"[A-Za-z0-9_]{3,}")

OMEGA_REQUIRED_TABLES = {
    "claims",
    "artifacts",
    "claim_evidence",
    "contradictions",
    "external_ceilings",
}
GRAPH_REQUIRED_TABLES = {"knowledge_nodes"}


class TruthError(RuntimeError):
    pass


class TruthKernelError(TruthError):
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


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise TruthError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise TruthError(f"{path}: expected JSON object")
    return value


def open_ro(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise TruthError(f"database does not exist: {path}")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# Backwards-compatible name for internal callers.
open_readonly = open_ro


def table_names(conn: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute(
            "select name from sqlite_master where type='table'"
        )
    }


def require_tables(
    conn: sqlite3.Connection,
    required: set[str],
    *,
    label: str,
) -> None:
    missing = required - table_names(conn)
    if missing:
        raise TruthError(
            f"{label} database missing tables: {sorted(missing)}"
        )


def verify_manifest(
    manifest: dict[str, Any],
    *,
    omega_db: Path,
    graph_db: Path,
) -> dict[str, Any]:
    if manifest.get("provenance") != PROVENANCE:
        raise TruthError(
            "truth-kernel manifest provenance mismatch"
        )

    expected = (
        manifest.get("omega_database") or {}
    ).get("sha256")
    actual = sha256_file(omega_db)
    if expected != actual:
        raise TruthError(
            f"OMEGA database hash mismatch: manifest={expected} actual={actual}"
        )

    graph_record = manifest.get("provenance_graph") or {}
    manifest_graph = graph_record.get("path")
    if manifest_graph and Path(manifest_graph) != graph_db:
        raise TruthError(
            f"provenance graph path mismatch: manifest={manifest_graph} runtime={graph_db}"
        )

    omega = open_ro(omega_db)
    graph = open_ro(graph_db)
    try:
        require_tables(
            omega,
            OMEGA_REQUIRED_TABLES,
            label="OMEGA",
        )
        require_tables(
            graph,
            GRAPH_REQUIRED_TABLES,
            label="provenance graph",
        )
        missing_evidence = int(
            omega.execute(
                """select count(*)
                     from claims c
                    where not exists(
                          select 1
                            from claim_evidence e
                           where e.claim_id=c.claim_id
                    )"""
            ).fetchone()[0]
        )
        if missing_evidence:
            raise TruthError(
                f"OMEGA contains {missing_evidence} claims without evidence"
            )
    finally:
        omega.close()
        graph.close()

    return {
        "truth_kernel_id": manifest.get("truth_kernel_id"),
        "omega_database_sha256": actual,
        "graph_path": str(graph_db),
    }


def _parse_payload(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def claim_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "claim_id": row["claim_id"],
        "claim_key": row["claim_key"],
        "domain": row["domain"],
        "version_scope": row["version_scope"],
        "provenance_grade": row["provenance_grade"],
        "authority_rank": int(row["authority_rank"]),
        "payload_sha256": row["payload_sha256"],
        "payload": _parse_payload(row["payload_json"]),
        "source_fact_id": row["source_fact_id"],
        "implementation_status": row["implementation_status"],
        "historical_claim": bool(row["historical_claim"]),
    }


def target_accepts_claim(
    claim: dict[str, Any],
    target: str,
) -> bool:
    if target == "any":
        return True
    if target == "global":
        scope = str(claim["version_scope"])
        grade = str(claim["provenance_grade"])
        return (
            grade in GLOBAL_ELIGIBLE_GRADES
            and (
                scope == GLOBAL_SCOPE
                or scope.startswith(GLOBAL_SCOPE + "<->")
            )
        )
    if target == "current-jp":
        return claim["version_scope"] == CURRENT_JP_SCOPE
    if target == "implementation":
        return claim["version_scope"] == IMPLEMENTATION_SCOPE
    raise TruthError(
        f"unknown target {target}; expected one of {TARGETS}"
    )


def _query_rows(
    omega: sqlite3.Connection,
    *,
    mode: str,
    value: str,
    limit: int,
) -> list[sqlite3.Row]:
    if mode not in QUERY_MODES:
        raise TruthError(
            f"unknown query mode {mode}; expected one of {QUERY_MODES}"
        )
    if not value:
        raise TruthError("query value must be non-empty")
    if limit < 1 or limit > 200:
        raise TruthError("limit must be between 1 and 200")

    if mode == "claim":
        sql = """
          select * from claims
           where claim_key=?
           order by authority_rank asc,historical_claim desc,
                    version_scope asc,claim_id asc
           limit ?
        """
        args = (value, limit)
    elif mode == "fact":
        sql = """
          select * from claims
           where source_fact_id=?
           order by authority_rank asc,historical_claim desc,
                    version_scope asc,claim_id asc
           limit ?
        """
        args = (value, limit)
    else:
        like = f"%{value}%"
        sql = """
          select * from claims
           where claim_key like ?
              or coalesce(source_fact_id,'') like ?
              or domain like ?
              or payload_json like ?
           order by authority_rank asc,historical_claim desc,
                    version_scope asc,claim_key asc,claim_id asc
           limit ?
        """
        args = (like, like, like, like, limit)
    return list(omega.execute(sql, args))


def claim_evidence(
    omega: sqlite3.Connection,
    claim_id: str,
) -> list[dict[str, Any]]:
    rows = list(
        omega.execute(
            """select e.artifact_id,e.evidence_role,e.evidence_path,
                      e.evidence_sha256,a.provenance,a.role
                 from claim_evidence e
                 left join artifacts a
                   on a.artifact_id=e.artifact_id
                where e.claim_id=?
                order by e.evidence_role,e.evidence_path,e.evidence_sha256""",
            (claim_id,),
        )
    )
    return [
        {
            "artifact_id": row["artifact_id"],
            "evidence_role": row["evidence_role"],
            "evidence_path": row["evidence_path"],
            "evidence_sha256": row["evidence_sha256"],
            "artifact_provenance": row["provenance"],
            "artifact_role": row["role"],
        }
        for row in rows
    ]


def graph_nodes_for_evidence(
    graph: sqlite3.Connection,
    evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    require_tables(
        graph,
        GRAPH_REQUIRED_TABLES,
        label="provenance graph",
    )
    result = {}
    for item in evidence:
        digest = str(item["evidence_sha256"])
        columns = {
            str(row[1])
            for row in graph.execute(
                "pragma table_info(knowledge_nodes)"
            )
        }
        wanted = [
            "node_id",
            "kind",
            "label",
            "provenance",
            "confidence",
            "artifact_path",
            "artifact_sha",
        ]
        select = ",".join(
            name
            for name in wanted
            if name in columns
        )
        rows = list(
            graph.execute(
                f"""select {select}
                      from knowledge_nodes
                     where node_id=?
                        or artifact_sha=?
                     order by confidence desc,node_id""",
                (f"artifact:{digest}", digest),
            )
        )
        for row in rows:
            value = {
                key: row[key]
                for key in row.keys()
            }
            result[str(value["node_id"])] = value
    return [
        result[key]
        for key in sorted(result)
    ]


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in TOKEN_RE.findall(text)
    }


def relevant_ceilings(
    omega: sqlite3.Connection,
    query: str,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    if limit < 1 or limit > 50:
        raise TruthError("ceiling limit must be between 1 and 50")
    terms = _tokens(query)
    rows = list(
        omega.execute(
            """select ceiling_id,text,source_fact_id
                 from external_ceilings
                order by ceiling_id"""
        )
    )
    scored = []
    for row in rows:
        haystack = _tokens(
            " ".join(
                [
                    str(row["ceiling_id"]),
                    str(row["text"]),
                    str(row["source_fact_id"]),
                ]
            )
        )
        hits = len(terms & haystack)
        if hits:
            scored.append(
                {
                    "ceiling_id": row["ceiling_id"],
                    "text": row["text"],
                    "source_fact_id": row["source_fact_id"],
                    "token_hits": hits,
                    "terminal": True,
                }
            )
    scored.sort(
        key=lambda row: (
            -int(row["token_hits"]),
            str(row["ceiling_id"]),
        )
    )
    return scored[:limit]


def contradiction_query(
    omega: sqlite3.Connection,
    task_id: str,
) -> dict[str, Any]:
    row = omega.execute(
        """select task_id,status,rationale,winner_authorities_json,
                  winner_claims_json,loser_claims_json,
                  external_ceilings_json,payload_sha256
             from contradictions
            where task_id=?""",
        (task_id,),
    ).fetchone()
    if row is None:
        return {
            "schema": SCHEMA,
            "status": "NOT_FOUND",
            "task_id": task_id,
            "contradiction": None,
        }
    return {
        "schema": SCHEMA,
        "status": "RESOLVED",
        "task_id": task_id,
        "contradiction": {
            "task_id": row["task_id"],
            "status": row["status"],
            "rationale": row["rationale"],
            "winner_authorities": json.loads(
                row["winner_authorities_json"]
            ),
            "winner_claims": json.loads(
                row["winner_claims_json"]
            ),
            "loser_claims": json.loads(
                row["loser_claims_json"]
            ),
            "external_ceilings": json.loads(
                row["external_ceilings_json"]
            ),
            "payload_sha256": row["payload_sha256"],
        },
    }


def _relevant_contradictions(
    omega: sqlite3.Connection,
    text: str,
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    terms = _tokens(text)
    rows = list(
        omega.execute(
            """select task_id,status,rationale,winner_authorities_json,
                      winner_claims_json,loser_claims_json,
                      external_ceilings_json,payload_sha256
                 from contradictions
                order by task_id"""
        )
    )
    scored = []
    for row in rows:
        haystack = _tokens(
            " ".join(
                str(row[key] or "")
                for key in (
                    "task_id",
                    "status",
                    "rationale",
                    "winner_authorities_json",
                    "winner_claims_json",
                    "loser_claims_json",
                    "external_ceilings_json",
                )
            )
        )
        hits = len(terms & haystack)
        if hits:
            scored.append(
                {
                    "task_id": row["task_id"],
                    "status": row["status"],
                    "rationale": row["rationale"],
                    "payload_sha256": row["payload_sha256"],
                    "token_hits": hits,
                }
            )
    scored.sort(
        key=lambda item: (
            -int(item["token_hits"]),
            str(item["task_id"]),
        )
    )
    return scored[:limit]


def stats_query(omega: sqlite3.Connection) -> dict[str, Any]:
    claims = int(
        omega.execute("select count(*) from claims").fetchone()[0]
    )
    evidence = int(
        omega.execute(
            "select count(*) from claim_evidence"
        ).fetchone()[0]
    )
    ceilings = int(
        omega.execute(
            "select count(*) from external_ceilings"
        ).fetchone()[0]
    )
    grades = {
        str(row["provenance_grade"]): int(row["n"])
        for row in omega.execute(
            """select provenance_grade,count(*) n
                 from claims
                group by provenance_grade
                order by authority_rank"""
        )
    }
    scopes = {
        str(row["version_scope"]): int(row["n"])
        for row in omega.execute(
            """select version_scope,count(*) n
                 from claims
                group by version_scope
                order by version_scope"""
        )
    }
    contradiction_counts = {
        str(row["status"]): int(row["n"])
        for row in omega.execute(
            """select status,count(*) n
                 from contradictions
                group by status
                order by status"""
        )
    }
    return {
        "schema": SCHEMA,
        "status": "RESOLVED",
        "claims": claims,
        "claim_evidence": evidence,
        "external_ceilings": ceilings,
        "grade_counts": grades,
        "version_scopes": scopes,
        "contradictions": {
            "status_counts": contradiction_counts,
            "unresolved": sum(
                count
                for status, count in contradiction_counts.items()
                if status.startswith("UNRESOLVED")
            ),
        },
    }


def _scope_results(
    claims: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for claim in claims:
        result[str(claim["version_scope"])].append(claim)
    return {
        key: value
        for key, value in sorted(result.items())
    }


def resolve_query(
    omega: sqlite3.Connection,
    graph: sqlite3.Connection,
    *,
    mode: str,
    value: str,
    target: str = "global",
    minimum_grade: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    require_tables(
        omega,
        OMEGA_REQUIRED_TABLES,
        label="OMEGA",
    )
    require_tables(
        graph,
        GRAPH_REQUIRED_TABLES,
        label="provenance graph",
    )
    if target not in TARGETS:
        raise TruthError(
            f"unknown target {target}; expected one of {TARGETS}"
        )
    if minimum_grade is not None and minimum_grade not in GRADE_RANK:
        raise TruthError(
            f"unknown minimum grade {minimum_grade}"
        )

    raw_rows = _query_rows(
        omega,
        mode=mode,
        value=value,
        limit=limit,
    )
    raw_claims = [claim_to_dict(row) for row in raw_rows]
    claims = [
        claim
        for claim in raw_claims
        if target_accepts_claim(claim, target)
    ]

    if not claims:
        reason = (
            "No claim at the requested version scope is supported. "
            "Current JP is not substituted for historical Global without "
            "a qualifying identity/corroboration predicate."
            if target == "global" and raw_claims
            else "No supported claim matches the requested query and target scope."
        )
        return {
            "schema": SCHEMA,
            "status": "UNRESOLVED",
            "mode": mode,
            "value": value,
            "target": target,
            "strongest_claim": None,
            "claims": [],
            "scoped_results": _scope_results(raw_claims),
            "evidence": [],
            "provenance_graph_nodes": [],
            "contradictions": _relevant_contradictions(
                omega,
                value,
            ),
            "unresolved_ceiling": {
                "reason": reason,
                "terminal_evidence": relevant_ceilings(
                    omega,
                    value,
                    limit=5,
                ),
            },
        }

    strongest = claims[0]
    if minimum_grade is not None:
        supported_rank = GRADE_RANK.get(
            str(strongest["provenance_grade"]),
            int(strongest["authority_rank"]),
        )
        required_rank = GRADE_RANK[minimum_grade]
        if supported_rank > required_rank:
            return {
                "schema": SCHEMA,
                "status": "REJECTED_CONFIDENCE_PROMOTION",
                "mode": mode,
                "value": value,
                "target": target,
                "required_grade": minimum_grade,
                "supported_grade": strongest["provenance_grade"],
                "strongest_claim": strongest,
                "claims": claims,
                "scoped_results": _scope_results(raw_claims),
                "evidence": [],
                "provenance_graph_nodes": [],
                "contradictions": _relevant_contradictions(
                    omega,
                    value,
                ),
                "unresolved_ceiling": {
                    "reason": (
                        "The requested authority exceeds the strongest "
                        "supported evidence; confidence promotion is refused."
                    ),
                    "terminal_evidence": relevant_ceilings(
                        omega,
                        value,
                        limit=5,
                    ),
                },
            }

    evidence = claim_evidence(
        omega,
        str(strongest["claim_id"]),
    )
    nodes = graph_nodes_for_evidence(
        graph,
        evidence,
    )
    context_text = " ".join(
        [
            value,
            str(strongest["claim_key"]),
            str(strongest.get("source_fact_id") or ""),
            str(strongest["domain"]),
            canonical_json(strongest["payload"]),
        ]
    )
    ceilings = relevant_ceilings(
        omega,
        context_text,
        limit=5,
    )

    return {
        "schema": SCHEMA,
        "status": "RESOLVED",
        "mode": mode,
        "value": value,
        "target": target,
        "strongest_claim": strongest,
        "claims": claims,
        "scoped_results": _scope_results(raw_claims),
        "evidence": evidence,
        "provenance_graph_nodes": nodes,
        "contradictions": _relevant_contradictions(
            omega,
            context_text,
        ),
        "unresolved_ceiling": (
            {
                "reason": (
                    "Terminal external evidence ceilings remain explicit and "
                    "do not weaken or expand this selected claim."
                ),
                "terminal_evidence": ceilings,
            }
            if ceilings
            else None
        ),
        "policy": {
            "current_jp_substitution_allowed": False,
            "confidence_promotion_allowed": False,
            "selection": (
                "Strongest supported claim by authority_rank within the "
                "requested target scope; version scopes remain distinct."
            ),
        },
    }


def build_manifest(
    *,
    omega_db: Path,
    graph_db: Path,
    output: Path,
) -> dict[str, Any]:
    omega = open_ro(omega_db)
    graph = open_ro(graph_db)
    try:
        require_tables(
            omega,
            OMEGA_REQUIRED_TABLES,
            label="OMEGA",
        )
        require_tables(
            graph,
            GRAPH_REQUIRED_TABLES,
            label="provenance graph",
        )
        stats = stats_query(omega)
    finally:
        omega.close()
        graph.close()

    core = {
        "provenance": PROVENANCE,
        "schema": SCHEMA,
        "omega_database": {
            "path": str(omega_db),
            "sha256": sha256_file(omega_db),
        },
        "provenance_graph": {
            "path": str(graph_db),
            "live_read_only": True,
            "whole_database_hash_pinned": False,
        },
        "canonical_grades": list(CANONICAL_GRADES),
        "scopes": {
            "global": GLOBAL_SCOPE,
            "current_jp": CURRENT_JP_SCOPE,
            "implementation": IMPLEMENTATION_SCOPE,
        },
        "stats": stats,
        "query_contract": {
            "modes": list(QUERY_MODES),
            "targets": list(TARGETS),
            "returns": [
                "strongest supported claim",
                "authority grade",
                "evidence path/hash",
                "version/time scope",
                "provenance graph nodes",
                "contradictions",
                "unresolved ceiling",
            ],
            "fail_closed": [
                "unsupported confidence promotion",
                "current JP substituted for historical Global",
            ],
        },
        "read_only": True,
    }
    kernel_id = hashlib.sha256(
        canonical_json(core).encode("utf-8")
    ).hexdigest()
    manifest = {
        **core,
        "truth_kernel_id": kernel_id,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    return manifest


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--manifest",
        type=Path,
        default=Path(
            "/home/ubuntu/logres/artifacts/"
            "logres-truth-kernel-20260924.json"
        ),
    )
    p.add_argument(
        "--omega-db",
        type=Path,
        default=Path(
            "/home/ubuntu/logres/artifacts/"
            "global-reconstruction-omega-20260924.sqlite"
        ),
    )
    p.add_argument(
        "--graph-db",
        type=Path,
        default=Path(
            "/home/ubuntu/logres/control/control.sqlite"
        ),
    )

    sub = p.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build")
    build.add_argument("--output", type=Path)

    for name in QUERY_MODES:
        q = sub.add_parser(name)
        q.add_argument("value")
        q.add_argument(
            "--target",
            choices=TARGETS,
            default="global",
        )
        q.add_argument(
            "--minimum-grade",
            choices=CANONICAL_GRADES,
        )
        q.add_argument("--limit", type=int, default=20)

    contradiction = sub.add_parser("contradiction")
    contradiction.add_argument("task_id")

    ceiling = sub.add_parser("ceilings")
    ceiling.add_argument("query")
    ceiling.add_argument("--limit", type=int, default=5)

    sub.add_parser("stats")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "build":
            output = args.output or args.manifest
            result = build_manifest(
                omega_db=args.omega_db,
                graph_db=args.graph_db,
                output=output,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0

        manifest = load_json(args.manifest)
        verify_manifest(
            manifest,
            omega_db=args.omega_db,
            graph_db=args.graph_db,
        )

        omega = open_ro(args.omega_db)
        graph = open_ro(args.graph_db)
        try:
            if args.command in QUERY_MODES:
                result = resolve_query(
                    omega,
                    graph,
                    mode=args.command,
                    value=args.value,
                    target=args.target,
                    minimum_grade=args.minimum_grade,
                    limit=args.limit,
                )
            elif args.command == "contradiction":
                result = contradiction_query(
                    omega,
                    args.task_id,
                )
            elif args.command == "ceilings":
                result = {
                    "schema": SCHEMA,
                    "status": "RESOLVED",
                    "query": args.query,
                    "ceilings": relevant_ceilings(
                        omega,
                        args.query,
                        limit=args.limit,
                    ),
                }
            else:
                result = stats_query(omega)
        finally:
            omega.close()
            graph.close()

        print(json.dumps(result, indent=2, sort_keys=True))
        if result.get("status") == "REJECTED_CONFIDENCE_PROMOTION":
            return 2
        return 0
    except (
        TruthError,
        sqlite3.Error,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "REJECTED",
                    "error": type(exc).__name__,
                    "message": str(exc),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
