from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Iterable

from logres_context_pack import _redact as _redact_context_value

TASK_RE = re.compile(r"\b[A-Z][A-Z0-9]+(?:-[A-Z0-9]+){1,}\b")
SHA_RE = re.compile(r"\b[0-9a-f]{40}\b", re.I)
FILE_RE = re.compile(r"(?<![\w.-])(?:[\w.-]+/)+[\w.-]+(?:\.[A-Za-z0-9]+)?")

FACT_KINDS = {
    "decision": ("decided", "decision", "we will", "will use", "chosen", "choose"),
    "failure": ("failed", "failure", "error", "broken", "blocked", "quarantined"),
    "discovery": ("found", "discovered", "evidence", "shows", "indicates", "confirmed"),
    "completion": ("completed", "done", "integrated", "merged", "passed"),
    "constraint": ("must", "do not", "don't", "never", "required", "cannot"),
}


@dataclass(frozen=True)
class MemoryFact:
    fact_id: int
    fingerprint: str
    session_id: str
    message_id: int
    ordinal: int
    chat_id: str
    role: str
    kind: str
    statement: str
    confidence: float
    truth_status: str
    task_id: str | None
    source_sha: str | None


SENSITIVE_METADATA_KEY_RE = re.compile(
    r"(token|secret|password|passwd|api[_-]?key|credential|private[_-]?key)",
    re.I,
)


def _sanitize_metadata(value, counter):
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if SENSITIVE_METADATA_KEY_RE.search(str(key)):
                out[str(key)] = "[REDACTED]"
                counter[0] += 1
            else:
                out[str(key)] = _sanitize_metadata(item, counter)
        return out
    if isinstance(value, list):
        return [_sanitize_metadata(item, counter) for item in value]
    return _redact_context_value(value, counter)


