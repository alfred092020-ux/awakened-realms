from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "2026-09-26.superbrain-v2.2"
ACTIVE_SESSION_STATES = {"ACTIVE", "RUNNING", "WORKING", "NEW"}
TERMINAL_TASK_STATES = {"DONE", "INTEGRATED", "SUPERSEDED", "CANCELLED", "BLOCKED_EVIDENCE"}
DEFAULT_PROTECTED_MEMBERS = {"lead", "nexus"}
PAID_COST_CLASSES = {"paid", "metered", "usage"}
WAKE_TERMINAL_STATES = {"DELIVERED", "FAILED", "IGNORED"}


def utc_now(ts: float | None = None) -> str:
    if ts is None:
        ts = time.time()
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "select 1 from sqlite_master where type='table' and name=?", (name,)
    ).fetchone() is not None


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists brain_agent_sessions(
          session_key text primary key,
          member_id text not null,
          provider text not null,
          external_session_id text,
          session_kind text not null default 'agent',
          state text not null default 'UNKNOWN',
          cost_class text not null default 'unknown',
          capabilities_json text not null default '[]',
          wake_method text not null default 'brain_event',
          wake_target text,
          last_seen_epoch real not null default 0,
          last_synced_at text not null,
          metadata_json text not null default '{}',
          unique(provider, external_session_id)
        );
        create index if not exists brain_agent_sessions_member_idx
          on brain_agent_sessions(member_id,state,last_seen_epoch);
        create index if not exists brain_agent_sessions_provider_idx
          on brain_agent_sessions(provider,state,last_seen_epoch);

        create table if not exists brain_event_subscriptions(
          subscription_id text primary key,
          subscriber text not null,
          event_type text not null default '*',
          priority_ceiling integer not null default 9,
          task_id text,
          wake_method text not null default 'brain_event',
          enabled integer not null default 1,
          created_at text not null,
          metadata_json text not null default '{}'
        );
        create index if not exists brain_event_subscriptions_subscriber_idx
          on brain_event_subscriptions(subscriber,enabled,event_type);

        create table if not exists brain_wake_queue(
          id integer primary key autoincrement,
          subscription_id text not null,
          event_id integer not null,
          subscriber text not null,
          state text not null default 'PENDING',
          attempts integer not null default 0,
          available_epoch real not null default 0,
          claimed_by text,
          claimed_at text,
          last_error text,
          created_at text not null,
          updated_at text not null,
          unique(subscription_id,event_id)
        );
        create index if not exists brain_wake_queue_state_idx
          on brain_wake_queue(state,available_epoch,id);
        create index if not exists brain_wake_queue_subscriber_idx
          on brain_wake_queue(subscriber,state,id);

        create table if not exists brain_context_deliveries(
          delivery_id text primary key,
          task_id text not null,
          recipient text not null,
          pack_sha256 text not null,
          artifact_path text not null,
          status text not null default 'READY',
          created_at text not null,
          consumed_at text,
          metadata_json text not null default '{}'
        );
        create index if not exists brain_context_deliveries_task_idx
          on brain_context_deliveries(task_id,recipient,status,created_at);

        create table if not exists brain_reconciliation_runs(
          run_id text primary key,
          started_at text not null,
          finished_at text,
          status text not null default 'RUNNING',
          checked_count integer not null default 0,
          finding_count integer not null default 0,
          metadata_json text not null default '{}'
        );

        create table if not exists brain_reconciliation_findings(
          id integer primary key autoincrement,
          run_id text not null,
          entity_kind text not null,
          entity_id text not null,
          severity text not null,
          code text not null,
          summary text not null,
          details_json text not null default '{}',
          created_at text not null,
          resolved_at text,
          unique(run_id,entity_kind,entity_id,code)
        );
        create index if not exists brain_reconciliation_findings_run_idx
          on brain_reconciliation_findings(run_id,severity,code);

        drop trigger if exists superbrain_event_wake_enqueue;
        create trigger superbrain_event_wake_enqueue
        after insert on brain_events
        begin
          insert or ignore into brain_wake_queue(
            subscription_id,event_id,subscriber,state,attempts,available_epoch,
            created_at,updated_at
          )
          select
            s.subscription_id,new.id,s.subscriber,'PENDING',0,new.ts_epoch,
            new.ts,new.ts
          from brain_event_subscriptions s
          where s.enabled=1
            and (s.event_type='*' or s.event_type=new.event_type)
            and new.priority <= s.priority_ceiling
            and (s.task_id is null or s.task_id=new.task_id)
            and s.subscriber <> new.sender;
        end;
        """
    )
    conn.executescript(
        """
        create table if not exists brain_capabilities(
          member_id text not null,
          capability text not null,
          provider text not null default '',
          model text not null default '',
          cost_class text not null default 'unknown',
          cost_per_mtoken real,
          isolation_level text not null default 'unknown',
          max_concurrency integer not null default 1,
          health text not null default 'UNKNOWN',
          updated_at text not null,
          metadata_json text not null default '{}',
          primary key(member_id,capability,provider,model)
        );
        create index if not exists brain_capabilities_route_idx
          on brain_capabilities(capability,health,cost_class,isolation_level);

        create table if not exists evidence_assertions(
          assertion_id text primary key,
          subject text not null,
          predicate text not null,
          object_json text not null,
          provenance text not null default '',
          confidence real not null default 0.0,
          status text not null default 'ACTIVE',
          source_task_id text,
          source_event_id integer,
          supersedes_id text,
          retracted_at text,
          retraction_reason text,
          created_at text not null,
          updated_at text not null,
          metadata_json text not null default '{}'
        );
        create index if not exists evidence_assertions_subject_idx
          on evidence_assertions(subject,predicate,status,confidence);
        create index if not exists evidence_assertions_task_idx
          on evidence_assertions(source_task_id,status);
        """
    )
    conn.executescript(
        """
        create table if not exists brain_reconciliation_actions(
          id integer primary key autoincrement,
          run_id text,
          entity_kind text not null,
          entity_id text not null,
          action text not null,
          before_state text,
          after_state text,
          reason text not null,
          created_at text not null,
          metadata_json text not null default '{}'
        );
        create index if not exists brain_reconciliation_actions_entity_idx
          on brain_reconciliation_actions(entity_kind,entity_id,id);

        create table if not exists brain_wake_dispatch_receipts(
          id integer primary key autoincrement,
          wake_id integer not null,
          attempt integer not null,
          dispatcher text not null,
          transport text not null,
          cost_class text not null default 'unknown',
          status text not null,
          started_at text not null,
          finished_at text,
          error text,
          metadata_json text not null default '{}'
        );
        create index if not exists brain_wake_dispatch_receipts_wake_idx
          on brain_wake_dispatch_receipts(wake_id,attempt,id);
        create index if not exists brain_wake_queue_claim_idx
          on brain_wake_queue(state,claimed_at,id);
        """
    )
    if _table_exists(conn, "meta"):
        conn.execute(
            """insert into meta(key,value) values('superbrain_schema_version',?)
               on conflict(key) do update set value=excluded.value""",
            (SCHEMA_VERSION,),
        )
    conn.commit()


def register_session(
    conn: sqlite3.Connection,
    *,
    session_key: str,
    member_id: str,
    provider: str,
    external_session_id: str | None = None,
    session_kind: str = "agent",
    state: str = "UNKNOWN",
    cost_class: str = "unknown",
    capabilities: list[str] | None = None,
    wake_method: str = "brain_event",
    wake_target: str | None = None,
    last_seen_epoch: float | None = None,
    metadata: dict | None = None,
) -> dict:
    ensure_schema(conn)
    now_epoch = time.time() if last_seen_epoch is None else float(last_seen_epoch)
    now_text = utc_now()
    conn.execute(
        """
        insert into brain_agent_sessions(
          session_key,member_id,provider,external_session_id,session_kind,state,
          cost_class,capabilities_json,wake_method,wake_target,last_seen_epoch,
          last_synced_at,metadata_json
        ) values(?,?,?,?,?,?,?,?,?,?,?,?,?)
        on conflict(session_key) do update set
          member_id=excluded.member_id,
          provider=excluded.provider,
          external_session_id=excluded.external_session_id,
          session_kind=excluded.session_kind,
          state=excluded.state,
          cost_class=excluded.cost_class,
          capabilities_json=excluded.capabilities_json,
          wake_method=excluded.wake_method,
          wake_target=excluded.wake_target,
          last_seen_epoch=excluded.last_seen_epoch,
          last_synced_at=excluded.last_synced_at,
          metadata_json=excluded.metadata_json
        """,
        (
            session_key,
            member_id,
            provider,
            external_session_id,
            session_kind,
            state.upper(),
            cost_class,
            _json(capabilities or []),
            wake_method,
            wake_target,
            now_epoch,
            now_text,
            _json(metadata or {}),
        ),
    )
    conn.commit()
    row = conn.execute(
        "select * from brain_agent_sessions where session_key=?", (session_key,)
    ).fetchone()
    return dict(row) if isinstance(row, sqlite3.Row) else {
        "session_key": session_key,
        "member_id": member_id,
        "provider": provider,
        "state": state.upper(),
    }


def subscribe(
    conn: sqlite3.Connection,
    *,
    subscriber: str,
    event_type: str = "*",
    priority_ceiling: int = 9,
    task_id: str | None = None,
    wake_method: str = "brain_event",
    subscription_id: str | None = None,
    metadata: dict | None = None,
) -> str:
    ensure_schema(conn)
    if subscription_id is None:
        seed = "|".join(
            [subscriber, event_type, str(priority_ceiling), task_id or "", wake_method]
        )
        subscription_id = "sub-" + hashlib.sha256(seed.encode()).hexdigest()[:20]
    conn.execute(
        """
        insert into brain_event_subscriptions(
          subscription_id,subscriber,event_type,priority_ceiling,task_id,
          wake_method,enabled,created_at,metadata_json
        ) values(?,?,?,?,?,?,1,?,?)
        on conflict(subscription_id) do update set
          subscriber=excluded.subscriber,
          event_type=excluded.event_type,
          priority_ceiling=excluded.priority_ceiling,
          task_id=excluded.task_id,
          wake_method=excluded.wake_method,
          enabled=1,
          metadata_json=excluded.metadata_json
        """,
        (
            subscription_id,
            subscriber,
            event_type,
            int(priority_ceiling),
            task_id,
            wake_method,
            utc_now(),
            _json(metadata or {}),
        ),
    )
    conn.commit()
    return subscription_id


def pending_wakes(
    conn: sqlite3.Connection, *, subscriber: str | None = None, limit: int = 100
) -> list[dict]:
    ensure_schema(conn)
    args: list[Any] = [time.time()]
    where = "state='PENDING' and available_epoch<=?"
    if subscriber:
        where += " and subscriber=?"
        args.append(subscriber)
    args.append(max(1, min(int(limit), 500)))
    rows = conn.execute(
        f"""select * from brain_wake_queue
            where {where}
            order by id
            limit ?""",
        tuple(args),
    ).fetchall()
    return [dict(r) for r in rows]


def ack_wake(
    conn: sqlite3.Connection,
    wake_id: int,
    *,
    state: str = "DELIVERED",
    error: str | None = None,
) -> None:
    ensure_schema(conn)
    state = state.upper()
    if state not in {"DELIVERED", "FAILED", "IGNORED"}:
        raise ValueError("wake state must be DELIVERED, FAILED, or IGNORED")
    conn.execute(
        """update brain_wake_queue
           set state=?, attempts=attempts+1, last_error=?, updated_at=?
           where id=?""",
        (state, error, utc_now(), int(wake_id)),
    )
    conn.commit()


def record_context_delivery(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    recipient: str,
    pack_sha256: str,
    artifact_path: str,
    metadata: dict | None = None,
) -> str:
    ensure_schema(conn)
    delivery_id = "ctx-" + uuid.uuid4().hex
    conn.execute(
        """insert into brain_context_deliveries(
             delivery_id,task_id,recipient,pack_sha256,artifact_path,status,
             created_at,metadata_json
           ) values(?,?,?,?,?,'READY',?,?)""",
        (
            delivery_id,
            task_id,
            recipient,
            pack_sha256,
            artifact_path,
            utc_now(),
            _json(metadata or {}),
        ),
    )
    conn.commit()
    return delivery_id


def export_context(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    recipient: str,
    output_dir: str | Path,
    integration_branch: str = "feat/logres-reconstruction",
) -> dict:
    from logres_context_pack import build_pack, canonical_json

    ensure_schema(conn)
    integration_sha = None
    if _table_exists(conn, "meta"):
        row = conn.execute(
            "select value from meta where key='integration_sha'"
        ).fetchone()
        if row:
            integration_sha = row[0]

    evidence = []
    if _table_exists(conn, "brain_discoveries"):
        rows = conn.execute(
            """select id,author,confidence,subject,summary,artifact_path,
                      artifact_sha256,status
               from brain_discoveries
               where task_id=?
               order by id desc
               limit 24""",
            (task_id,),
        ).fetchall()
        for row in rows:
            evidence.append(
                {
                    "id": f"brain-discovery-{row['id']}",
                    "source": f"brain:{row['author']}",
                    "path": row["artifact_path"] or "",
                    "sha256": row["artifact_sha256"],
                    "snippet": row["summary"] or row["subject"] or "",
                    "confidence": row["confidence"],
                    "authority": (
                        "IMPLEMENTATION_VERIFIED"
                        if row["artifact_sha256"]
                        else "CONFIRMED"
                    ),
                    "status": row["status"],
                    "relevance": 1.0,
                }
            )

    pack = build_pack(
        conn,
        task_id,
        integration_sha=integration_sha,
        integration_branch=integration_branch,
        evidence=evidence,
    )
    payload = canonical_json(pack)
    digest = hashlib.sha256(payload.encode()).hexdigest()

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    safe_recipient = "".join(
        c if c.isalnum() or c in "._-" else "_" for c in recipient
    )[:80]
    path = root / f"{task_id}--{safe_recipient}--{digest[:12]}.json"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)

    delivery_id = record_context_delivery(
        conn,
        task_id=task_id,
        recipient=recipient,
        pack_sha256=digest,
        artifact_path=str(path),
        metadata={"schema": pack.get("schema"), "integration_branch": integration_branch},
    )

    if _table_exists(conn, "brain_events"):
        ts = time.time()
        conn.execute(
            """insert into brain_events(
                 ts_epoch,ts,sender,recipient,event_type,priority,task_id,
                 subject,body,artifact_path,artifact_sha256,dedupe_key,meta_json
               ) values(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ts,
                utc_now(ts),
                "superbrain",
                recipient,
                "HANDOFF",
                2,
                task_id,
                "Context pack ready",
                f"delivery={delivery_id}",
                str(path),
                digest,
                f"superbrain-context:{delivery_id}",
                _json({"delivery_id": delivery_id, "schema_version": SCHEMA_VERSION}),
            ),
        )
        conn.commit()

    return {
        "delivery_id": delivery_id,
        "task_id": task_id,
        "recipient": recipient,
        "artifact_path": str(path),
        "sha256": digest,
        "bytes": len(payload.encode()),
    }


