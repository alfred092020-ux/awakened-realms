import sqlite3
import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db, seed_active_lease, seed_task
from logres_goal import (
    active_milestones,
    ensure_schema,
    plan_milestone,
    portfolio,
    watch_milestone,
)


def seed_milestone(conn, milestone_id="M1"):
    conn.execute(
        """create table if not exists milestones(
             id text primary key,title text not null,sort_order integer not null,
             status text not null,definition_of_done text not null,
             created_at text not null,updated_at text not null
           )"""
    )
    conn.execute(
        """insert into milestones(
             id,title,sort_order,status,definition_of_done,created_at,updated_at
           ) values(?,?,10,'ACTIVE','ship the slice','now','now')""",
        (milestone_id, milestone_id),
    )
    conn.commit()


def move_to_milestone(conn, *task_ids, milestone_id="M1"):
    for task_id in task_ids:
        conn.execute(
            "update task_metadata set milestone=? where task_id=?",
            (milestone_id, task_id),
        )
    conn.commit()


class GoalTests(unittest.TestCase):
    def setUp(self):
        self.conn = make_test_db()
        seed_milestone(self.conn)
        ensure_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_weighted_progress_uses_done_and_active_lease_progress(self):
        seed_task(self.conn, task_id="DONE", status="DONE")
        seed_task(self.conn, task_id="ACTIVE", status="ACTIVE")
        move_to_milestone(self.conn, "DONE", "ACTIVE")
        self.conn.execute(
            "update task_metadata set expected_minutes=30 where task_id='DONE'"
        )
        self.conn.execute(
            "update task_metadata set expected_minutes=30 where task_id='ACTIVE'"
        )
        seed_active_lease(self.conn, "ACTIVE")
        self.conn.execute(
            "update brain_task_leases set progress=50 where task_id='ACTIVE'"
        )
        self.conn.commit()

        plan = plan_milestone(self.conn, "M1")
        self.assertEqual("RUNNABLE", plan.state)
        self.assertEqual(75.0, plan.progress_percent)
        self.assertEqual(45.0, plan.completed_minutes)

    def test_external_only_blockers_stop_recursive_work(self):
        seed_task(self.conn, task_id="E1", status="BLOCKED_EVIDENCE")
        seed_task(self.conn, task_id="E2", status="BLOCKED_EVIDENCE")
        move_to_milestone(self.conn, "E1", "E2")

        plan = plan_milestone(self.conn, "M1")

        self.assertEqual("WAITING_EXTERNAL", plan.state)
        self.assertEqual(2, len(plan.external_blockers))
        self.assertEqual(0, len(plan.next_actions))

    def test_blocked_dependency_is_distinct_from_external_ceiling(self):
        seed_task(self.conn, task_id="DEP", status="BLOCKED_DEP")
        seed_task(self.conn, task_id="ROOT", status="DONE")
        move_to_milestone(self.conn, "DEP", "ROOT")
        self.conn.execute(
            """insert into task_dependencies(task_id,depends_on,kind,rationale)
               values('DEP','ROOT','hard','fixture')"""
        )
        self.conn.commit()

        plan = plan_milestone(self.conn, "M1")

        self.assertEqual("BLOCKED_DEP", plan.state)
        self.assertEqual(1, len(plan.dependency_blockers))

    def test_complete_ignores_superseded_work(self):
        seed_task(self.conn, task_id="DONE", status="DONE")
        seed_task(self.conn, task_id="OLD", status="SUPERSEDED")
        move_to_milestone(self.conn, "DONE", "OLD")

        plan = plan_milestone(self.conn, "M1")

        self.assertEqual("COMPLETE", plan.state)
        self.assertEqual(100.0, plan.progress_percent)

    def test_watch_is_idempotent_until_goal_state_changes(self):
        seed_task(self.conn, task_id="T1", status="READY")
        move_to_milestone(self.conn, "T1")

        first = watch_milestone(self.conn, "M1", apply=True)
        second = watch_milestone(self.conn, "M1", apply=True)
        self.conn.execute("update tasks set status='DONE' where id='T1'")
        self.conn.commit()
        third = watch_milestone(self.conn, "M1", apply=True)

        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        self.assertTrue(third["changed"])
        self.assertEqual("COMPLETE", third["plan"]["state"])

    def test_portfolio_reports_active_milestones_without_creating_tasks(self):
        seed_task(self.conn, task_id="T1", status="BLOCKED_EVIDENCE")
        move_to_milestone(self.conn, "T1")
        before = self.conn.execute("select count(*) from tasks").fetchone()[0]

        result = portfolio(self.conn)

        after = self.conn.execute("select count(*) from tasks").fetchone()[0]
        self.assertEqual(before, after)
        self.assertEqual(["M1"], active_milestones(self.conn))
        self.assertEqual(1, result["states"]["WAITING_EXTERNAL"])
        self.assertFalse(result["policy"]["manufacture_missing_work"])


if __name__ == "__main__":
    unittest.main()
