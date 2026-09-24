from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ImpactPlan:
    source_task_id: str
    impacted_tasks: tuple[str, ...]
    integrated_commits: tuple[dict, ...]

    def to_dict(self) -> dict:
        return {
            "source_task_id": self.source_task_id,
            "impacted_tasks": list(self.impacted_tasks),
            "integrated_commits": list(self.integrated_commits),
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists impact_incidents(
          event_id integer primary key,
          source_task_id text not null,
          fingerprint text not null unique,
          review_task_id text,
          impacted_tasks_json text not null,
          integrated_commits_json text not null,
          status text not null default 'OPEN',
          created_at text not null,
          updated_at text not null
        );
        create index if not exists idx_impact_incidents_source
          on impact_incidents(source_task_id);
        create table if not exists impact_state(
          key text primary key,
          value text not null,
          updated_at text not null
        );
        """
    )
    try:
        max_conflict = int(
            conn.execute(
                """select coalesce(max(id),0) from brain_events
                    where event_type='EVIDENCE_CONFLICT'"""
            ).fetchone()[0]
        )
    except sqlite3.OperationalError:
        max_conflict = 0
    conn.execute(
        """insert or ignore into impact_state(key,value,updated_at)
           values('last_event_id',?,?)""",
        (str(max_conflict), _now()),
    )
    conn.commit()


def _task_exists(conn: sqlite3.Connection, task_id: str) -> bool:
    return conn.execute(
        "select 1 from tasks where id=?",
        (task_id,),
    ).fetchone() is not None


def downstream_tasks(
    conn: sqlite3.Connection,
    source_task_id: str,
) -> list[str]:
    if not _task_exists(conn, source_task_id):
        return []
    rows = conn.execute(
        """
        with recursive downstream(task_id) as (
          select ?
          union
          select d.task_id
            from task_dependencies d
            join downstream x on d.depends_on=x.task_id
        )
        select distinct task_id from downstream
        """,
        (source_task_id,),
    )
    return sorted(str(row[0]) for row in rows)


def _integrated_commits(
    conn: sqlite3.Connection,
    task_ids: list[str],
) -> list[dict]:
    if not task_ids:
        return []
    marks = ",".join("?" for _ in task_ids)
    try:
        rows = conn.execute(
            f"""
            select task_id,sha,branch,status,verification_mode,integrated_at
              from integration_queue
             where task_id in ({marks})
               and status in ('INTEGRATED','APPLIED')
             order by task_id,integrated_at,sha
            """,
            task_ids,
        )
    except sqlite3.OperationalError:
        return []
    return [dict(row) for row in rows]


def impact_plan(
    conn: sqlite3.Connection,
    source_task_id: str,
) -> ImpactPlan:
    tasks = downstream_tasks(conn, source_task_id)
    commits = _integrated_commits(conn, tasks)
    return ImpactPlan(
        source_task_id=source_task_id,
        impacted_tasks=tuple(tasks),
        integrated_commits=tuple(commits),
    )


def _fingerprint(event: sqlite3.Row, plan: ImpactPlan) -> str:
    payload = {
        "event_id": int(event["id"]),
        "task_id": event["task_id"],
        "artifact_sha256": event["artifact_sha256"],
        "subject": event["subject"],
        "impacted_tasks": list(plan.impacted_tasks),
        "commits": [
            {
                "task_id": row.get("task_id"),
                "sha": row.get("sha"),
            }
            for row in plan.integrated_commits
        ],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _review_task_id(source_task_id: str, fingerprint: str) -> str:
    safe = re.sub(r"[^A-Z0-9-]+", "-", source_task_id.upper()).strip("-")
    safe = safe[:58] or "UNSCOPED"
    return f"IMPACT-REVIEW-{safe}-{fingerprint[:10].upper()}"


def _insert_review_task(
    conn: sqlite3.Connection,
    *,
    event: sqlite3.Row,
    plan: ImpactPlan,
    fingerprint: str,
) -> str:
    task_id = _review_task_id(plan.source_task_id, fingerprint)
    if _task_exists(conn, task_id):
        return task_id

    source = conn.execute(
        "select priority,title from tasks where id=?",
        (plan.source_task_id,),
    ).fetchone()
    priority = max(0, int(source[0] if source else 0))
    title = f"Review evidence impact: {plan.source_task_id}"[:240]
    note = (
        f"Generated from explicit EVIDENCE_CONFLICT Brain event {event['id']}. "
        "Review only. Do not automatically change historical truth, code, "
        "confidence, merge state, or main."
    )
    now = _now()
    conn.execute(
        """insert into tasks(
             id,priority,lane,title,status,branch,owner,note,updated_at
           ) values(?,?,?,?,?,'',null,?,?)""",
        (task_id, priority, "research", title, "READY", note, now),
    )
    conn.execute(
        """insert into task_metadata(
             task_id,milestone,work_type,concurrency_key,expected_minutes,
             evidence_policy,created_at,updated_at
           ) values(?,?,?,?,?,?,?,?)""",
        (
            task_id,
            "impact-review",
            "research",
            f"impact:{plan.source_task_id}",
            30,
            "Evidence-first review. Explicit conflict may invalidate downstream "
            "implementation. Preserve provenance and require deterministic proof.",
            now,
            now,
        ),
    )
    criterion = (
        f"Resolve Brain EVIDENCE_CONFLICT event {event['id']} for "
        f"{plan.source_task_id}; inspect {len(plan.impacted_tasks)} impacted "
        f"task(s) and {len(plan.integrated_commits)} integrated commit(s). "
        "Record which downstream claims remain valid, require repair, or remain "
        "unresolved. No silent confidence promotion."
    )
    conn.execute(
        "insert into task_acceptance(task_id,ordinal,criterion) values(?,?,?)",
        (task_id, 1, criterion),
    )
    conn.execute(
        """insert or ignore into task_dependencies(
             task_id,depends_on,kind,rationale
           ) values(?,?,'evidence',?)""",
        (
            task_id,
            plan.source_task_id,
            f"Impact review for EVIDENCE_CONFLICT event {event['id']}",
        ),
    )
    return task_id


def scan_conflicts(
    conn: sqlite3.Connection,
    *,
    apply: bool = False,
    limit: int = 100,
) -> dict:
    ensure_schema(conn)
    watermark_row = conn.execute(
        "select value from impact_state where key='last_event_id'"
    ).fetchone()
    watermark = int(watermark_row[0] if watermark_row else 0)
    events = list(
        conn.execute(
            """
            select id,task_id,subject,body,artifact_path,artifact_sha256,ts
              from brain_events
             where event_type='EVIDENCE_CONFLICT'
               and task_id is not null
               and id>?
             order by id
             limit ?
            """,
            (watermark, max(1, limit)),
        )
    )
    candidates = []
    created = []
    skipped = []

    for event in events:
        if conn.execute(
            "select 1 from impact_incidents where event_id=?",
            (event["id"],),
        ).fetchone():
            continue
        source_task_id = str(event["task_id"])
        plan = impact_plan(conn, source_task_id)
        if not plan.impacted_tasks:
            skipped.append({"event_id": event["id"], "reason": "unknown task"})
            continue
        fingerprint = _fingerprint(event, plan)
        candidate = {
            "event_id": int(event["id"]),
            "source_task_id": source_task_id,
            "fingerprint": fingerprint,
            "impacted_tasks": list(plan.impacted_tasks),
            "integrated_commits": list(plan.integrated_commits),
            "subject": event["subject"],
        }
        candidates.append(candidate)
        if not apply:
            continue

        review_task_id = _insert_review_task(
            conn,
            event=event,
            plan=plan,
            fingerprint=fingerprint,
        )
        now = _now()
        conn.execute(
            """insert into impact_incidents(
                 event_id,source_task_id,fingerprint,review_task_id,
                 impacted_tasks_json,integrated_commits_json,status,
                 created_at,updated_at
               ) values(?,?,?,?,?,?,'OPEN',?,?)""",
            (
                event["id"],
                source_task_id,
                fingerprint,
                review_task_id,
                json.dumps(list(plan.impacted_tasks), sort_keys=True),
                json.dumps(list(plan.integrated_commits), sort_keys=True),
                now,
                now,
            ),
        )
        created.append(review_task_id)

    if apply:
        if events:
            conn.execute(
                """update impact_state set value=?,updated_at=?
                    where key='last_event_id'""",
                (str(max(int(event["id"]) for event in events)), _now()),
            )
        conn.commit()

    return {
        "apply": apply,
        "watermark": watermark,
        "candidates": candidates,
        "created_review_tasks": created,
        "skipped": skipped,
        "counts": {
            "candidates": len(candidates),
            "created": len(created),
            "skipped": len(skipped),
            "incidents_total": int(
                conn.execute("select count(*) from impact_incidents").fetchone()[0]
            ),
        },
        "policy": {
            "trigger": "explicit Brain EVIDENCE_CONFLICT events only",
            "automatic_truth_mutation": False,
            "automatic_code_mutation": False,
            "automatic_merge": False,
            "review_scope": "source task plus transitive downstream dependents",
        },
    }


def incident_status(conn: sqlite3.Connection, limit: int = 100) -> list[dict]:
    ensure_schema(conn)
    rows = conn.execute(
        """select event_id,source_task_id,fingerprint,review_task_id,status,
                  impacted_tasks_json,integrated_commits_json,created_at,updated_at
             from impact_incidents
            order by event_id desc limit ?""",
        (max(1, limit),),
    )
    result = []
    for row in rows:
        item = dict(row)
        item["impacted_tasks"] = json.loads(item.pop("impacted_tasks_json"))
        item["integrated_commits"] = json.loads(
            item.pop("integrated_commits_json")
        )
        result.append(item)
    return result