def upsert_capability(
    conn: sqlite3.Connection,
    *,
    member_id: str,
    capability: str,
    provider: str = "",
    model: str = "",
    cost_class: str = "unknown",
    cost_per_mtoken: float | None = None,
    isolation_level: str = "unknown",
    max_concurrency: int = 1,
    health: str = "UNKNOWN",
    metadata: dict | None = None,
) -> dict:
    ensure_schema(conn)
    conn.execute(
        """insert into brain_capabilities(
             member_id,capability,provider,model,cost_class,cost_per_mtoken,
             isolation_level,max_concurrency,health,updated_at,metadata_json
           ) values(?,?,?,?,?,?,?,?,?,?,?)
           on conflict(member_id,capability,provider,model) do update set
             cost_class=excluded.cost_class,
             cost_per_mtoken=excluded.cost_per_mtoken,
             isolation_level=excluded.isolation_level,
             max_concurrency=excluded.max_concurrency,
             health=excluded.health,
             updated_at=excluded.updated_at,
             metadata_json=excluded.metadata_json""",
        (
            member_id,
            capability,
            provider,
            model,
            cost_class,
            cost_per_mtoken,
            isolation_level,
            max(1, int(max_concurrency)),
            health.upper(),
            utc_now(),
            _json(metadata or {}),
        ),
    )
    conn.commit()
    row = conn.execute(
        """select * from brain_capabilities
           where member_id=? and capability=? and provider=? and model=?""",
        (member_id, capability, provider, model),
    ).fetchone()
    return dict(row)


