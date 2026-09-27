import importlib.machinery
import importlib.util
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent


def load_script(name: str, filename: str):
    path = CONTROL_ROOT / "bin" / filename
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


coordinator = load_script("logres_coordinator_test_module", "logres-coordinator")


def make_scheduler_db(path=":memory:"):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        create table tasks(
          id text primary key,priority integer,lane text,title text,status text,
          branch text,owner text,note text,updated_at text
        );
        create table task_metadata(
          task_id text primary key,milestone text,work_type text,concurrency_key text,
          expected_minutes integer,evidence_policy text,created_at text,updated_at text
        );
        create table task_dependencies(
          task_id text,depends_on text,kind text,rationale text
        );
        create table task_scopes(
          task_id text,path_prefix text,primary key(task_id,path_prefix)
        );
        create table claims(
          path_prefix text primary key,task_id text,owner text,branch text,
          created_at text,note text
        );
        create table brain_task_leases(
          task_id text primary key,chat_id text,branch text,lease_until_epoch real,
          acquired_at text,renewed_at text,progress integer,note text
        );
        create table brain_members(
          chat_id text primary key,status text,last_seen_epoch real
        );
        create table task_recovery(
          task_id text,status text
        );
        create table brain_events(
          id integer primary key autoincrement,ts_epoch real,ts text,sender text,
          recipient text,event_type text,priority integer,task_id text,subject text,
          body text,dedupe_key text,meta_json text
        );
        create table copilot_jobs(
          id integer primary key autoincrement,route_job_id integer,task_id text,
          issue_number integer,pr_number integer,branch text,base_sha text,
          candidate_sha text,state text,last_error text,created_at text,updated_at text
        );
        """
    )
    conn.execute(
        "insert into tasks values(?,?,?,?,?,?,?,?,?)",
        ("T1",0,"core","T1","READY",None,None,"","now"),
    )
    conn.execute(
        "insert into task_metadata values(?,?,?,?,?,?,?,?)",
        ("T1","M","implementation","coord-key",30,"","now","now"),
    )
    conn.execute("insert into task_scopes values('T1','src/a.ts')")
    conn.execute("insert into brain_members values('worker-1','IDLE',0)")
    conn.commit()
    return conn


def add_copilot_job(conn, state: str):
    conn.execute(
        """insert into copilot_jobs(
             route_job_id,task_id,branch,base_sha,state,created_at,updated_at
           ) values(?,?,?,?,?,?,?)""",
        (1,"T1","copilot/t1","b" * 40,state,"now","now"),
    )
    conn.commit()


def make_queue_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """create table integration_queue(
             task_id text not null,
             sha text not null,
             branch text not null,
             status text not null,
             verification_mode text,
             queued_at text not null,
             updated_at text not null,
             note text not null default '',
             ready_at text,
             integrated_at text,
             primary key(task_id,sha)
           )"""
    )
    return conn


class CoordinatorQuarantineTests(unittest.TestCase):
    def test_quarantined_exact_sha_is_never_reclassified_by_upsert(self):
        conn = make_queue_db()
        sha = "a" * 40
        conn.execute(
            """insert into integration_queue(
                 task_id,sha,branch,status,verification_mode,
                 queued_at,updated_at,note
               ) values(?,?,?,?,?,?,?,?)""",
            (
                "T1",
                sha,
                "worker/original",
                "QUARANTINED",
                "fast",
                "old",
                "old",
                "failed exact-SHA preflight",
            ),
        )

        changed = coordinator.upsert_integration_candidate(
            conn,
            task_id="T1",
            sha=sha,
            branch="worker/moved",
            status="READY_FOR_INTEGRATION",
            verification_mode="full-e2e",
            stamp="new",
        )

        self.assertFalse(changed)
        row = conn.execute(
            "select * from integration_queue where task_id='T1' and sha=?",
            (sha,),
        ).fetchone()
        self.assertEqual("QUARANTINED", row["status"])
        self.assertEqual("worker/original", row["branch"])
        self.assertEqual("fast", row["verification_mode"])
        self.assertEqual("old", row["updated_at"])
        self.assertEqual("failed exact-SHA preflight", row["note"])

    def test_superseeded_and_integrated_exact_sha_are_preserved(self):
        for status in ("SUPERSEDED", "INTEGRATED"):
            with self.subTest(status=status):
                conn = make_queue_db()
                sha = ("b" if status == "SUPERSEDED" else "c") * 40
                conn.execute(
                    """insert into integration_queue(
                         task_id,sha,branch,status,verification_mode,
                         queued_at,updated_at,note
                       ) values(?,?,?,?,?,?,?,?)""",
                    (
                        "T1",
                        sha,
                        "worker/original",
                        status,
                        "fast",
                        "old",
                        "old",
                        "terminal",
                    ),
                )
                changed = coordinator.upsert_integration_candidate(
                    conn,
                    task_id="T1",
                    sha=sha,
                    branch="worker/new",
                    status="READY_FOR_PREFLIGHT",
                    verification_mode="fast",
                    stamp="new",
                )
                self.assertFalse(changed)
                row = conn.execute(
                    "select status,branch,note from integration_queue where task_id='T1' and sha=?",
                    (sha,),
                ).fetchone()
                self.assertEqual(status, row["status"])
                self.assertEqual("worker/original", row["branch"])
                self.assertEqual("terminal", row["note"])

    def test_distinct_repaired_sha_enters_normally(self):
        conn = make_queue_db()
        failed_sha = "d" * 40
        repaired_sha = "e" * 40
        conn.execute(
            """insert into integration_queue(
                 task_id,sha,branch,status,verification_mode,
                 queued_at,updated_at,note
               ) values(?,?,?,?,?,?,?,?)""",
            (
                "T1",
                failed_sha,
                "worker/fix",
                "QUARANTINED",
                "fast",
                "old",
                "old",
                "failed",
            ),
        )

        changed = coordinator.upsert_integration_candidate(
            conn,
            task_id="T1",
            sha=repaired_sha,
            branch="worker/fix",
            status="READY_FOR_PREFLIGHT",
            verification_mode="fast",
            stamp="new",
        )

        self.assertTrue(changed)
        old = conn.execute(
            "select status from integration_queue where task_id='T1' and sha=?",
            (failed_sha,),
        ).fetchone()
        new = conn.execute(
            "select status,verification_mode from integration_queue where task_id='T1' and sha=?",
            (repaired_sha,),
        ).fetchone()
        self.assertEqual("QUARANTINED", old["status"])
        self.assertEqual("READY_FOR_PREFLIGHT", new["status"])
        self.assertEqual("fast", new["verification_mode"])

    def test_coordinator_source_preserves_terminal_rows_during_reconcile(self):
        source = (CONTROL_ROOT / "bin" / "logres-coordinator").read_text()
        self.assertIn(
            "where status not in ('INTEGRATED','SUPERSEDED','QUARANTINED')",
            source,
        )
        self.assertIn(
            "status not in ('INTEGRATED','SUPERSEDED','QUARANTINED','CANDIDATE_MOVED')",
            source,
        )
        self.assertIn("PRESERVED_QUEUE_STATES", source)


class CoordinatorCopilotOwnershipTests(unittest.TestCase):
    def test_live_copilot_states_are_excluded_from_ready_rows(self):
        for state in ("ASSIGNING", "ACTIVE", "PR_READY", "VERIFYING"):
            with self.subTest(state=state):
                conn = make_scheduler_db()
                add_copilot_job(conn, state)
                with mock.patch.object(coordinator, "git_sha", return_value="a" * 40):
                    task_ids = [row["id"] for row in coordinator.ready_rows(conn)]
                self.assertNotIn("T1", task_ids)

    def test_terminal_copilot_jobs_restore_worker_eligibility(self):
        for state in ("QUEUED", "SUPERSEDED", "SCOPE_VIOLATION", "FAILED_BOUNDED"):
            with self.subTest(state=state):
                conn = make_scheduler_db()
                add_copilot_job(conn, state)
                with mock.patch.object(coordinator, "git_sha", return_value="a" * 40):
                    task_ids = [row["id"] for row in coordinator.ready_rows(conn)]
                self.assertIn("T1", task_ids)


    def test_latest_terminal_job_does_not_leave_older_live_job_blocking(self):
        conn = make_scheduler_db()
        add_copilot_job(conn, "ACTIVE")
        add_copilot_job(conn, "SUPERSEDED")
        with mock.patch.object(coordinator, "git_sha", return_value="a" * 40):
            self.assertIn("T1", [row["id"] for row in coordinator.ready_rows(conn)])

    def test_latest_terminal_route_releases_older_reserved_route(self):
        conn = make_scheduler_db()
        conn.execute(
            "create table route_jobs(id integer primary key,task_id text,route_kind text,state text)"
        )
        conn.execute("insert into route_jobs values(1,'T1','COPILOT','ASSIGNING')")
        conn.execute("insert into route_jobs values(2,'T1','COPILOT','SUPERSEDED')")
        conn.commit()
        with mock.patch.object(coordinator, "git_sha", return_value="a" * 40):
            self.assertIn("T1", [row["id"] for row in coordinator.ready_rows(conn)])

    def test_explicit_task_acquire_respects_copilot_route_reservation(self):
        conn = make_scheduler_db()
        conn.execute(
            "create table route_jobs(id integer primary key,task_id text,route_kind text,state text)"
        )
        conn.execute("insert into route_jobs values(1,'T1','COPILOT','ROUTED')")
        conn.commit()
        args = SimpleNamespace(chat="worker-1", task="T1", minutes=60, max_active=6)
        with (
            mock.patch.object(coordinator, "reconcile", return_value=None),
            mock.patch.object(coordinator, "git_sha", return_value="a" * 40),
        ):
            with self.assertRaises(SystemExit) as raised:
                coordinator.cmd_acquire(conn, args)
        self.assertEqual("NO_READY_WORK", str(raised.exception))
        self.assertIsNone(
            conn.execute("select task_id from brain_task_leases where task_id='T1'").fetchone()
        )

    def test_existing_lease_and_claim_authority_still_excludes_ready_task(self):
        lease_conn = make_scheduler_db()
        add_copilot_job(lease_conn, "SUPERSEDED")
        lease_conn.execute(
            "insert into brain_task_leases values(?,?,?,?,?,?,?,?)",
            ("T1","existing-worker","worker/existing",time.time()+3600,"now","now",0,"live"),
        )
        lease_conn.commit()
        with mock.patch.object(coordinator, "git_sha", return_value="a" * 40):
            self.assertEqual([], coordinator.ready_rows(lease_conn))

        claim_conn = make_scheduler_db()
        add_copilot_job(claim_conn, "SUPERSEDED")
        claim_conn.execute(
            "insert into claims values(?,?,?,?,?,?)",
            ("src/a.ts","OTHER","existing-worker","worker/other","now","live"),
        )
        claim_conn.commit()
        with mock.patch.object(coordinator, "git_sha", return_value="a" * 40):
            self.assertEqual([], coordinator.ready_rows(claim_conn))

    def test_begin_immediate_serializes_copilot_winner_before_worker_recheck(self):
        with tempfile.TemporaryDirectory() as td:
            db_path = str(Path(td) / "race.sqlite")
            seed = make_scheduler_db(db_path)
            with mock.patch.object(coordinator, "git_sha", return_value="a" * 40):
                stale_plan = coordinator.ready_rows(seed)
            seed.close()
            self.assertEqual(["T1"], [row["id"] for row in stale_plan])

            copilot_has_lock = threading.Event()
            release_copilot = threading.Event()
            worker_result = {}

            def copilot_writer():
                conn = sqlite3.connect(db_path, timeout=5)
                conn.execute("begin immediate")
                conn.execute(
                    """insert into copilot_jobs(
                         route_job_id,task_id,branch,base_sha,state,created_at,updated_at
                       ) values(?,?,?,?,?,?,?)""",
                    (1,"T1","copilot/t1","b" * 40,"ACTIVE","now","now"),
                )
                copilot_has_lock.set()
                release_copilot.wait(2)
                conn.commit()
                conn.close()

            def worker_acquire():
                conn = sqlite3.connect(db_path, timeout=5)
                conn.row_factory = sqlite3.Row
                trace = []
                conn.set_trace_callback(trace.append)
                args = SimpleNamespace(
                    chat="worker-1", task=None, minutes=60, max_active=6
                )
                try:
                    with (
                        mock.patch.object(coordinator, "reconcile", return_value=None),
                        mock.patch.object(coordinator, "ready_rows", return_value=stale_plan),
                    ):
                        coordinator.cmd_acquire(conn, args)
                    worker_result["outcome"] = "ACQUIRED"
                except SystemExit as exc:
                    worker_result["outcome"] = str(exc)
                finally:
                    worker_result["trace"] = trace
                    conn.close()

            copilot_thread = threading.Thread(target=copilot_writer)
            worker_thread = threading.Thread(target=worker_acquire)
            copilot_thread.start()
            self.assertTrue(copilot_has_lock.wait(1))
            worker_thread.start()
            time.sleep(0.05)
            self.assertTrue(worker_thread.is_alive())
            release_copilot.set()
            copilot_thread.join(2)
            worker_thread.join(2)

            self.assertFalse(copilot_thread.is_alive())
            self.assertFalse(worker_thread.is_alive())
            self.assertTrue(
                worker_result["outcome"].startswith("COPILOT_OWNED task=T1")
            )
            normalized = [entry.upper() for entry in worker_result["trace"]]
            begin_index = next(
                i for i, entry in enumerate(normalized) if "BEGIN IMMEDIATE" in entry
            )
            recheck_index = next(
                i for i, entry in enumerate(normalized) if "FROM COPILOT_JOBS" in entry
            )
            self.assertLess(begin_index, recheck_index)

            verify = sqlite3.connect(db_path)
            self.assertIsNone(
                verify.execute(
                    "select task_id from brain_task_leases where task_id='T1'"
                ).fetchone()
            )
            self.assertEqual(
                "ACTIVE",
                verify.execute(
                    "select state from copilot_jobs where task_id='T1'"
                ).fetchone()[0],
            )
            verify.close()

    def test_atomic_acquire_rejects_stale_planner_result_when_copilot_now_owns_task(self):
        conn = make_scheduler_db()
        with mock.patch.object(coordinator, "git_sha", return_value="a" * 40):
            stale_plan = coordinator.ready_rows(conn)
        self.assertEqual(["T1"], [row["id"] for row in stale_plan])

        add_copilot_job(conn, "VERIFYING")
        args = SimpleNamespace(
            chat="worker-1",
            task=None,
            minutes=60,
            max_active=6,
        )
        with (
            mock.patch.object(coordinator, "reconcile", return_value=None),
            mock.patch.object(coordinator, "ready_rows", return_value=stale_plan),
        ):
            with self.assertRaises(SystemExit) as raised:
                coordinator.cmd_acquire(conn, args)

        self.assertTrue(str(raised.exception).startswith("COPILOT_OWNED task=T1"))
        self.assertIsNone(
            conn.execute(
                "select task_id from brain_task_leases where task_id='T1'"
            ).fetchone()
        )

    def test_atomic_acquire_rechecks_copilot_owner_after_planning_race(self):
        conn = make_scheduler_db()
        with mock.patch.object(coordinator, "git_sha", return_value="a" * 40):
            planned = [row["id"] for row in coordinator.ready_rows(conn)]
        self.assertIn("T1", planned)

        # Copilot wins after planning but before worker-start AUTO reserves a lease.
        add_copilot_job(conn, "ACTIVE")
        args = SimpleNamespace(
            chat="worker-1",
            task=None,
            minutes=60,
            max_active=6,
        )
        with (
            mock.patch.object(coordinator, "reconcile", return_value=None),
            mock.patch.object(coordinator, "git_sha", return_value="a" * 40),
        ):
            with self.assertRaises(SystemExit) as raised:
                coordinator.cmd_acquire(conn, args)

        self.assertEqual("NO_READY_WORK", str(raised.exception))
        self.assertIsNone(
            conn.execute(
                "select task_id from brain_task_leases where task_id='T1'"
            ).fetchone()
        )
        self.assertEqual(
            "ACTIVE",
            conn.execute(
                "select state from copilot_jobs where task_id='T1'"
            ).fetchone()[0],
        )


if __name__ == "__main__":
    unittest.main()
