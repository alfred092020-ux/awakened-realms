import sqlite3
import sys
import unittest
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_regression_reconcile import reconcile_regression_states


def make_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        create table tasks(
          id text primary key,
          status text not null
        );
        create table integration_queue(
          task_id text not null,
          branch text,
          sha text not null,
          status text not null
        );
        create table regressions(
          id integer primary key,
          task_id text,
          kind text,
          ref text,
          sha text,
          status text not null
        );
        """
    )
    return conn


def add_regression(
    conn,
    row_id,
    task_id,
    *,
    status="OPEN",
    kind="integration-conflict",
    ref=None,
    sha=None,
):
    conn.execute(
        "insert into regressions(id,task_id,kind,ref,sha,status) "
        "values(?,?,?,?,?,?)",
        (row_id, task_id, kind, ref, sha, status),
    )


class RegressionReconcileTests(unittest.TestCase):
    def test_integrated_repair_resolves(self):
        conn = make_db()
        conn.execute("insert into tasks values('R1','DONE')")
        conn.execute(
            "insert into integration_queue values('R1','worker/r1','a','INTEGRATED')"
        )
        add_regression(conn, 1, "R1")
        self.assertEqual((1, 0), reconcile_regression_states(conn))
        self.assertEqual(
            "RESOLVED",
            conn.execute("select status from regressions where id=1").fetchone()[0],
        )

    def test_superseded_repair_supersedes(self):
        conn = make_db()
        conn.execute("insert into tasks values('R1','SUPERSEDED')")
        conn.execute(
            "insert into integration_queue values('R1','worker/r1','a','CONFLICT')"
        )
        add_regression(conn, 1, "R1")
        self.assertEqual((0, 1), reconcile_regression_states(conn))
        self.assertEqual(
            "SUPERSEDED",
            conn.execute("select status from regressions where id=1").fetchone()[0],
        )
        self.assertEqual(
            "SUPERSEDED",
            conn.execute(
                "select status from integration_queue where task_id='R1'"
            ).fetchone()[0],
        )

    def test_terminal_parent_repair_supersedes_descendant_conflict(self):
        conn = make_db()
        conn.execute("insert into tasks values('PARENT','DONE')")
        conn.execute("insert into tasks values('CHILD','READY')")
        conn.execute(
            "insert into integration_queue "
            "values('PARENT','worker/parent','p123','CONFLICT')"
        )
        add_regression(
            conn,
            1,
            "PARENT",
            status="RESOLVED",
            ref="worker/original",
            sha="original",
        )
        add_regression(
            conn,
            2,
            "CHILD",
            ref="worker/parent",
            sha="p123",
        )

        self.assertEqual((0, 1), reconcile_regression_states(conn))
        self.assertEqual(
            "SUPERSEDED",
            conn.execute("select status from regressions where id=2").fetchone()[0],
        )
        self.assertEqual(
            "SUPERSEDED",
            conn.execute("select status from tasks where id='CHILD'").fetchone()[0],
        )
        self.assertEqual(
            "SUPERSEDED",
            conn.execute(
                "select status from integration_queue where task_id='PARENT'"
            ).fetchone()[0],
        )

    def test_open_parent_repair_keeps_descendant_conflict_open(self):
        conn = make_db()
        conn.execute("insert into tasks values('PARENT','DONE')")
        conn.execute("insert into tasks values('CHILD','READY')")
        conn.execute(
            "insert into integration_queue "
            "values('PARENT','worker/parent','p123','CONFLICT')"
        )
        add_regression(
            conn,
            1,
            "PARENT",
            status="OPEN",
            ref="worker/original",
            sha="original",
        )
        add_regression(
            conn,
            2,
            "CHILD",
            ref="worker/parent",
            sha="p123",
        )

        self.assertEqual((0, 0), reconcile_regression_states(conn))
        self.assertEqual(
            "OPEN",
            conn.execute("select status from regressions where id=2").fetchone()[0],
        )
        self.assertEqual(
            "READY",
            conn.execute("select status from tasks where id='CHILD'").fetchone()[0],
        )
        self.assertEqual(
            "CONFLICT",
            conn.execute(
                "select status from integration_queue where task_id='PARENT'"
            ).fetchone()[0],
        )

    def test_unrelated_terminal_parent_does_not_supersede_child(self):
        conn = make_db()
        conn.execute("insert into tasks values('PARENT','DONE')")
        conn.execute("insert into tasks values('CHILD','READY')")
        conn.execute(
            "insert into integration_queue "
            "values('PARENT','worker/parent','p123','CONFLICT')"
        )
        add_regression(conn, 1, "PARENT", status="SUPERSEDED")
        add_regression(
            conn,
            2,
            "CHILD",
            ref="worker/other",
            sha="different",
        )

        self.assertEqual((0, 0), reconcile_regression_states(conn))
        self.assertEqual(
            "OPEN",
            conn.execute("select status from regressions where id=2").fetchone()[0],
        )
        self.assertEqual(
            "SUPERSEDED",
            conn.execute(
                "select status from integration_queue where task_id='PARENT'"
            ).fetchone()[0],
        )

    def test_other_repair_states_remain_open(self):
        states = "ACTIVE READY DONE BLOCKED_DEP BLOCKED_EVIDENCE CANCELLED".split()
        for status in states:
            with self.subTest(status=status):
                conn = make_db()
                conn.execute("insert into tasks values('R1',?)", (status,))
                add_regression(conn, 1, "R1")
                self.assertEqual((0, 0), reconcile_regression_states(conn))
                self.assertEqual(
                    "OPEN",
                    conn.execute(
                        "select status from regressions where id=1"
                    ).fetchone()[0],
                )

    def test_terminal_regression_rows_are_idempotent(self):
        for state in ("RESOLVED", "SUPERSEDED"):
            with self.subTest(state=state):
                conn = make_db()
                conn.execute("insert into tasks values('R1','SUPERSEDED')")
                add_regression(conn, 1, "R1", status=state)
                self.assertEqual((0, 0), reconcile_regression_states(conn))
                self.assertEqual(
                    state,
                    conn.execute(
                        "select status from regressions where id=1"
                    ).fetchone()[0],
                )

    def test_descendant_cleanup_is_idempotent(self):
        conn = make_db()
        conn.execute("insert into tasks values('PARENT','DONE')")
        conn.execute("insert into tasks values('CHILD','READY')")
        conn.execute(
            "insert into integration_queue "
            "values('PARENT','worker/parent','p123','CONFLICT')"
        )
        add_regression(conn, 1, "PARENT", status="RESOLVED")
        add_regression(
            conn,
            2,
            "CHILD",
            ref="worker/parent",
            sha="p123",
        )
        self.assertEqual((0, 1), reconcile_regression_states(conn))
        self.assertEqual((0, 0), reconcile_regression_states(conn))


if __name__ == "__main__":
    unittest.main()