def assert_evidence(
    conn: sqlite3.Connection,
    *,
    subject: str,
    predicate: str,
    value: Any,
    provenance: str = "",
    confidence: float = 0.0,
    source_task_id: str | None = None,
    source_event_id: int | None = None,
    supersedes_id: str | None = None,
    assertion_id: str | None = None,
    metadata: dict | None = None,
) -> dict:
    ensure_schema(conn)
    assertion_id = assertion_id or ("ev-" + uuid.uuid4().hex)
    confidence = max(0.0, min(float(confidence), 1.0))
    now = utc_now()
    if supersedes_id:
        conn.execute(
            """update evidence_assertions
               set status='SUPERSEDED',updated_at=?
               where assertion_id=? and status='ACTIVE'""",
            (now, supersedes_id),
        )
    conn.execute(
        """insert into evidence_assertions(
             assertion_id,subject,predicate,object_json,provenance,confidence,
             status,source_task_id,source_event_id,supersedes_id,created_at,
             updated_at,metadata_json
           ) values(?,?,?,?,?,?,'ACTIVE',?,?,?,?,?,?)""",
        (
            assertion_id,
            subject,
            predicate,
            _json(value),
            provenance,
            confidence,
            source_task_id,
            source_event_id,
            supersedes_id,
            now,
            now,
            _json(metadata or {}),
        ),
    )
    conn.commit()
    return dict(
        conn.execute(
            "select * from evidence_assertions where assertion_id=?", (assertion_id,)
        ).fetchone()
    )


