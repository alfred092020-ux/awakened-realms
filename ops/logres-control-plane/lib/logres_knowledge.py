from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path


CONFIDENCE_SCORE = {
    "CONFIRMED": 1.0,
    "CONFIRMED ORIGINAL": 1.0,
    "HIGH": 0.90,
    "INFERENCE": 0.72,
    "SUPPORTED INFERENCE": 0.72,
    "MEDIUM": 0.62,
    "RECONSTRUCTED": 0.58,
    "VERSION_SENSITIVE": 0.45,
    "VERSION SENSITIVE": 0.45,
    "LOW": 0.28,
    "UNRESOLVED": 0.10,
}


@dataclass(frozen=True)
class TaskKnowledge:
    task_id: str
    support_score: float
    discovery_count: int
    confirmed_count: int
    artifact_count: int
    source_count: int
    unresolved_count: int


def confidence_score(label: str | None) -> float:
    return CONFIDENCE_SCORE.get(str(label or "").upper(), 0.20)


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists knowledge_nodes(
          node_id text primary key,
          kind text not null,
          label text not null,
          provenance text not null default '',
          confidence real not null default 0.0,
          artifact_path text,
          artifact_sha text,
          metadata_json text not null default '{}',
          updated_at text not null default (datetime('now'))
        );
        create index if not exists idx_knowledge_nodes_kind
          on knowledge_nodes(kind);
        create index if not exists idx_knowledge_nodes_label
          on knowledge_nodes(label);

        create table if not exists knowledge_edges(
          src text not null,
          dst text not null,
          relation text not null,
          confidence real not null default 0.0,
          task_id text,
          metadata_json text not null default '{}',
          updated_at text not null default (datetime('now')),
          primary key(src,dst,relation)
        );
        create index if not exists idx_knowledge_edges_task
          on knowledge_edges(task_id);
        create index if not exists idx_knowledge_edges_dst
          on knowledge_edges(dst);

        create table if not exists optimizer_observations(
          id integer primary key autoincrement,
          task_id text,
          engine text not null,
          work_type text,
          outcome text not null,
          duration_seconds real,
          estimated_cost_usd real,
          recorded_at text not null default (datetime('now'))
        );
        """
    )
    conn.commit()


def _upsert_node(
    conn: sqlite3.Connection,
    node_id: str,
    kind: str,
    label: str,
    *,
    provenance: str = "",
    confidence: float = 0.0,
    artifact_path: str | None = None,
    artifact_sha: str | None = None,
    metadata: dict | None = None,
) -> None:
    conn.execute(
        """insert into knowledge_nodes(
             node_id,kind,label,provenance,confidence,artifact_path,
             artifact_sha,metadata_json,updated_at
           ) values(?,?,?,?,?,?,?,?,datetime('now'))
           on conflict(node_id) do update set
             kind=excluded.kind,
             label=excluded.label,
             provenance=excluded.provenance,
             confidence=max(knowledge_nodes.confidence,excluded.confidence),
             artifact_path=coalesce(excluded.artifact_path,knowledge_nodes.artifact_path),
             artifact_sha=coalesce(excluded.artifact_sha,knowledge_nodes.artifact_sha),
             metadata_json=excluded.metadata_json,
             updated_at=datetime('now')""",
        (
            node_id,
            kind,
            label,
            provenance,
            float(confidence),
            artifact_path,
            artifact_sha,
            json.dumps(metadata or {}, sort_keys=True),
        ),
    )


def _upsert_edge(
    conn: sqlite3.Connection,
    src: str,
    dst: str,
    relation: str,
    *,
    confidence: float = 0.0,
    task_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    conn.execute(
        """insert into knowledge_edges(
             src,dst,relation,confidence,task_id,metadata_json,updated_at
           ) values(?,?,?,?,?,?,datetime('now'))
           on conflict(src,dst,relation) do update set
             confidence=max(knowledge_edges.confidence,excluded.confidence),
             task_id=coalesce(excluded.task_id,knowledge_edges.task_id),
             metadata_json=excluded.metadata_json,
             updated_at=datetime('now')""",
        (
            src,
            dst,
            relation,
            float(confidence),
            task_id,
            json.dumps(metadata or {}, sort_keys=True),
        ),
    )


def _safe_artifact_json(path: str | None) -> dict | None:
    if not path:
        return None
    p = Path(path)
    if not p.is_file() or p.stat().st_size > 8_000_000:
        return None
    try:
        value = json.loads(p.read_text(errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _artifact_provenance(
    payload: dict | None,
    path: str | None,
) -> str:
    if payload:
        direct = payload.get("provenance")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()

        result = payload.get("result")
        if isinstance(result, dict):
            result_provenance = result.get("provenance")
            if isinstance(result_provenance, list):
                values = [
                    str(item).strip()
                    for item in result_provenance
                    if str(item).strip()
                ]
                if values:
                    return " | ".join(values[:6])
            if isinstance(result_provenance, str) and result_provenance.strip():
                return result_provenance.strip()

    name = Path(path).name.lower() if path else ""
    if name.startswith("global-jp-"):
        return "GLOBAL_AUTHORITY_WITH_CURRENT_JP_LINEAGE"
    if name.startswith("global-3024-") or name.startswith("global-"):
        return "GLOBAL_RECOVERED"
    if name.startswith("current-jp-"):
        return "CURRENT_JP_REFERENCE"
    if "swarm-research" in str(path or "").lower():
        return "AUTONOMOUS_RESEARCH_MIXED"
    return "UNSPECIFIED"


def _artifact_sources(payload: dict | None) -> list[str]:
    if not payload:
        return []
    found: list[str] = []

    def walk(value, depth=0):
        if depth > 5:
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "sources" and isinstance(item, list):
                    for source in item:
                        if isinstance(source, str) and source.startswith(("http://", "https://")):
                            found.append(source)
                else:
                    walk(item, depth + 1)
        elif isinstance(value, list):
            for item in value[:100]:
                walk(item, depth + 1)

    walk(payload)
    return list(dict.fromkeys(found))


def refresh_graph(conn: sqlite3.Connection) -> dict:
    ensure_schema(conn)
    # Reserve the single WAL writer before reading source rows that this
    # refresh will project back into the knowledge tables. Without this,
    # another writer can commit after our SELECT begins and SQLite correctly
    # rejects the later read->write upgrade as SQLITE_BUSY_SNAPSHOT.
    conn.execute("begin immediate")
    counts = {
        "tasks": 0,
        "dependencies": 0,
        "discoveries": 0,
        "artifacts": 0,
        "sources": 0,
        "commits": 0,
    }

    # Task/dependency graph is the execution backbone.
    for row in conn.execute(
        "select id,title,status,priority,lane,note from tasks"
    ):
        node_id = f"task:{row[0]}"
        _upsert_node(
            conn,
            node_id,
            "task",
            row[1],
            provenance="CONTROL_PLANE",
            confidence=1.0,
            metadata={
                "task_id": row[0],
                "status": row[2],
                "priority": row[3],
                "lane": row[4],
                "note": row[5] or "",
            },
        )
        counts["tasks"] += 1

    for row in conn.execute(
        "select task_id,depends_on,kind,rationale from task_dependencies"
    ):
        _upsert_edge(
            conn,
            f"task:{row[0]}",
            f"task:{row[1]}",
            "depends_on",
            confidence=1.0,
            task_id=row[0],
            metadata={"kind": row[2], "rationale": row[3] or ""},
        )
        counts["dependencies"] += 1

    # Brain discoveries become provenance-scored claim nodes. Fresh/unit-test
    # databases may not have the optional Brain discovery projection yet.
    try:
        discovery_rows = list(
            conn.execute(
                """select id,task_id,confidence,subject,summary,artifact_path,
                          artifact_sha256,status,author,ts
                     from brain_discoveries"""
            )
        )
    except sqlite3.OperationalError:
        discovery_rows = []

    for row in discovery_rows:
        score = confidence_score(row[2])
        artifact_payload = _safe_artifact_json(row[5])
        provenance = _artifact_provenance(
            artifact_payload,
            row[5],
        )
        claim_id = f"discovery:{row[0]}"
        _upsert_node(
            conn,
            claim_id,
            "claim",
            row[3],
            provenance=provenance,
            confidence=score,
            artifact_path=row[5],
            artifact_sha=row[6],
            metadata={
                "discovery_id": row[0],
                "confidence_label": row[2],
                "summary": row[4],
                "status": row[7],
                "author": row[8],
                "ts": row[9],
            },
        )
        if row[1]:
            _upsert_edge(
                conn,
                claim_id,
                f"task:{row[1]}",
                "supports",
                confidence=score,
                task_id=row[1],
            )
        counts["discoveries"] += 1

        if row[6] or row[5]:
            artifact_key = row[6] or hashlib.sha256(str(row[5]).encode()).hexdigest()
            artifact_id = f"artifact:{artifact_key}"
            _upsert_node(
                conn,
                artifact_id,
                "artifact",
                Path(row[5]).name if row[5] else artifact_key[:16],
                provenance=provenance,
                confidence=score,
                artifact_path=row[5],
                artifact_sha=row[6],
            )
            _upsert_edge(
                conn,
                artifact_id,
                claim_id,
                "evidence_for",
                confidence=score,
                task_id=row[1],
            )
            counts["artifacts"] += 1

            for url in _artifact_sources(artifact_payload):
                source_id = "source:" + hashlib.sha256(url.encode()).hexdigest()
                _upsert_node(
                    conn,
                    source_id,
                    "source",
                    url,
                    provenance="PUBLIC_WEB",
                    confidence=min(score, 0.85),
                    metadata={"url": url},
                )
                _upsert_edge(
                    conn,
                    source_id,
                    artifact_id,
                    "cited_by",
                    confidence=min(score, 0.85),
                    task_id=row[1],
                )
                counts["sources"] += 1

    # Immutable integration candidates connect tasks to commits.
    try:
        queue_rows = conn.execute(
            """select task_id,sha,branch,status,verification_mode,
                      integrated_at,updated_at
                 from integration_queue"""
        )
        for row in queue_rows:
            commit_id = f"commit:{row[1]}"
            conf = 1.0 if row[3] == "INTEGRATED" else 0.85
            _upsert_node(
                conn,
                commit_id,
                "commit",
                row[1][:12],
                provenance="GIT_EXACT_SHA",
                confidence=conf,
                metadata={
                    "sha": row[1],
                    "branch": row[2],
                    "status": row[3],
                    "verification_mode": row[4],
                    "integrated_at": row[5],
                    "updated_at": row[6],
                },
            )
            _upsert_edge(
                conn,
                f"task:{row[0]}",
                commit_id,
                "produced",
                confidence=conf,
                task_id=row[0],
            )
            counts["commits"] += 1
    except sqlite3.OperationalError:
        pass

    conn.commit()
    return counts


def task_knowledge(conn: sqlite3.Connection, task_id: str) -> TaskKnowledge:
    ensure_schema(conn)
    task_node = f"task:{task_id}"
    policy_row = conn.execute(
        "select coalesce(evidence_policy,'') from task_metadata where task_id=?",
        (task_id,),
    ).fetchone()
    evidence_policy = str(policy_row[0] if policy_row else "")
    requires_global_authority = "global" in evidence_policy.lower()

    claims = list(
        conn.execute(
            """select n.confidence,n.provenance,n.artifact_sha
                 from knowledge_edges e
                 join knowledge_nodes n on n.node_id=e.src
                where e.dst=? and e.relation='supports'""",
            (task_node,),
        )
    )
    artifacts = set()
    confirmed = 0
    unresolved = 0
    scores = []
    for row in claims:
        score = float(row[0] or 0)
        provenance = str(row[1] or "").upper()
        if (
            requires_global_authority
            and "CURRENT_JP" in provenance
            and "GLOBAL" not in provenance
        ):
            # A perfectly confirmed current-JP observation is still only
            # lineage/reference evidence for a historical-Global predicate.
            score = min(score, CONFIDENCE_SCORE["SUPPORTED INFERENCE"])
        scores.append(score)
        if score >= 0.90:
            confirmed += 1
        if score <= 0.30:
            unresolved += 1
        if row[2]:
            artifacts.add(row[2])

    source_count = int(
        conn.execute(
            """select count(distinct s.node_id)
                 from knowledge_edges supports
                 join knowledge_nodes claim on claim.node_id=supports.src
                 join knowledge_edges evidence on evidence.dst=claim.node_id
                                             and evidence.relation='evidence_for'
                 join knowledge_edges cited on cited.dst=evidence.src
                                          and cited.relation='cited_by'
                 join knowledge_nodes s on s.node_id=cited.src
                where supports.dst=? and supports.relation='supports'
                  and s.kind='source'""",
            (task_node,),
        ).fetchone()[0]
    )
    if scores:
        # Confidence cannot be upgraded merely by quantity. Use strongest
        # support with a small corroboration bonus capped below 1.0.
        strongest = max(scores)
        corroboration = min(0.08, 0.02 * max(0, len(scores) - 1))
        support = min(1.0, strongest + corroboration)
    else:
        support = 0.0

    return TaskKnowledge(
        task_id=task_id,
        support_score=support,
        discovery_count=len(claims),
        confirmed_count=confirmed,
        artifact_count=len(artifacts),
        source_count=source_count,
        unresolved_count=unresolved,
    )


def graph_stats(conn: sqlite3.Connection) -> dict:
    ensure_schema(conn)
    return {
        "nodes": int(conn.execute("select count(*) from knowledge_nodes").fetchone()[0]),
        "edges": int(conn.execute("select count(*) from knowledge_edges").fetchone()[0]),
        "tasks": int(
            conn.execute(
                "select count(*) from knowledge_nodes where kind='task'"
            ).fetchone()[0]
        ),
        "claims": int(
            conn.execute(
                "select count(*) from knowledge_nodes where kind='claim'"
            ).fetchone()[0]
        ),
        "artifacts": int(
            conn.execute(
                "select count(*) from knowledge_nodes where kind='artifact'"
            ).fetchone()[0]
        ),
        "sources": int(
            conn.execute(
                "select count(*) from knowledge_nodes where kind='source'"
            ).fetchone()[0]
        ),
    }


def query_nodes(conn: sqlite3.Connection, term: str, limit: int = 20) -> list[dict]:
    ensure_schema(conn)
    like = f"%{term}%"
    rows = conn.execute(
        """select node_id,kind,label,provenance,confidence,artifact_path,
                  artifact_sha,metadata_json
             from knowledge_nodes
            where label like ? or metadata_json like ?
            order by confidence desc,kind,node_id
            limit ?""",
        (like, like, max(1, limit)),
    )
    return [dict(row) for row in rows]
