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
from logres_governor import (
    AUTHORITY,
    ensure_schema,
    evaluate_experiment,
    list_experiments,
    persist_proposals,
    propose_experiments,
    record_outcome,
    shadow_executable_proposals,
)


def base_observations():
    return {
        "bottleneck": {"ranked": []},
        "zero_human": {
            "can_continue_without_human": True,
            "stop_reasons": [],
        },
        "health": [],
        "throughput": {"summary": {"recent": {}}},
        "shadow_scheduler": {
            "top5_overlap": 5,
            "shadow": [],
        },
    }


class GovernorProposalTests(unittest.TestCase):
    def test_throughput_failure_proposes_bounded_measurement(self):
        observations = base_observations()
        observations["throughput"] = {
            "summary": {
                "recent": {
                    "20m": {
                        "metrics": {
                            "queue_ready_to_preflight_verified": {
                                "slo_status": "FAIL",
                                "p95_seconds": 180.0,
                                "target_seconds": 120.0,
                                "samples": 5,
                            }
                        }
                    }
                }
            }
        }

        proposals = propose_experiments(observations)

        proposal = next(
            row for row in proposals
            if row.source_kind == "THROUGHPUT_SLO"
        )
        self.assertEqual(
            "queue_ready_to_preflight_verified_p95_seconds",
            proposal.metric_name,
        )
        self.assertEqual("lower", proposal.direction)
        self.assertEqual(180.0, proposal.baseline_value)
        self.assertEqual(120.0, proposal.success_target)
        self.assertIn("One", proposal.max_scope)
        self.assertIn("exact-SHA", proposal.max_scope)

    def test_bottleneck_dependency_proposal_cannot_bypass_ancestry(self):
        observations = base_observations()
        observations["bottleneck"] = {
            "ranked": [
                {
                    "kind": "DEPENDENCY",
                    "severity": 0.8,
                    "metrics": {"blocked_dep": 4, "incomplete": 8},
                }
            ]
        }

        proposals = propose_experiments(observations)

        proposal = next(
            row for row in proposals
            if row.source_kind == "BOTTLENECK_DEPENDENCY"
        )
        self.assertEqual("blocked_dependency_tasks", proposal.metric_name)
        self.assertEqual(4.0, proposal.baseline_value)
        self.assertEqual(3.0, proposal.success_target)
        self.assertIn("canonical ancestry", proposal.rollback_condition)

    def test_zero_human_stop_produces_dry_run_only_experiment(self):
        observations = base_observations()
        observations["zero_human"] = {
            "can_continue_without_human": False,
            "stop_reasons": [
                {"code": "NO_RUNNABLE_WORK", "count": 3},
            ],
        }

        proposals = propose_experiments(observations)

        proposal = next(
            row for row in proposals
            if row.source_kind == "ZERO_HUMAN_STOP"
        )
        self.assertEqual(
            "can_continue_without_human",
            proposal.metric_name,
        )
        self.assertEqual("higher", proposal.direction)
        self.assertEqual(1.0, proposal.success_target)
        self.assertIn("dry-run", proposal.max_scope.lower())
        self.assertIn("fabricated evidence", proposal.rollback_condition)

    def test_health_confidence_proposal_preserves_raw_failure_visibility(self):
        observations = base_observations()
        observations["health"] = [
            {
                "subsystem": "brain",
                "status": "PASS",
                "confidence": 0.9,
            },
            {
                "subsystem": "remote_pool",
                "status": "WARN",
                "confidence": 0.8,
            },
        ]

        proposals = propose_experiments(observations)

        proposal = next(
            row for row in proposals
            if row.source_kind == "HEALTH_CONFIDENCE"
        )
        self.assertEqual(
            "healthy_subsystem_fraction",
            proposal.metric_name,
        )
        self.assertEqual(0.5, proposal.baseline_value)
        self.assertEqual("higher", proposal.direction)
        self.assertIn("credible FAIL", proposal.rollback_condition)

    def test_shadow_scheduler_experiment_remains_zero_dispatch(self):
        observations = base_observations()
        observations["shadow_scheduler"] = {
            "top5_overlap": 2,
            "shadow": [
                {"task_id": "A"},
                {"task_id": "B"},
                {"task_id": "C"},
                {"task_id": "D"},
                {"task_id": "E"},
            ],
        }

        proposals = propose_experiments(observations)

        proposal = next(
            row for row in proposals
            if row.source_kind == "SHADOW_SCHEDULER"
        )
        self.assertEqual("top5_overlap", proposal.metric_name)
        self.assertEqual(2.0, proposal.baseline_value)
        self.assertEqual(3.0, proposal.success_target)
        self.assertIn("zero dispatches", proposal.max_scope)
        self.assertIn(
            "authoritative ordering",
            proposal.rollback_condition,
        )

    def test_shadow_filter_keeps_only_executable_advisory_contracts(self):
        observations = base_observations()
        observations["shadow_scheduler"] = {
            "top5_overlap": 1,
            "shadow": [
                {"task_id": "A"},
                {"task_id": "B"},
                {"task_id": "C"},
            ],
        }
        observations["bottleneck"] = {
            "ranked": [
                {
                    "kind": "RESOURCE",
                    "severity": 1.0,
                    "metrics": {"recent_overload": True},
                }
            ]
        }

        proposals = propose_experiments(observations)
        filtered = shadow_executable_proposals(proposals)

        self.assertTrue(filtered)
        self.assertTrue(
            all(
                proposal.source_kind == "SHADOW_SCHEDULER"
                and proposal.metric_name == "top5_overlap"
                for proposal in filtered
            )
        )
        self.assertLess(len(filtered), len(proposals))

    def test_every_proposal_has_predeclared_experiment_contract(self):
        observations = base_observations()
        observations["bottleneck"] = {
            "ranked": [
                {
                    "kind": "RESOURCE",
                    "severity": 1.0,
                    "metrics": {"recent_overload": True},
                }
            ]
        }
        observations["zero_human"] = {
            "can_continue_without_human": False,
            "stop_reasons": [{"code": "OPEN_REGRESSION", "count": 1}],
        }

        proposals = propose_experiments(observations)

        self.assertGreaterEqual(len(proposals), 2)
        for proposal in proposals:
            payload = proposal.to_dict()
            for key in (
                "hypothesis",
                "metric_name",
                "baseline_value",
                "success_target",
                "rollback_condition",
                "max_scope",
                "proposed_action",
                "authority",
            ):
                self.assertIn(key, payload)
                self.assertNotEqual("", str(payload[key]))
            self.assertEqual(AUTHORITY, payload["authority"])


class GovernorPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.conn = make_test_db()
        ensure_schema(self.conn)
        seed_task(
            self.conn,
            task_id="SAFE-TASK",
            status="READY",
            work_type="implementation",
        )
        self.conn.execute(
            """insert into integration_queue(
                 task_id,sha,branch,status,verification_mode,
                 queued_at,updated_at,note,integrated_at
               ) values(
                 'SAFE-TASK',?,'worker/safe','READY_FOR_PREFLIGHT','fast',
                 'now','now','unchanged',null
               )""",
            ("a" * 40,),
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def proposal(self):
        observations = base_observations()
        observations["shadow_scheduler"] = {
            "top5_overlap": 1,
            "shadow": [
                {"task_id": "A"},
                {"task_id": "B"},
                {"task_id": "C"},
            ],
        }
        return propose_experiments(observations)[0]

    def test_persist_is_idempotent_and_does_not_create_tasks(self):
        before_tasks = self.conn.execute(
            "select count(*) from tasks"
        ).fetchone()[0]
        before_queue = dict(
            self.conn.execute(
                "select * from integration_queue where task_id='SAFE-TASK'"
            ).fetchone()
        )

        first = persist_proposals(self.conn, [self.proposal()])
        second = persist_proposals(self.conn, [self.proposal()])

        self.assertEqual(first[0]["id"], second[0]["id"])
        self.assertEqual(
            1,
            self.conn.execute(
                "select count(*) from governor_experiments"
            ).fetchone()[0],
        )
        self.assertEqual(
            before_tasks,
            self.conn.execute("select count(*) from tasks").fetchone()[0],
        )
        after_queue = dict(
            self.conn.execute(
                "select * from integration_queue where task_id='SAFE-TASK'"
            ).fetchone()
        )
        self.assertEqual(before_queue, after_queue)

    def test_successful_measurement_recommends_keep_only(self):
        experiment = persist_proposals(
            self.conn,
            [self.proposal()],
        )[0]
        target = float(experiment["success_target"])

        record_outcome(
            self.conn,
            experiment["id"],
            metric_value=target,
            notes="shadow replay only",
        )
        result = evaluate_experiment(
            self.conn,
            experiment["id"],
        )

        self.assertEqual("KEEP", result["recommendation"])
        self.assertEqual(AUTHORITY, result["authority"])
        self.assertIn("Recommendation only", result["effect"])

    def test_guardrail_breach_forces_reject_even_when_metric_wins(self):
        experiment = persist_proposals(
            self.conn,
            [self.proposal()],
        )[0]

        record_outcome(
            self.conn,
            experiment["id"],
            metric_value=float(experiment["success_target"]) + 10,
            guardrail_breached=True,
            notes="authoritative scheduler was touched",
        )
        result = evaluate_experiment(
            self.conn,
            experiment["id"],
        )

        self.assertEqual("REJECT", result["recommendation"])
        self.assertTrue(result["guardrail_breached"])

    def test_failed_metric_recommends_reject(self):
        proposal = self.proposal()
        experiment = persist_proposals(
            self.conn,
            [proposal],
        )[0]

        record_outcome(
            self.conn,
            experiment["id"],
            metric_value=proposal.baseline_value,
        )
        result = evaluate_experiment(
            self.conn,
            experiment["id"],
        )

        self.assertEqual("REJECT", result["recommendation"])

    def test_evaluated_experiment_is_immutable(self):
        experiment = persist_proposals(
            self.conn,
            [self.proposal()],
        )[0]
        record_outcome(
            self.conn,
            experiment["id"],
            metric_value=float(experiment["success_target"]),
        )
        evaluate_experiment(self.conn, experiment["id"])

        with self.assertRaisesRegex(ValueError, "immutable"):
            record_outcome(
                self.conn,
                experiment["id"],
                metric_value=999,
            )

    def test_list_experiments_exposes_authority_boundary(self):
        persist_proposals(self.conn, [self.proposal()])

        rows = list_experiments(self.conn)

        self.assertEqual(1, len(rows))
        self.assertEqual(AUTHORITY, rows[0]["authority"])

    def test_governor_binary_supports_shadow_only_proposal_persistence(self):
        text = (CONTROL_ROOT / "bin" / "logres-governor").read_text()

        self.assertIn('"--shadow-only"', text)
        self.assertIn("shadow_executable_proposals(proposals)", text)
        self.assertIn('"shadow_only": bool(args.shadow_only)', text)

    def test_governor_binary_exposes_no_execute_or_promote_command(self):
        text = (CONTROL_ROOT / "bin" / "logres-governor").read_text()

        self.assertNotIn('add_parser("execute")', text)
        self.assertNotIn('add_parser("deploy")', text)
        self.assertNotIn('add_parser("merge")', text)
        self.assertNotIn('add_parser("promote")', text)
        self.assertIn('add_parser("propose")', text)
        self.assertIn('add_parser("record")', text)
        self.assertIn('add_parser("evaluate")', text)


if __name__ == "__main__":
    unittest.main()