def retract_evidence(
    conn: sqlite3.Connection,
    assertion_id: str,
    *,
    reason: str,
) -> dict:
    ensure_schema(conn)
    now = utc_now()
    cur = conn.execute(
        """update evidence_assertions
           set status='RETRACTED',retracted_at=?,retraction_reason=?,updated_at=?
           where assertion_id=? and status in ('ACTIVE','SUPERSEDED')""",
        (now, reason, now, assertion_id),
    )
    if cur.rowcount != 1:
        raise ValueError(f"assertion not active/superseded: {assertion_id}")
    conn.commit()
    return dict(
        conn.execute(
            "select * from evidence_assertions where assertion_id=?", (assertion_id,)
        ).fetchone()
    )


def _add_finding(
    findings: list[dict],
    *,
    entity_kind: str,
    entity_id: str,
    severity: str,
    code: str,
    summary: str,
    details: dict | None = None,
) -> None:
    findings.append(
        {
            "entity_kind": entity_kind,
            "entity_id": entity_id,
            "severity": severity,
            "code": code,
            "summary": summary,
            "details": details or {},
        }
    )


def reconcile(
    conn: sqlite3.Connection,
    *,
    now_epoch: float | None = None,
    stale_seconds: int = 1800,
) -> dict:
    ensure_schema(conn)
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    started = utc_now(now_epoch)
    run_id = "recon-" + uuid.uuid4().hex
    findings: list[dict] = []
    checked = 0

    if _table_exists(conn, "brain_members"):
        rows = conn.execute(
            """select chat_id,status,last_seen_epoch from brain_members
               where upper(status)='ACTIVE'"""
        ).fetchall()
        checked += len(rows)
        for row in rows:
            if float(row["last_seen_epoch"] or 0) <= 0:
                continue
            age = now_epoch - float(row["last_seen_epoch"])
            if age > stale_seconds:
                _add_finding(
                    findings,
                    entity_kind="brain_member",
                    entity_id=str(row["chat_id"]),
                    severity="WARN",
                    code="stale_member",
                    summary=f"ACTIVE member heartbeat is {int(age)}s old",
                    details={"age_seconds": int(age), "threshold_seconds": stale_seconds},
                )

    if _table_exists(conn, "tasks") and _table_exists(conn, "brain_task_leases"):
        rows = conn.execute(
            """
            select t.id,t.status,t.owner,l.chat_id,l.lease_until_epoch
            from tasks t
            left join brain_task_leases l
              on l.task_id=t.id and l.lease_until_epoch>?
            where upper(t.status)='ACTIVE'
            """,
            (now_epoch,),
        ).fetchall()
        checked += len(rows)
        for row in rows:
            if row["chat_id"] is None:
                _add_finding(
                    findings,
                    entity_kind="task",
                    entity_id=str(row["id"]),
                    severity="WARN",
                    code="active_task_without_live_lease",
                    summary="ACTIVE task has no unexpired Brain lease",
                    details={"owner": row["owner"] or ""},
                )

        rows = conn.execute(
            """
            select l.task_id,l.chat_id,l.lease_until_epoch,t.status
            from brain_task_leases l
            left join tasks t on t.id=l.task_id
            where l.lease_until_epoch>?
            """,
            (now_epoch,),
        ).fetchall()
        checked += len(rows)
        for row in rows:
            status = row["status"]
            if status is None:
                _add_finding(
                    findings,
                    entity_kind="lease",
                    entity_id=str(row["task_id"]),
                    severity="ERROR",
                    code="lease_without_task",
                    summary="Live lease references a missing task",
                    details={"chat_id": row["chat_id"]},
                )
            elif str(status).upper() in TERMINAL_TASK_STATES:
                _add_finding(
                    findings,
                    entity_kind="lease",
                    entity_id=str(row["task_id"]),
                    severity="WARN",
                    code="lease_on_terminal_task",
                    summary=f"Live lease remains on terminal task state {status}",
                    details={"chat_id": row["chat_id"]},
                )

    rows = conn.execute(
        """select session_key,provider,state,last_seen_epoch
           from brain_agent_sessions"""
    ).fetchall()
    checked += len(rows)
    for row in rows:
        if str(row["state"]).upper() not in ACTIVE_SESSION_STATES:
            continue
        seen = float(row["last_seen_epoch"] or 0)
        if seen > 0 and now_epoch - seen > stale_seconds:
            age = int(now_epoch - seen)
            _add_finding(
                findings,
                entity_kind="agent_session",
                entity_id=str(row["session_key"]),
                severity="WARN",
                code="stale_agent_session",
                summary=f"{row['provider']} session marked {row['state']} but stale for {age}s",
                details={"provider": row["provider"], "age_seconds": age},
            )

    conn.execute(
        """insert into brain_reconciliation_runs(
             run_id,started_at,status,checked_count,finding_count,metadata_json
           ) values(?,?,'RUNNING',0,0,?)""",
        (run_id, started, _json({"schema_version": SCHEMA_VERSION})),
    )
    for item in findings:
        conn.execute(
            """insert into brain_reconciliation_findings(
                 run_id,entity_kind,entity_id,severity,code,summary,
                 details_json,created_at
               ) values(?,?,?,?,?,?,?,?)""",
            (
                run_id,
                item["entity_kind"],
                item["entity_id"],
                item["severity"],
                item["code"],
                item["summary"],
                _json(item["details"]),
                utc_now(),
            ),
        )
    conn.execute(
        """update brain_reconciliation_runs
           set finished_at=?,status='DONE',checked_count=?,finding_count=?
           where run_id=?""",
        (utc_now(), checked, len(findings), run_id),
    )
    conn.commit()
    return {
        "run_id": run_id,
        "checked_count": checked,
        "finding_count": len(findings),
        "findings": findings,
    }


