import sqlite3
import unittest

from logres_swarm import (
    classify_execution_mode,
    coordinator_reality_snapshot,
    ensure_schema,
    repeated_failure_strategy,
)


class AdaptiveCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_schema(self.conn)
        self.conn.execute("create table brain_task_leases(task_id text primary key, chat_id text, branch text, lease_until_epoch real)")

    def test_capability_routing_is_output_aware(self):
        self.assertEqual("deterministic-verification", classify_execution_mode({"work_type":"verification"}))
        self.assertEqual("patch-implementation", classify_execution_mode({"work_type":"implementation"}))
        self.assertEqual("evidence-research", classify_execution_mode({"work_type":"research"}))
        self.assertEqual("device-qa", classify_execution_mode({"work_type":"device-qa"}))
        self.assertEqual("governed-integration", classify_execution_mode({"work_type":"integration"}))

    def test_repeated_equivalent_failure_forces_diagnosis(self):
        for worker in ("a","b"):
            self.conn.execute("insert into swarm_jobs(task_id,worker_id,engine,state,last_error) values('T',?,'copilot','FAILED','Devin child produced no repository diff')", (worker,))
        decision = repeated_failure_strategy(self.conn, "T")
        self.assertEqual("diagnose", decision["action"])
        self.assertEqual("no_diff", decision["failure_class"])

    def test_reality_snapshot_detects_claim_without_job(self):
        self.conn.execute("insert into brain_task_leases values('T','c','worker/t',9999999999)")
        snap = coordinator_reality_snapshot(self.conn)
        self.assertTrue(snap["requires_reconciliation"])
        self.assertEqual(1, snap["claim_job_delta"])


if __name__ == "__main__":
    unittest.main()
