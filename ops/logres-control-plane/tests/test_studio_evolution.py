import json
import sqlite3
import sys
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(LIB))

import logres_studio_evolution as evo


class StudioEvolutionTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
        create table brain_events(
          id integer primary key autoincrement, ts_epoch real, ts text, sender text,
          recipient text, event_type text, priority integer, task_id text,
          subject text, body text, dedupe_key text, meta_json text
        );
        """)
        evo.ensure_schema(self.conn)
        self.policy = evo.load_policy(Path(__file__).resolve().parents[1] / "config" / "studio_evolution.json")

    def tearDown(self):
        self.conn.close()

    def outcome(self, **overrides):
        row = {
            "department": "gameplay_engineering",
            "window": "canary-001",
            "throughput": 3.0,
            "verification_pass_rate": 0.72,
            "rework_rate": 0.24,
            "queue_depth": 7,
            "queue_age_seconds": 900.0,
            "blocker_count": 2,
            "blocker_age_seconds": 600.0,
            "regressions": 2,
            "resource_pressure": 0.65,
            "critical_path_completions": 1.0,
        }
        row.update(overrides)
        return row

    def test_proposal_persists_all_measured_outcomes_and_bounded_contract(self):
        proposal = evo.propose_improvement(self.conn, self.policy, self.outcome())
        self.assertEqual(proposal["status"], "PROPOSED")
        contract = proposal["contract"]
        self.assertIn(contract["domain"], self.policy["evolvable_domains"])
        self.assertFalse(contract["direct_integration_authority"])
        self.assertTrue(contract["requires_shadow_evaluation"])
        self.assertTrue(contract["requires_independent_verification"])
        evidence = proposal["evidence"]
        for key in (
            "throughput", "verification_pass_rate", "rework_rate", "queue_depth",
            "queue_age_seconds", "blocker_count", "blocker_age_seconds",
            "regressions", "resource_pressure", "critical_path_completions",
        ):
            self.assertIn(key, evidence)
        stored = self.conn.execute("select contract_json,evidence_json from studio_evolution_proposals where id=?", (proposal["proposal_id"],)).fetchone()
        self.assertEqual(json.loads(stored[0])["domain"], contract["domain"])
        self.assertEqual(json.loads(stored[1])["window"], "canary-001")

    def test_only_five_policy_domains_are_evolvable(self):
        self.assertEqual(
            set(self.policy["evolvable_domains"]),
            {"routing", "concurrency", "decomposition", "review_scheduling", "specialization"},
        )
        for domain in ("safety", "spending", "credentials", "protected_branches", "merge_authority", "deploy_authority", "independent_verification"):
            with self.assertRaisesRegex(ValueError, "not evolvable"):
                evo.validate_patch(self.policy, {domain: {"enabled": True}})

    def test_patch_is_bounded_and_protected_authority_fails_closed(self):
        evo.validate_patch(self.policy, {"concurrency": {"max_workers": 4}})
        with self.assertRaisesRegex(ValueError, "outside bounded contract"):
            evo.validate_patch(self.policy, {"concurrency": {"max_workers": 99}})
        for candidate in (
            {"routing": {"merge_authority": True}},
            {"review_scheduling": {"independent_verification_required": False}},
            {"specialization": {"paid_model_authority": True}},
            {"decomposition": {"protected_branch": "main"}},
        ):
            with self.assertRaisesRegex(ValueError, "protected"):
                evo.validate_patch(self.policy, candidate)

    def test_shadow_must_improve_objective_before_promotion(self):
        proposal = evo.propose_improvement(self.conn, self.policy, self.outcome())
        metric = proposal["contract"]["metric_name"]
        bad = evo.record_shadow_result(self.conn, self.policy, proposal["proposal_id"], {metric: proposal["baseline_value"]})
        self.assertEqual(bad["verdict"], "REJECT")
        with self.assertRaisesRegex(ValueError, "shadow"):
            evo.promote_policy(self.conn, self.policy, proposal["proposal_id"], "reviewer=qa-test;verdict=PASS")

    def test_promotion_requires_independent_pass_attestation(self):
        proposal = evo.propose_improvement(self.conn, self.policy, self.outcome())
        metric = proposal["contract"]["metric_name"]
        improved = proposal["baseline_value"] * (1.10 if proposal["direction"] == "higher" else 0.90)
        evo.record_shadow_result(self.conn, self.policy, proposal["proposal_id"], {metric: improved})
        with self.assertRaisesRegex(ValueError, "independent"):
            evo.promote_policy(self.conn, self.policy, proposal["proposal_id"], "")
        with self.assertRaisesRegex(ValueError, "independent"):
            evo.promote_policy(self.conn, self.policy, proposal["proposal_id"], "reviewer=studio-evolution;verdict=PASS")

    def test_version_history_restart_state_and_automatic_rollback(self):
        first = evo.propose_improvement(self.conn, self.policy, self.outcome(window="v1"))
        metric = first["contract"]["metric_name"]
        improved = first["baseline_value"] * (1.10 if first["direction"] == "higher" else 0.90)
        evo.record_shadow_result(self.conn, self.policy, first["proposal_id"], {metric: improved})
        v1 = evo.promote_policy(self.conn, self.policy, first["proposal_id"], "reviewer=qa-test;verdict=PASS")
        state = evo.restart_state(self.conn)
        self.assertEqual(state["active_version"], v1["version"])
        self.assertTrue(state["versions"])
        rolled = evo.rollback_if_regressed(self.conn, self.policy, {"verification_pass_rate": 0.40, "rework_rate": 0.60, "regressions": 5, metric: first["rollback_threshold"]})
        self.assertTrue(rolled["rolled_back"])
        self.assertEqual(evo.restart_state(self.conn)["active_version"], 0)
        self.assertEqual(self.conn.execute("select status from studio_policy_versions where version=?", (v1["version"],)).fetchone()[0], "ROLLED_BACK")

    def test_closed_loop_canary_is_end_to_end_but_has_no_integration_authority(self):
        outcome = self.outcome(window="closed-loop-canary")
        result = evo.closed_loop_canary(
            self.conn,
            self.policy,
            outcome,
            shadow_multiplier=0.90,
            independent_attestation="reviewer=qa-test;verdict=PASS",
        )
        self.assertEqual(result["status"], "CANARY_PASS")
        self.assertFalse(result["direct_integration_authority"])
        self.assertGreaterEqual(result["policy_version"], 1)
        self.assertEqual(self.conn.execute("select count(*) from studio_evolution_decisions").fetchone()[0] >= 3, True)
        self.assertEqual(self.conn.execute("select count(*) from brain_events where event_type in ('EVIDENCE','DECISION')").fetchone()[0] >= 3, True)

    def test_invalid_or_incomplete_outcome_fails_closed(self):
        broken = self.outcome()
        del broken["regressions"]
        with self.assertRaisesRegex(ValueError, "missing measured outcome"):
            evo.propose_improvement(self.conn, self.policy, broken)
        with self.assertRaisesRegex(ValueError, "objective metric"):
            evo.propose_improvement(self.conn, self.policy, self.outcome(resource_pressure=float("nan")))


    def test_cli_status_exposes_restartable_brain_state_without_integration_authority(self):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "brain.sqlite"
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            evo.ensure_schema(conn)
            conn.close()
            cli = Path(__file__).resolve().parents[1] / "bin" / "logres-studio-evolve"
            proc = subprocess.run([str(cli), "--db", str(db), "status", "--json"], text=True, capture_output=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["active_version"], 0)
            self.assertFalse(payload["direct_integration_authority"])


if __name__ == "__main__":
    unittest.main()
