from __future__ import annotations

import json
import math
import re
import sqlite3
from datetime import datetime, timezone
from typing import Iterable


CONNECTION_STATES = {"CONNECTED", "AVAILABLE", "UNKNOWN", "DISCONNECTED", "DENIED"}
HEALTH_STATES = {"HEALTHY", "DEGRADED", "UNHEALTHY", "UNKNOWN"}
OUTCOMES = {"SUCCESS", "FAILURE", "PARTIAL", "SKIPPED"}

DEFAULT_CAPABILITIES = [
    {
        "capability_id": "github",
        "provider": "GitHub",
        "tool_family": "github",
        "connection_state": "CONNECTED",
        "health": "HEALTHY",
        "action_class": "READ_WRITE",
        "fallback_rank": 10,
        "actions": ["repo_read", "branch", "commit", "issue", "pull_request", "code_search"],
        "affinities": ["git", "github", "repo", "repository", "branch", "commit", "pull request", "source code", "code"],
    },
    {
        "capability_id": "remote-desktop",
        "provider": "Remote Desktop Commander",
        "tool_family": "remote_desktop",
        "connection_state": "CONNECTED",
        "health": "HEALTHY",
        "action_class": "READ_WRITE",
        "fallback_rank": 10,
        "actions": ["shell", "filesystem", "process", "runtime", "vm"],
        "affinities": ["vm", "oracle", "terminal", "shell", "runtime", "process", "logs", "build", "deploy", "server"],
    },
    {
        "capability_id": "web",
        "provider": "OpenAI Web",
        "tool_family": "web",
        "connection_state": "AVAILABLE",
        "health": "HEALTHY",
        "action_class": "READ_ONLY",
        "fallback_rank": 20,
        "actions": ["search", "research", "public_docs", "current_info"],
        "affinities": ["web", "research", "latest", "current", "public", "documentation", "docs", "internet", "reference"],
    },
    {
        "capability_id": "files",
        "provider": "OpenAI Files",
        "tool_family": "files",
        "connection_state": "AVAILABLE",
        "health": "HEALTHY",
        "action_class": "READ_WRITE",
        "fallback_rank": 20,
        "actions": ["search", "read", "materialize", "library"],
        "affinities": ["file", "artifact", "upload", "document", "project knowledge", "library"],
    },
    {
        "capability_id": "image-generation",
        "provider": "OpenAI Image Generation",
        "tool_family": "image_gen",
        "connection_state": "AVAILABLE",
        "health": "HEALTHY",
        "action_class": "WRITE",
        "fallback_rank": 30,
        "actions": ["generate", "edit"],
        "affinities": ["image", "art", "sprite", "visual", "concept", "illustration", "asset", "anime"],
    },
    {
        "capability_id": "automations",
        "provider": "OpenAI Automations",
        "tool_family": "automations",
        "connection_state": "AVAILABLE",
        "health": "HEALTHY",
        "action_class": "WRITE",
        "fallback_rank": 30,
        "actions": ["schedule", "condition_watch", "recurring"],
        "affinities": ["schedule", "reminder", "monitor", "watch", "recurring", "deadline", "notify"],
    },
    {
        "capability_id": "google-drive",
        "provider": "Google Drive",
        "tool_family": "google_drive",
        "connection_state": "UNKNOWN",
        "health": "UNKNOWN",
        "action_class": "READ_WRITE",
        "fallback_rank": 40,
        "actions": ["drive", "docs", "sheets", "slides"],
        "affinities": ["drive", "google docs", "sheet", "spreadsheet", "slides", "document", "shared file"],
    },
    {
        "capability_id": "gmail",
        "provider": "Gmail",
        "tool_family": "gmail",
        "connection_state": "UNKNOWN",
        "health": "UNKNOWN",
        "action_class": "READ_WRITE",
        "fallback_rank": 40,
        "actions": ["search_mail", "read_mail", "draft", "send"],
        "affinities": ["gmail", "email", "mail", "inbox", "message", "attachment"],
    },
    {
        "capability_id": "google-calendar",
        "provider": "Google Calendar",
        "tool_family": "google_calendar",
        "connection_state": "UNKNOWN",
        "health": "UNKNOWN",
        "action_class": "READ_WRITE",
        "fallback_rank": 40,
        "actions": ["read_events", "availability", "create_event", "update_event"],
        "affinities": ["calendar", "meeting", "event", "availability", "schedule"],
    },
    {
        "capability_id": "notion",
        "provider": "Notion",
        "tool_family": "notion",
        "connection_state": "UNKNOWN",
        "health": "UNKNOWN",
        "action_class": "READ_WRITE",
        "fallback_rank": 40,
        "actions": ["search", "read", "create_page", "update_page"],
        "affinities": ["notion", "wiki", "knowledge base", "project docs", "documentation"],
    },
    {
        "capability_id": "linear",
        "provider": "Linear",
        "tool_family": "linear",
        "connection_state": "UNKNOWN",
        "health": "UNKNOWN",
        "action_class": "READ_WRITE",
        "fallback_rank": 40,
        "actions": ["issues", "projects", "initiatives"],
        "affinities": ["linear", "issue", "ticket", "project management", "backlog", "task"],
    },
    {
        "capability_id": "supabase",
        "provider": "Supabase",
        "tool_family": "supabase",
        "connection_state": "UNKNOWN",
        "health": "UNKNOWN",
        "action_class": "READ_WRITE",
        "fallback_rank": 40,
        "actions": ["database", "auth", "storage", "edge_functions", "logs"],
        "affinities": ["supabase", "postgres", "database", "sql", "auth", "storage", "edge function", "realtime"],
    },
    {
        "capability_id": "figma",
        "provider": "Figma",
        "tool_family": "figma",
        "connection_state": "UNKNOWN",
        "health": "UNKNOWN",
        "action_class": "READ_WRITE",
        "fallback_rank": 40,
        "actions": ["design_read", "design_write", "code_connect"],
        "affinities": ["figma", "design", "ui", "ux", "component", "design system", "mockup"],
    },
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _compact(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists tool_capabilities(
          capability_id text primary key,
          provider text not null,
          tool_family text not null,
          connection_state text not null,
          health text not null,
          action_class text not null,
          fallback_rank integer not null default 50,
          actions_json text not null default '[]',
          affinities_json text not null default '[]',
          metadata_json text not null default '{}',
          observed_at text not null,
          last_success_at text,
          last_failure_at text
        );
        create index if not exists tool_capabilities_state_idx
          on tool_capabilities(connection_state,health,fallback_rank);

        create table if not exists tool_usage(
          id integer primary key autoincrement,
          ts text not null,
          capability_id text not null,
          task_id text,
          chat_id text,
          action text not null default '',
          outcome text not null,
          useful integer not null,
          latency_ms integer,
          error_class text,
          metadata_json text not null default '{}',
          foreign key(capability_id) references tool_capabilities(capability_id)
        );
        create index if not exists tool_usage_capability_idx
          on tool_usage(capability_id,ts);
        create index if not exists tool_usage_task_idx
          on tool_usage(task_id,ts);
        """
    )
    conn.commit()


def register_capability(
    conn: sqlite3.Connection,
    *,
    capability_id: str,
    provider: str,
    tool_family: str,
    connection_state: str = "UNKNOWN",
    health: str = "UNKNOWN",
    action_class: str = "READ_ONLY",
    fallback_rank: int = 50,
    actions: Iterable[str] = (),
    affinities: Iterable[str] = (),
    metadata: dict | None = None,
) -> dict:
    ensure_schema(conn)
    connection_state = connection_state.upper()
    health = health.upper()
    if connection_state not in CONNECTION_STATES:
        raise ValueError(f"invalid connection_state: {connection_state}")
    if health not in HEALTH_STATES:
        raise ValueError(f"invalid health: {health}")
    if not capability_id.strip():
        raise ValueError("capability_id is required")
    stamp = now()
    conn.execute(
        """
        insert into tool_capabilities(
          capability_id,provider,tool_family,connection_state,health,action_class,
          fallback_rank,actions_json,affinities_json,metadata_json,observed_at
        ) values(?,?,?,?,?,?,?,?,?,?,?)
        on conflict(capability_id) do update set
          provider=excluded.provider,
          tool_family=excluded.tool_family,
          connection_state=excluded.connection_state,
          health=excluded.health,
          action_class=excluded.action_class,
          fallback_rank=excluded.fallback_rank,
          actions_json=excluded.actions_json,
          affinities_json=excluded.affinities_json,
          metadata_json=excluded.metadata_json,
          observed_at=excluded.observed_at
        """,
        (
            capability_id.strip(), provider.strip(), tool_family.strip(),
            connection_state, health, action_class.upper(), int(fallback_rank),
            _compact(sorted(set(actions))), _compact(sorted(set(affinities))),
            _compact(metadata or {}), stamp,
        ),
    )
    conn.commit()
    return get_capability(conn, capability_id)


def seed_defaults(conn: sqlite3.Connection) -> list[dict]:
    out = []
    for item in DEFAULT_CAPABILITIES:
        out.append(register_capability(conn, **item))
    return out


def get_capability(conn: sqlite3.Connection, capability_id: str) -> dict:
    ensure_schema(conn)
    row = conn.execute(
        """
        select capability_id,provider,tool_family,connection_state,health,
               action_class,fallback_rank,actions_json,affinities_json,
               metadata_json,observed_at,last_success_at,last_failure_at
          from tool_capabilities where capability_id=?
        """,
        (capability_id,),
    ).fetchone()
    if not row:
        raise ValueError(f"unknown capability: {capability_id}")
    return _capability_dict(row)


def list_capabilities(conn: sqlite3.Connection, *, include_disconnected: bool = True) -> list[dict]:
    ensure_schema(conn)
    sql = """
        select capability_id,provider,tool_family,connection_state,health,
               action_class,fallback_rank,actions_json,affinities_json,
               metadata_json,observed_at,last_success_at,last_failure_at
          from tool_capabilities
    """
    params: tuple = ()
    if not include_disconnected:
        sql += " where connection_state not in ('DISCONNECTED','DENIED')"
    sql += " order by fallback_rank,provider,capability_id"
    return [_capability_dict(r) for r in conn.execute(sql, params)]


def set_health(
    conn: sqlite3.Connection,
    capability_id: str,
    *,
    connection_state: str | None = None,
    health: str | None = None,
) -> dict:
    ensure_schema(conn)
    fields = ["observed_at=?"]
    values: list[object] = [now()]
    if connection_state is not None:
        state = connection_state.upper()
        if state not in CONNECTION_STATES:
            raise ValueError(f"invalid connection_state: {state}")
        fields.append("connection_state=?")
        values.append(state)
    if health is not None:
        h = health.upper()
        if h not in HEALTH_STATES:
            raise ValueError(f"invalid health: {h}")
        fields.append("health=?")
        values.append(h)
    values.append(capability_id)
    cur = conn.execute(
        f"update tool_capabilities set {','.join(fields)} where capability_id=?",
        values,
    )
    if cur.rowcount != 1:
        conn.rollback()
        raise ValueError(f"unknown capability: {capability_id}")
    conn.commit()
    return get_capability(conn, capability_id)


def record_usage(
    conn: sqlite3.Connection,
    *,
    capability_id: str,
    outcome: str,
    useful: bool,
    task_id: str | None = None,
    chat_id: str | None = None,
    action: str = "",
    latency_ms: int | None = None,
    error_class: str | None = None,
    metadata: dict | None = None,
) -> dict:
    ensure_schema(conn)
    get_capability(conn, capability_id)
    outcome = outcome.upper()
    if outcome not in OUTCOMES:
        raise ValueError(f"invalid outcome: {outcome}")
    stamp = now()
    cur = conn.execute(
        """
        insert into tool_usage(
          ts,capability_id,task_id,chat_id,action,outcome,useful,latency_ms,
          error_class,metadata_json
        ) values(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            stamp, capability_id, task_id, chat_id, action, outcome,
            1 if useful else 0, latency_ms, error_class, _compact(metadata or {}),
        ),
    )
    if outcome == "SUCCESS":
        conn.execute(
            """
            update tool_capabilities
               set last_success_at=?, health=case when health='UNKNOWN' then 'HEALTHY' else health end
             where capability_id=?
            """,
            (stamp, capability_id),
        )
    elif outcome == "FAILURE":
        conn.execute(
            "update tool_capabilities set last_failure_at=? where capability_id=?",
            (stamp, capability_id),
        )
    conn.commit()
    return {"id": int(cur.lastrowid), "ts": stamp, "capability_id": capability_id}


def _usage_stats(conn: sqlite3.Connection, capability_id: str) -> dict:
    row = conn.execute(
        """
        select count(*),
               sum(case when outcome='SUCCESS' then 1 else 0 end),
               sum(case when outcome='FAILURE' then 1 else 0 end),
               sum(case when useful=1 then 1 else 0 end),
               avg(case when latency_ms is not null then latency_ms end)
          from tool_usage where capability_id=?
        """,
        (capability_id,),
    ).fetchone()
    total = int(row[0] or 0)
    return {
        "uses": total,
        "successes": int(row[1] or 0),
        "failures": int(row[2] or 0),
        "useful": int(row[3] or 0),
        "avg_latency_ms": None if row[4] is None else round(float(row[4]), 1),
        "success_rate": None if not total else round(float(row[1] or 0) / total, 3),
        "useful_rate": None if not total else round(float(row[3] or 0) / total, 3),
    }


def _task_context(conn: sqlite3.Connection, task_id: str) -> dict:
    row = conn.execute(
        "select id,title,status,priority,lane,note,owner from tasks where id=?",
        (task_id,),
    ).fetchone()
    if not row:
        raise ValueError(f"unknown task: {task_id}")
    scopes = []
    if conn.execute(
        "select 1 from sqlite_master where type='table' and name='task_scopes'"
    ).fetchone():
        scopes = [r[0] for r in conn.execute(
            "select path_prefix from task_scopes where task_id=? order by path_prefix",
            (task_id,),
        )]
    return {
        "id": row[0], "title": row[1] or "", "status": row[2] or "",
        "priority": row[3], "lane": row[4] or "", "note": row[5] or "",
        "owner": row[6] or "", "scopes": scopes,
    }


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9][a-z0-9_+-]*", text.lower()))


