#!/usr/bin/env python3
"""Focused repo-local tests for the Nexus Native Command API server."""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ.setdefault("NEXUS_NATIVE_API_DB", tempfile.mktemp(suffix=".sqlite"))
spec = importlib.util.spec_from_file_location("ncc_native_server", HERE / "server.py")
srv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(srv)

WHO = """\
lead ACTIVE seen=2s unread=0 work=-
worker-a ACTIVE seen=4s unread=2 work=TASK-001:40%
worker-b IDLE seen=1m unread=0 work=-
ghost STALE seen=3h unread=9 work=-
"""
HISTORY = """\
[12] [HIGH] CONTROL_REQUEST nexus→lead task=T-9: Pause autonomy
  Operator note goes here
[11] [INFO] TASK brain→worker-a: dispatched TASK-001
"""
HEALTH = "PASS brain-db ok\nFAIL lease-lock stale\nSUMMARY fails=1 checks=2\n"
DASH = """=== ACTIVE TASK LEASES ===
P0 TASK-001 owner=worker-a progress=40% branch=worker/a until=2026-01-01T00:00:00+00:00
=== READY WORK PACKAGES ===
P1 TASK-002 [implementation] ~20m :: Build the thing
P2 TASK-003 [BLOCKED_DEP] control-plane Blocked thing :: extra
"""

def lead_doc():
    now = __import__("time").time()
    return {
        "meta": {"integration_sha": "a" * 40},
        "tasks": [
            {"id": "TASK-001", "title": "Ship the console", "status": "ACTIVE",
             "lane": "control-plane", "owner": "worker-a", "priority": 0,
             "branch": "worker/a", "updated_at": "2026-10-02T00:00:00+00:00"},
            {"id": "TASK-002", "title": "Queue work", "status": "READY",
             "lane": "control-plane", "owner": None, "priority": 1,
             "branch": None, "updated_at": "2026-10-02T00:00:00+00:00"},
            {"id": "TASK-003", "title": "Blocked work", "status": "BLOCKED_DEP",
             "lane": "control-plane", "owner": None, "priority": 2,
             "branch": None, "updated_at": "2026-10-02T00:00:00+00:00"},
            {"id": "TASK-004", "title": "Done work", "status": "DONE",
             "lane": "control-plane", "owner": None, "priority": 3,
             "branch": None, "updated_at": "2026-10-01T00:00:00+00:00"},
        ],
        "lease_history": [
            {"task_id": "TASK-001", "action": "RENEW", "chat_id": "worker-a",
             "branch": "worker/a", "progress": 40, "ts_epoch": now - 600,
             "lease_until_epoch": now + 3600},
        ],
        "task_dependencies": [
            {"task_id": "TASK-003", "depends_on": "TASK-001", "kind": "integration",
             "rationale": "needs it"},
        ],
        "claims": [{"task_id": "TASK-001", "owner": "worker-a",
                    "path_prefix": "ops/x", "created_at": "2026-10-02"}],
        "task_recovery": [{"task_id": "TASK-009", "branch": "worker/r",
                           "status": "PRESERVED", "created_at": "2026-09-29",
                           "manifest_path": "/m.json"}],
        "verification": [{"ref": "worker/a", "sha": "b" * 40, "status": "PASS",
                          "mode": "fast", "duration_sec": 2.0,
                          "details": "tests", "ran_at": "2026-10-02"}],
        "milestones": [{"id": "M1", "title": "Autonomy", "status": "IN_PROGRESS",
                        "definition_of_done": "dod"}],
        "task_state_history": [], "regressions": [], "integration_queue": [],
        "worktrees": [], "branches": [],
    }

class ParseTests(unittest.TestCase):
    def test_parse_who(self):
        w = srv.parse_who(WHO)
        self.assertEqual(len(w), 4)
        self.assertEqual(w[1]["task"], "TASK-001")
        self.assertEqual(w[1]["progress"], "40%")
        self.assertEqual(w[3]["state"], "STALE")

    def test_parse_history(self):
        ev = srv.parse_history(HISTORY)
        self.assertEqual(len(ev), 2)
        self.assertEqual(ev[0]["task"], "T-9")
        self.assertIn("Operator note", ev[0]["detail"])

    def test_parse_health(self):
        h = srv.parse_health(HEALTH)
        self.assertEqual(h["summary"]["fails"], 1)
        self.assertEqual(len(h["checks"]), 2)

    def test_parse_dashboard(self):
        d = srv.parse_dashboard(DASH)
        self.assertEqual(d["active"][0]["task"], "TASK-001")
        self.assertEqual(d["ready"][0]["task"], "TASK-002")

