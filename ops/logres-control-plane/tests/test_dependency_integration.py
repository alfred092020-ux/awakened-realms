import sqlite3
import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
LIB_DIR = CONTROL_ROOT / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_dependency import (
    hard_dependencies_satisfied,
    integration_prerequisite_satisfied,
)


def make_db():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """create table tasks(
             id text primary key,
             status text not null
           )"""
    )
    conn.execute(
        """create table task_dependencies(
             task_id text not null,
             depends_on text not null,
             kind text not null,
             rationale text not null default '',
             primary key(task_id,depends_on)
           )"""
    )
    conn.execute(
        """create table integration_queue(
             task_id text not null,
             sha text not null,
             status text not null
           )"""
    )
    return conn


def is_ancestor(expected):
    def check(candidate, head):
        return candidate in expected and head == "h" * 40

    return check


class DependencyIntegrationTests(unittest.TestCase):
    def test_done_but_prefight_prerequisite_remains_blocked(self):
        conn = make_db()
        conn.execute("insert into tasks values('DEP','DONE')")
        conn.execute("insert into tasks values('CHILD','READY')")
        conn.execute(
            "insert into task_dependencies values("
            "'CHILD','DEP','integration','uses canonical API')"
        )
        conn.execute(
            "insert into integration_queue values(?,?,?)",
            ("DEP", "a" * 40, "READY_FOR_PREFLIGHT"),
        )

        self.assertFalse(
            hard_dependencies_satisfied(
                conn,
                "CHILD",
                integration_head="h" * 40,
                ancestor_checker=is_ancestor({"a" * 40}),
            )
        )

    def test_done_but_conflicted_prerequisite_remains_blocked(self):
        conn = make_db()
        conn.execute("insert into tasks values('DEP','DONE')")
        conn.execute("insert into tasks values('CHILD','READY')")
        conn.execute(
            "insert into task_dependencies values("
            "'CHILD','DEP','integration','uses canonical API')"
        )
        conn.execute(
            "insert into integration_queue values(?,?,?)",
            ("DEP", "a" * 40, "CONFLICT"),
        )

        self.assertFalse(
            hard_dependencies_satisfied(
                conn,
                "CHILD",
                integration_head="h" * 40,
                ancestor_checker=is_ancestor({"a" * 40}),
            )
        )

    def test_integrated_ancestor_satisfies_integration_dependency(self):
        conn = make_db()
        conn.execute("insert into tasks values('DEP','DONE')")
        conn.execute("insert into tasks values('CHILD','BLOCKED_DEP')")
        conn.execute(
            "insert into task_dependencies values("
            "'CHILD','DEP','integration','uses canonical API')"
        )
        conn.execute(
            "insert into integration_queue values(?,?,?)",
            ("DEP", "a" * 40, "INTEGRATED"),
        )

        self.assertTrue(
            hard_dependencies_satisfied(
                conn,
                "CHILD",
                integration_head="h" * 40,
                ancestor_checker=is_ancestor({"a" * 40}),
            )
        )

    def test_integrated_row_not_on_current_ancestry_does_not_satisfy(self):
        conn = make_db()
        conn.execute("insert into tasks values('DEP','DONE')")
        conn.execute(
            "insert into integration_queue values(?,?,?)",
            ("DEP", "b" * 40, "INTEGRATED"),
        )

        self.assertFalse(
            integration_prerequisite_satisfied(
                conn,
                "DEP",
                integration_head="h" * 40,
                ancestor_checker=is_ancestor({"a" * 40}),
            )
        )

    def test_superseded_prerequisite_does_not_satisfy_even_with_old_integrated_row(self):
        conn = make_db()
        conn.execute("insert into tasks values('DEP','SUPERSEDED')")
        conn.execute(
            "insert into integration_queue values(?,?,?)",
            ("DEP", "a" * 40, "INTEGRATED"),
        )

        self.assertFalse(
            integration_prerequisite_satisfied(
                conn,
                "DEP",
                integration_head="h" * 40,
                ancestor_checker=is_ancestor({"a" * 40}),
            )
        )

    def test_ordinary_hard_dependency_keeps_existing_done_semantics(self):
        conn = make_db()
        conn.execute("insert into tasks values('DEP','DONE')")
        conn.execute("insert into tasks values('CHILD','READY')")
        conn.execute(
            "insert into task_dependencies values("
            "'CHILD','DEP','hard','normal dependency')"
        )

        self.assertTrue(
            hard_dependencies_satisfied(
                conn,
                "CHILD",
                integration_head=None,
                ancestor_checker=lambda _a, _b: False,
            )
        )

    def test_coordinator_exposes_explicit_integrated_dependency_mode(self):
        script = (CONTROL_ROOT / "bin" / "logres-coordinator").read_text()
        self.assertIn("from logres_dependency import hard_dependencies_satisfied", script)
        self.assertIn('"--depends-integrated"', script)
        self.assertIn("values(?,?,'integration'", script)
        self.assertIn("d.kind in ('hard','integration')", script)


if __name__ == "__main__":
    unittest.main()