def _compact(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists memory_facts(
          id integer primary key autoincrement,
          fingerprint text not null unique,
          session_id text not null,
          message_id integer not null,
          message_sha256 text,
          ordinal integer not null,
          chat_id text not null,
          role text not null,
          kind text not null,
          statement text not null,
          confidence real not null,
          truth_status text not null default 'CLAIM',
          task_id text,
          source_sha text,
          metadata_json text not null default '{}',
          supersedes_id integer,
          created_at text not null default (datetime('now')),
          updated_at text not null default (datetime('now'))
        );
        create index if not exists memory_facts_task_idx
          on memory_facts(task_id,truth_status,id);
        create index if not exists memory_facts_session_idx
          on memory_facts(session_id,ordinal,id);
        create index if not exists memory_facts_kind_idx
          on memory_facts(kind,truth_status,id);

        create table if not exists memory_distill_state(
          session_id text primary key,
          last_message_id integer not null default 0,
          updated_at text not null default (datetime('now'))
        );
        """
    )
    columns = {row[1] for row in conn.execute("pragma table_info(memory_facts)")}
    if "message_sha256" not in columns:
        conn.execute("alter table memory_facts add column message_sha256 text")
    journal_exists = conn.execute(
        "select 1 from sqlite_master where type='table' and name='chat_messages'"
    ).fetchone()
    if journal_exists:
        conn.execute(
            """
            update memory_facts
               set message_sha256=(
                   select m.message_sha256 from chat_messages m
                    where m.id=memory_facts.message_id
                      and m.session_id=memory_facts.session_id
               )
             where message_sha256 is null
            """
        )
    conn.commit()


def _infer_kind(text: str) -> str:
    low = text.lower()
    for kind, terms in FACT_KINDS.items():
        if any(term in low for term in terms):
            return kind
    return "note"


def _infer_confidence(role: str, text: str) -> tuple[float, str]:
    low = text.lower()
    if role == "user":
        confidence = 0.35
    elif role == "system-note":
        confidence = 0.55
    elif role == "tool-summary":
        confidence = 0.82 if any(
            x in low for x in ("pass", "integrated", "exact sha", "hash-match", "verified")
        ) else 0.68
    elif any(x in low for x in ("verified", "full e2e", "exact sha", "hash-match")):
        confidence = 0.72
    else:
        confidence = 0.50
    # Transcript-derived memory is always advisory. Brain remains operational truth.
    return confidence, "CLAIM"


def _sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    out: list[str] = []
    for chunk in chunks:
        clean = " ".join(chunk.split()).strip(" -*•\t")
        if len(clean) < 12:
            continue
        if len(clean) > 600:
            clean = clean[:600]
        out.append(clean)
    return out[:24]


def _task_candidates(text: str, metadata: dict) -> list[str]:
    # Task scoping comes only from explicit journal metadata. Task-like text is
    # advisory content and must not silently bind a fact to a Brain task.
    del text
    direct = metadata.get("task_id")
    if isinstance(direct, str):
        value = direct.strip()
        if TASK_RE.fullmatch(value):
            return [value]
    return []


def _source_sha(text: str, metadata: dict) -> str | None:
    # Transcript memory never asserts Git provenance. Exact-SHA truth stays in Brain/Git.
    del text, metadata
    return None


def distill_message(conn: sqlite3.Connection, message_id: int) -> dict:
    ensure_schema(conn)
    row = conn.execute(
        """
        select m.id,m.session_id,m.ordinal,m.role,m.content,m.message_sha256,
               m.metadata_json,s.chat_id
          from chat_messages m join chat_sessions s on s.session_id=m.session_id
         where m.id=?
        """,
        (message_id,),
    ).fetchone()
    if not row:
        raise ValueError(f"unknown chat message id: {message_id}")

    metadata = json.loads(row[6] or "{}")
    redactions = [0]
    safe_metadata = _sanitize_metadata(metadata, redactions)
    safe_content = _redact_context_value(row[4], redactions)
    statements = _sentences(safe_content)
    inserted = 0
    facts = []
    tasks = _task_candidates(safe_content, safe_metadata)
    source_sha = _source_sha(safe_content, safe_metadata)

    for statement in statements:
        kind = _infer_kind(statement)
        # Do not clutter structured memory with generic conversational filler.
        if kind == "note" and not TASK_RE.search(statement) and not SHA_RE.search(statement):
            continue
        confidence, truth_status = _infer_confidence(row[3], statement)
        task_id = next((t for t in tasks if t in statement), tasks[0] if len(tasks) == 1 else None)
        fp_payload = {
            "session_id": row[1],
            "message_sha256": row[5],
            "statement": statement,
            "kind": kind,
            "task_id": task_id,
        }
        fingerprint = hashlib.sha256(_compact(fp_payload).encode()).hexdigest()
        cur = conn.execute(
            """
            insert into memory_facts(
              fingerprint,session_id,message_id,message_sha256,ordinal,chat_id,role,kind,
              statement,confidence,truth_status,task_id,source_sha,metadata_json
            ) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            on conflict(fingerprint) do nothing
            """,
            (
                fingerprint,row[1],row[0],row[5],row[2],row[7],row[3],kind,statement,
                confidence,truth_status,task_id,source_sha,
                _compact({"message_sha256": row[5], "metadata": safe_metadata, "redactions": redactions[0]}),
            ),
        )
        if cur.rowcount:
            inserted += 1
        fact_row = conn.execute(
            """
            select f.id,f.fingerprint,f.session_id,f.message_id,f.ordinal,f.chat_id,
                   f.role,f.kind,f.statement,f.confidence,f.truth_status,f.task_id,
                   f.source_sha,f.message_sha256
              from memory_facts f
             where f.fingerprint=?
            """,
            (fingerprint,),
        ).fetchone()
        facts.append(_fact_dict(fact_row))

    conn.execute(
        """
        insert into memory_distill_state(session_id,last_message_id,updated_at)
        values(?,?,datetime('now'))
        on conflict(session_id) do update set
          last_message_id=max(memory_distill_state.last_message_id,excluded.last_message_id),
          updated_at=datetime('now')
        """,
        (row[1], row[0]),
    )
    conn.commit()
    return {"message_id": row[0], "inserted": inserted, "facts": facts}


def distill_pending(conn: sqlite3.Connection, session_id: str | None = None, limit: int = 200) -> dict:
    ensure_schema(conn)
    if not session_id:
        raise ValueError("session_id is required for pending distillation")
    if not 1 <= int(limit) <= 500:
        raise ValueError("limit must be between 1 and 500")
    rows = conn.execute(
        """
        select m.id from chat_messages m
         where m.session_id=?
           and not exists(select 1 from memory_facts f where f.message_id=m.id)
         order by m.id asc limit ?
        """,
        (session_id, int(limit)),
    ).fetchall()
    processed = 0
    inserted = 0
    for row in rows:
        result = distill_message(conn, int(row[0]))
        processed += 1
        inserted += result["inserted"]
    return {"processed_messages": processed, "inserted_facts": inserted}


def relevant_facts(conn: sqlite3.Connection, task_id: str, *, terms: Iterable[str] = (),
                   limit: int = 20) -> list[dict]:
    ensure_schema(conn)
    terms = [t.strip().lower() for t in terms if t and t.strip()]
    rows = conn.execute(
        """
        select f.id,f.fingerprint,f.session_id,f.message_id,f.ordinal,f.chat_id,
               f.role,f.kind,f.statement,f.confidence,f.truth_status,f.task_id,
               f.source_sha,f.message_sha256
          from memory_facts f
         where f.truth_status='CLAIM'
           and f.task_id=?
         order by f.confidence desc,f.id desc
         limit 500
        """,
        (task_id,),
    ).fetchall()
    scored = []
    task_tokens = set(re.findall(r"[a-z0-9]+", task_id.lower()))
    for row in rows:
        d = _fact_dict(row)
        text_tokens = set(re.findall(r"[a-z0-9]+", d["statement"].lower()))
        overlap = len(task_tokens & text_tokens)
        term_hits = sum(1 for t in terms if t in d["statement"].lower())
        direct = 4 if d["task_id"] == task_id else 0
        score = direct + overlap + (term_hits * 2) + d["confidence"]
        if direct or overlap or term_hits:
            scored.append((score, d))
    scored.sort(key=lambda x: (-x[0], -x[1]["id"]))
    return [x[1] for x in scored[:max(1, limit)]]


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return bool(conn.execute(
        "select 1 from sqlite_master where type='table' and name=?", (name,)
    ).fetchone())


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row[1] == column for row in conn.execute(f"pragma table_info({table})"))


def build_context_packet(conn: sqlite3.Connection, task_id: str, *,
                         transcript_limit: int = 12, fact_limit: int = 20,
                         knowledge_limit: int = 12) -> dict:
    ensure_schema(conn)
    task = conn.execute(
        "select id,title,status,priority,lane,note,owner from tasks where id=?",
        (task_id,),
    ).fetchone()
    if not task:
        raise ValueError(f"unknown task: {task_id}")
    task_dict = {
        "id": task[0], "title": task[1], "status": task[2], "priority": task[3],
        "lane": task[4], "note": task[5] or "", "owner": task[6] or "",
    }
    scopes = []
    if _table_exists(conn, "task_scopes"):
        scopes = [r[0] for r in conn.execute(
            "select path_prefix from task_scopes where task_id=? order by path_prefix",
            (task_id,),
        )]
    deps = []
    if _table_exists(conn, "task_dependencies"):
        deps = [
            {"depends_on": r[0], "kind": r[1], "rationale": r[2] or ""}
            for r in conn.execute(
                "select depends_on,kind,rationale from task_dependencies where task_id=? order by depends_on,kind",
                (task_id,),
            )
        ]
    integration = []
    if _table_exists(conn, "integration_queue"):
        integration = [
            {
                "sha": r[0], "branch": r[1], "status": r[2],
                "verification_mode": r[3], "updated_at": r[4],
            }
            for r in conn.execute(
                """
                select sha,branch,status,verification_mode,updated_at
                  from integration_queue where task_id=? order by updated_at desc,sha asc limit 5
                """,
                (task_id,),
            )
        ]

    terms = [task[1], task[4] or "", *scopes[:8]]
    facts = relevant_facts(conn, task_id, terms=terms, limit=fact_limit)
    for fact in facts:
        fact["operational_truth"] = False
        fact["provenance"]["claimed_source_sha"] = fact.get("source_sha")

    knowledge = []
    if _table_exists(conn, "knowledge_nodes") and _table_exists(conn, "knowledge_edges"):
        if _column_exists(conn, "knowledge_edges", "task_id"):
            knowledge_rows = conn.execute(
                """
                select n.node_id,n.kind,n.label,n.provenance,n.confidence,e.relation
                  from knowledge_edges e join knowledge_nodes n on n.node_id=e.src
                 where e.dst=? or e.task_id=?
                 order by n.confidence desc,n.node_id asc,e.relation asc limit ?
                """,
                (f"task:{task_id}", task_id, knowledge_limit),
            )
        else:
            knowledge_rows = conn.execute(
                """
                select n.node_id,n.kind,n.label,n.provenance,n.confidence,e.relation
                  from knowledge_edges e join knowledge_nodes n on n.node_id=e.src
                 where e.dst=?
                 order by n.confidence desc,n.node_id asc,e.relation asc limit ?
                """,
                (f"task:{task_id}", knowledge_limit),
            )
        knowledge = [
            {
                "node_id": r[0], "kind": r[1], "label": r[2],
                "provenance": r[3], "confidence": r[4],
                "relation": r[5],
            }
            for r in knowledge_rows
        ]

    # Transcript persistence remains in the journal. Memory context exposes only
    # distilled, provenance-labeled facts and never replays raw transcript text.
    excerpts: list[dict] = []

    packet = {
        "task": task_dict,
        "scopes": scopes,
        "dependencies": deps,
        "integration": integration,
        "structured_memory": facts,
        "memory_policy": {
            "operational_truth_source": "Brain only",
            "memory_facts_are_context_only": True,
            "raw_transcript_replay": False,
        },
        "knowledge": knowledge,
        "transcript_excerpts": excerpts[:transcript_limit],
        "bounds": {
            "fact_limit": fact_limit,
            "knowledge_limit": knowledge_limit,
            "transcript_limit": transcript_limit,
        },
    }
    redactions = [0]
    packet = _redact_context_value(packet, redactions)
    packet["redactions"] = redactions[0]
    return packet


def _fact_dict(row) -> dict:
    truth_status = row[10]
    source_sha = row[12]
    message_sha256 = row[13] if len(row) > 13 else None
    task_id = row[11]
    return {
        "id": row[0], "fingerprint": row[1], "session_id": row[2],
        "message_id": row[3], "ordinal": row[4], "chat_id": row[5],
        "role": row[6], "kind": row[7], "statement": row[8],
        "confidence": float(row[9]), "truth_status": truth_status,
        "task_id": task_id, "source_sha": source_sha,
        "operational_truth": False,
        "provenance": {
            "session_id": row[2], "message_id": row[3], "ordinal": row[4],
            "message_sha256": message_sha256,
            "chat_id": row[5], "role": row[6], "source_sha": source_sha,
            "task_binding": "journal-metadata" if task_id else None,
        },
    }