class TaskViewTests(unittest.TestCase):
    def test_state_derivation_and_summary(self):
        view = srv.build_task_view(lead_doc(), srv.parse_who(WHO), set(), False)
        states = {t["id"]: t["state"] for t in view["open"]}
        self.assertEqual(states["TASK-001"], "AUTONOMOUS")
        self.assertEqual(states["TASK-002"], "READY")
        self.assertEqual(states["TASK-003"], "BLOCKED")
        self.assertEqual(view["recent_done"][0]["id"], "TASK-004")
        t1 = [t for t in view["open"] if t["id"] == "TASK-001"][0]
        self.assertEqual(t1["progress"], 40)
        self.assertIsNotNone(t1["elapsed_ms"])
        self.assertIn("autonomously", t1["summary"])
        t3 = [t for t in view["open"] if t["id"] == "TASK-003"][0]
        self.assertIn("TASK-001", t3["summary"])

    def test_approval_required_overrides(self):
        view = srv.build_task_view(lead_doc(), srv.parse_who(WHO), {"TASK-001"}, False)
        t1 = [t for t in view["open"] if t["id"] == "TASK-001"][0]
        self.assertEqual(t1["state"], "APPROVAL_REQUIRED")

    def test_active_leases(self):
        leases = srv.active_leases(lead_doc())
        self.assertEqual(len(leases), 1)
        self.assertEqual(leases[0]["task_id"], "TASK-001")
        self.assertGreater(leases[0]["lease_remaining_ms"], 0)

    def test_graph(self):
        workers = srv.parse_who(WHO)
        view = srv.build_task_view(lead_doc(), workers, set(), False)
        g = srv.build_graph(lead_doc(), workers, view, [], {"verify_active": True})
        ids = {n["id"] for n in g["nodes"]}
        self.assertIn("brain", ids)
        self.assertIn("worker:worker-a", ids)
        self.assertIn("verify", ids)
        kinds = {e["kind"] for e in g["edges"]}
        self.assertIn("blocks", kinds)
        lane_ids = {l["id"] for l in g["lanes"]}
        self.assertEqual(lane_ids, {"authority", "workers", "tasks", "verification", "approvals"})

class ApprovalTests(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        os.unlink(self.db)
        srv.DB = Path(self.db)

    def test_register_and_decide(self):
        code, row = srv.register_approval({
            "id": "ap-1", "sha": "a" * 40, "reason": "integrate candidate",
            "scope": "ops/", "risk": "low", "action": "integrate-candidate",
            "evidence": {"verify": "PASS"}, "rollback": "revert sha",
            "task_id": "TASK-001"})
        self.assertEqual(code, 201)
        self.assertEqual(row["status"], "PENDING")
        self.assertEqual(row["scope"], "ops/")
        pending = srv.approval_rows("PENDING")
        self.assertEqual(len(pending), 1)
        self.assertIsNotNone(pending[0]["elapsed_ms"])
        # wrong sha cannot decide
        code, obj = srv.decide_approval({"action": "approve-gate", "approval_id": "ap-1",
                                       "sha": "b" * 40})
        self.assertEqual(code, 409)
        code, obj = srv.decide_approval({"action": "approve-gate", "approval_id": "ap-1",
                                       "sha": "a" * 40, "note": "ok"})
        self.assertEqual(code, 200)
        self.assertEqual(obj["decision"], "APPROVED")
        # second decision rejected
        code, _ = srv.decide_approval({"action": "reject-gate", "approval_id": "ap-1",
                                     "sha": "a" * 40})
        self.assertEqual(code, 409)

    def test_register_validation(self):
        code, obj = srv.register_approval({"id": "x", "sha": "zz", "reason": "r"})
        self.assertEqual(code, 400)
        self.assertEqual(obj["error"], "invalid_sha")
        code, obj = srv.register_approval({"id": "x", "sha": "a" * 40})
        self.assertEqual(code, 400)
        self.assertEqual(obj["error"], "missing_reason")

class ControlTests(unittest.TestCase):
    def test_emergency_requires_confirm(self):
        ok, msg = srv.control_request("emergency-stop", confirm="")
        self.assertFalse(ok)
        self.assertIn("EMERGENCY STOP", msg)

    def test_revoke_requires_task_and_confirm(self):
        ok, msg = srv.control_request("revoke-lease", confirm="REVOKE")
        self.assertFalse(ok)
        ok, msg = srv.control_request("revoke-lease", task="T-1", confirm="bad")
        self.assertFalse(ok)

    def test_unsupported_rejected(self):
        ok, msg = srv.control_request("rm-rf-everything")
        self.assertFalse(ok)

    def test_verify_ref_validation(self):
        ok, msg = srv.control_request("verify-ref", ref="bad ref!!")
        self.assertFalse(ok)

if __name__ == "__main__":
    unittest.main()
