import sqlite3
import time

from logres_superbrain import (
    ensure_schema,
    pending_wakes,
    reconcile,
    register_session,
    status,
    subscribe,
)


def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        create table meta(key text primary key,value text);
        create table brain_events(
          id integer primary key autoincrement,
          ts_epoch real not null,
          ts text not null,
          sender text not null,
          recipient text not null default 'ALL',
          event_type text not null,
          priority integer not null default 5,
          task_id text,
          subject text not null,
          body text not null default '',
          artifact_path text,
          artifact_sha256 text,
          dedupe_key text,
          meta_json text not null default '{}'
        );
        create table brain_members(
          chat_id text primary key,
          role text not null default '',
          display_name text not null default '',
          authority integer not null default 0,
          status text not null default 'IDLE',
          last_seen_epoch real not null default 0,
          joined_at text not null default '',
          capabilities_json text not null default '{}',
          metadata_json text not null default '{}'
        );
        create table tasks(
          id text primary key, priority integer, lane text, title text,
          status text, branch text, owner text, note text, updated_at text
        );
        create table brain_task_leases(
          task_id text primary key,
          chat_id text not null,
          branch text,
          lease_until_epoch real not null,
          acquired_at text not null,
          renewed_at text not null,
          progress integer,
          note text not null default ''
        );
        """
    )
    ensure_schema(conn)
    return conn


def test_subscription_trigger_queues_matching_event():
    conn = db()
    sub = subscribe(
        conn,
        subscriber="devin-peer",
        event_type="BLOCKER",
        priority_ceiling=3,
        task_id="T-1",
    )
    conn.execute(
        """insert into brain_events(
             ts_epoch,ts,sender,recipient,event_type,priority,task_id,subject
           ) values(?,?,?,?,?,?,?,?)""",
        (time.time(), "now", "lead", "ALL", "BLOCKER", 1, "T-1", "blocked"),
    )
    conn.commit()
    wakes = pending_wakes(conn, subscriber="devin-peer")
    assert len(wakes) == 1
    assert wakes[0]["subscription_id"] == sub

    conn.execute(
        """insert into brain_events(
             ts_epoch,ts,sender,recipient,event_type,priority,task_id,subject
           ) values(?,?,?,?,?,?,?,?)""",
        (time.time(), "now", "lead", "ALL", "INFO", 1, "T-1", "noise"),
    )
    conn.commit()
    assert len(pending_wakes(conn, subscriber="devin-peer")) == 1


def test_register_session_and_status():
    conn = db()
    register_session(
        conn,
        session_key="devin:lead",
        member_id="devin-lead",
        provider="devin-mcp",
        external_session_id="devin-123",
        state="running",
        cost_class="paid",
        capabilities=["consult", "code"],
    )
    report = status(conn)
    assert report["sessions_total"] == 1
    assert report["sessions_active"] == 1


def test_reconcile_observes_without_mutating():
    conn = db()
    now = 2_000_000.0
    conn.execute(
        """insert into brain_members(
             chat_id,role,display_name,authority,status,last_seen_epoch,joined_at
           ) values('old-worker','','old-worker',0,'ACTIVE',?,'now')""",
        (now - 5000,),
    )
    conn.execute(
        """insert into tasks(
             id,priority,lane,title,status,branch,owner,note,updated_at
           ) values('T-ACTIVE',1,'x','x','ACTIVE','','old-worker','','now')"""
    )
    conn.commit()
    result = reconcile(conn, now_epoch=now, stale_seconds=1800)
    codes = {x["code"] for x in result["findings"]}
    assert "stale_member" in codes
    assert "active_task_without_live_lease" in codes

    member_status = conn.execute(
        "select status from brain_members where chat_id='old-worker'"
    ).fetchone()[0]
    task_status = conn.execute(
        "select status from tasks where id='T-ACTIVE'"
    ).fetchone()[0]
    assert member_status == "ACTIVE"
    assert task_status == "ACTIVE"
