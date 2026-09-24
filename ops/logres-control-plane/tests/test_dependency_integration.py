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


def add_preflight_tables(conn):
    conn.execute(
        """create table integration_preflights(
             id integer primary key,
             result_sha text,
             status text not null,
             verification_mode text
           )"""
    )
    conn.execute(
        """create table integration_preflight_items(
             preflight_id integer not null,
             task_id text not null,
             candidate_sha text not null
           )"""
    )


def add_preflight(
    conn,
    *,
    candidate,
    result,
    status="APPLIED",
    verification_mode="full-e2e",
    task_id="DEP",
):
    conn.execute(
        "insert into integration_preflights values(1,?,?,?)",
        (result, status, verification_mode),
    )
    conn.execute(
        "insert into integration_preflight_items values(1,?,?)",
        (task_id, candidate),
    )


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

    def test_applied_full_e2e_preflight_result_satisfies_dependency(self):
        conn = make_db()
        add_preflight_tables(conn)
        candidate = "c" * 40
        result = "r" * 40
        conn.execute("insert into tasks values('DEP','DONE')")
        conn.execute("insert into tasks values('CHILD','BLOCKED_DEP')")
        conn.execute(
            "insert into task_dependencies values("
            "'CHILD','DEP','integration','uses canonical API')"
        )
        conn.execute(
            "insert into integration_queue values(?,?,?)",
            ("DEP", candidate, "INTEGRATED"),
        )
        add_preflight(conn, candidate=candidate, result=result)

        self.assertTrue(
            hard_dependencies_satisfied(
                conn,
                "CHILD",
                integration_head="h" * 40,
                ancestor_checker=is_ancestor({result}),
            )
        )

    def test_verified_but_unapplied_preflight_stays_blocked(self):
        conn = make_db()
        add_preflight_tables(conn)
        candidate = "c" * 40
        result = "r" * 40
        conn.execute("insert into tasks values('DEP','DONE')")
        conn.execute(
            "insert into integration_queue values(?,?,?)",
            ("DEP", candidate, "INTEGRATED"),
        )
        add_preflight(
            conn,
            candidate=candidate,
            result=result,
            status="VERIFIED",
        )

        self.assertFalse(
            integration_prerequisite_satisfied(
                conn,
                "DEP",
                integration_head="h" * 40,
                ancestor_checker=is_ancestor({result}),
            )
        )

    def test_non_full_e2e_applied_preflight_stays_blocked(self):
        conn = make_db()
        add_preflight_tables(conn)
        candidate = "c" * 40
        result = "r" * 40
        conn.execute("insert into tasks values('DEP','DONE')")
        conn.execute(
            "insert into integration_queue values(?,?,?)",
            ("DEP", candidate, "INTEGRATED"),
        )
        add_preflight(
            conn,
            candidate=candidate,
            result=result,
            verification_mode="fast",
        )

        self.assertFalse(
            integration_prerequisite_satisfied(
                conn,
                "DEP",
                integration_head="h" * 40,
                ancestor_checker=is_ancestor({result}),
            )
        )

    def test_mismatched_preflight_candidate_stays_blocked(self):
        conn = make_db()
        add_preflight_tables(conn)
        candidate = "c" * 40
        result = "r" * 40
        conn.execute("insert into tasks values('DEP','DONE')")
        conn.execute(
            "insert into integration_queue values(?,?,?)",
            ("DEP", candidate, "INTEGRATED"),
        )
        add_preflight(
            conn,
            candidate="x" * 40,
            result=result,
        )

        self.assertFalse(
            integration_prerequisite_satisfied(
                conn,
                "DEP",
                integration_head="h" * 40,
                ancestor_checker=is_ancestor({result}),
            )
        )

    def test_mismatched_preflight_task_stays_blocked(self):
        conn = make_db()
        add_preflight_tables(conn)
        candidate = "c" * 40
        result = "r" * 40
        conn.execute("insert into tasks values('DEP','DONE')")
        conn.execute(
            "insert into integration_queue values(?,?,?)",
            ("DEP", candidate, "INTEGRATED"),
        )
        add_preflight(
            conn,
            candidate=candidate,
            result=result,
            task_id="OTHER",
        )

        self.assertFalse(
            integration_prerequisite_satisfied(
                conn,
                "DEP",
                integration_head="h" * 40,
                ancestor_checker=is_ancestor({result}),
            )
        )

    def test_failed_preflight_stays_blocked(self):
        conn = make_db()
        add_preflight_tables(conn)
        candidate = "c" * 40
        result = "r" * 40
        conn.execute("insert into tasks values('DEP','DONE')")
        conn.execute(
            "insert into integration_queue values(?,?,?)",
            ("DEP", candidate, "INTEGRATED"),
        )
        add_preflight(
            conn,
            candidate=candidate,
            result=result,
            status="FAILED",
        )

        self.assertFalse(
            integration_prerequisite_satisfied(
                conn,
                "DEP",
                integration_head="h" * 40,
                ancestor_checker=is_ancestor({result}),
            )
        )

    def test_applied_preflight_result_not_on_current_ancestry_stays_blocked(self):
        conn = make_db()
        add_preflight_tables(conn)
        candidate = "c" * 40
        result = "r" * 40
        conn.execute("insert into tasks values('DEP','DONE')")
        conn.execute(
            "insert into integration_queue values(?,?,?)",
            ("DEP", candidate, "INTEGRATED"),
        )
        add_preflight(conn, candidate=candidate, result=result)

        self.assertFalse(
            integration_prerequisite_satisfied(
                conn,
                "DEP",
                integration_head="h" * 40,
                ancestor_checker=is_ancestor({"z" * 40}),
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
