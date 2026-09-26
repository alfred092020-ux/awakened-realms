import json
import sqlite3
import sys
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(LIB))

import logres_governor as gov
import logres_devin_lead_evolution as bridge


class LeadEvolutionBridgeTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        gov.ensure_schema(self.conn)
        bridge.ensure_schema(self.conn)
        self.policy = bridge.load_policy(Path(__file__).resolve().parents[1] / "config" / "devin_lead_experiments.json")

    def tearDown(self):
        self.conn.close()

    def decision(self, domain="routing", metric="verification_pass_rate", before=0.80, after=0.92):
        return {
            "decision_id": "lead-cycle-42",
            "domain": domain,
            "summary": "bounded lead policy experiment",
            "metric_name": metric,
            "before_value": before,
            "after_value": after,
            "shadow_evaluated": True,
            "independent_verification": {"verdict": "PASS", "reviewer": "independent-test"},
        }

    def test_objective_decision_emits_governor_experiment_with_explicit_contract(self):
        out = bridge.emit_experiment(self.conn, self.policy, self.decision())
        self.assertEqual(out["status"], "PROPOSED")
        row = self.conn.execute("select * from governor_experiments where id=?", (out["experiment_id"],)).fetchone()
        source = json.loads(row["source_json"])
        self.assertEqual(row["source_kind"], "DEVIN_LEAD_ROUTING")
        self.assertEqual(row["baseline_value"], 0.80)
        self.assertEqual(source["objective_before"], 0.80)
        self.assertEqual(source["objective_after"], 0.92)
        self.assertEqual(source["evolution_contract"]["measurement_key"], "verification_pass_rate")
        self.assertTrue(source["evolution_contract"]["scopes"])


    def test_all_domains_emit_bounded_contracts(self):
        for domain, spec in self.policy["domains"].items():
            before, after = (10.0, 8.0) if spec["direction"] == "lower" else (0.5, 0.7)
            decision = {**self.decision(), "decision_id": f"cycle-{domain}", "domain": domain, "metric_name": spec["metric"], "before_value": before, "after_value": after}
            out = bridge.emit_experiment(self.conn, self.policy, decision)
            row = self.conn.execute("select source_json from governor_experiments where id=?", (out["experiment_id"],)).fetchone()
            contract = json.loads(row[0])["evolution_contract"]
            self.assertEqual(contract["domain"], f"lead_{domain}")
            self.assertEqual(contract["measurement_key"], spec["metric"])
            self.assertTrue(all(scope.startswith("ops/logres-control-plane/") for scope in contract["scopes"]))

    def test_subjective_or_unknown_metric_fails_closed(self):
        bad = self.decision(metric="lead_confidence_score")
        with self.assertRaisesRegex(ValueError, "objective metric"):
            bridge.emit_experiment(self.conn, self.policy, bad)

    def test_all_seven_domains_are_bounded_and_protected_domains_are_rejected(self):
        expected = {"task_decomposition", "routing", "concurrency", "retry_policy", "verification_scheduling", "context_packing", "worker_specialization"}
        self.assertEqual(set(self.policy["domains"]), expected)
        for blocked in ("safety", "spending", "protected_branch", "independent_verification"):
            with self.assertRaisesRegex(ValueError, "domain"):
                bridge.emit_experiment(self.conn, self.policy, self.decision(domain=blocked))

    def seed_keep(self):
        out = bridge.emit_experiment(self.conn, self.policy, self.decision())
        self.conn.execute("update governor_experiments set status='EVALUATED', recommendation='KEEP' where id=?", (out["experiment_id"],))
        self.conn.commit()
        return out["experiment_id"]

    def test_policy_promotion_requires_shadow_and_independent_verification(self):
        exp = self.seed_keep()
        candidate = {"routing": {"max_assignments": 2}}
        with self.assertRaisesRegex(ValueError, "shadow"):
            bridge.promote_policy(self.conn, self.policy, candidate, source_experiment_id=exp, shadow_pass=False, independent_attestation="reviewer=x;verdict=PASS")
        with self.assertRaisesRegex(ValueError, "independent"):
            bridge.promote_policy(self.conn, self.policy, candidate, source_experiment_id=exp, shadow_pass=True, independent_attestation="")

    def test_protected_constraints_cannot_be_changed(self):
        exp = self.seed_keep()
        for candidate in ({"models": {"allow_paid_default": True}}, {"protected_branch": "main"}, {"independent_verification_required": False}, {"privileged_exec": "allow"}):
            with self.assertRaisesRegex(ValueError, "protected"):
                bridge.promote_policy(self.conn, self.policy, candidate, source_experiment_id=exp, shadow_pass=True, independent_attestation="reviewer=x;verdict=PASS")

    def test_version_history_and_automatic_rollback(self):
        exp1 = self.seed_keep()
        v1 = bridge.promote_policy(self.conn, self.policy, {"routing": {"max_assignments": 2}}, source_experiment_id=exp1, shadow_pass=True, independent_attestation="reviewer=a;verdict=PASS")
        out2 = bridge.emit_experiment(self.conn, self.policy, {**self.decision(), "decision_id": "lead-cycle-43", "before_value": 0.81, "after_value": 0.93})
        self.conn.execute("update governor_experiments set status='EVALUATED', recommendation='KEEP' where id=?", (out2["experiment_id"],))
        self.conn.commit()
        v2 = bridge.promote_policy(self.conn, self.policy, {"routing": {"max_assignments": 3}}, source_experiment_id=out2["experiment_id"], shadow_pass=True, independent_attestation="reviewer=b;verdict=PASS")
        self.assertGreater(v2["version"], v1["version"])
        rolled = bridge.rollback_if_regressed(self.conn, self.policy, {"verification_pass_rate": 0.50, "rework_rate": 0.50})
        self.assertTrue(rolled["rolled_back"])
        self.assertEqual(rolled["active_version"], v1["version"])


if __name__ == "__main__":
    unittest.main()
