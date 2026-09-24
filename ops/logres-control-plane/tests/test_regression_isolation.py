import json
import sqlite3
import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
LIB_DIR = CONTROL_ROOT / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_autonomy import failed_preflight_isolation


class RegressionIsolationTests(unittest.TestCase):
    def make_db(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """create table integration_preflights(
                 id integer primary key,
                 base_sha text not null,
                 tasks_json text not null,
                 candidates_json text not null,
                 status text not null,
                 verification_log text,
                 note text,
                 created_epoch real not null
               )"""
        )
        return conn

    def test_failed_multi_candidate_batch_forces_serial_isolation(self):
        conn = self.make_db()
        base = "a" * 40
        conn.execute(
            """insert into integration_preflights(
                 id,base_sha,tasks_json,candidates_json,status,
                 verification_log,note,created_epoch
               ) values(?,?,?,?,?,?,?,?)""",
            (
                9,
                base,
                json.dumps(["A", "B", "C"]),
                json.dumps(["1" * 40, "2" * 40, "3" * 40]),
                "FAILED",
                "/tmp/preflight.log",
                "full-e2e failed",
                100.0,
            ),
        )
        conn.commit()

        policy = failed_preflight_isolation(conn, base)

        self.assertIsNotNone(policy)
        self.assertEqual(1, policy["batch_limit"])
        self.assertEqual(3, policy["task_count"])
        self.assertEqual(["A", "B", "C"], policy["tasks"])
        self.assertEqual(9, policy["preflight_id"])
        self.assertIn("isolate candidates serially", policy["reason"])

    def test_single_candidate_failure_does_not_poison_future_batch_size(self):
        conn = self.make_db()
        base = "b" * 40
        conn.execute(
            """insert into integration_preflights(
                 id,base_sha,tasks_json,candidates_json,status,
                 verification_log,note,created_epoch
               ) values(1,?,?,?,?,?,?,1.0)""",
            (
                base,
                json.dumps(["ONLY"]),
                json.dumps(["4" * 40]),
                "FAILED",
                "/tmp/only.log",
                "failed",
            ),
        )
        conn.commit()

        self.assertIsNone(failed_preflight_isolation(conn, base))

    def test_failure_on_old_base_does_not_reduce_current_batch(self):
        conn = self.make_db()
        conn.execute(
            """insert into integration_preflights(
                 id,base_sha,tasks_json,candidates_json,status,
                 verification_log,note,created_epoch
               ) values(1,?,?,?,?,?,?,1.0)""",
            (
                "c" * 40,
                json.dumps(["A", "B"]),
                json.dumps(["5" * 40, "6" * 40]),
                "FAILED",
                "/tmp/old.log",
                "failed",
            ),
        )
        conn.commit()

        self.assertIsNone(
            failed_preflight_isolation(conn, "d" * 40)
        )

    def test_merge_preflight_preserves_and_quarantines_exact_failed_candidate(self):
        script = (
            CONTROL_ROOT / "bin" / "logres-merge-preflight"
        ).read_text()

        self.assertIn("if len(selected)==1:", script)
        self.assertIn("set status='QUARANTINED'", script)
        self.assertIn("PREFLIGHT_QUARANTINED", script)
        self.assertIn("PREFLIGHT_ISOLATE_NEXT", script)
        self.assertIn("logres-regression-capture", script)
        self.assertIn("never mutate/retry this queued SHA", script)

    def test_autonomy_consumes_failed_batch_isolation_limit(self):
        script = (CONTROL_ROOT / "bin" / "logres-autonomy").read_text()

        self.assertIn("failed_preflight_isolation", script)
        self.assertIn('min(decision.batch_limit, int(isolation["batch_limit"]))', script)
        self.assertIn('"isolation": isolation', script)


if __name__ == "__main__":
    unittest.main()
