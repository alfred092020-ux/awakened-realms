import json
import os
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_supervisor import (
    ScheduledJob,
    default_jobs,
    due,
    ensure_running,
    supervisor_health,
    tick,
)


class FakePopen:
    def __init__(self, pid=4321):
        self.pid = pid

    def __call__(self, *args, **kwargs):
        return types.SimpleNamespace(pid=self.pid)


class SupervisorTests(unittest.TestCase):
    def test_default_jobs_cover_authoritative_and_maintenance_loops(self):
        names = {job.name for job in default_jobs(Path("/x"))}
        self.assertTrue(
            {
                "autonomy",
                "swarm",
                "autopilot",
                "lead_snapshot",
                "health_snapshot",
                "control_backup",
                "evidence_refresh",
                "preview_reaper",
                "maintenance",
            }.issubset(names)
        )

    def test_due_respects_interval(self):
        job = ScheduledJob("x", ("true",), 60, 10)
        self.assertTrue(due(job, {}, 100.0))
        state = {"last_runs": {"x": {"finished_epoch": 70.0}}}
        self.assertFalse(due(job, state, 100.0))
        self.assertTrue(due(job, state, 131.0))

    def test_tick_records_job_result_and_does_not_immediately_repeat(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            heartbeat = root / "heartbeat.json"
            job = ScheduledJob("probe", ("probe",), 60, 5)
            calls = []

            def runner(argv, **kwargs):
                calls.append(list(argv))
                return subprocess.CompletedProcess(argv, 0, "ok", "")

            first = tick(
                root,
                heartbeat,
                jobs=(job,),
                runner=runner,
                now_epoch=100.0,
            )
            second = tick(
                root,
                heartbeat,
                jobs=(job,),
                runner=runner,
                now_epoch=101.0,
            )

            self.assertEqual(["probe"], first["ran"])
            self.assertEqual([], second["ran"])
            self.assertEqual([["probe"]], calls)
            saved = json.loads(heartbeat.read_text())
            self.assertEqual(0, saved["last_runs"]["probe"]["rc"])

    def test_healthy_existing_supervisor_is_not_duplicated(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            heartbeat = root / "heartbeat.json"
            heartbeat.write_text(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "updated_epoch": time.time(),
                        "updated_at": "x",
                        "started_at": "x",
                        "last_runs": {},
                    }
                )
            )
            popen = FakePopen()
            result = ensure_running(
                root,
                root / "logres-supervisor",
                heartbeat,
                max_age_seconds=900,
                popen=popen,
            )
            self.assertFalse(result["started"])
            self.assertTrue(result["alive"])
            self.assertTrue(result["healthy"])

    def test_missing_supervisor_is_spawned_detached(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            heartbeat = root / "heartbeat.json"
            popen = FakePopen(pid=9876)

            result = ensure_running(
                root,
                root / "logres-supervisor",
                heartbeat,
                popen=popen,
            )

            self.assertTrue(result["started"])
            self.assertEqual(9876, result["pid"])
            self.assertTrue(result["healthy"])

    def test_health_requires_live_pid_and_fresh_heartbeat(self):
        with tempfile.TemporaryDirectory() as td:
            heartbeat = Path(td) / "heartbeat.json"
            heartbeat.write_text(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "updated_epoch": 100.0,
                        "updated_at": "x",
                    }
                )
            )
            healthy = supervisor_health(
                heartbeat,
                now_epoch=150.0,
                max_age_seconds=100,
            )
            stale = supervisor_health(
                heartbeat,
                now_epoch=250.0,
                max_age_seconds=100,
            )
            self.assertTrue(healthy["healthy"])
            self.assertFalse(stale["healthy"])


if __name__ == "__main__":
    unittest.main()
