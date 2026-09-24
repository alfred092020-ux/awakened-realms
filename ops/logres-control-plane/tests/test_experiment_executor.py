import sqlite3
import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
CONTROL_ROOT = TEST_DIR.parent
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db, seed_task
from logres_experiment_executor import (
    AUTHORITY,
    next_shadow_experiment,
    run_shadow_experiment,
)
from logres_governor import (
    ExperimentProposal,
    ensure_schema as ensure_governor_schema,
    persist_proposals,
)


class ExperimentExecutorTests(unittest.TestCase):
    def setUp(self):
        self.conn = make_test_db()
        ensure_governor_schema(self.conn)
        for task_id, priority, minutes in (
            ("A", 0, 20),
            ("B", 1, 45),
            ("C", 2, 60),
            ("D", 3, 90),
            ("E", 4, 120),
            ("F", 5, 15),
        ):
            seed_task(
                self.conn,
                task_id=task_id,
                status="READY",
                work_type="implementation",
                priority=priority,
            )
            self.conn.execute(
                "update task_metadata set expected_minutes=? where task_id=?",
                (minutes, task_id),
            )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def shadow_proposal(self):
        return ExperimentProposal(
            source_kind="SHADOW_SCHEDULER",
            hypothesis="A bounded weight variant can improve top-5 overlap.",
            metric_name="top5_overlap",
            direction="higher",
            baseline_value=2.0,
            success_target=3.0,
            rollback_threshold=1.0,
            rollback_condition="Reject if overlap decreases or dispatch occurs.",
            max_scope="Five shadow rankings; zero dispatches.",
            proposed_action="Replay predefined shadow-only weights.",
            source={"top5_overlap": 2, "candidate_count": 6},
        )

    def test_next_returns_only_executable_shadow_proposal(self):
        experiment = persist_proposals(
            self.conn,
            [self.shadow_proposal()],
        )[0]

        self.assertEqual(
            experiment["id"],
            next_shadow_experiment(self.conn),
        )

    def test_run_records_and_evaluates_without_task_or_queue_mutation(self):
        experiment = persist_proposals(
            self.conn,
            [self.shadow_proposal()],
        )[0]
        before_tasks = [
            tuple(row)
            for row in self.conn.execute(
                "select id,status,priority from tasks order by id"
            )
        ]
        before_queue = [
            tuple(row)
            for row in self.conn.execute(
                "select task_id,sha,status,note from integration_queue order by task_id"
            )
        ]

        result = run_shadow_experiment(
            self.conn,
            experiment["id"],
        )

        after_tasks = [
            tuple(row)
            for row in self.conn.execute(
                "select id,status,priority from tasks order by id"
            )
        ]
        after_queue = [
            tuple(row)
            for row in self.conn.execute(
                "select task_id,sha,status,note from integration_queue order by task_id"
            )
        ]
        self.assertEqual(before_tasks, after_tasks)
        self.assertEqual(before_queue, after_queue)
        self.assertEqual(AUTHORITY, result["authority"])
        self.assertEqual(4, len(result["variants"]))
        self.assertIn(
            result["evaluation"]["recommendation"],
            {"KEEP", "REJECT"},
        )
        self.assertIn("No task dispatch", result["effect"])
        row = self.conn.execute(
            "select status,recommendation from governor_experiments where id=?",
            (experiment["id"],),
        ).fetchone()
        self.assertEqual("EVALUATED", row["status"])

    def test_executor_uses_same_approved_contract_registry_as_governor(self):
        text = (
            CONTROL_ROOT / "lib" / "logres_experiment_executor.py"
        ).read_text()

        self.assertIn("EXECUTABLE_SHADOW_CONTRACTS", text)
        self.assertIn("contract not in EXECUTABLE_SHADOW_CONTRACTS", text)

    def test_non_shadow_experiment_is_refused(self):
        proposal = ExperimentProposal(
            source_kind="BOTTLENECK_RESOURCE",
            hypothesis="remote lane may help",
            metric_name="recent_overload",
            direction="lower",
            baseline_value=1.0,
            success_target=0.0,
            rollback_threshold=1.0,
            rollback_condition="reject on regression",
            max_scope="one canary",
            proposed_action="verification-only canary",
            source={},
        )
        experiment = persist_proposals(self.conn, [proposal])[0]

        with self.assertRaisesRegex(
            ValueError,
            "not approved for executable shadow mode",
        ):
            run_shadow_experiment(self.conn, experiment["id"])

    def test_evaluated_experiment_cannot_be_replayed(self):
        experiment = persist_proposals(
            self.conn,
            [self.shadow_proposal()],
        )[0]
        run_shadow_experiment(self.conn, experiment["id"])

        with self.assertRaisesRegex(
            ValueError,
            "is not PROPOSED",
        ):
            run_shadow_experiment(self.conn, experiment["id"])

    def test_executor_binary_has_no_authoritative_action_commands(self):
        text = (
            CONTROL_ROOT / "bin" / "logres-experiment-executor"
        ).read_text()
        for forbidden in (
            "logres-merge-train",
            "logres-merge-preflight",
            "logres-coordinator",
            "git push",
            "deploy_control_plane",
        ):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
