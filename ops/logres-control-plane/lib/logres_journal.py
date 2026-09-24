from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone

def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

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
    """)
    conn.commit()

def append_event(conn: sqlite3.Connection, *, actor: str, entity_type: str,
                 entity_id: str, action: str, cause: str = "", sha: str | None = None,
                 artifact_path: str | None = None, payload: dict | None = None,
                 dedupe_key: str | None = None) -> dict:
    ensure_schema(conn)
    payload_json = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"))
    try:
        cur = conn.execute(
            """insert into project_journal(
                 ts,actor,entity_type,entity_id,action,cause,sha,artifact_path,
                 payload_json,dedupe_key
               ) values(?,?,?,?,?,?,?,?,?,?)""",
            (now(),actor,entity_type,entity_id,action,cause,sha,artifact_path,payload_json,dedupe_key),
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
        (now(),actor,scope,subject,why,json.dumps(alternatives),selected,
         json.dumps(evidence),expected_outcome,task_id,sha,supersedes_id),
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
        (entity_type,entity_id),
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
    out=[]
    for r in rows:
        out.append({"id":r[0],"ts":r[1],"actor":r[2],"scope":r[3],"subject":r[4],
                    "why":r[5],"alternatives":json.loads(r[6]),"selected":r[7],
                    "evidence":json.loads(r[8]),"expected_outcome":r[9],
                    "task_id":r[10],"sha":r[11],"supersedes_id":r[12]})
    return out

def _event_dict(r) -> dict:
    return {"id":r[0],"ts":r[1],"actor":r[2],"entity_type":r[3],"entity_id":r[4],
            "action":r[5],"cause":r[6],"sha":r[7],"artifact_path":r[8],
            "payload":json.loads(r[9])}
