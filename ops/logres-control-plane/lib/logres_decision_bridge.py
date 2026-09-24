from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone

from logres_journal import ensure_schema as ensure_journal_schema


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_schema(conn: sqlite3.Connection) -> None:
    ensure_journal_schema(conn)
    conn.execute(
        """create table if not exists decision_bridge_imports(
             source_event_id integer primary key,
             decision_id integer not null,
             source_sha256 text not null,
             imported_at text not null
           )"""
    )
    conn.commit()


def _source_hash(row: sqlite3.Row) -> str:
    payload = {
        "id": row["id"],
        "ts": row["ts"],
        "sender": row["sender"],
        "task_id": row["task_id"],
        "subject": row["subject"],
        "body": row["body"],
        "artifact_path": row["artifact_path"],
        "artifact_sha256": row["artifact_sha256"],
        "meta_json": row["meta_json"],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _explicit_alternatives(meta: dict) -> list[str]:
    value = meta.get("alternatives")
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _evidence(row: sqlite3.Row) -> list[str]:
    evidence = [f"brain_event:{row['id']}"]
    if row["task_id"]:
        evidence.append(f"task:{row['task_id']}")
    if row["artifact_path"]:
        token = f"artifact:{row['artifact_path']}"
        if row["artifact_sha256"]:
            token += f"#sha256={row['artifact_sha256']}"
        evidence.append(token)
    return evidence


def plan(conn: sqlite3.Connection) -> list[dict]:
    ensure_schema(conn)
    rows = conn.execute(
        """select id,ts,sender,task_id,subject,body,
                  artifact_path,artifact_sha256,meta_json
             from brain_events
            where event_type='DECISION'
            order by id"""
    ).fetchall()
    out = []
    for row in rows:
        imported = conn.execute(
            "select decision_id from decision_bridge_imports where source_event_id=?",
            (row["id"],),
        ).fetchone()
        if imported:
            continue
        meta = json.loads(row["meta_json"] or "{}")
        scope = str(meta.get("scope") or (
            f"task:{row['task_id']}" if row["task_id"] else "project"
        ))
        out.append(
            {
                "source_event_id": int(row["id"]),
                "source_sha256": _source_hash(row),
                "ts": str(row["ts"]),
                "actor": str(row["sender"]),
                "scope": scope,
                "subject": str(row["subject"]),
                "why": str(row["body"]),
                "alternatives": _explicit_alternatives(meta),
                "selected": str(meta.get("selected") or row["subject"]),
                "evidence": _evidence(row),
                "expected_outcome": str(meta.get("expected_outcome") or ""),
                "task_id": str(row["task_id"]) if row["task_id"] else None,
                "sha": str(row["artifact_sha256"]) if row["artifact_sha256"] else None,
            }
        )
    return out


def apply(conn: sqlite3.Connection) -> list[dict]:
    candidates = plan(conn)
    imported = []
    for item in candidates:
        cur = conn.execute(
            """insert into project_decisions(
                 ts,actor,scope,subject,why,alternatives_json,selected,
                 evidence_json,expected_outcome,task_id,sha,supersedes_id
               ) values(?,?,?,?,?,?,?,?,?,?,?,null)""",
            (
                item["ts"],
                item["actor"],
                item["scope"],
                item["subject"],
                item["why"],
                json.dumps(item["alternatives"], sort_keys=True),
                item["selected"],
                json.dumps(item["evidence"], sort_keys=True),
                item["expected_outcome"],
                item["task_id"],
                item["sha"],
            ),
        )
        decision_id = int(cur.lastrowid)
        conn.execute(
            """insert into decision_bridge_imports(
                 source_event_id,decision_id,source_sha256,imported_at
               ) values(?,?,?,?)""",
            (
                item["source_event_id"],
                decision_id,
                item["source_sha256"],
                now(),
            ),
        )
        imported.append(
            {
                "source_event_id": item["source_event_id"],
                "decision_id": decision_id,
            }
        )
    conn.commit()
    return imported


def status(conn: sqlite3.Connection) -> dict:
    ensure_schema(conn)
    total = int(
        conn.execute(
            "select count(*) from brain_events where event_type='DECISION'"
        ).fetchone()[0]
    )
    imported = int(
        conn.execute("select count(*) from decision_bridge_imports").fetchone()[0]
    )
    return {
        "explicit_brain_decisions": total,
        "imported": imported,
        "pending": max(0, total - imported),
    }
