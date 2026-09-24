import json
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_regression_signature import (
    reconcile_semantic_duplicates,
    semantic_groups,
)


def make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        create table tasks(
          id text primary key,priority integer,lane text,title text,status text,
          branch text,owner text,note text,updated_at text
        );
        create table regressions(
          id integer primary key autoincrement,
          fingerprint text not null unique,
          task_id text,kind text not null,ref text,sha text,
          summary text not null,logs_json text not null,
          created_at text,created_epoch real,status text not null
        );
        create table brain_task_leases(
          task_id text primary key,chat_id text,branch text,
          lease_until_epoch real,acquired_at text,renewed_at text,
          progress integer,note text
        );
        create table claims(
          path_prefix text primary key,task_id text,owner text,branch text,
          created_at text,note text
        );
        create table integration_queue(
          task_id text,sha text,branch text,status text,
          verification_mode text,queued_at text,updated_at text,
          note text,ready_at text,integrated_at text
        );
        """
    )
    return conn


def add_task(conn, task_id):
    conn.execute(
        """insert into tasks(
             id,priority,lane,title,status,branch,owner,note,updated_at
           ) values(?,0,'regression',?,'READY','',null,'','now')""",
        (task_id, task_id),
    )


def add_regression(conn, fingerprint, task_id, log_path, row_id=None):
    conn.execute(
        """insert into regressions(
             id,fingerprint,task_id,kind,ref,sha,summary,logs_json,
             created_at,created_epoch,status
           ) values(?,?,?,?,?,?,?,?,?,?,?)""",
        (
            row_id,
            fingerprint,
            task_id,
            "candidate-verify",
            "ref",
            "a" * 40,
            "verify-farm e2e failed",
            json.dumps([str(log_path)]),
            "now",
            time.time(),
            "OPEN",
        ),
    )


class RegressionDedupeTests(unittest.TestCase):
    def test_apply_supersedes_duplicate_task_but_preserves_logs_and_canonical(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            log1 = root / "one.log"
            log2 = root / "two.log"
            log1.write_text(
                "Visual checkpoint title failed\n"
                "sqlite3.OperationalError: database is locked\n"
            )
            log2.write_text(
                "Visual checkpoint field failed\n"
                "sqlite3.OperationalError: database is locked\n"
            )
            conn = make_db()
            add_task(conn, "REG-A")
            add_task(conn, "REG-B")
            add_regression(conn, "legacy-a", "REG-A", log1, 1)
            add_regression(conn, "legacy-b", "REG-B", log2, 2)
            conn.execute(
                """insert into integration_queue(
                     task_id,sha,branch,status,verification_mode,
                     queued_at,updated_at,note
                   ) values(
                     'REG-B',?,'worker/b','READY_FOR_PREFLIGHT',
                     'fast','now','now','queued'
                   )""",
                ("b" * 40,),
            )
            conn.commit()

            dry = reconcile_semantic_duplicates(conn, apply=False)
            self.assertEqual(1, dry["counts"]["groups"])
            self.assertEqual(1, dry["counts"]["duplicates"])
            self.assertEqual(
                "OPEN",
                conn.execute(
                    "select status from regressions where id=2"
                ).fetchone()[0],
            )

            applied = reconcile_semantic_duplicates(conn, apply=True)
            self.assertEqual(1, applied["counts"]["duplicates"])
            self.assertEqual(
                "OPEN",
                conn.execute(
                    "select status from regressions where id=1"
                ).fetchone()[0],
            )
            self.assertEqual(
                "SUPERSEDED",
                conn.execute(
                    "select status from regressions where id=2"
                ).fetchone()[0],
            )
            task = conn.execute(
                "select status,note from tasks where id='REG-B'"
            ).fetchone()
            self.assertEqual("SUPERSEDED", task["status"])
            self.assertIn("Semantic duplicate of REG-A", task["note"])
            self.assertEqual(
                "SUPERSEDED",
                conn.execute(
                    "select status from integration_queue where task_id='REG-B'"
                ).fetchone()[0],
            )
            self.assertEqual(
                [str(log2)],
                json.loads(
                    conn.execute(
                        "select logs_json from regressions where id=2"
                    ).fetchone()[0]
                ),
            )

    def test_quarantined_queue_row_is_never_rewritten_by_dedupe(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            log1 = root / "one.log"
            log2 = root / "two.log"
            for path in (log1, log2):
                path.write_text(
                    "RuntimeError: visual truth recording timed out after 8s"
                )
            conn = make_db()
            add_task(conn, "REG-A")
            add_task(conn, "REG-B")
            add_regression(conn, "legacy-a", "REG-A", log1, 1)
            add_regression(conn, "legacy-b", "REG-B", log2, 2)
            conn.execute(
                """insert into integration_queue(
                     task_id,sha,branch,status,verification_mode,
                     queued_at,updated_at,note
                   ) values(
                     'REG-B',?,'worker/b','QUARANTINED',
                     'fast','now','now','immutable failure'
                   )""",
                ("c" * 40,),
            )
            conn.commit()

            reconcile_semantic_duplicates(conn, apply=True)

            row = conn.execute(
                "select status,note from integration_queue where task_id='REG-B'"
            ).fetchone()
            self.assertEqual("QUARANTINED", row["status"])
            self.assertEqual("immutable failure", row["note"])

    def test_missing_logs_do_not_dedupe_generic_summaries(self):
        conn = make_db()
        add_task(conn, "REG-A")
        add_task(conn, "REG-B")
        add_regression(conn, "legacy-a", "REG-A", "/missing/a", 1)
        add_regression(conn, "legacy-b", "REG-B", "/missing/b", 2)
        conn.commit()

        self.assertEqual([], semantic_groups(conn))

    def test_active_repair_is_preferred_as_canonical(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            log1 = root / "one.log"
            log2 = root / "two.log"
            for path in (log1, log2):
                path.write_text("Error: LOGRES_BEHAVIOR_TRACE_OUT is required")
            conn = make_db()
            add_task(conn, "REG-OLD")
            add_task(conn, "REG-ACTIVE")
            add_regression(conn, "legacy-old", "REG-OLD", log1, 1)
            add_regression(conn, "legacy-active", "REG-ACTIVE", log2, 2)
            conn.execute(
                """insert into brain_task_leases(
                     task_id,chat_id,branch,lease_until_epoch,
                     acquired_at,renewed_at,progress,note
                   ) values(
                     'REG-ACTIVE','worker','worker/x',?,
                     'now','now',10,''
                   )""",
                (time.time() + 3600,),
            )
            conn.commit()

            report = reconcile_semantic_duplicates(conn, apply=True)

            self.assertEqual(
                "REG-ACTIVE",
                report["actions"][0]["canonical_task_id"],
            )
            self.assertEqual(
                "SUPERSEDED",
                conn.execute(
                    "select status from tasks where id='REG-OLD'"
                ).fetchone()[0],
            )
            self.assertEqual(
                "READY",
                conn.execute(
                    "select status from tasks where id='REG-ACTIVE'"
                ).fetchone()[0],
            )


if __name__ == "__main__":
    unittest.main()
