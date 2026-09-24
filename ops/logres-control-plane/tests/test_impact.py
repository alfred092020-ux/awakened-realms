import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db, seed_event, seed_task
from logres_impact import (
    ensure_schema,
    impact_plan,
    incident_status,
    scan_conflicts,
)


class ImpactTests(unittest.TestCase):
    def setUp(self):
        self.conn = make_test_db()
        ensure_schema(self.conn)
        seed_task(self.conn, task_id="ROOT", status="DONE")
        seed_task(self.conn, task_id="CHILD", status="DONE")
        seed_task(self.conn, task_id="LEAF", status="DONE")
        self.conn.execute(
            """insert into task_dependencies(
                 task_id,depends_on,kind,rationale
               ) values('CHILD','ROOT','hard','uses root truth')"""
        )
        self.conn.execute(
            """insert into task_dependencies(
                 task_id,depends_on,kind,rationale
               ) values('LEAF','CHILD','hard','uses child result')"""
        )
        self.conn.execute(
            """insert into integration_queue(
                 task_id,sha,branch,status,verification_mode,
                 queued_at,updated_at,note,integrated_at
               ) values(
                 'ROOT',?,'worker/root','INTEGRATED','full-e2e',
                 'now','now','done','now'
               )""",
            ("a" * 40,),
        )
        self.conn.execute(
            """insert into integration_queue(
                 task_id,sha,branch,status,verification_mode,
                 queued_at,updated_at,note,integrated_at
               ) values(
                 'LEAF',?,'worker/leaf','INTEGRATED','full-e2e',
                 'now','now','done','now'
               )""",
            ("b" * 40,),
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_impact_plan_walks_reverse_dependency_graph(self):
        plan = impact_plan(self.conn, "ROOT")
        self.assertEqual(
            ("CHILD", "LEAF", "ROOT"),
            plan.impacted_tasks,
        )
        commits = {
            row["task_id"]: row["sha"]
            for row in plan.integrated_commits
        }
        self.assertEqual("a" * 40, commits["ROOT"])
        self.assertEqual("b" * 40, commits["LEAF"])

    def test_explicit_conflict_creates_one_bounded_review_task(self):
        seed_event(
            self.conn,
            event_id=77,
            event_type="EVIDENCE_CONFLICT",
            task_id="ROOT",
            artifact_sha="c" * 64,
        )

        report = scan_conflicts(self.conn, apply=True)
        again = scan_conflicts(self.conn, apply=True)

        self.assertEqual(1, report["counts"]["created"])
        self.assertEqual(0, again["counts"]["created"])
        review = report["created_review_tasks"][0]
        row = self.conn.execute(
            "select status,lane,note from tasks where id=?",
            (review,),
        ).fetchone()
        self.assertEqual("READY", row["status"])
        self.assertEqual("research", row["lane"])
        self.assertIn("Review only", row["note"])
        meta = self.conn.execute(
            "select work_type,evidence_policy from task_metadata where task_id=?",
            (review,),
        ).fetchone()
        self.assertEqual("research", meta["work_type"])
        self.assertIn("Explicit conflict", meta["evidence_policy"])
        incident = incident_status(self.conn)[0]
        self.assertEqual(77, incident["event_id"])
        self.assertEqual(review, incident["review_task_id"])
        self.assertEqual(
            ["CHILD", "LEAF", "ROOT"],
            incident["impacted_tasks"],
        )

    def test_first_install_baselines_historical_conflicts(self):
        conn = make_test_db()
        seed_task(conn, task_id="OLD", status="DONE")
        seed_event(
            conn,
            event_id=50,
            event_type="EVIDENCE_CONFLICT",
            task_id="OLD",
        )

        ensure_schema(conn)
        report = scan_conflicts(conn, apply=True)

        self.assertEqual(50, report["watermark"])
        self.assertEqual([], report["created_review_tasks"])
        self.assertEqual(
            0,
            conn.execute("select count(*) from impact_incidents").fetchone()[0],
        )
        conn.close()

    def test_non_conflict_events_do_not_create_reviews(self):
        seed_event(
            self.conn,
            event_id=88,
            event_type="EVIDENCE",
            task_id="ROOT",
        )

        report = scan_conflicts(self.conn, apply=True)

        self.assertEqual([], report["created_review_tasks"])
        self.assertEqual(0, report["counts"]["incidents_total"])

    def test_dry_run_is_non_mutating(self):
        seed_event(
            self.conn,
            event_id=99,
            event_type="EVIDENCE_CONFLICT",
            task_id="ROOT",
        )

        report = scan_conflicts(self.conn, apply=False)

        self.assertEqual(1, report["counts"]["candidates"])
        self.assertEqual([], report["created_review_tasks"])
        self.assertEqual(
            0,
            self.conn.execute(
                "select count(*) from impact_incidents"
            ).fetchone()[0],
        )
        self.assertEqual(
            0,
            self.conn.execute(
                "select count(*) from tasks where id like 'IMPACT-REVIEW-%'"
            ).fetchone()[0],
        )

    def test_unknown_task_conflict_is_reported_but_not_invented(self):
        seed_event(
            self.conn,
            event_id=100,
            event_type="EVIDENCE_CONFLICT",
            task_id="MISSING",
        )

        report = scan_conflicts(self.conn, apply=True)

        self.assertEqual(1, report["counts"]["skipped"])
        self.assertEqual("unknown task", report["skipped"][0]["reason"])
        self.assertEqual([], report["created_review_tasks"])

    def test_policy_forbids_automatic_truth_or_merge_mutation(self):
        seed_event(
            self.conn,
            event_id=101,
            event_type="EVIDENCE_CONFLICT",
            task_id="ROOT",
        )

        report = scan_conflicts(self.conn, apply=False)

        self.assertFalse(report["policy"]["automatic_truth_mutation"])
        self.assertFalse(report["policy"]["automatic_code_mutation"])
        self.assertFalse(report["policy"]["automatic_merge"])


if __name__ == "__main__":
    unittest.main()