def _live_claim_owners(conn: sqlite3.Connection) -> set[str]:
    if not (_table_exists(conn, "claims") and _table_exists(conn, "tasks")):
        return set()
    placeholders = ",".join("?" for _ in TERMINAL_TASK_STATES)
    rows = conn.execute(
        f"""select distinct c.owner
              from claims c
              join tasks t on t.id=c.task_id
             where c.owner is not null
               and upper(t.status) not in ({placeholders})""",
        tuple(sorted(TERMINAL_TASK_STATES)),
    ).fetchall()
    return {str(row[0]) for row in rows if row[0]}


def plan_member_self_heal(
    conn: sqlite3.Connection,
    *,
    now_epoch: float | None = None,
    stale_seconds: int = 3600,
    protected_members: set[str] | None = None,
) -> list[dict]:
    """Return conservative ACTIVE->STALE actions without mutating state."""
    ensure_schema(conn)
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    stale_seconds = max(300, int(stale_seconds))
    cutoff = now_epoch - stale_seconds
    protected = set(DEFAULT_PROTECTED_MEMBERS)
    protected.update(protected_members or set())

    live_leases: set[str] = set()
    if _table_exists(conn, "brain_task_leases"):
        live_leases = {
            str(row[0])
            for row in conn.execute(
                """select distinct chat_id from brain_task_leases
                   where lease_until_epoch>?""",
                (now_epoch,),
            )
            if row[0]
        }

    fresh_sessions = {
        str(row[0])
        for row in conn.execute(
            """select distinct member_id
                 from brain_agent_sessions
                where upper(state) in ('ACTIVE','RUNNING','WORKING','NEW')
                  and last_seen_epoch>=?""",
            (cutoff,),
        )
        if row[0]
    }
    claim_owners = _live_claim_owners(conn)

    actions: list[dict] = []
    if not _table_exists(conn, "brain_members"):
        return actions
    rows = conn.execute(
        """select chat_id,status,last_seen_epoch,display_name
             from brain_members
            where upper(status)='ACTIVE'
              and last_seen_epoch>0
              and last_seen_epoch<?
            order by last_seen_epoch,chat_id""",
        (cutoff,),
    ).fetchall()
    for row in rows:
        member_id = str(row["chat_id"])
        if (
            member_id in protected
            or member_id in live_leases
            or member_id in fresh_sessions
            or member_id in claim_owners
        ):
            continue
        age = max(0, int(now_epoch - float(row["last_seen_epoch"] or 0)))
        actions.append(
            {
                "member_id": member_id,
                "display_name": row["display_name"] or member_id,
                "from_state": "ACTIVE",
                "to_state": "STALE",
                "age_seconds": age,
                "reason": "stale heartbeat with no live lease, fresh agent session, or live claim",
            }
        )
    return actions


