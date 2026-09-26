import json
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from logres_devin_evolution import (
    ensure_schema,
    reconcile_runs,
    snapshot_metrics,
    tick,
)


class FakeRunner:
    def __init__(self, rc=0):
        self.calls = []
        self.rc = rc

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        return subprocess.CompletedProcess(argv, self.rc, "ok\n", "")


class DevinEvolutionTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            create table tasks(id text primary key, priority integer, lane text,
              title text, status text, branch text, owner text, note text,
              updated_at text);
            create table claims(path_prefix text primary key, task_id text,
              owner text, branch text, created_at text, note text);
            create table task_scopes(task_id text, path_prefix text);
            create table verification(ref text primary key, sha text, mode text,
              status text, duration_sec real, ran_at text, details text);
            create table integration_queue(task_id text, sha text, branch text,
              status text, verification_mode text, queued_at text,
              updated_at text, note text, ready_at text, integrated_at text);
            create table swarm_jobs(id integer primary key, task_id text,
              worker_id text, engine text, state text, pid integer,
              artifact_path text, last_error text, started_at text,
              updated_at text, finished_at text, branch text, model text,
              session_id text, verification text);
            create table regressions(id integer primary key, fingerprint text,
              task_id text, kind text, ref text, sha text, summary text,
              logs_json text, created_at text, created_epoch real, status text);
            create table governor_experiments(id integer primary key,
              created_at text, source_kind text, source_json text,
              hypothesis text, metric_name text, direction text,
              baseline_value real, success_target real,
              rollback_threshold real, rollback_condition text,
              max_scope text, proposed_action text, status text,
              recommendation text, authority text, fingerprint text unique);
            """
        )
        ensure_schema(self.conn)
        self.policy = {
            "enabled": True,
            "task_prefix": "DEVIN-EVOLUTION",
            "allowed_scope_prefixes": ["ops/logres-control-plane/"],
            "max_scopes": 6,
            "max_acceptance": 8,
            "max_generated_per_tick": 1,
            "max_open_generated": 2,
            "cooldown_seconds": 3600,
            "coordinator_bin": "/home/ubuntu/logres/bin/logres-coordinator",
            "swarm_bin": "/home/ubuntu/logres/bin/logres-swarm",
        }

    def add_experiment(self, eid, recommendation="KEEP", contract=None,
                       fingerprint=None, direction="lower", baseline=10,
                       target=8, rollback=12, metric="verification_latency_seconds"):
        source = {"evolution_contract": contract} if contract is not None else {}
        self.conn.execute(
            """insert into governor_experiments values(
            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (eid, "2026-09-26T00:00:00+00:00", "TEST", json.dumps(source),
             "bounded improvement", metric, direction, baseline, target, rollback,
             "rollback on regression", "bounded", "implement bounded change",
             "EVALUATED", recommendation, "ADVISORY", fingerprint or f"fp-{eid}"),
        )
        self.conn.commit()

    def contract(self, domain="verification"):
        return {
            "version": 1,
            "domain": domain,
            "title": "Bounded verified improvement",
            "lane": "control-plane",            "priority": 1,
            "expected_minutes": 45,
            "measurement_key": "verification_latency_seconds",
            "scopes": [
                "ops/logres-control-plane/lib/example.py",
                "ops/logres-control-plane/tests/test_example.py",
            ],
            "acceptance": ["Behavior is covered by executable tests."],
            "depends": [],
            "depends_integrated": [],
        }

    def test_reject_or_missing_contract_never_dispatches(self):
        self.add_experiment(1, recommendation="REJECT", contract=self.contract())
        self.add_experiment(2, recommendation="KEEP", contract=None)
        runner = FakeRunner()
        report = tick(self.conn, self.policy, runner=runner, now_epoch=10000)
        self.assertEqual([], runner.calls)
        self.assertEqual([], report["created"])
        row = self.conn.execute(
            "select state,reason from devin_evolution_runs where experiment_id=2"
        ).fetchone()
        self.assertEqual("QUARANTINED", row["state"])
        self.assertIn("explicit", row["reason"])

    def test_valid_keep_uses_only_coordinator_then_guarded_swarm(self):
        self.add_experiment(3, contract=self.contract())
        runner = FakeRunner()
        report = tick(self.conn, self.policy, runner=runner, now_epoch=10000)
        self.assertEqual(1, len(report["created"]))
        self.assertEqual(2, len(runner.calls))
        self.assertEqual(self.policy["coordinator_bin"], runner.calls[0][0])
        self.assertEqual("add-task", runner.calls[0][1])
        self.assertEqual([self.policy["swarm_bin"], "tick"], runner.calls[1])
        joined = " ".join(runner.calls[0])
        self.assertIn("--scope ops/logres-control-plane/lib/example.py", joined)
        self.assertIn("--scope ops/logres-control-plane/tests/test_example.py", joined)
        self.assertNotIn("sudo", joined)
        self.assertNotIn(" git ", f" {joined} ")
        self.assertNotIn(" devin ", f" {joined} ")
        row = self.conn.execute(
            "select state,task_id from devin_evolution_runs where experiment_id=3"
        ).fetchone()
        self.assertEqual("CREATED", row["state"])
        self.assertTrue(row["task_id"].startswith("DEVIN-EVOLUTION-3-"))

    def test_active_scope_conflict_is_quarantined(self):
        contract = self.contract()
        self.add_experiment(4, contract=contract)
        self.conn.execute(
            "insert into claims values(?,?,?,?,?,?)",
            ("ops/logres-control-plane/lib/example.py", "OTHER", "worker-x",
             "worker/other", "now", ""),
        )
        self.conn.commit()
        runner = FakeRunner()
        report = tick(self.conn, self.policy, runner=runner, now_epoch=10000)
        self.assertEqual([], runner.calls)
        self.assertEqual([], report["created"])
        row = self.conn.execute(
            "select state,reason from devin_evolution_runs where experiment_id=4"
        ).fetchone()
        self.assertEqual("QUARANTINED", row["state"])
        self.assertIn("ownership", row["reason"])

    def test_dedupe_and_domain_cooldown_bound_followup_generation(self):
        self.add_experiment(5, contract=self.contract("routing"))
        runner = FakeRunner()
        first = tick(self.conn, self.policy, runner=runner, now_epoch=10000)
        self.assertEqual(1, len(first["created"]))
        calls_after_first = len(runner.calls)
        second = tick(self.conn, self.policy, runner=runner, now_epoch=10010)
        self.assertEqual([], second["created"])
        self.assertEqual(calls_after_first, len(runner.calls))

        self.add_experiment(6, contract=self.contract("routing"))
        third = tick(self.conn, self.policy, runner=runner, now_epoch=10100)
        self.assertEqual([], third["created"])
        row = self.conn.execute(
            "select state,reason from devin_evolution_runs where experiment_id=6"
        ).fetchone()
        self.assertEqual("DEFERRED", row["state"])
        self.assertIn("cooldown", row["reason"])

    def test_metric_snapshot_records_required_operational_dimensions(self):
        self.conn.execute(
            "insert into swarm_jobs(id,task_id,worker_id,engine,state,started_at,updated_at) "
            "values(1,'A','w','devin','FAILED','x','x')"
        )
        self.conn.execute(
            "insert into verification values('b','s','full-e2e','PASS',7.5,'x','')"
        )
        self.conn.execute(
            "insert into tasks(id,status,updated_at) values('DONE-1','DONE','x')"
        )
        self.conn.commit()
        snap = snapshot_metrics(self.conn)
        self.assertIn("throughput", snap)
        self.assertIn("failure_rate", snap)
        self.assertIn("verification_latency_seconds", snap)
        self.assertIn("resource_cost", snap)
        self.assertIn("task_quality", snap)

    def _insert_created_run(self, eid=20, task_id="EVOLVE-TASK", metric_key="failure_rate"):
        self.add_experiment(eid, contract=self.contract(), direction="lower",
                            baseline=0.2, target=0.1, rollback=0.3,
                            metric=metric_key)
        self.conn.execute(
            """insert into devin_evolution_runs(
            experiment_id,fingerprint,domain,task_id,state,reason,created_epoch,
            baseline_metrics_json,contract_json) values(?,?,?,?,?,?,?,?,?)""",
            (eid, f"fp-{eid}", "verification", task_id, "CREATED", "", 10000,
             json.dumps({}), json.dumps(self.contract())),
        )
        self.conn.execute(
            "insert into tasks(id,status,branch,updated_at) values(?,?,?,?)",
            (task_id, "DONE", f"worker/{task_id.lower()}", "x"),
        )
        self.conn.execute(
            "insert into task_scopes values(?,?)",
            (task_id, "ops/logres-control-plane/tests/test_example.py"),
        )
        self.conn.commit()

    def test_failed_verification_quarantines_created_work(self):
        self._insert_created_run(eid=21, task_id="EVOLVE-FAIL")
        self.conn.execute(
            "insert into verification values(?,?,?,?,?,?,?)",
            ("worker/evolve-fail", "sha", "full-e2e", "FAIL", 3.0, "x", "bad"),
        )
        self.conn.commit()
        report = reconcile_runs(self.conn, self.policy)
        self.assertIn("EVOLVE-FAIL", report["quarantined"])
        state = self.conn.execute(
            "select state from devin_evolution_runs where experiment_id=21"
        ).fetchone()[0]
        self.assertEqual("QUARANTINED", state)

    def test_rollback_threshold_quarantines_even_after_verification_pass(self):
        self._insert_created_run(eid=22, task_id="EVOLVE-ROLLBACK")
        self.conn.execute(
            "insert into verification values(?,?,?,?,?,?,?)",
            ("worker/evolve-rollback", "sha", "full-e2e", "PASS", 2.0, "x", "ok"),
        )
        self.conn.execute(
            "insert into integration_queue(task_id,status,integrated_at) values(?,?,?)",
            ("EVOLVE-ROLLBACK", "INTEGRATED", "x"),
        )
        self.conn.commit()
        metrics = lambda _conn: {
            "throughput": 1.0,
            "failure_rate": 0.35,
            "verification_latency_seconds": 2.0,
            "resource_cost": 1.0,
            "task_quality": 1.0,
        }
        report = reconcile_runs(self.conn, self.policy, metrics_fn=metrics)
        self.assertIn("EVOLVE-ROLLBACK", report["quarantined"])
        state = self.conn.execute(
            "select state from devin_evolution_runs where experiment_id=22"
        ).fetchone()[0]
        self.assertEqual("QUARANTINED", state)

    def test_integrated_verified_test_covered_work_persists_reusable_pattern(self):
        self._insert_created_run(eid=23, task_id="EVOLVE-PASS",
                                 metric_key="failure_rate")
        self.conn.execute(
            "insert into verification values(?,?,?,?,?,?,?)",
            ("worker/evolve-pass", "sha", "full-e2e", "PASS", 2.0, "x", "ok"),
        )
        self.conn.execute(
            "insert into integration_queue(task_id,status,integrated_at) values(?,?,?)",
            ("EVOLVE-PASS", "INTEGRATED", "x"),
        )
        self.conn.commit()
        metrics = lambda _conn: {
            "throughput": 1.0,
            "failure_rate": 0.05,
            "verification_latency_seconds": 2.0,
            "resource_cost": 1.0,
            "task_quality": 1.0,
        }
        report = reconcile_runs(self.conn, self.policy, metrics_fn=metrics)
        self.assertIn("EVOLVE-PASS", report["verified"])
        row = self.conn.execute(
            "select state,rule_json from devin_evolution_patterns where experiment_id=23"
        ).fetchone()
        self.assertEqual("VERIFIED", row["state"])
        rule = json.loads(row["rule_json"])
        self.assertEqual("EVOLVE-PASS", rule["verified_task_id"])
        self.assertTrue(rule["test_covered"])


    def test_open_regression_quarantines_as_guardrail_breach(self):
        self._insert_created_run(eid=24, task_id="EVOLVE-GUARDRAIL", metric_key="failure_rate")
        self.conn.execute(
            "insert into verification values(?,?,?,?,?,?,?)",
            ("worker/evolve-guardrail", "sha", "full-e2e", "PASS", 2.0, "x", "ok"),
        )
        self.conn.execute(
            "insert into integration_queue(task_id,status,integrated_at) values(?,?,?)",
            ("EVOLVE-GUARDRAIL", "INTEGRATED", "x"),
        )
        self.conn.execute(
            "insert into regressions values(1,'r','EVOLVE-GUARDRAIL','guardrail','','','boom','[]','x',1,'OPEN')"
        )
        self.conn.commit()
        report = reconcile_runs(self.conn, self.policy, metrics_fn=lambda _c: {
            "throughput": 1.0, "failure_rate": 0.05,
            "verification_latency_seconds": 2.0, "resource_cost": 1.0,
            "task_quality": 1.0,
        })
        self.assertIn("EVOLVE-GUARDRAIL", report["quarantined"])

    def test_open_generated_work_hard_cap_defers_new_experiment(self):
        self.policy["max_open_generated"] = 1
        self.add_experiment(25, contract=self.contract("one"))
        first = tick(self.conn, self.policy, runner=FakeRunner(), now_epoch=10000)
        self.assertEqual(1, len(first["created"]))
        self.add_experiment(26, contract=self.contract("two"))
        second = tick(self.conn, self.policy, runner=FakeRunner(), now_epoch=20000)
        self.assertEqual([], second["created"])
        row = self.conn.execute(
            "select state,reason from devin_evolution_runs where experiment_id=26"
        ).fetchone()
        self.assertEqual("DEFERRED", row["state"])
        self.assertIn("hard cap", row["reason"])

if __name__ == "__main__":
    unittest.main()
