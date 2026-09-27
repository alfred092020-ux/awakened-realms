import json
import sqlite3
import sys
import tempfile
import unittest
import subprocess
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_studio_org import (
    REQUIRED_DEPARTMENTS,
    classify_task,
    create_work_order,
    department_health,
    ensure_schema,
    load_policy,
    plan_departments,
    record_decision,
)


class StudioOrgTests(unittest.TestCase):
    def setUp(self):
        self.config = TEST_DIR.parent / "config" / "studio_departments.json"

    def test_policy_defines_required_departments_and_guardrails(self):
        policy = load_policy(self.config)
        self.assertEqual(set(REQUIRED_DEPARTMENTS), set(policy["departments"]))
        for dept in policy["departments"].values():
            for key in ("charter", "objectives", "task_types", "owned_artifacts", "required_evidence", "quality_gates", "concurrency_budget", "engines"):
                self.assertTrue(dept.get(key), key)
        guardrails = set(policy["guardrails"])
        self.assertIn("brain_ownership", guardrails)
        self.assertIn("independent_verification", guardrails)
        self.assertIn("protected_branches", guardrails)
        self.assertIn("spending_policy", guardrails)
        self.assertIn("cross_department_gates", guardrails)

    def test_capability_routing_is_department_based_not_identity_based(self):
        policy = load_policy(self.config)
        research = classify_task({"lane": "research", "title": "Recover native battle behavior", "work_type": "research"}, policy)
        gameplay = classify_task({"lane": "battle", "title": "Implement attack resolution", "work_type": "implementation"}, policy)
        self.assertEqual("reverse_engineering_research", research["department"])
        self.assertEqual("gameplay_engineering", gameplay["department"])
        self.assertIn("research", research["engines"])
        self.assertTrue(any(x in gameplay["engines"] for x in ("devin", "chatgpt", "copilot")))

    def test_dynamic_activation_collapses_empty_queues_and_respects_budgets(self):
        policy = load_policy(self.config)
        tasks = [
            {"id": "A", "status": "READY", "lane": "battle", "title": "Battle fix", "priority": 0},
            {"id": "B", "status": "READY", "lane": "battle", "title": "Battle test", "priority": 1},
            {"id": "C", "status": "READY", "lane": "qa", "title": "Device proof", "priority": 0},
        ]
        plan = plan_departments(tasks, policy, verifier_capacity=1, resource_pressure="normal")
        self.assertGreater(plan["gameplay_engineering"]["desired_workers"], 0)
        self.assertLessEqual(plan["gameplay_engineering"]["desired_workers"], policy["departments"]["gameplay_engineering"]["concurrency_budget"])
        self.assertEqual(0, plan["art_ui_ux"]["desired_workers"])
        self.assertLessEqual(sum(v["desired_workers"] for v in plan.values()), 1)

    def test_work_orders_and_decisions_persist_with_provenance(self):
        policy = load_policy(self.config)
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        ensure_schema(conn)
        work_id = create_work_order(
            conn,
            source_department="game_design",
            target_department="gameplay_engineering",
            subject="Implement encounter contract",
            acceptance=["state transition matches evidence", "tests pass"],
            provenance={"task_id": "X1", "evidence": "G17"},
            policy=policy,
        )
        decision_id = record_decision(conn, "executive_production", "Prioritize critical path", {"milestone": "slice"})
        row = conn.execute("select * from studio_work_orders where id=?", (work_id,)).fetchone()
        self.assertEqual("OPEN", row["status"])
        self.assertIn("G17", row["provenance_json"])
        self.assertIsNotNone(conn.execute("select 1 from studio_decisions where id=?", (decision_id,)).fetchone())

    def test_health_metrics_cover_required_operating_signals(self):
        metrics = department_health(
            completed=8,
            verification_passed=7,
            verification_failed=1,
            rework=2,
            queue_age_seconds=120,
            blocker_age_seconds=60,
            regressions=1,
            resource_cost=3.5,
            critical_path_completions=2,
        )
        for key in ("throughput", "verification_pass_rate", "rework_rate", "queue_age_seconds", "blocker_age_seconds", "regression_rate", "resource_cost", "critical_path_contribution"):
            self.assertIn(key, metrics)
        self.assertEqual(0.875, metrics["verification_pass_rate"])

    def test_cli_uses_root_control_database(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config").mkdir()
            (root / "control").mkdir()
            (root / "config" / "studio_departments.json").write_text(self.config.read_text())
            sqlite3.connect(root / "control" / "control.sqlite").close()
            cli = TEST_DIR.parent / "bin" / "logres-studio-org"
            proc = subprocess.run([str(cli), "init", "--root", str(root), "--json"], text=True, capture_output=True)
            self.assertEqual(0, proc.returncode, proc.stderr)
            self.assertEqual(10, json.loads(proc.stdout)["departments"])

    def test_unknown_department_work_order_rejected(self):
        policy = load_policy(self.config)
        conn = sqlite3.connect(":memory:")
        ensure_schema(conn)
        with self.assertRaises(ValueError):
            create_work_order(conn, source_department="game_design", target_department="imaginary", subject="x", acceptance=["y"], provenance={}, policy=policy)


if __name__ == "__main__":
    unittest.main()
