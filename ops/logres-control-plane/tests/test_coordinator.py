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


if __name__ == "__main__":
    unittest.main()
