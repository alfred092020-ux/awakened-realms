import time

from logres_superbrain import (
    apply_member_self_heal,
    dispatch_wakes,
    pending_wakes,
    plan_member_self_heal,
    register_session,
    subscribe,
)
from test_superbrain import db


def add_member(conn, chat_id, seen, status="ACTIVE"):
    conn.execute(
        """insert into brain_members(
             chat_id,role,display_name,authority,status,last_seen_epoch,joined_at
           ) values(?, '', ?, 0, ?, ?, 'now')""",
        (chat_id, chat_id, status, seen),
    )


def post_event(conn, *, sender="lead", event_type="HANDOFF", priority=1, task_id="T-1"):
    now = time.time()
    cur = conn.execute(
        """insert into brain_events(
             ts_epoch,ts,sender,recipient,event_type,priority,task_id,subject,body
           ) values(?,?,?,?,?,?,?,?,?)""",
        (now, "now", sender, "ALL", event_type, priority, task_id, "wake-subject", "wake-body"),
    )
    conn.commit()
    return cur.lastrowid


def test_member_self_heal_marks_only_unprotected_stale_member():
    conn = db()
    now = 2_000_000.0
    conn.executescript(
        """
        create table claims(
          path_prefix text primary key,task_id text,owner text,branch text,
          created_at text,note text
        );
        """
    )

    add_member(conn, "old", now - 7200)
    add_member(conn, "fresh", now - 60)
    add_member(conn, "lead", now - 7200)
    add_member(conn, "leased", now - 7200)
    add_member(conn, "claimed", now - 7200)
    add_member(conn, "sessioned", now - 7200)

    conn.execute(
        """insert into tasks(id,priority,lane,title,status,branch,owner,note,updated_at)
           values('T-L',1,'x','x','ACTIVE','','leased','','now')"""
    )
    conn.execute(
        """insert into brain_task_leases(
             task_id,chat_id,branch,lease_until_epoch,acquired_at,renewed_at,progress,note
           ) values('T-L','leased','',?,'now','now',1,'')""",
        (now + 3600,),
    )

    conn.execute(
        """insert into tasks(id,priority,lane,title,status,branch,owner,note,updated_at)
           values('T-C',1,'x','x','READY','','claimed','','now')"""
    )
    conn.execute(
        """insert into claims(path_prefix,task_id,owner,branch,created_at,note)
           values('x/','T-C','claimed','','now','')"""
    )
    register_session(
        conn,
        session_key="sessioned:1",
        member_id="sessioned",
        provider="test",
        state="ACTIVE",
        last_seen_epoch=now - 60,
    )
    conn.commit()

    plan = plan_member_self_heal(conn, now_epoch=now, stale_seconds=3600)
    assert [x["member_id"] for x in plan] == ["old"]

    result = apply_member_self_heal(conn, now_epoch=now, stale_seconds=3600)
    assert result["applied"] == 1
    assert conn.execute("select status from brain_members where chat_id='old'").fetchone()[0] == "STALE"

    for member in ("fresh", "lead", "leased", "claimed", "sessioned"):
        assert conn.execute(
            "select status from brain_members where chat_id=?", (member,)
        ).fetchone()[0] == "ACTIVE"

    audit = conn.execute(
        """select action,before_state,after_state
             from brain_reconciliation_actions
            where entity_id='old'"""
    ).fetchone()
    assert tuple(audit) == ("MARK_STALE", "ACTIVE", "STALE")


def test_paid_nonurgent_wake_is_deferred_without_dispatch():
    conn = db()
    register_session(
        conn,
        session_key="devin:paid",
        member_id="devin-paid",
        provider="devin-mcp",
        external_session_id="session-1",
        state="SUSPENDED",
        cost_class="paid",
    )
    subscribe(
        conn,
        subscriber="devin-paid",
        event_type="HANDOFF",
        priority_ceiling=3,
        wake_method="devin_mcp",
    )
    post_event(conn, priority=2)

    called = []
    result = dispatch_wakes(
        conn,
        dispatchers={"devin_mcp": lambda payload: called.append(payload)},
        now_epoch=time.time(),
        paid_priority_ceiling=1,
    )
    assert result["claimed"] == 0
    assert len(result["deferred"]) == 1
    assert called == []
    wake = conn.execute(
        "select state,available_epoch,last_error from brain_wake_queue"
    ).fetchone()
    assert wake["state"] == "PENDING"
    assert wake["available_epoch"] > time.time()
    assert wake["last_error"] == "deferred by paid wake policy"


def test_critical_paid_wake_dispatches_once_and_records_receipt():
    conn = db()
    register_session(
        conn,
        session_key="devin:critical",
        member_id="devin-critical",
        provider="devin-mcp",
        external_session_id="session-critical",
        state="SUSPENDED",
        cost_class="paid",
    )
    subscribe(
        conn,
        subscriber="devin-critical",
        event_type="BLOCKER",
        priority_ceiling=1,
        wake_method="devin_mcp",
    )
    post_event(conn, event_type="BLOCKER", priority=1)

    called = []
    result = dispatch_wakes(
        conn,
        dispatchers={"devin_mcp": lambda payload: called.append(payload["wake_id"])},
        now_epoch=time.time(),
        paid_priority_ceiling=1,
    )
    assert result["claimed"] == 1
    assert len(called) == 1
    assert pending_wakes(conn, subscriber="devin-critical") == []

    receipt = conn.execute(
        """select status,transport,cost_class
             from brain_wake_dispatch_receipts
            order by id desc limit 1"""
    ).fetchone()
    assert tuple(receipt) == ("DELIVERED", "devin_mcp", "paid")


def test_failed_dispatch_requeues_with_backoff():
    conn = db()
    register_session(
        conn,
        session_key="local:free",
        member_id="local-free",
        provider="local",
        state="ACTIVE",
        cost_class="local",
    )
    subscribe(
        conn,
        subscriber="local-free",
        event_type="BLOCKER",
        priority_ceiling=1,
        wake_method="local_test",
    )
    post_event(conn, event_type="BLOCKER", priority=1)

    def fail(_payload):
        raise RuntimeError("boom")

    now = time.time()
    result = dispatch_wakes(
        conn,
        dispatchers={"local_test": fail},
        now_epoch=now,
    )
    assert result["results"][0]["state"] == "PENDING"
    wake = conn.execute("select state,attempts,available_epoch,last_error from brain_wake_queue").fetchone()
    assert wake["state"] == "PENDING"
    assert wake["attempts"] == 1
    assert wake["available_epoch"] > now
    assert "boom" in wake["last_error"]
