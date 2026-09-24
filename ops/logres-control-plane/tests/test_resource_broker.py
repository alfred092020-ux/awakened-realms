import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db, seed_task
from logres_resource_broker import (
    choose_remote_role,
    infer_task_workload,
    plan_workload,
    remote_observations,
    score_remote_lanes,
    summarize_remote_history,
)


def health(role, *, slots, max_slots, cpu, memory_gib=8):
    return {
        "role": role,
        "reachable": True,
        "active_workers": max_slots - slots,
        "available_slots": slots,
        "max_slots": max_slots,
        "cpu_count": cpu,
        "memory_available_bytes": memory_gib * 1024**3,
    }


def write_result(root, job, role, *, script, duration, ok=True):
    path = root / job / role / "pool-result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": 1,
                "role": role,
                "status": "success" if ok else "failed",
                "exit_code": 0 if ok else 1,
                "duration_seconds": duration,
                "npm_script": script,
            }
        )
    )


class ResourceBrokerTests(unittest.TestCase):
    def test_script_specific_history_beats_legacy_role_prior(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_result(root, "build-1", "heavy", script="build", duration=2)
            write_result(root, "test-1", "heavy", script="test", duration=40)
            write_result(root, "test-2", "light", script="test", duration=12)

            rows = [
                health("heavy", slots=2, max_slots=2, cpu=8),
                health("light", slots=1, max_slots=1, cpu=4),
            ]
            role = choose_remote_role(rows, root, npm_script="test")

            self.assertEqual("light", role)
            scored = score_remote_lanes(rows, root, npm_script="test")
            self.assertEqual("remote-light", scored[0].lane)
            self.assertEqual(12.0, scored[0].median_seconds)

    def test_capacity_can_override_small_speed_advantage(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_result(root, "test-h", "heavy", script="test", duration=9)
            write_result(root, "test-l", "light", script="test", duration=10)
            rows = [
                health("heavy", slots=1, max_slots=2, cpu=8),
                health("light", slots=1, max_slots=1, cpu=4),
            ]

            role = choose_remote_role(rows, root, npm_script="test")

            self.assertIn(role, {"heavy", "light"})
            self.assertTrue(
                any(
                    "slots=" in item
                    for lane in score_remote_lanes(rows, root, npm_script="test")
                    for item in lane.rationale
                )
            )

    def test_unreachable_or_full_workers_are_ineligible(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            rows = [
                {
                    **health("heavy", slots=0, max_slots=2, cpu=8),
                    "reachable": True,
                },
                {
                    **health("light", slots=1, max_slots=1, cpu=4),
                    "reachable": False,
                },
            ]

            with self.assertRaises(RuntimeError):
                choose_remote_role(rows, root, npm_script="test")

    def test_private_work_is_forced_local(self):
        plan = plan_workload(
            workload="research",
            sensitivity="local_only",
            openai_allowed=True,
        )

        self.assertEqual("local", plan.selected_lane)
        openai = next(l for l in plan.lanes if l.lane == "openai")
        self.assertFalse(openai.eligible)

    def test_research_and_code_use_specialist_lanes_when_safe(self):
        research = plan_workload(workload="research")
        code = plan_workload(workload="implementation")

        self.assertEqual("openai", research.selected_lane)
        self.assertEqual("copilot", code.selected_lane)

    def test_task_inference_preserves_private_evidence_policy(self):
        conn = make_test_db()
        seed_task(
            conn,
            task_id="R1",
            work_type="research",
            evidence_policy="Private Global evidence; local only",
        )

        work_type, sensitivity = infer_task_workload(conn, "R1")

        self.assertEqual("research", work_type)
        self.assertEqual("local_only", sensitivity)

    def test_history_summary_uses_only_matching_script_records(self):
        rows = [
            {
                "status": "success",
                "exit_code": 0,
                "duration_seconds": 10,
                "npm_script": "test",
            },
            {
                "status": "success",
                "exit_code": 0,
                "duration_seconds": 100,
                "_legacy_script_unknown": True,
            },
        ]

        summary = summarize_remote_history(rows)

        self.assertEqual(1, summary["count"])
        self.assertEqual(10, summary["median_seconds"])

    def test_observation_reader_keeps_legacy_as_weak_prior(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "legacy" / "heavy" / "pool-result.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "role": "heavy",
                        "status": "success",
                        "exit_code": 0,
                        "duration_seconds": 5,
                    }
                )
            )

            rows = remote_observations(root, npm_script="test")

            self.assertTrue(rows["heavy"][0]["_legacy_script_unknown"])


if __name__ == "__main__":
    unittest.main()
