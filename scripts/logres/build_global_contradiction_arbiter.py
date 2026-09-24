#!/usr/bin/env python3
"""Deterministic contradiction arbiter for Logres reconstruction evidence.

The arbiter creates no new facts. It resolves only tasks explicitly flagged by
Brain as EVIDENCE_CONFLICT, ranks factual claims by evidence authority, keeps
external ceilings separate, and leaves same-authority disagreements unresolved.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

AUTHORITY_ORDER = {
    "GLOBAL_DIRECT": 700,
    "GLOBAL_BINARY_DERIVED": 650,
    "GLOBAL_JP_IDENTICAL": 600,
    "SAME_ERA_JP_CORROBORATED": 550,
    "JP_LINEAGE_SUPPORTED": 500,
    "IMPLEMENTATION_VERIFIED": 400,
    "SPECULATION_OR_UNRESOLVED": 100,
}

AUTHORITY_DESCRIPTION = [
    "GLOBAL_DIRECT",
    "GLOBAL_BINARY_DERIVED",
    "GLOBAL_JP_IDENTICAL",
    "SAME_ERA_JP_CORROBORATED",
    "JP_LINEAGE_SUPPORTED",
    "IMPLEMENTATION_VERIFIED",
    "SPECULATION_OR_UNRESOLVED",
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify_claim(provenance: str, metadata: dict[str, Any], label: str) -> tuple[str, bool]:
    p = str(provenance or "").upper()
    summary = str(metadata.get("summary") or "")
    confidence_label = str(metadata.get("confidence_label") or "").upper()
    text = " ".join((p, summary.upper(), label.upper(), confidence_label))

    if any(token in text for token in (
        "EXTERNAL_CEILING",
        "EXTERNAL EVIDENCE CEILING",
        "RETIRED-SERVER EVIDENCE CEILING",
        "SERVER_BEHAVIOR_UNKNOWN",
        "UNRECOVERABLE",
    )):
        return "EXTERNAL_CEILING", True

    if any(token in p for token in (
        "CONFIRMED_GLOBAL_3_0_24",
        "CONFIRMED_ORIGINAL_GLOBAL",
        "GLOBAL_3_0_24_PROTOCOL_AUTHORITY",
        "GLOBAL_DIRECT",
    )):
        return "GLOBAL_DIRECT", False

    if any(token in p for token in (
        "GLOBAL_BINARY_DERIVED",
        "GLOBAL_RECOVERED",
        "GLOBAL_NATIVE",
    )):
        return "GLOBAL_BINARY_DERIVED", False

    if any(token in p for token in (
        "GLOBAL_JP_IDENTICAL",
        "GLOBAL_AUTHORITY_WITH_CURRENT_JP_BYTE",
        "GLOBAL_AUTHORITY_WITH_CURRENT_JP_PUBLIC_MANIFEST",
        "GLOBAL_AUTHORITY_WITH_CURRENT_JP_LINEAGE",
    )):
        return "GLOBAL_JP_IDENTICAL", False

    if "SAME_ERA_JP" in p:
        return "SAME_ERA_JP_CORROBORATED", False

    if any(token in p for token in (
        "JP_LINEAGE",
        "CURRENT_JP_REFERENCE",
        "CURRENT_JP",
    )):
        return "JP_LINEAGE_SUPPORTED", False

    if any(token in p for token in (
        "IMPLEMENTATION_VERIFIED",
        "GIT_EXACT_SHA",
        "RUNTIME_CONTROL_PLANE",
    )):
        return "IMPLEMENTATION_VERIFIED", False

    return "SPECULATION_OR_UNRESOLVED", False


def normalized_summary(metadata: dict[str, Any]) -> str:
    value = str(metadata.get("summary") or "")
    return re.sub(r"\s+", " ", value.strip()).casefold()


def load_claims(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rows = conn.execute(
        """
        select e.task_id,n.node_id,n.label,n.provenance,n.confidence,
               n.artifact_path,n.artifact_sha,n.metadata_json,n.updated_at
          from knowledge_edges e
          join knowledge_nodes n on n.node_id=e.src
         where e.relation='supports'
           and n.kind='claim'
           and e.task_id is not null
         order by e.task_id,n.updated_at,n.node_id
        """
    )
    for row in rows:
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except json.JSONDecodeError:
            metadata = {}
        authority, ceiling = classify_claim(
            row["provenance"], metadata, row["label"]
        )
        result[row["task_id"]].append(
            {
                "node_id": row["node_id"],
                "label": row["label"],
                "provenance": row["provenance"],
                "confidence": float(row["confidence"] or 0),
                "artifact_path": row["artifact_path"],
                "artifact_sha": row["artifact_sha"],
                "metadata": metadata,
                "updated_at": row["updated_at"],
                "authority": authority,
                "authority_rank": AUTHORITY_ORDER.get(authority, 0),
                "is_external_ceiling": ceiling,
            }
        )
    return result


def load_conflicts(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rows = conn.execute(
        """
        select id,ts,sender,task_id,subject,body
          from brain_events
         where event_type='EVIDENCE_CONFLICT'
           and task_id is not null
         order by id
        """
    )
    for row in rows:
        result[row["task_id"]].append(
            {
                "event_id": row["id"],
                "ts": row["ts"],
                "sender": row["sender"],
                "subject": row["subject"],
                "body": row["body"],
            }
        )
    return result


def claim_digest(claim: dict[str, Any]) -> tuple[str, str]:
    return (
        str(claim.get("artifact_sha") or ""),
        normalized_summary(claim.get("metadata") or {}),
    )


def arbitrate_task(
    task_id: str,
    claims: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> dict[str, Any]:
    ceilings = [claim for claim in claims if claim["is_external_ceiling"]]
    factual = [claim for claim in claims if not claim["is_external_ceiling"]]
    factual.sort(
        key=lambda claim: (
            claim["authority_rank"],
            claim["confidence"],
            claim["updated_at"],
            claim["node_id"],
        ),
        reverse=True,
    )

    if not factual:
        status = "UNRESOLVED_NO_FACTUAL_CLAIM"
        winners: list[dict[str, Any]] = []
        losers: list[dict[str, Any]] = []
        rationale = "Only ceilings or no factual claims are available."
    else:
        top_rank = factual[0]["authority_rank"]
        top = [claim for claim in factual if claim["authority_rank"] == top_rank]
        next_lower = [claim for claim in factual if claim["authority_rank"] < top_rank]

        if top[0]["authority"] == "SPECULATION_OR_UNRESOLVED":
            status = "UNRESOLVED_LOW_AUTHORITY"
            winners = []
            losers = []
            rationale = (
                "No claim rises above speculation/unresolved authority; "
                "arbitration cannot manufacture a supported winner."
            )
        elif len(top) == 1:
            status = "RESOLVED_BY_AUTHORITY"
            winners = top
            losers = next_lower
            rationale = (
                f"Unique highest authority {top[0]['authority']} outranks "
                "all lower-authority factual claims."
            )
        else:
            digests = {claim_digest(claim) for claim in top}
            if len(digests) == 1:
                status = "RESOLVED_EQUIVALENT_TOP_AUTHORITY"
                winners = top
                losers = next_lower
                rationale = (
                    "Highest-authority claims are equivalent by artifact/summary "
                    "and jointly outrank lower-authority claims."
                )
            else:
                status = "UNRESOLVED_SAME_AUTHORITY_TIE"
                winners = []
                losers = next_lower
                rationale = (
                    f"{len(top)} claims share highest authority "
                    f"{top[0]['authority']} but disagree; no automatic winner."
                )

    def compact(claim: dict[str, Any]) -> dict[str, Any]:
        return {
            "node_id": claim["node_id"],
            "label": claim["label"],
            "authority": claim["authority"],
            "confidence": claim["confidence"],
            "provenance": claim["provenance"],
            "artifact_path": claim["artifact_path"],
            "artifact_sha": claim["artifact_sha"],
            "summary": claim["metadata"].get("summary"),
            "updated_at": claim["updated_at"],
        }

    return {
        "task_id": task_id,
        "status": status,
        "rationale": rationale,
        "conflict_events": conflicts,
        "winner_claims": [compact(claim) for claim in winners],
        "loser_claims": [compact(claim) for claim in losers],
        "top_tied_claims": [
            compact(claim)
            for claim in factual
            if factual and claim["authority_rank"] == factual[0]["authority_rank"]
        ],
        "external_ceilings": [compact(claim) for claim in ceilings],
        "all_claim_count": len(claims),
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    conn = sqlite3.connect(args.database)
    conn.row_factory = sqlite3.Row
    claims_by_task = load_claims(conn)
    conflicts_by_task = load_conflicts(conn)

    results = []
    for task_id in sorted(conflicts_by_task):
        results.append(
            arbitrate_task(
                task_id,
                claims_by_task.get(task_id, []),
                conflicts_by_task[task_id],
            )
        )

    counts = Counter(row["status"] for row in results)
    winner_authorities = Counter(
        winner["authority"]
        for row in results
        for winner in row["winner_claims"]
    )
    unresolved = [
        row["task_id"]
        for row in results
        if row["status"].startswith("UNRESOLVED")
    ]

    # Snapshot hashes of evidence artifacts used by material winners/ceilings.
    artifact_hashes = {}
    for row in results:
        for claim in row["winner_claims"] + row["external_ceilings"]:
            path = claim.get("artifact_path")
            if not path:
                continue
            p = Path(path)
            if p.is_file():
                artifact_hashes[str(p)] = sha256_file(p)

    conn.close()
    return {
        "provenance": "DETERMINISTIC_ARBITRATION_OVER_EXISTING_PROVENANCE_GRAPH",
        "creates_new_facts": False,
        "authority_order": AUTHORITY_DESCRIPTION,
        "counts": {
            "explicit_conflict_tasks": len(results),
            "status_counts": dict(sorted(counts.items())),
            "winner_authorities": dict(sorted(winner_authorities.items())),
            "unresolved_tasks": len(unresolved),
            "artifact_hashes_snapshotted": len(artifact_hashes),
        },
        "results": results,
        "unresolved_task_ids": unresolved,
        "artifact_hashes": artifact_hashes,
        "policy": {
            "scope": "Only explicit Brain EVIDENCE_CONFLICT tasks are auto-arbitrated.",
            "external_ceilings": (
                "External evidence ceilings are constraints, not factual rivals, "
                "and are preserved separately."
            ),
            "same_authority": (
                "Same-authority disagreement is unresolved unless claims are "
                "equivalent by artifact hash plus normalized summary."
            ),
            "version_scope": (
                "Claims from different tasks are not collapsed merely because "
                "their labels look similar; this preserves version/time/scope."
            ),
            "no_new_evidence": (
                "Arbitration chooses among existing claims and never creates a "
                "new historical fact."
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("/home/ubuntu/logres/control/control.sqlite"),
    )
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
