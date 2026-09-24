import importlib.machinery
import importlib.util
import sqlite3
import sys
import unittest
from pathlib import Path


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


def make_scheduler_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        create table tasks(
          id text primary key,
          priority integer,
          lane text,
          title text,
          status text,
          branch text,
          owner text,
          note text,
          updated_at text
        );
        create table task_metadata(
          task_id text primary key,
          milestone text,
          work_type text,
          concurrency_key text,
          expected_minutes integer,
          evidence_policy text,
          created_at text,
          updated_at text
        );
        create table task_dependencies(
          task_id text,
          depends_on text,
          kind text,
          rationale text
        );
        create table task_scopes(
          task_id text,
          path_prefix text
        );
        create table claims(
          path_prefix text,
          task_id text,
          owner text,
          branch text,
          created_at text,
          note text
        );
        create table task_recovery(
          id integer primary key,
          task_id text,
          branch text,
          worktree text,
          created_at text,
          created_epoch real,
          dirty_count integer,
          status text,
          manifest_path text,
          note text
        );
        create table brain_task_leases(
          task_id text primary key,
          chat_id text,
          branch text,
          lease_until_epoch real,
          acquired_at text,
          renewed_at text,
          progress integer,
          note text
        );
        create table brain_members(
          chat_id text primary key,
          status text,
          last_seen_epoch real
        );
        create table brain_events(
          id integer primary key autoincrement,
          ts_epoch real,
          ts text,
          sender text,
          recipient text,
          event_type text,
          priority integer,
          task_id text,
          subject text,
          body text,
          dedupe_key text,
          meta_json text
        );
        create table copilot_jobs(
          id integer primary key,
          task_id text,
          state text
        );
        """
    )
    conn.execute(
        """insert into tasks
           values('T1',0,'core','T1','READY',null,null,'','now')"""
    )
    conn.execute(
        """insert into task_metadata
           values('T1','AUTONOMY','implementation','t1',30,'','now','now')"""
    )
    conn.execute(
        "insert into task_scopes values('T1','src/t1.ts')"
    )
    conn.execute(
        "insert into brain_members values('worker','IDLE',0)"
    )
    conn.commit()
    return conn


class CoordinatorCopilotOwnershipTests(unittest.TestCase):
    def test_ready_rows_excludes_live_copilot_owner_and_reopens_after_terminal(self):
        conn = make_scheduler_db()
        original_hard_deps_ok = coordinator.hard_deps_ok
        coordinator.hard_deps_ok = lambda _conn, _task: True
        try:
            for state in (
                "ASSIGNING",
                "ACTIVE",
                "PR_READY",
                "VERIFYING",
            ):
                with self.subTest(state=state):
                    conn.execute("delete from copilot_jobs")
                    conn.execute(
                        "insert into copilot_jobs values(1,'T1',?)",
                        (state,),
                    )
                    conn.commit()
                    self.assertEqual([], coordinator.ready_rows(conn))

            conn.execute(
                "update copilot_jobs set state='SUPERSEDED' where id=1"
            )
            conn.commit()
            self.assertEqual(
                ["T1"],
                [row["id"] for row in coordinator.ready_rows(conn)],
            )
        finally:
            coordinator.hard_deps_ok = original_hard_deps_ok

    def test_atomic_acquire_rechecks_copilot_owner_after_planning_race(self):
        conn = make_scheduler_db()
        conn.execute(
            "insert into copilot_jobs values(1,'T1','ASSIGNING')"
        )
        conn.commit()

        original_reconcile = coordinator.reconcile
        original_ready_rows = coordinator.ready_rows
        coordinator.reconcile = lambda _conn, _verbose=False: None
        coordinator.ready_rows = lambda _conn: [
            {
                "id": "T1",
                "branch": None,
            }
        ]

        class Args:
            chat = "worker"
            minutes = 60
            max_active = 6
            task = "T1"

        try:
            with self.assertRaises(SystemExit) as raised:
                coordinator.cmd_acquire(conn, Args())
            self.assertIn("COPILOT_OWNED task=T1", str(raised.exception))
            self.assertEqual(
                0,
                conn.execute(
                    "select count(*) from brain_task_leases"
                ).fetchone()[0],
            )
            self.assertEqual(
                "READY",
                conn.execute(
                    "select status from tasks where id='T1'"
                ).fetchone()[0],
            )
            self.assertEqual(
                0,
                conn.execute(
                    "select count(*) from claims"
                ).fetchone()[0],
            )
        finally:
            coordinator.reconcile = original_reconcile
            coordinator.ready_rows = original_ready_rows

    def test_queued_copilot_candidate_no_longer_owns_ready_implementation_slot(self):
        conn = make_scheduler_db()
        conn.execute(
            "insert into copilot_jobs values(1,'T1','QUEUED')"
        )
        conn.commit()
        original_hard_deps_ok = coordinator.hard_deps_ok
        coordinator.hard_deps_ok = lambda _conn, _task: True
        try:
            self.assertEqual(
                ["T1"],
                [row["id"] for row in coordinator.ready_rows(conn)],
            )
        finally:
            coordinator.hard_deps_ok = original_hard_deps_ok


if __name__ == "__main__":
    unittest.main()
