import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

CONTROL_ROOT = Path(__file__).resolve().parents[1]
LIB = CONTROL_ROOT / "lib" / "logres_devin_lead.py"
SPEC = importlib.util.spec_from_file_location("logres_devin_lead", LIB)
lead = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lead)


class DevinLeadLifecycleTests(unittest.TestCase):
    def connection(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        return conn

    def test_single_leader_election(self):
        conn = self.connection()
        self.assertTrue(lead.acquire_leader(conn, instance_id="lead-a", now=100.0, ttl_seconds=30))
        self.assertFalse(lead.acquire_leader(conn, instance_id="lead-b", now=110.0, ttl_seconds=30))
        self.assertTrue(lead.renew_leader(conn, instance_id="lead-a", now=115.0, ttl_seconds=30))

    def test_stale_leader_can_be_reclaimed(self):
        conn = self.connection()
        self.assertTrue(lead.acquire_leader(conn, instance_id="lead-a", now=100.0, ttl_seconds=10))
        self.assertTrue(lead.acquire_leader(conn, instance_id="lead-b", now=111.0, ttl_seconds=20))
        row = conn.execute("select instance_id from devin_lead_runtime where singleton=1").fetchone()
        self.assertEqual("lead-b", row["instance_id"])

    def test_pause_blocks_actions_but_keeps_heartbeat(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "control").mkdir(parents=True)
            (root / "control" / "devin-lead.pause").write_text("operator pause\n")
            pause = lead.read_pause(root)
            self.assertTrue(pause["paused"])
            self.assertIn("operator pause", pause["reason"])
            lead.write_heartbeat(root, {"instance_id": "lead-a", "paused": True})
            heartbeat = json.loads((root / "control" / "devin-lead-heartbeat.json").read_text())
            self.assertEqual("lead-a", heartbeat["instance_id"])
            self.assertTrue(heartbeat["paused"])

    def test_policy_rejects_paid_default(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "devin_lead.json"
            path.write_text(json.dumps({"models": {"allow_paid_default": True}}))
            with self.assertRaisesRegex(ValueError, "paid"):
                lead.load_lead_policy(path)


if __name__ == "__main__":
    unittest.main()