def _affinity_score(context_text: str, context_tokens: set[str], affinity: str) -> float:
    affinity_low = affinity.lower().strip()
    if not affinity_low:
        return 0.0
    affinity_tokens = _tokens(affinity_low)
    if not affinity_tokens:
        return 0.0
    if " " in affinity_low:
        if affinity_low in context_text:
            return 5.0
        overlap = len(context_tokens & affinity_tokens)
        return min(2.5, overlap * 1.1)
    return 3.5 if affinity_low in context_tokens else 0.0


def recommend(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    limit: int = 6,
    include_unknown: bool = True,
    min_score: float = 2.0,
) -> dict:
    ensure_schema(conn)
    task = _task_context(conn, task_id)
    context_text = " ".join(
        [task["id"], task["title"], task["lane"], task["note"], *task["scopes"]]
    ).lower()
    context_tokens = _tokens(context_text)
    ranked = []
    for cap in list_capabilities(conn, include_disconnected=True):
        state = cap["connection_state"]
        health = cap["health"]
        if state in {"DISCONNECTED", "DENIED"} or health == "UNHEALTHY":
            continue
        if state == "UNKNOWN" and not include_unknown:
            continue
        affinity = sum(
            _affinity_score(context_text, context_tokens, item)
            for item in cap["affinities"]
        )
        if affinity <= 0:
            continue
        stats = _usage_stats(conn, cap["capability_id"])
        success_bonus = 0.0
        if stats["success_rate"] is not None:
            success_bonus += stats["success_rate"] * 1.5
        if stats["useful_rate"] is not None:
            success_bonus += stats["useful_rate"] * 1.0
        state_bonus = {"CONNECTED": 2.0, "AVAILABLE": 1.5, "UNKNOWN": -0.5}.get(state, 0.0)
        health_bonus = {"HEALTHY": 1.0, "DEGRADED": -0.5, "UNKNOWN": 0.0}.get(health, 0.0)
        score = affinity + success_bonus + state_bonus + health_bonus
        if score < min_score:
            continue
        ranked.append({
            "capability": cap,
            "score": round(score, 3),
            "connection_check_required": state == "UNKNOWN",
            "stats": stats,
        })
    ranked.sort(
        key=lambda item: (
            -item["score"],
            item["capability"]["fallback_rank"],
            item["capability"]["capability_id"],
        )
    )
    selected = ranked[:max(1, limit)]
    ready = [x for x in selected if not x["connection_check_required"]]
    unknown = [x for x in selected if x["connection_check_required"]]
    return {
        "task": task,
        "recommended": selected,
        "ready": ready,
        "needs_connection_check": unknown,
        "use_tool": bool(ready),
        "reason": (
            "ready capabilities materially match task context"
            if ready else
            "no confirmed capability materially matches; unknown candidates may be checked"
            if unknown else
            "no capability adds enough value for this task"
        ),
    }


