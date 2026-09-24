import sqlite3
import time


def make_test_db(path=":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        create table tasks (
          id text primary key, priority integer, lane text, title text, status text,
          branch text, owner text, note text, updated_at text
        );
        create table task_metadata (
          task_id text primary key, milestone text, work_type text not null,
          concurrency_key text, expected_minutes integer not null,
          evidence_policy text not null, created_at text not null, updated_at text not null
        );
        create table task_acceptance (
          task_id text not null, ordinal integer not null, criterion text not null
        );
        create table task_dependencies (
          task_id text not null, depends_on text not null, kind text not null, rationale text not null
        );
        create table task_scopes (
          task_id text not null, path_prefix text not null,
          primary key(task_id,path_prefix)
        );
        create table claims (
          path_prefix text primary key, task_id text, owner text, branch text,
          created_at text, note text
        );
        create table brain_events (
          id integer primary key, ts_epoch real not null, ts text not null,
          sender text not null, recipient text not null, event_type text not null,
          priority integer not null, task_id text, subject text not null, body text not null,
          artifact_path text, artifact_sha256 text, dedupe_key text, meta_json text not null
        );
        create table brain_task_leases (
          task_id text primary key, chat_id text not null, branch text,
          lease_until_epoch real not null, acquired_at text not null, renewed_at text not null,
          progress integer, note text not null
        );
        create table verification (
          ref text, sha text, mode text, status text, duration_sec real, ran_at text, details text
        );
        create table integration_queue (
          task_id text not null, sha text not null, branch text not null, status text not null,
          verification_mode text, queued_at text not null, updated_at text not null,
          note text not null, ready_at text, integrated_at text
        );
        create table ai_runs (
          id integer primary key autoincrement, dedupe_key text unique not null,
          artifact_sha text not null, question text not null, artifact_path text not null,
          task_id text, model text, status text not null, result_json text, created_at text
        );
        """
    )
    return conn
def seed_task(
    conn,
    task_id="T1",
    priority=0,
    status="READY",
    work_type="implementation",
    evidence_policy="",
    concurrency_key="default",
    acceptance=("criterion",),
):
    now = "2026-09-23T19:00:00-07:00"
    conn.execute(
        "insert into tasks(id,priority,lane,title,status,branch,owner,note,updated_at) values(?,?,?,?,?,?,?,?,?)",
        (task_id, priority, "core", task_id, status, None, None, "", now),
    )
    conn.execute(
        "insert into task_metadata(task_id,milestone,work_type,concurrency_key,expected_minutes,evidence_policy,created_at,updated_at) values(?,?,?,?,?,?,?,?)",
        (task_id, "slice", work_type, concurrency_key, 30, evidence_policy, now, now),
    )
    for ordinal, criterion in enumerate(acceptance, start=1):
        conn.execute(
            "insert into task_acceptance(task_id,ordinal,criterion) values(?,?,?)",
            (task_id, ordinal, criterion),
        )
    conn.commit()
def seed_event(
    conn,
    event_id=10,
    event_type="EVIDENCE",
    task_id="T1",
    artifact_path="/tmp/artifact.txt",
    artifact_sha="a" * 64,
    meta=None,
):
    import json

    now = "2026-09-23T19:00:00-07:00"
    conn.execute(
        "insert into brain_events(id,ts_epoch,ts,sender,recipient,event_type,priority,task_id,subject,body,artifact_path,artifact_sha256,dedupe_key,meta_json) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            event_id, time.time(), now, "finder", "ALL", event_type, 1, task_id,
            "fixture", "fixture", artifact_path, artifact_sha, None, json.dumps(meta or {}),
        ),
    )
    conn.commit()


def seed_ai_run(conn, artifact_sha, question, status="PASS"):
    conn.execute(
        "insert into ai_runs(dedupe_key,artifact_sha,question,artifact_path,task_id,model,status,result_json,created_at) values(?,?,?,?,?,?,?,?,?)",
        (
            f"{artifact_sha}:{question}", artifact_sha, question, "/tmp/artifact.txt",
            "T1", "gpt-5.6-luna", status, "{}", "2026-09-23T19:00:00-07:00",
        ),
    )
    conn.commit()

def seed_active_lease(
    conn,
    task_id,
    chat_id="worker",
    branch="worker/test",
    lease_seconds=3600,
):
    now = "2026-09-23T19:00:00-07:00"
    conn.execute(
        "insert into brain_task_leases(task_id,chat_id,branch,lease_until_epoch,acquired_at,renewed_at,progress,note) values(?,?,?,?,?,?,?,?)",
        (task_id, chat_id, branch, time.time() + lease_seconds, now, now, 0, ""),
    )
    conn.commit()


def test_config():
    return {
        "routing": {
            "ai_dispatch_enabled": False,
            "copilot_dispatch_enabled": False,
            "copilot_mode": "report_only",
        },
        "openai": {
            "budget_usd": 10.0,
            "max_active": 1,
            "max_active_hard": 2,
            "model_rates_per_million": {},
        },
        "copilot": {"max_active": 2, "max_queued": 1},
        "backpressure": {
            "ready_for_integration": 4,
            "verification_backlog": 3,
        },
        "autonomy": {
            "enabled": False,
            "auto_preflight_enabled": False,
            "auto_apply_preflight_enabled": False,
            "max_preflight_batch": 4,
            "circuit_breaker_failures": 2,
            "block_on_open_regressions": False,
            "min_free_memory_gib": 12.0,
            "min_free_disk_gib": 30.0,
            "max_load_per_cpu": 1.25,
        },
    }

def seed_route(
    conn,
    state,
    dedupe_key,
    route_kind="AI",
    task_id="T1",
    external_ref=None,
    source_event_id=None,
    artifact_sha=None,
    meta_json="{}",
    base_sha=None,
):
    now = "2026-09-23T19:00:00-07:00"
    cursor = conn.execute(
        """insert into route_jobs(
             dedupe_key,source_event_id,task_id,route_kind,state,artifact_sha,
             base_sha,external_ref,meta_json,created_at,updated_at
           ) values(?,?,?,?,?,?,?,?,?,?,?)""",
        (
            dedupe_key,
            source_event_id,
            task_id,
            route_kind,
            state,
            artifact_sha,
            base_sha,
            external_ref,
            meta_json,
            now,
            now,
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)
