import sqlite3
import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_finish_loop import (
    FinishDecision,
    action_for,
    active_milestone_id,
    apply_decision,
    decide,
    decision_fingerprint,
    event_payload,
    status_payload,
)


def contract(state, statuses=None):
    statuses = statuses or []
    criteria = []
    for index, item in enumerate(statuses, 1):
        criteria.append(
            {
                "criterion_id": item["id"],
                "description": item.get("description", item["id"]),
                "weight": 1.0,
                "status": item["status"],
                "passed": item.get("passed", False),
                "reason": item.get("reason", item["status"]),
                "check_type": item.get("check_type", "task_state"),
                "task_id": item.get("task_id"),
            }
        )
    return {
        "milestone_id": "DEMO-0.2",
        "state": state,
        "progress_percent": 80.0,
        "integration_sha": "a" * 40,
        "contract_fingerprint": "f" * 64,
        "criteria": criteria,
        "unmet_criterion_ids": [
            item["criterion_id"] for item in criteria if not item["passed"]
        ],
    }


class FinishLoopTests(unittest.TestCase):
    def test_contract_states_map_to_exact_finish_states(self):
        cases = {
            "RUNNABLE": "EXECUTE",
            "WAIT_ACTIVE": "WAIT_ACTIVE",
            "BLOCKED_DEP": "BLOCKED_DEP",
            "BLOCKED_EVIDENCE": "BLOCKED_EVIDENCE",
            "BLOCKED_EXTERNAL": "BLOCKED_EXTERNAL",
        }
        for contract_state, wanted in cases.items():
            with self.subTest(contract_state=contract_state):
                decision = decide(
                    contract(contract_state),
                    certificate_valid=False,
                )
                self.assertEqual(wanted, decision.state)

    def test_complete_requires_current_certificate(self):
        pending = decide(contract("COMPLETE"), certificate_valid=False)
        done = decide(contract("COMPLETE"), certificate_valid=True)
        self.assertEqual("CERTIFY", pending.state)
        self.assertEqual("COMPLETE", done.state)
        self.assertEqual("goal-certifier", action_for(pending))
        self.assertIsNone(action_for(done))

    def test_execute_invokes_exactly_one_authority(self):
        decision = decide(
            contract(
                "RUNNABLE",
                [
                    {
                        "id": "gap",
                        "status": "EXECUTABLE",
                        "reason": "explicit template available",
                    }
                ],
            ),
            certificate_valid=False,
        )
        calls = []

        def runner(action, milestone):
            calls.append((action, milestone))
            return {"action": action}

        result = apply_decision(decision, runner)
        self.assertEqual({"action": "goal-executor"}, result)
        self.assertEqual(
            [("goal-executor", "DEMO-0.2")],
            calls,
        )

    def test_non_action_states_never_invoke_authority(self):
        for state in (
            "WAIT_ACTIVE",
            "BLOCKED_DEP",
            "BLOCKED_EVIDENCE",
            "BLOCKED_EXTERNAL",
        ):
            with self.subTest(state=state):
                decision = decide(contract(state), certificate_valid=False)
                calls = []
                result = apply_decision(
                    decision,
                    lambda action, milestone: calls.append((action, milestone)),
                )
                self.assertIsNone(result)
                self.assertEqual([], calls)

    def test_blocked_event_is_reasoned_and_idempotent(self):
        raw = contract(
            "BLOCKED_EXTERNAL",
            [
                {
                    "id": "global-evidence",
                    "status": "BLOCKED_EVIDENCE",
                    "reason": "bounded research exhausted",
                    "task_id": "G17-TUT-001",
                },
                {
                    "id": "device-proof",
                    "status": "BLOCKED_EXTERNAL",
                    "reason": "real Android device required",
                    "task_id": "ANDROID-VISUAL-QA-001",
                },
            ],
        )
        first = decide(raw, certificate_valid=False)
        second = decide(raw, certificate_valid=False)
        event1 = event_payload(first)
        event2 = event_payload(second)
        self.assertEqual(event1, event2)
        self.assertIn("global-evidence", event1["body"])
        self.assertIn("device-proof", event1["body"])
        self.assertTrue(event1["dedupe"].startswith("finish-loop:DEMO-0.2:"))
        self.assertEqual(
            decision_fingerprint(first),
            decision_fingerprint(second),
        )

    def test_integration_sha_does_not_spam_blocked_event(self):
        raw = contract(
            "BLOCKED_EVIDENCE",
            [
                {
                    "id": "evidence",
                    "status": "BLOCKED_EVIDENCE",
                    "reason": "new primary evidence required",
                }
            ],
        )
        first = decide(raw, certificate_valid=False)
        raw["integration_sha"] = "b" * 40
        second = decide(raw, certificate_valid=False)
        self.assertEqual(
            event_payload(first)["dedupe"],
            event_payload(second)["dedupe"],
        )

    def test_certificate_states_are_sha_sensitive(self):
        first = decide(contract("COMPLETE"), certificate_valid=False)
        changed = contract("COMPLETE")
        changed["integration_sha"] = "b" * 40
        second = decide(changed, certificate_valid=False)
        self.assertNotEqual(
            decision_fingerprint(first),
            decision_fingerprint(second),
        )

    def test_status_surface_answers_work_remaining_blocker_and_completion(self):
        decision = decide(
            contract(
                "WAIT_ACTIVE",
                [
                    {
                        "id": "active-gap",
                        "status": "ACTIVE",
                        "reason": "worker is active",
                        "task_id": "TASK-A",
                    },
                    {
                        "id": "blocked-gap",
                        "status": "BLOCKED_DEP",
                        "reason": "waiting on canonical dependency",
                        "task_id": "TASK-B",
                    },
                ],
            ),
            certificate_valid=False,
        )
        payload = status_payload(decision)
        self.assertEqual(["TASK-A"], payload["working"])
        self.assertEqual(
            ["active-gap", "blocked-gap"],
            payload["remaining"],
        )
        self.assertEqual(
            ["blocked-gap: waiting on canonical dependency"],
            payload["why_blocked"],
        )
        self.assertFalse(payload["certifiably_complete"])

    def test_certifiably_complete_requires_complete_state_and_valid_certificate(self):
        decision = decide(contract("COMPLETE"), certificate_valid=True)
        payload = status_payload(decision)
        self.assertTrue(payload["certifiably_complete"])
        self.assertEqual([], payload["remaining"])

    def test_active_milestone_uses_sort_order_and_ignores_terminal(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            """create table milestones(
                 id text primary key,
                 sort_order integer not null,
                 status text not null
               )"""
        )
        conn.executemany(
            "insert into milestones values(?,?,?)",
            [
                ("DONE-ONE", 1, "DONE"),
                ("LATER", 30, "ACTIVE"),
                ("FIRST", 20, "ACTIVE"),
            ],
        )
        self.assertEqual("FIRST", active_milestone_id(conn))

    def test_completed_milestone_is_stable_fallback(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            """create table milestones(
                 id text primary key,
                 sort_order integer not null,
                 status text not null
               )"""
        )
        conn.executemany(
            "insert into milestones values(?,?,?)",
            [
                ("OLD", 10, "DONE"),
                ("LATEST", 20, "DONE"),
            ],
        )
        self.assertEqual("LATEST", active_milestone_id(conn))

    def test_missing_milestones_fail_closed(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            """create table milestones(
                 id text primary key,
                 sort_order integer not null,
                 status text not null
               )"""
        )
        with self.assertRaisesRegex(ValueError, "no active or completed milestone"):
            active_milestone_id(conn)

    def test_blocker_post_uses_reserved_brain_sender(self):
        script = (
            TEST_DIR.parent / "bin" / "logres-finish-loop"
        ).read_text()
        self.assertIn(
            '"post",\n            "brain",\n            "ALL",',
            script,
        )
        self.assertNotIn(
            '"post",\n            "finish-loop",\n            "ALL",',
            script,
        )

    def test_autopilot_delegates_goal_authority_to_finish_loop(self):
        script = (
            TEST_DIR.parent / "bin" / "logres-autopilot-watch"
        ).read_text()
        self.assertIn(
            '"/home/ubuntu/logres/bin/logres-finish-loop","cycle","--apply","--json"',
            script,
        )
        self.assertNotIn(
            '"/home/ubuntu/logres/bin/logres-goal-executor","DEMO-0.2","--apply"',
            script,
        )

    def test_invalid_contract_state_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unsupported contract state"):
            decide(contract("MYSTERY"), certificate_valid=False)


if __name__ == "__main__":
    unittest.main()