def audit_unused(
    conn: sqlite3.Connection,
    *,
    task_statuses: Iterable[str] = ("READY", "ACTIVE", "BLOCKED_DEP"),
    min_score: float = 3.0,
    max_items: int = 30,
) -> list[dict]:
    ensure_schema(conn)
    statuses = list(task_statuses)
    marks = ",".join("?" for _ in statuses)
    tasks = [r[0] for r in conn.execute(
        f"""select id from tasks
             where status in ({marks})
               and id not like 'REG-%'
               and id not like 'UNBLOCK-%'
             order by priority,id""",
        statuses,
    )]
    opportunities = []
    for task_id in tasks[:100]:
        rec = recommend(conn, task_id, limit=10, include_unknown=True, min_score=min_score)
        for item in rec["recommended"]:
            cap = item["capability"]
            stats = item["stats"]
            if stats["uses"] > 0:
                continue
            opportunities.append({
                "task_id": task_id,
                "task_title": rec["task"]["title"],
                "capability_id": cap["capability_id"],
                "provider": cap["provider"],
                "score": item["score"],
                "connection_state": cap["connection_state"],
                "health": cap["health"],
                "needs_connection_check": item["connection_check_required"],
                "reason": "useful task affinity but no recorded usage",
            })
    opportunities.sort(key=lambda x: (-x["score"], x["task_id"], x["capability_id"]))
    return opportunities[:max_items]


def report(conn: sqlite3.Connection) -> list[dict]:
    ensure_schema(conn)
    out = []
    for cap in list_capabilities(conn, include_disconnected=True):
        item = dict(cap)
        item["stats"] = _usage_stats(conn, cap["capability_id"])
        out.append(item)
    return out


def _capability_dict(row) -> dict:
    return {
        "capability_id": row[0],
        "provider": row[1],
        "tool_family": row[2],
        "connection_state": row[3],
        "health": row[4],
        "action_class": row[5],
        "fallback_rank": int(row[6]),
        "actions": json.loads(row[7]),
        "affinities": json.loads(row[8]),
        "metadata": json.loads(row[9]),
        "observed_at": row[10],
        "last_success_at": row[11],
        "last_failure_at": row[12],
    }
