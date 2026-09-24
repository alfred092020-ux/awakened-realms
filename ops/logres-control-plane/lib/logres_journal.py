from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _compact(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _default_archive_root() -> Path:
    root = Path(os.environ.get("LOGRES_ROOT", "/home/ubuntu/logres"))
    return root / "control" / "chat-archive"


def _safe_session_filename(session_id: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", session_id).strip("-._") or "session"
    suffix = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:10]
    return f"{stem[:80]}-{suffix}.jsonl"


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    create table if not exists project_journal(
      id integer primary key autoincrement,
      ts text not null,
      actor text not null,
      entity_type text not null,
      entity_id text not null,
      action text not null,
      cause text not null default '',
      sha text,
      artifact_path text,
      payload_json text not null default '{}',
      dedupe_key text
    );
    create unique index if not exists project_journal_dedupe_uq
      on project_journal(dedupe_key) where dedupe_key is not null;
    create index if not exists project_journal_entity_idx
      on project_journal(entity_type,entity_id,id);
    create table if not exists project_decisions(
      id integer primary key autoincrement,
      ts text not null,
      actor text not null,
      scope text not null,
      subject text not null,
      why text not null,
      alternatives_json text not null default '[]',
      selected text not null,
      evidence_json text not null default '[]',
      expected_outcome text not null default '',
      task_id text,
      sha text,
      supersedes_id integer
    );
    create index if not exists project_decisions_scope_idx
      on project_decisions(scope,id);

    create table if not exists chat_sessions(
      session_id text primary key,
      chat_id text not null,
      title text not null default '',
      source text not null default 'chatgpt',
      opened_at text not null,
      updated_at text not null,
      archive_path text not null,
      metadata_json text not null default '{}'
    );
    create index if not exists chat_sessions_chat_idx
      on chat_sessions(chat_id,updated_at);

    create table if not exists chat_messages(
      id integer primary key autoincrement,
      session_id text not null,
      ordinal integer not null,
      ts text,
      role text not null,
      content text not null,
      external_id text,
      message_sha256 text not null,
      raw_json text not null,
      metadata_json text not null default '{}',
      source_path text,
      ingested_at text not null,
      foreign key(session_id) references chat_sessions(session_id) on delete cascade,
      unique(session_id,ordinal),
      unique(session_id,message_sha256)
    );
    create index if not exists chat_messages_session_idx
      on chat_messages(session_id,ordinal);
    create index if not exists chat_messages_hash_idx
      on chat_messages(message_sha256);
    """)
    conn.commit()


def append_event(conn: sqlite3.Connection, *, actor: str, entity_type: str,
                 entity_id: str, action: str, cause: str = "", sha: str | None = None,
                 artifact_path: str | None = None, payload: dict | None = None,
                 dedupe_key: str | None = None) -> dict:
    ensure_schema(conn)
    payload_json = _compact(payload or {})
    try:
        cur = conn.execute(
            """insert into project_journal(
                 ts,actor,entity_type,entity_id,action,cause,sha,artifact_path,
                 payload_json,dedupe_key
               ) values(?,?,?,?,?,?,?,?,?,?)""",
            (now(), actor, entity_type, entity_id, action, cause, sha, artifact_path,
             payload_json, dedupe_key),
        )
        conn.commit()
        return {"id": int(cur.lastrowid), "inserted": True}
    except sqlite3.IntegrityError:
        row = conn.execute(
            "select id from project_journal where dedupe_key=?", (dedupe_key,)
        ).fetchone()
        return {"id": int(row[0]), "inserted": False}


def add_decision(conn: sqlite3.Connection, *, actor: str, scope: str, subject: str,
                 why: str, alternatives: list[str], selected: str,
                 evidence: list[str], expected_outcome: str = "",
                 task_id: str | None = None, sha: str | None = None,
                 supersedes_id: int | None = None) -> int:
    ensure_schema(conn)
    cur = conn.execute(
        """insert into project_decisions(
             ts,actor,scope,subject,why,alternatives_json,selected,evidence_json,
             expected_outcome,task_id,sha,supersedes_id
           ) values(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (now(), actor, scope, subject, why, json.dumps(alternatives), selected,
         json.dumps(evidence), expected_outcome, task_id, sha, supersedes_id),
    )
    conn.commit()
    return int(cur.lastrowid)


def tail(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    ensure_schema(conn)
    rows = conn.execute(
        """select id,ts,actor,entity_type,entity_id,action,cause,sha,
                  artifact_path,payload_json
             from project_journal order by id desc limit ?""", (limit,)
    )
    return [_event_dict(row) for row in rows]


def entity_history(conn: sqlite3.Connection, entity_type: str, entity_id: str) -> list[dict]:
    ensure_schema(conn)
    rows = conn.execute(
        """select id,ts,actor,entity_type,entity_id,action,cause,sha,
                  artifact_path,payload_json
             from project_journal
            where entity_type=? and entity_id=? order by id""",
        (entity_type, entity_id),
    )
    return [_event_dict(row) for row in rows]


def decisions(conn: sqlite3.Connection, scope: str | None = None) -> list[dict]:
    ensure_schema(conn)
    if scope:
        rows = conn.execute(
            """select id,ts,actor,scope,subject,why,alternatives_json,selected,
                      evidence_json,expected_outcome,task_id,sha,supersedes_id
                 from project_decisions where scope=? order by id""", (scope,)
        )
    else:
        rows = conn.execute(
            """select id,ts,actor,scope,subject,why,alternatives_json,selected,
                      evidence_json,expected_outcome,task_id,sha,supersedes_id
                 from project_decisions order by id"""
        )
    out = []
    for r in rows:
        out.append({
            "id": r[0], "ts": r[1], "actor": r[2], "scope": r[3], "subject": r[4],
            "why": r[5], "alternatives": json.loads(r[6]), "selected": r[7],
            "evidence": json.loads(r[8]), "expected_outcome": r[9],
            "task_id": r[10], "sha": r[11], "supersedes_id": r[12],
        })
    return out


def open_chat(conn: sqlite3.Connection, *, chat_id: str, session_id: str | None = None,
              title: str = "", source: str = "chatgpt", metadata: dict | None = None,
              archive_root: str | Path | None = None) -> dict:
    ensure_schema(conn)
    session_id = session_id or str(uuid.uuid4())
    archive_root = Path(archive_root) if archive_root else _default_archive_root()
    archive_path = archive_root / _safe_session_filename(session_id)
    existing = conn.execute(
        "select chat_id,archive_path from chat_sessions where session_id=?", (session_id,)
    ).fetchone()
    stamp = now()
    if existing:
        if existing[0] != chat_id:
            raise ValueError(
                f"session {session_id} already belongs to chat_id {existing[0]!r}"
            )
        meta_json = _compact(metadata or {})
        conn.execute(
            """update chat_sessions
                  set title=case when ?<>'' then ? else title end,
                      source=case when ?<>'' then ? else source end,
                      updated_at=?,
                      metadata_json=case when ?<>'{}' then ? else metadata_json end
                where session_id=?""",
            (title, title, source, source, stamp, meta_json, meta_json, session_id),
        )
        conn.commit()
    else:
        conn.execute(
            """insert into chat_sessions(
                 session_id,chat_id,title,source,opened_at,updated_at,archive_path,metadata_json
               ) values(?,?,?,?,?,?,?,?)""",
            (session_id, chat_id, title, source, stamp, stamp, str(archive_path),
             _compact(metadata or {})),
        )
        conn.commit()
    row = conn.execute(
        """select session_id,chat_id,title,source,opened_at,updated_at,archive_path,
                  metadata_json from chat_sessions where session_id=?""",
        (session_id,),
    ).fetchone()
    return _session_dict(row, message_count=_message_count(conn, session_id))



def append_chat_message(conn: sqlite3.Connection, *, session_id: str, role: str,
                        content: str, ts: str | None = None,
                        external_id: str | None = None,
                        metadata: dict | None = None,
                        source_path: str = "live") -> dict:
    """Append one live message with an ordinal allocated under a SQLite write lock."""
    ensure_schema(conn)
    role = str(role).strip()
    if not role:
        raise ValueError("role must not be empty")
    if not isinstance(content, str):
        raise TypeError("content must be a string")
    if metadata is not None and not isinstance(metadata, dict):
        raise TypeError("metadata must be a dict")

    session = conn.execute(
        "select archive_path from chat_sessions where session_id=?", (session_id,)
    ).fetchone()
    if not session:
        raise ValueError(f"unknown chat session: {session_id}")
    archive_path = Path(session[0])

    conn.execute("begin immediate")
    try:
        if external_id:
            prior = conn.execute(
                """select id,session_id,ordinal,ts,role,content,external_id,
                          message_sha256,metadata_json,source_path,ingested_at
                     from chat_messages
                    where session_id=? and external_id=?
                    order by ordinal limit 1""",
                (session_id, external_id),
            ).fetchone()
            if prior:
                if prior[4] != role or prior[5] != content:
                    raise ValueError(
                        f"external_id {external_id!r} already exists with different content"
                    )
                conn.commit()
                out = _message_dict(prior)
                out.update({"inserted": False, "archive_appended": 0})
                return out

        ordinal = int(conn.execute(
            "select coalesce(max(ordinal),0)+1 from chat_messages where session_id=?",
            (session_id,),
        ).fetchone()[0])
        stamp = ts or now()
        source_record = {
            "ordinal": ordinal,
            "ts": stamp,
            "role": role,
            "content": content,
            "id": external_id,
            "metadata": metadata or {},
        }
        raw_json = _compact(source_record)
        record = _normalize_message(
            source_record, line_no=ordinal, raw_json=raw_json
        )
        cur = conn.execute(
            """insert into chat_messages(
                 session_id,ordinal,ts,role,content,external_id,message_sha256,
                 raw_json,metadata_json,source_path,ingested_at
               ) values(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                session_id, ordinal, record["ts"], record["role"],
                record["content"], record["external_id"], record["message_sha256"],
                record["raw_json"], _compact(record["metadata"]),
                source_path, now(),
            ),
        )
        conn.execute(
            "update chat_sessions set updated_at=? where session_id=?",
            (now(), session_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    archived = _append_archive_records(archive_path, session_id, [record])
    row = conn.execute(
        """select id,session_id,ordinal,ts,role,content,external_id,message_sha256,
                  metadata_json,source_path,ingested_at
             from chat_messages where id=?""",
        (int(cur.lastrowid),),
    ).fetchone()
    out = _message_dict(row)
    out.update({"inserted": True, "archive_appended": archived})
    return out


def list_chats(conn: sqlite3.Connection, *, chat_id: str | None = None,
               limit: int = 100) -> list[dict]:
    ensure_schema(conn)
    if chat_id:
        rows = conn.execute(
            """select session_id,chat_id,title,source,opened_at,updated_at,archive_path,
                      metadata_json,
                      (select count(*) from chat_messages m where m.session_id=s.session_id)
                 from chat_sessions s where chat_id=?
                order by updated_at desc limit ?""",
            (chat_id, limit),
        )
    else:
        rows = conn.execute(
            """select session_id,chat_id,title,source,opened_at,updated_at,archive_path,
                      metadata_json,
                      (select count(*) from chat_messages m where m.session_id=s.session_id)
                 from chat_sessions s
                order by updated_at desc limit ?""",
            (limit,),
        )
    return [_session_dict(r, message_count=int(r[8])) for r in rows]


def ingest_jsonl(conn: sqlite3.Connection, *, session_id: str,
                 transcript_path: str | Path,
                 archive_root: str | Path | None = None) -> dict:
    ensure_schema(conn)
    session = conn.execute(
        "select archive_path from chat_sessions where session_id=?", (session_id,)
    ).fetchone()
    if not session:
        raise ValueError(f"unknown chat session: {session_id}")
    transcript_path = Path(transcript_path)
    records = []
    with transcript_path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            raw = line.rstrip("\n")
            if not raw.strip():
                continue
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at line {line_no}: {exc}") from exc
            if not isinstance(parsed, dict):
                raise ValueError(f"JSONL line {line_no} must be an object")
            records.append(_normalize_message(parsed, line_no=line_no, raw_json=raw))

    archive_path = Path(session[0])
    if archive_root is not None:
        archive_path = Path(archive_root) / _safe_session_filename(session_id)
        conn.execute(
            "update chat_sessions set archive_path=?, updated_at=? where session_id=?",
            (str(archive_path), now(), session_id),
        )
        conn.commit()

    inserted = 0
    duplicate = 0
    conn.execute("begin immediate")
    try:
        for record in records:
            prior = conn.execute(
                """select message_sha256 from chat_messages
                    where session_id=? and ordinal=?""",
                (session_id, record["ordinal"]),
            ).fetchone()
            if prior:
                if prior[0] != record["message_sha256"]:
                    raise ValueError(
                        f"ordinal {record['ordinal']} already exists with different content"
                    )
                duplicate += 1
                continue
            conn.execute(
                """insert into chat_messages(
                     session_id,ordinal,ts,role,content,external_id,message_sha256,
                     raw_json,metadata_json,source_path,ingested_at
                   ) values(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    session_id, record["ordinal"], record["ts"], record["role"],
                    record["content"], record["external_id"], record["message_sha256"],
                    record["raw_json"], _compact(record["metadata"]),
                    str(transcript_path), now(),
                ),
            )
            inserted += 1
        conn.execute(
            "update chat_sessions set updated_at=? where session_id=?",
            (now(), session_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    archived = _append_archive_records(archive_path, session_id, records)
    return {
        "session_id": session_id,
        "source_path": str(transcript_path),
        "archive_path": str(archive_path),
        "input_records": len(records),
        "inserted": inserted,
        "duplicates": duplicate,
        "archive_appended": archived,
        "message_count": _message_count(conn, session_id),
    }


def show_chat(conn: sqlite3.Connection, session_id: str, *,
              after_ordinal: int = 0, limit: int = 100) -> list[dict]:
    ensure_schema(conn)
    rows = conn.execute(
        """select id,session_id,ordinal,ts,role,content,external_id,message_sha256,
                  metadata_json,source_path,ingested_at
             from chat_messages
            where session_id=? and ordinal>?
            order by ordinal asc limit ?""",
        (session_id, after_ordinal, limit),
    )
    return [_message_dict(r) for r in rows]


def search_chat(conn: sqlite3.Connection, query: str, *, session_id: str | None = None,
                chat_id: str | None = None, limit: int = 50) -> list[dict]:
    ensure_schema(conn)
    clauses = ["m.content like ?"]
    params: list[object] = [f"%{query}%"]
    if session_id:
        clauses.append("m.session_id=?")
        params.append(session_id)
    if chat_id:
        clauses.append("s.chat_id=?")
        params.append(chat_id)
    params.append(limit)
    where = " and ".join(clauses)
    rows = conn.execute(
        f"""select m.id,m.session_id,m.ordinal,m.ts,m.role,m.content,m.external_id,
                   m.message_sha256,m.metadata_json,m.source_path,m.ingested_at
              from chat_messages m
              join chat_sessions s on s.session_id=m.session_id
             where {where}
             order by m.id desc limit ?""",
        tuple(params),
    )
    return [_message_dict(r) for r in rows]


def export_chat(conn: sqlite3.Connection, session_id: str, output_path: str | Path) -> dict:
    ensure_schema(conn)
    exists = conn.execute(
        "select 1 from chat_sessions where session_id=?", (session_id,)
    ).fetchone()
    if not exists:
        raise ValueError(f"unknown chat session: {session_id}")
    rows = conn.execute(
        "select raw_json from chat_messages where session_id=? order by ordinal",
        (session_id,),
    ).fetchall()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(output_path.parent, 0o700)
    tmp = output_path.with_name(output_path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(row[0])
            handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, output_path)
    digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
    return {
        "session_id": session_id,
        "path": str(output_path),
        "messages": len(rows),
        "sha256": digest,
    }


def _normalize_message(record: dict, *, line_no: int, raw_json: str) -> dict:
    ordinal = record.get("ordinal", line_no)
    if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 1:
        raise ValueError(f"invalid ordinal at line {line_no}: {ordinal!r}")
    role = str(record.get("role", record.get("type", "unknown"))).strip() or "unknown"
    content = record.get("content", record.get("text", ""))
    if not isinstance(content, str):
        content = _compact(content)
    ts = record.get("ts", record.get("timestamp"))
    external_id = record.get("id", record.get("message_id"))
    metadata = record.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {"value": metadata}
    canonical = {
        "ordinal": ordinal,
        "ts": ts,
        "role": role,
        "content": content,
        "external_id": external_id,
        "metadata": metadata,
    }
    return {
        **canonical,
        "raw_json": raw_json,
        "message_sha256": _sha256_text(_compact(canonical)),
    }


def _append_archive_records(path: Path, session_id: str, records: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    appended = 0
    with path.open("a+", encoding="utf-8", newline="\n") as handle:
        os.chmod(path, 0o600)
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        existing = set()
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            digest = row.get("message_sha256")
            if digest:
                existing.add(digest)
        handle.seek(0, os.SEEK_END)
        for record in records:
            digest = record["message_sha256"]
            if digest in existing:
                continue
            envelope = {
                "session_id": session_id,
                "ordinal": record["ordinal"],
                "ts": record["ts"],
                "role": record["role"],
                "content": record["content"],
                "external_id": record["external_id"],
                "metadata": record["metadata"],
                "message_sha256": digest,
                "raw_json": record["raw_json"],
            }
            handle.write(_compact(envelope))
            handle.write("\n")
            existing.add(digest)
            appended += 1
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return appended


def _message_count(conn: sqlite3.Connection, session_id: str) -> int:
    row = conn.execute(
        "select count(*) from chat_messages where session_id=?", (session_id,)
    ).fetchone()
    return int(row[0])


def _session_dict(r, *, message_count: int) -> dict:
    return {
        "session_id": r[0],
        "chat_id": r[1],
        "title": r[2],
        "source": r[3],
        "opened_at": r[4],
        "updated_at": r[5],
        "archive_path": r[6],
        "metadata": json.loads(r[7]),
        "message_count": message_count,
    }


def _message_dict(r) -> dict:
    return {
        "id": r[0],
        "session_id": r[1],
        "ordinal": r[2],
        "ts": r[3],
        "role": r[4],
        "content": r[5],
        "external_id": r[6],
        "message_sha256": r[7],
        "metadata": json.loads(r[8]),
        "source_path": r[9],
        "ingested_at": r[10],
    }


def _event_dict(r) -> dict:
    return {
        "id": r[0], "ts": r[1], "actor": r[2], "entity_type": r[3], "entity_id": r[4],
        "action": r[5], "cause": r[6], "sha": r[7], "artifact_path": r[8],
        "payload": json.loads(r[9]),
    }
