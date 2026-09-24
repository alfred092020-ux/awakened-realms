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
        create table tasks(id text primary key,status text not null);
        create table integration_queue(task_id text,sha text,status text);
        create table regressions(id integer primary key,task_id text,status text not null);
        """
    )
    return conn


class RegressionReconcileTests(unittest.TestCase):
    def test_integrated_repair_resolves(self):
        conn = make_db()
        conn.execute("insert into tasks values('R1','DONE')")
        conn.execute("insert into integration_queue values('R1','a','INTEGRATED')")
        conn.execute("insert into regressions values(1,'R1','OPEN')")
        self.assertEqual((1, 0), reconcile_regression_states(conn))
        self.assertEqual(
            "RESOLVED",
            conn.execute("select status from regressions").fetchone()[0],
        )

    def test_superseded_repair_supersedes(self):
        conn = make_db()
        conn.execute("insert into tasks values('R1','SUPERSEDED')")
        conn.execute("insert into regressions values(1,'R1','OPEN')")
        self.assertEqual((0, 1), reconcile_regression_states(conn))
        self.assertEqual(
            "SUPERSEDED",
            conn.execute("select status from regressions").fetchone()[0],
        )


    def test_other_repair_states_remain_open(self):
        states = "ACTIVE READY DONE BLOCKED_DEP BLOCKED_EVIDENCE CANCELLED".split()
        for status in states:
            with self.subTest(status=status):
                conn = make_db()
                conn.execute("insert into tasks values('R1',?)", (status,))
                conn.execute("insert into regressions values(1,'R1','OPEN')")
                self.assertEqual((0, 0), reconcile_regression_states(conn))
                actual = conn.execute(
                    "select status from regressions"
                ).fetchone()[0]
                self.assertEqual("OPEN", actual)


    def test_terminal_regression_rows_are_idempotent(self):
        for state in ("RESOLVED", "SUPERSEDED"):
            with self.subTest(state=state):
                conn = make_db()
                conn.execute("insert into tasks values('R1','SUPERSEDED')")
                conn.execute(
                    "insert into regressions values(1,'R1',?)",
                    (state,),
                )
                self.assertEqual((0, 0), reconcile_regression_states(conn))
                actual = conn.execute(
                    "select status from regressions"
                ).fetchone()[0]
                self.assertEqual(state, actual)


if __name__ == "__main__":
    unittest.main()