def apply_member_self_heal(
    conn: sqlite3.Connection,
    *,
    now_epoch: float | None = None,
    stale_seconds: int = 3600,
    protected_members: set[str] | None = None,
    actor: str = "superbrain-maintain",
) -> dict:
    """Safely demote stale member presence while preserving work ownership."""
    ensure_schema(conn)
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    actions = plan_member_self_heal(
        conn,
        now_epoch=now_epoch,
        stale_seconds=stale_seconds,
        protected_members=protected_members,
    )
    if not actions:
        return {"planned": 0, "applied": 0, "actions": []}

    run_id = "member-heal-" + uuid.uuid4().hex
    stamp = utc_now(now_epoch)
    applied: list[dict] = []
    conn.execute("begin immediate")
    try:
        for action in actions:
            member_id = action["member_id"]
            cur = conn.execute(
                """update brain_members
                      set status='STALE'
                    where chat_id=?
                      and upper(status)='ACTIVE'
                      and last_seen_epoch<?""",
                (member_id, now_epoch - max(300, int(stale_seconds))),
            )
            if cur.rowcount != 1:
                continue
            conn.execute(
                """insert into brain_reconciliation_actions(
                     run_id,entity_kind,entity_id,action,before_state,after_state,
                     reason,created_at,metadata_json
                   ) values(?,?,?,?,?,?,?,?,?)""",
                (
                    run_id,
                    "brain_member",
                    member_id,
                    "MARK_STALE",
                    "ACTIVE",
                    "STALE",
                    action["reason"],
                    stamp,
                    _json(
                        {
                            "actor": actor,
                            "age_seconds": action["age_seconds"],
                            "stale_seconds": int(stale_seconds),
                        }
                    ),
                ),
            )
            conn.execute(
                """update brain_reconciliation_findings
                      set resolved_at=coalesce(resolved_at,?)
                    where entity_kind='brain_member'
                      and entity_id=?
                      and code='stale_member'
                      and resolved_at is null""",
                (stamp, member_id),
            )
            applied.append(action)

        if applied and _table_exists(conn, "brain_events"):
            sample = ",".join(x["member_id"] for x in applied[:12])
            conn.execute(
                """insert into brain_events(
                     ts_epoch,ts,sender,recipient,event_type,priority,subject,body,
                     dedupe_key,meta_json
                   ) values(?,?,?,?,?,?,?,?,?,?)""",
                (
                    now_epoch,
                    stamp,
                    actor,
                    "ALL",
                    "RECONCILIATION",
                    3,
                    f"Super Brain marked {len(applied)} stale members",
                    f"members={sample}" + ("..." if len(applied) > 12 else ""),
                    f"superbrain-member-heal:{run_id}",
                    _json(
                        {
                            "run_id": run_id,
                            "count": len(applied),
                            "stale_seconds": int(stale_seconds),
                        }
                    ),
                ),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return {
        "run_id": run_id,
        "planned": len(actions),
        "applied": len(applied),
        "actions": applied,
    }


def requeue_stale_claimed_wakes(
    conn: sqlite3.Connection,
    *,
    now_epoch: float | None = None,
    claim_timeout_seconds: int = 600,
) -> int:
    ensure_schema(conn)
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    cutoff_text = utc_now(now_epoch - max(60, int(claim_timeout_seconds)))
    cur = conn.execute(
        """update brain_wake_queue
              set state='PENDING',
                  claimed_by=null,
                  claimed_at=null,
                  available_epoch=?,
                  last_error=coalesce(last_error,'stale dispatch claim reclaimed'),
                  updated_at=?
            where state='CLAIMED'
              and claimed_at is not null
              and claimed_at<?""",
        (now_epoch, utc_now(now_epoch), cutoff_text),
    )
    conn.commit()
    return int(cur.rowcount or 0)


def _session_for_subscriber(
    conn: sqlite3.Connection, subscriber: str
) -> sqlite3.Row | None:
    return conn.execute(
        """select * from brain_agent_sessions
            where member_id=?
            order by last_synced_at desc,session_key
            limit 1""",
        (subscriber,),
    ).fetchone()


def _wake_payload(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    event = conn.execute(
        """select id,event_type,priority,task_id,subject,body,
                  artifact_path,artifact_sha256,sender,recipient
             from brain_events where id=?""",
        (row["event_id"],),
    ).fetchone()
    sub = conn.execute(
        """select subscriber,wake_method,metadata_json
             from brain_event_subscriptions
            where subscription_id=?""",
        (row["subscription_id"],),
    ).fetchone()
    if event is None or sub is None:
        raise ValueError("wake references missing event or subscription")
    session = _session_for_subscriber(conn, str(row["subscriber"]))
    try:
        sub_meta = json.loads(sub["metadata_json"] or "{}")
    except json.JSONDecodeError:
        sub_meta = {}
    return {
        "wake_id": int(row["id"]),
        "attempt": int(row["attempts"] or 0) + 1,
        "subscriber": str(row["subscriber"]),
        "subscription_id": str(row["subscription_id"]),
        "wake_method": str(sub["wake_method"] or "brain_event"),
        "subscription_metadata": sub_meta,
        "event": dict(event),
        "session": dict(session) if session is not None else None,
        "cost_class": str(session["cost_class"] if session is not None else "unknown"),
    }


def claim_pending_wakes(
    conn: sqlite3.Connection,
    *,
    claimant: str,
    limit: int = 8,
    now_epoch: float | None = None,
    allow_paid: bool = False,
    paid_priority_ceiling: int = 1,
    defer_seconds: int = 300,
) -> dict:
    """Atomically claim eligible wake intents, deferring nonurgent paid calls."""
    ensure_schema(conn)
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    limit = max(1, min(int(limit), 64))
    paid_priority_ceiling = int(paid_priority_ceiling)
    claimed: list[dict] = []
    deferred: list[dict] = []
    conn.execute("begin immediate")
    try:
        rows = conn.execute(
            """select * from brain_wake_queue
                where state='PENDING' and available_epoch<=?
                order by id
                limit ?""",
            (now_epoch, limit * 4),
        ).fetchall()
        for row in rows:
            if len(claimed) >= limit:
                break
            payload = _wake_payload(conn, row)
            sub_meta = payload["subscription_metadata"]
            priority = int(payload["event"].get("priority") or 9)
            is_paid = payload["cost_class"].lower() in PAID_COST_CLASSES
            paid_override = bool(sub_meta.get("allow_paid_auto"))
            if is_paid and not allow_paid and not paid_override and priority > paid_priority_ceiling:
                conn.execute(
                    """update brain_wake_queue
                          set available_epoch=?,last_error=?,updated_at=?
                        where id=? and state='PENDING'""",
                    (
                        now_epoch + max(60, int(defer_seconds)),
                        "deferred by paid wake policy",
                        utc_now(now_epoch),
                        int(row["id"]),
                    ),
                )
                deferred.append(
                    {
                        "wake_id": int(row["id"]),
                        "subscriber": payload["subscriber"],
                        "priority": priority,
                        "cost_class": payload["cost_class"],
                    }
                )
                continue
            cur = conn.execute(
                """update brain_wake_queue
                      set state='CLAIMED',
                          attempts=attempts+1,
                          claimed_by=?,
                          claimed_at=?,
                          last_error=null,
                          updated_at=?
                    where id=? and state='PENDING'""",
                (
                    claimant,
                    utc_now(now_epoch),
                    utc_now(now_epoch),
                    int(row["id"]),
                ),
            )
            if cur.rowcount == 1:
                payload["attempt"] = int(row["attempts"] or 0) + 1
                claimed.append(payload)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"claimed": claimed, "deferred": deferred}


def build_wake_message(
    payload: dict,
    *,
    max_context_bytes: int = 24_000,
) -> str:
    event = payload["event"]
    lines = [
        "LOGRES SUPER BRAIN WAKE",
        f"wake_id={payload['wake_id']} event_id={event['id']} attempt={payload['attempt']}",
        f"event_type={event['event_type']} priority={event['priority']} task={event.get('task_id') or '-'}",
        f"subject={event.get('subject') or ''}",
    ]
    if event.get("body"):
        lines.append("body=" + str(event["body"])[:4000])
    if event.get("artifact_path"):
        lines.append("artifact_path=" + str(event["artifact_path"]))
    if event.get("artifact_sha256"):
        lines.append("artifact_sha256=" + str(event["artifact_sha256"]))

    artifact = str(event.get("artifact_path") or "")
    context_root = "/home/ubuntu/logres/control/superbrain-context/"
    if artifact.startswith(context_root):
        path = Path(artifact)
        try:
            if path.is_file() and path.stat().st_size <= max_context_bytes:
                lines.extend(["", "CONTEXT_PACK", path.read_text()])
        except OSError:
            pass
    return "\n".join(lines)


def finish_wake_dispatch(
    conn: sqlite3.Connection,
    *,
    wake_id: int,
    attempt: int,
    dispatcher: str,
    transport: str,
    cost_class: str,
    ok: bool,
    started_at: str,
    error: str | None = None,
    now_epoch: float | None = None,
    retry_base_seconds: int = 30,
) -> dict:
    ensure_schema(conn)
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    stamp = utc_now(now_epoch)
    state = "DELIVERED" if ok else "PENDING"
    if ok:
        available_epoch = now_epoch
        last_error = None
    else:
        backoff = min(900, max(30, int(retry_base_seconds)) * (2 ** max(0, attempt - 1)))
        available_epoch = now_epoch + backoff
        last_error = (error or "dispatch failed")[:1000]

    conn.execute("begin immediate")
    try:
        conn.execute(
            """insert into brain_wake_dispatch_receipts(
                 wake_id,attempt,dispatcher,transport,cost_class,status,
                 started_at,finished_at,error,metadata_json
               ) values(?,?,?,?,?,?,?,?,?,?)""",
            (
                int(wake_id),
                int(attempt),
                dispatcher,
                transport,
                cost_class,
                "DELIVERED" if ok else "RETRY",
                started_at,
                stamp,
                error,
                "{}",
            ),
        )
        conn.execute(
            """update brain_wake_queue
                  set state=?,available_epoch=?,claimed_by=null,claimed_at=null,
                      last_error=?,updated_at=?
                where id=? and state='CLAIMED'""",
            (
                state,
                available_epoch,
                last_error,
                stamp,
                int(wake_id),
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"wake_id": int(wake_id), "state": state, "ok": bool(ok)}


def dispatch_wakes(
    conn: sqlite3.Connection,
    *,
    dispatchers: dict[str, Any],
    claimant: str = "superbrain-dispatcher",
    limit: int = 8,
    allow_paid: bool = False,
    paid_priority_ceiling: int = 1,
    now_epoch: float | None = None,
) -> dict:
    """Dispatch durable wake intents with bounded retry and cost-aware gating."""
    ensure_schema(conn)
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    reclaimed = requeue_stale_claimed_wakes(conn, now_epoch=now_epoch)
    batch = claim_pending_wakes(
        conn,
        claimant=claimant,
        limit=limit,
        now_epoch=now_epoch,
        allow_paid=allow_paid,
        paid_priority_ceiling=paid_priority_ceiling,
    )
    results: list[dict] = []
    for payload in batch["claimed"]:
        method = payload["wake_method"]
        dispatcher = dispatchers.get(method)
        started = utc_now()
        ok = False
        error = None
        if dispatcher is None:
            error = f"no dispatcher registered for wake method {method}"
        else:
            try:
                dispatcher(payload)
                ok = True
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"[:1000]
        result = finish_wake_dispatch(
            conn,
            wake_id=payload["wake_id"],
            attempt=payload["attempt"],
            dispatcher=claimant,
            transport=method,
            cost_class=payload["cost_class"],
            ok=ok,
            started_at=started,
            error=error,
        )
        result["subscriber"] = payload["subscriber"]
        result["transport"] = method
        results.append(result)
    return {
        "reclaimed_claims": reclaimed,
        "claimed": len(batch["claimed"]),
        "deferred": batch["deferred"],
        "results": results,
    }


def status(conn: sqlite3.Connection, *, fresh_seconds: int = 900) -> dict:
    ensure_schema(conn)
    now_epoch = time.time()
    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "now": utc_now(now_epoch),
    }

    out["sessions_total"] = conn.execute(
        "select count(*) from brain_agent_sessions"
    ).fetchone()[0]
    out["sessions_active"] = conn.execute(
        """select count(*) from brain_agent_sessions
           where upper(state) in ('ACTIVE','RUNNING','WORKING','NEW')"""
    ).fetchone()[0]
    out["subscriptions_enabled"] = conn.execute(
        "select count(*) from brain_event_subscriptions where enabled=1"
    ).fetchone()[0]
    out["wakes_pending"] = conn.execute(
        "select count(*) from brain_wake_queue where state='PENDING'"
    ).fetchone()[0]
    out["context_deliveries"] = conn.execute(
        "select count(*) from brain_context_deliveries"
    ).fetchone()[0]
    out["wake_dispatch_receipts"] = conn.execute(
        "select count(*) from brain_wake_dispatch_receipts"
    ).fetchone()[0]
    out["member_reconciliation_actions"] = conn.execute(
        "select count(*) from brain_reconciliation_actions"
    ).fetchone()[0]
    out["capability_profiles"] = conn.execute(
        "select count(*) from brain_capabilities"
    ).fetchone()[0]
    out["active_evidence_assertions"] = conn.execute(
        "select count(*) from evidence_assertions where status='ACTIVE'"
    ).fetchone()[0]

    if _table_exists(conn, "brain_task_leases"):
        out["live_leases"] = conn.execute(
            "select count(*) from brain_task_leases where lease_until_epoch>?",
            (now_epoch,),
        ).fetchone()[0]
    if _table_exists(conn, "brain_members"):
        out["members_fresh"] = conn.execute(
            """select count(*) from brain_members
               where last_seen_epoch>=?""",
            (now_epoch - fresh_seconds,),
        ).fetchone()[0]
        out["members_stale_active"] = conn.execute(
            """select count(*) from brain_members
               where upper(status)='ACTIVE' and last_seen_epoch>0 and last_seen_epoch<?""",
            (now_epoch - fresh_seconds,),
        ).fetchone()[0]
        out["members_stale"] = conn.execute(
            "select count(*) from brain_members where upper(status)='STALE'"
        ).fetchone()[0]
    if _table_exists(conn, "brain_events"):
        row = conn.execute("select count(*),coalesce(max(id),0) from brain_events").fetchone()
        out["brain_events"] = row[0]
        out["latest_event_id"] = row[1]

    latest = conn.execute(
        """select run_id,finished_at,checked_count,finding_count
           from brain_reconciliation_runs
           where status='DONE'
           order by rowid desc limit 1"""
    ).fetchone()
    out["latest_reconciliation"] = dict(latest) if latest else None
    return out
