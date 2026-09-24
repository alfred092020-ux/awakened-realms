import sqlite3
import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TEST_DIR.parent / "lib"))

from logres_regression_supersede import apply_supersede, plan_supersede


def make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        create table integration_preflights(
          id integer primary key,
          status text not null,
          tasks_json text not null,
          result_sha text,
          created_epoch real not null
        );
        create table regressions(
          id integer primary key,
          task_id text,
          kind text,
          ref text,
          sha text,
          status text not null,
          created_epoch real not null
        );
        create table tasks(
          id text primary key,
          status text not null,
          owner text,
          branch text,
          note text,
          updated_at text
        );
        create table integration_queue(
          task_id text,
          status text,
          updated_at text,
          note text
        );
        """
    )
    return conn


def preflight(conn, row_id, status, tasks, result, created):
    import json

    conn.execute(
        "insert into integration_preflights values(?,?,?,?,?)",
        (row_id, status, json.dumps(tasks), result, created),
    )


def regression(conn, row_id, task_id, kind, ref, created, status="OPEN"):
    conn.execute(
        "insert into regressions values(?,?,?,?,?,?,?)",
        (row_id, task_id, kind, ref, ref, status, created),
    )
    conn.execute(
        "insert or ignore into tasks(id,status) values(?,?)",
        (task_id, "READY"),
    )


class RegressionSupersedeTests(unittest.TestCase):
    def test_broader_success_supersedes_subset_failure_and_exact_ref_sibling(self):
        conn = make_db()
        preflight(conn, 10, "FAILED", ["VISUAL"], "v" * 40, 10)
        preflight(conn, 20, "APPLIED", ["VISUAL", "DEPLOY"], "s" * 40, 20)
        regression(conn, 1, "REG-MERGE", "merge-preflight", "v" * 40, 11)
        regression(conn, 2, "REG-CAND", "candidate-verify", "v" * 40, 10.5)
        regression(conn, 3, "OTHER", "candidate-verify", "x" * 40, 10.5)

        targets = plan_supersede(conn, 20)
        self.assertEqual([1, 2], [item.regression_id for item in targets])

    def test_mixed_failure_remains_open_when_success_does_not_cover_every_task(self):
        conn = make_db()
        preflight(
            conn,
            10,
            "FAILED",
            ["VISUAL", "BEHAVIOR"],
            "m" * 40,
            10,
        )
        preflight(conn, 20, "APPLIED", ["VISUAL", "DEPLOY"], "s" * 40, 20)
        regression(conn, 1, "REG-MERGE", "merge-preflight", "m" * 40, 11)
        regression(conn, 2, "REG-CAND", "candidate-verify", "m" * 40, 10.5)

        self.assertEqual([], plan_supersede(conn, 20))

    def test_candidate_siblings_require_exact_failed_result_ref(self):
        conn = make_db()
        preflight(conn, 10, "FAILED", ["VISUAL"], "v" * 40, 10)
        preflight(conn, 20, "VERIFIED", ["VISUAL"], "s" * 40, 20)
        regression(conn, 1, "REG-MERGE", "merge-preflight", "v" * 40, 11)
        regression(conn, 2, "REG-CAND-YES", "candidate-verify", "v" * 40, 10.5)
        regression(conn, 3, "REG-CAND-NO", "candidate-verify", "z" * 40, 10.5)

        targets = plan_supersede(conn, 20)
        self.assertEqual(
            {"REG-MERGE", "REG-CAND-YES"},
            {item.task_id for item in targets},
        )

    def test_apply_is_idempotent(self):
        conn = make_db()
        preflight(conn, 10, "FAILED", ["VISUAL"], "v" * 40, 10)
        preflight(conn, 20, "APPLIED", ["VISUAL"], "s" * 40, 20)
        regression(conn, 1, "REG-MERGE", "merge-preflight", "v" * 40, 11)
        regression(conn, 2, "REG-CAND", "candidate-verify", "v" * 40, 10.5)
        conn.execute(
            "insert into integration_queue values('REG-MERGE','READY',null,'')"
        )

        first = apply_supersede(conn, 20)
        second = apply_supersede(conn, 20)
        self.assertEqual(2, len(first["superseded"]))
        self.assertEqual([], second["superseded"])
        self.assertEqual(
            0,
            conn.execute(
                "select count(*) from regressions where status='OPEN'"
            ).fetchone()[0],
        )
        self.assertEqual(
            "SUPERSEDED",
            conn.execute(
                "select status from tasks where id='REG-MERGE'"
            ).fetchone()[0],
        )
        self.assertEqual(
            "SUPERSEDED",
            conn.execute(
                "select status from integration_queue where task_id='REG-MERGE'"
            ).fetchone()[0],
        )

    def test_active_repair_task_is_preserved_while_regression_is_superseded(self):
        conn = make_db()
        preflight(conn, 10, "FAILED", ["VISUAL"], "v" * 40, 10)
        preflight(conn, 20, "APPLIED", ["VISUAL"], "s" * 40, 20)
        regression(conn, 1, "REG-MERGE", "merge-preflight", "v" * 40, 11)
        conn.execute("update tasks set status='ACTIVE' where id='REG-MERGE'")

        result = apply_supersede(
            conn,
            20,
            active_task_ids={"REG-MERGE"},
        )
        self.assertEqual(["REG-MERGE"], result["preserved_active_tasks"])
        self.assertEqual(
            "SUPERSEDED",
            conn.execute(
                "select status from regressions where id=1"
            ).fetchone()[0],
        )
        self.assertEqual(
            "ACTIVE",
            conn.execute(
                "select status from tasks where id='REG-MERGE'"
            ).fetchone()[0],
        )


if __name__ == "__main__":
    unittest.main()
