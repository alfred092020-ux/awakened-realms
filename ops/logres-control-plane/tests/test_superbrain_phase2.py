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



def test_subscription_metadata_cannot_bypass_paid_policy():
    conn = db()
    register_session(
        conn,
        session_key="devin:metadata-bypass",
        member_id="devin-metadata-bypass",
        provider="devin-mcp",
        external_session_id="session-bypass",
        state="SUSPENDED",
        cost_class="paid",
    )
    subscribe(
        conn,
        subscriber="devin-metadata-bypass",
        event_type="HANDOFF",
        priority_ceiling=3,
        wake_method="devin_mcp",
        metadata={"allow_paid_auto": True},
    )
    post_event(conn, priority=2)

    called = []
    now = time.time()
    result = dispatch_wakes(
        conn,
        dispatchers={"devin_mcp": lambda payload: called.append(payload)},
        now_epoch=now,
        paid_priority_ceiling=1,
    )
    assert result["claimed"] == 0
    assert len(result["deferred"]) == 1
    assert called == []
    wake = conn.execute(
        "select state,last_error from brain_wake_queue"
    ).fetchone()
    assert tuple(wake) == ("PENDING", "deferred by paid wake policy")


def test_failed_wake_becomes_terminal_after_max_attempts():
    conn = db()
    register_session(
        conn,
        session_key="devin:bounded-failure",
        member_id="devin-bounded-failure",
        provider="devin-mcp",
        external_session_id="session-failure",
        state="SUSPENDED",
        cost_class="paid",
    )
    subscribe(
        conn,
        subscriber="devin-bounded-failure",
        event_type="BLOCKER",
        priority_ceiling=1,
        wake_method="devin_mcp",
    )
    post_event(conn, event_type="BLOCKER", priority=1, task_id="T-FAIL")

    def fail(_payload):
        raise RuntimeError("dead session")

    now = time.time()
    result = dispatch_wakes(
        conn,
        dispatchers={"devin_mcp": fail},
        now_epoch=now,
        max_attempts=1,
        paid_priority_ceiling=1,
    )
    assert result["claimed"] == 1
    assert result["results"][0]["state"] == "FAILED"

    wake = conn.execute(
        "select state,attempts,last_error from brain_wake_queue"
    ).fetchone()
    assert wake["state"] == "FAILED"
    assert wake["attempts"] == 1
    assert "dead session" in wake["last_error"]

    receipt = conn.execute(
        """select status,attempt,transport,cost_class
             from brain_wake_dispatch_receipts
            order by id desc limit 1"""
    ).fetchone()
    assert tuple(receipt) == ("FAILED", 1, "devin_mcp", "paid")

    events = conn.execute(
        """select event_type,priority,task_id,subject
             from brain_events
            where event_type='WAKE_FAILED'"""
    ).fetchall()
    assert len(events) == 1
    assert tuple(events[0]) == (
        "WAKE_FAILED",
        1,
        "T-FAIL",
        "Wake delivery exhausted: 1",
    )

    second = dispatch_wakes(
        conn,
        dispatchers={"devin_mcp": fail},
        now_epoch=now + 1000,
        max_attempts=1,
        paid_priority_ceiling=1,
    )
    assert second["claimed"] == 0
    assert conn.execute(
        "select count(*) from brain_wake_dispatch_receipts"
    ).fetchone()[0] == 1
    assert conn.execute(
        "select count(*) from brain_events where event_type='WAKE_FAILED'"
    ).fetchone()[0] == 1


def test_stale_claim_recovery_uses_epoch_comparison():
    from logres_superbrain import requeue_stale_claimed_wakes, utc_now

    conn = db()
    subscribe(
        conn,
        subscriber="local-worker",
        event_type="BLOCKER",
        priority_ceiling=1,
        wake_method="brain_event",
    )
    post_event(conn, event_type="BLOCKER", priority=1)
    conn.execute(
        """update brain_wake_queue
              set state='CLAIMED',
                  claimed_by='dead-dispatcher',
                  claimed_at=?,
                  available_epoch=?
            where id=1""",
        (utc_now(1_000_000.0), 1_000_000.0),
    )
    conn.commit()

    reclaimed = requeue_stale_claimed_wakes(
        conn,
        now_epoch=2_000_000.0,
        claim_timeout_seconds=600,
    )
    assert reclaimed == 1
    wake = conn.execute(
        "select state,claimed_by,claimed_at,last_error from brain_wake_queue where id=1"
    ).fetchone()
    assert wake["state"] == "PENDING"
    assert wake["claimed_by"] is None
    assert wake["claimed_at"] is None
    assert wake["last_error"] == "stale dispatch claim reclaimed"



def test_terminal_failure_does_not_feedback_to_wildcard():
    conn = db()
    register_session(
        conn,
        session_key="devin:wildcard-failure",
        member_id="devin-wildcard-failure",
        provider="devin-mcp",
        external_session_id="wildcard-failure",
        state="SUSPENDED",
        cost_class="paid",
    )
    subscribe(
        conn,
        subscriber="devin-wildcard-failure",
        event_type="*",
        priority_ceiling=9,
        wake_method="devin_mcp",
    )
    post_event(conn, event_type="BLOCKER", priority=1, task_id="T-WILD")

    def fail(_payload):
        raise RuntimeError("dead session")

    result = dispatch_wakes(
        conn,
        dispatchers={"devin_mcp": fail},
        now_epoch=time.time(),
        max_attempts=1,
        paid_priority_ceiling=1,
    )
    assert result["results"][0]["state"] == "FAILED"
    rows = conn.execute(
        "select id,state,event_id from brain_wake_queue order by id"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["state"] == "FAILED"
    assert conn.execute(
        "select count(*) from brain_events where event_type='WAKE_FAILED'"
    ).fetchone()[0] == 1


def test_directed_event_only_wakes_intended_subscriber():
    conn = db()
    subscribe(conn, subscriber="worker-a", event_type="*", priority_ceiling=9)
    subscribe(conn, subscriber="worker-b", event_type="*", priority_ceiling=9)
    now = time.time()
    conn.execute(
        """insert into brain_events(
             ts_epoch,ts,sender,recipient,event_type,priority,task_id,subject,body
           ) values(?,?,?,?,?,?,?,?,?)""",
        (now, "now", "lead", "worker-a", "HANDOFF", 2, "T-DIR", "directed", ""),
    )
    conn.commit()
    rows = conn.execute(
        "select subscriber,state from brain_wake_queue order by id"
    ).fetchall()
    assert [tuple(r) for r in rows] == [("worker-a", "PENDING")]


def test_maintenance_events_never_enqueue_wakes():
    conn = db()
    subscribe(conn, subscriber="worker-all", event_type="*", priority_ceiling=9)
    for event_type in ("WAKE_FAILED", "RECONCILIATION"):
        now = time.time()
        conn.execute(
            """insert into brain_events(
                 ts_epoch,ts,sender,recipient,event_type,priority,subject
               ) values(?,?,?,?,?,?,?)""",
            (now, "now", "superbrain", "ALL", event_type, 1, event_type),
        )
    conn.commit()
    assert conn.execute("select count(*) from brain_wake_queue").fetchone()[0] == 0
