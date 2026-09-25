from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Iterable

TASK_RE = re.compile(r"\b[A-Z][A-Z0-9]+(?:-[A-Z0-9]+){1,}\b")
SHA_RE = re.compile(r"\b[0-9a-f]{12,40}\b", re.I)
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
        return 0.35, "CLAIM"
    if role == "system-note":
        return 0.55, "CLAIM"
    if role == "tool-summary":
        if any(x in low for x in ("pass", "integrated", "exact sha", "hash-match", "verified")):
            return 0.82, "SUPPORTED"
        return 0.68, "SUPPORTED"
    if any(x in low for x in ("verified", "full e2e", "exact sha", "hash-match")):
        return 0.72, "SUPPORTED"
    return 0.50, "CLAIM"


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
    found = []
    direct = metadata.get("task_id")
    if isinstance(direct, str) and direct.strip():
        found.append(direct.strip())
    found.extend(TASK_RE.findall(text))
    return list(dict.fromkeys(found))


def _source_sha(text: str, metadata: dict) -> str | None:
    direct = metadata.get("sha")
    if isinstance(direct, str) and SHA_RE.fullmatch(direct.strip()):
        return direct.strip().lower()
    match = SHA_RE.search(text)
    return match.group(0).lower() if match else None


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
    statements = _sentences(row[4])
    inserted = 0
    facts = []
    tasks = _task_candidates(row[4], metadata)
    source_sha = _source_sha(row[4], metadata)

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
              fingerprint,session_id,message_id,ordinal,chat_id,role,kind,
              statement,confidence,truth_status,task_id,source_sha,metadata_json
            ) values(?,?,?,?,?,?,?,?,?,?,?,?,?)
            on conflict(fingerprint) do nothing
            """,
            (
                fingerprint,row[1],row[0],row[2],row[7],row[3],kind,statement,
                confidence,truth_status,task_id,source_sha,
                _compact({"message_sha256": row[5], "metadata": metadata}),
            ),
        )
        if cur.rowcount:
            inserted += 1
        fact_row = conn.execute(
            """
            select id,fingerprint,session_id,message_id,ordinal,chat_id,role,kind,
                   statement,confidence,truth_status,task_id,source_sha
              from memory_facts where fingerprint=?
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
    params: list[object] = []
    where = []
    if session_id:
        where.append("m.session_id=?")
        params.append(session_id)
    where_sql = ("where " + " and ".join(where)) if where else ""
    rows = conn.execute(
        f"""
        select m.id from chat_messages m
        {where_sql}
        and not exists(select 1 from memory_facts f where f.message_id=m.id)
        order by m.id asc limit ?
        """ if where else
        """
        select m.id from chat_messages m
         where not exists(select 1 from memory_facts f where f.message_id=m.id)
         order by m.id asc limit ?
        """,
        (*params, limit),
    ).fetchall()
    processed = 0
    inserted = 0
    for row in rows:
        result = distill_message(conn, int(row[0]))
        processed += 1
        inserted += result["inserted"]
    return {"processed_messages": processed, "inserted_facts": inserted}


def mark_truth(conn: sqlite3.Connection, fact_id: int, status: str, *,
               confidence: float | None = None, supersedes_id: int | None = None) -> dict:
    ensure_schema(conn)
    status = status.upper()
    if status not in {"CLAIM", "SUPPORTED", "VERIFIED", "REJECTED", "SUPERSEDED"}:
        raise ValueError(f"invalid truth status: {status}")
    fields = ["truth_status=?", "updated_at=datetime('now')"]
    values: list[object] = [status]
    if confidence is not None:
        fields.append("confidence=?")
        values.append(float(confidence))
    if supersedes_id is not None:
        fields.append("supersedes_id=?")
        values.append(int(supersedes_id))
    values.append(fact_id)
    conn.execute(f"update memory_facts set {','.join(fields)} where id=?", values)
    conn.commit()
    row = conn.execute(
        """
        select id,fingerprint,session_id,message_id,ordinal,chat_id,role,kind,
               statement,confidence,truth_status,task_id,source_sha
          from memory_facts where id=?
        """,
        (fact_id,),
    ).fetchone()
    if not row:
        raise ValueError(f"unknown memory fact: {fact_id}")
    return _fact_dict(row)


def relevant_facts(conn: sqlite3.Connection, task_id: str, *, terms: Iterable[str] = (),
                   limit: int = 20) -> list[dict]:
    ensure_schema(conn)
    terms = [t.strip().lower() for t in terms if t and t.strip()]
    rows = conn.execute(
        """
        select id,fingerprint,session_id,message_id,ordinal,chat_id,role,kind,
               statement,confidence,truth_status,task_id,source_sha
          from memory_facts
         where truth_status not in ('REJECTED','SUPERSEDED')
           and (task_id=? or task_id is null)
         order by confidence desc,id desc
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
                "select depends_on,kind,rationale from task_dependencies where task_id=?",
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
                  from integration_queue where task_id=? order by updated_at desc limit 5
                """,
                (task_id,),
            )
        ]

    terms = [task[1], task[4] or "", *scopes[:8]]
    facts = relevant_facts(conn, task_id, terms=terms, limit=fact_limit)

    knowledge = []
    if _table_exists(conn, "knowledge_nodes") and _table_exists(conn, "knowledge_edges"):
        knowledge = [
            {
                "node_id": r[0], "kind": r[1], "label": r[2],
                "provenance": r[3], "confidence": r[4],
                "relation": r[5],
            }
            for r in conn.execute(
                """
                select n.node_id,n.kind,n.label,n.provenance,n.confidence,e.relation
                  from knowledge_edges e join knowledge_nodes n on n.node_id=e.src
                 where e.dst=? or e.task_id=?
                 order by n.confidence desc limit ?
                """,
                (f"task:{task_id}", task_id, knowledge_limit),
            )
        ]

    # Transcript excerpts are only messages backing selected facts, bounded by limit.
    message_ids = [f["message_id"] for f in facts[:transcript_limit]]
    excerpts = []
    if message_ids:
        marks = ",".join("?" for _ in message_ids)
        excerpts = [
            {
                "message_id": r[0], "session_id": r[1], "ordinal": r[2],
                "role": r[3], "content": r[4][:900], "ts": r[5],
            }
            for r in conn.execute(
                f"""
                select id,session_id,ordinal,role,content,ts
                  from chat_messages where id in ({marks})
                 order by id desc
                """,
                message_ids,
            )
        ]

    return {
        "task": task_dict,
        "scopes": scopes,
        "dependencies": deps,
        "integration": integration,
        "structured_memory": facts,
        "knowledge": knowledge,
        "transcript_excerpts": excerpts[:transcript_limit],
        "bounds": {
            "fact_limit": fact_limit,
            "knowledge_limit": knowledge_limit,
            "transcript_limit": transcript_limit,
        },
    }


def _fact_dict(row) -> dict:
    return {
        "id": row[0], "fingerprint": row[1], "session_id": row[2],
        "message_id": row[3], "ordinal": row[4], "chat_id": row[5],
        "role": row[6], "kind": row[7], "statement": row[8],
        "confidence": float(row[9]), "truth_status": row[10],
        "task_id": row[11], "source_sha": row[12],
    }
