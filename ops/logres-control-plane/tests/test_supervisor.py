import json
import os
import signal
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
    actionable_integration_backlog,
    actionable_worker_backlog,
    background_lane_busy,
    default_jobs,
    direct_child_pids,
    due,
    ensure_running,
    launch_background_job,
    refresh_background_run,
    reload_if_idle,
    should_run_job,
    supervisor_health,
    tick,
)


class FakePopen:
    def __init__(self, pid=4321):
        self.pid = pid
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return types.SimpleNamespace(pid=self.pid)


class SupervisorTests(unittest.TestCase):
    def test_default_jobs_cover_authoritative_and_maintenance_loops(self):
        jobs = {job.name: job for job in default_jobs(Path("/x"))}
        names = set(jobs)
        self.assertTrue(
            {
                "autonomy",
                "swarm",
                "autopilot",
                "lead_snapshot",
                "code_index",
                "sync_health",
                "health_snapshot",
                "control_backup",
                "evidence_refresh",
                "preview_reaper",
                "governor_propose",
                "shadow_experiment",
                "chaos_cert",
                "maintenance",
            }.issubset(names)
        )
        self.assertTrue(jobs["autonomy"].background)
        self.assertEqual("autonomy", jobs["autonomy"].background_group)
        for name in ("autopilot", "lead_snapshot", "health_snapshot", "maintenance"):
            self.assertTrue(jobs[name].background, name)
            self.assertEqual("maintenance", jobs[name].background_group)
        for name in ("governor_propose", "shadow_experiment", "chaos_cert"):
            self.assertTrue(jobs[name].background, name)
            self.assertEqual("governor", jobs[name].background_group)
        self.assertIn("--shadow-only", jobs["governor_propose"].argv)
        self.assertEqual("next", jobs["shadow_experiment"].argv[-1])
        self.assertIn("--shadow", jobs["chaos_cert"].argv)
        self.assertIn("--quiet", jobs["chaos_cert"].argv)
        for name in (
            "swarm",
            "code_index",
            "sync_health",
            "control_backup",
            "evidence_refresh",
            "preview_reaper",
        ):
            self.assertFalse(jobs[name].background, name)

    def test_due_respects_interval(self):
        job = ScheduledJob("x", ("true",), 60, 10)
        self.assertTrue(due(job, {}, 100.0))
        state = {"last_runs": {"x": {"finished_epoch": 70.0}}}
        self.assertFalse(due(job, state, 100.0))
        self.assertTrue(due(job, state, 131.0))

    def test_ready_integration_backlog_wakes_autonomy_early_only(self):
        state = {
            "last_runs": {
                "autonomy": {"finished_epoch": 90.0},
                "swarm": {"finished_epoch": 90.0},
            }
        }
        autonomy = ScheduledJob("autonomy", ("true",), 60, 10)
        swarm = ScheduledJob("swarm", ("true",), 60, 10)
        self.assertTrue(
            should_run_job(
                autonomy,
                state,
                101.0,
                integration_backlog=1,
            )
        )
        self.assertFalse(
            should_run_job(
                swarm,
                state,
                101.0,
                integration_backlog=1,
            )
        )

    def test_ready_worker_backlog_wakes_swarm_early_only(self):
        state = {
            "last_runs": {
                "autonomy": {"finished_epoch": 90.0},
                "swarm": {"finished_epoch": 90.0},
                "code_index": {"finished_epoch": 90.0},
            }
        }
        autonomy = ScheduledJob("autonomy", ("true",), 60, 10)
        swarm = ScheduledJob("swarm", ("true",), 60, 10)
        code_index = ScheduledJob("code_index", ("true",), 60, 10)
        self.assertTrue(
            should_run_job(
                swarm,
                state,
                101.0,
                integration_backlog=0,
                worker_backlog=1,
            )
        )
        self.assertFalse(
            should_run_job(
                autonomy,
                state,
                101.0,
                integration_backlog=0,
                worker_backlog=1,
            )
        )
        self.assertFalse(
            should_run_job(
                code_index,
                state,
                101.0,
                integration_backlog=0,
                worker_backlog=1,
            )
        )

    def test_no_backlog_preserves_fixed_interval(self):
        state = {"last_runs": {"autonomy": {"finished_epoch": 90.0}}}
        autonomy = ScheduledJob("autonomy", ("true",), 60, 10)
        self.assertFalse(
            should_run_job(
                autonomy,
                state,
                101.0,
                integration_backlog=0,
            )
        )
        self.assertTrue(
            should_run_job(
                autonomy,
                state,
                151.0,
                integration_backlog=0,
            )
        )

    def test_actionable_backlog_reads_ready_for_preflight_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            control = root / "control"
            control.mkdir()
            db = control / "control.sqlite"
            import sqlite3

            conn = sqlite3.connect(db)
            conn.execute(
                "create table integration_queue("
                "task_id text, status text)"
            )
            conn.executemany(
                "insert into integration_queue values(?,?)",
                [
                    ("A", "READY_FOR_PREFLIGHT"),
                    ("B", "INTEGRATED"),
                    ("C", "SUPERSEDED"),
                ],
            )
            conn.commit()
            conn.close()
            self.assertEqual(1, actionable_integration_backlog(root))

    def test_actionable_worker_backlog_reads_ready_tasks_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            control = root / "control"
            control.mkdir()
            db = control / "control.sqlite"
            import sqlite3

            conn = sqlite3.connect(db)
            conn.execute("create table tasks(id text, status text)")
            conn.executemany(
                "insert into tasks values(?,?)",
                [
                    ("A", "READY"),
                    ("B", "ACTIVE"),
                    ("C", "BLOCKED_DEP"),
                    ("D", "DONE"),
                ],
            )
            conn.commit()
            conn.close()
            self.assertEqual(1, actionable_worker_backlog(root))

    def test_tick_wakes_swarm_early_for_ready_work(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            heartbeat = root / "heartbeat.json"
            heartbeat.write_text(
                json.dumps(
                    {
                        "last_runs": {
                            "swarm": {
                                "finished_epoch": 90.0,
                                "finished_at": "x",
                                "rc": 0,
                            }
                        }
                    }
                )
            )
            swarm = ScheduledJob("swarm", ("swarm", "tick"), 60, 10)
            calls = []

            def runner(argv, **kwargs):
                calls.append(list(argv))
                return subprocess.CompletedProcess(argv, 0, "ok", "")

            result = tick(
                root,
                heartbeat,
                jobs=(swarm,),
                runner=runner,
                now_epoch=101.0,
                integration_backlog=0,
                worker_backlog=1,
            )
            self.assertEqual(["swarm"], result["ran"])
            self.assertEqual([["swarm", "tick"]], calls)

    def test_background_launch_records_tracked_pid(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            job = ScheduledJob(
                "autonomy",
                ("autonomy", "cycle"),
                60,
                240,
                True,
            )
            popen = FakePopen(pid=777)
            state = launch_background_job(
                root,
                job,
                popen=popen,
                now_epoch=100.0,
            )
            self.assertTrue(state["running"])
            self.assertEqual(777, state["pid"])
            self.assertEqual(100.0, state["started_epoch"])
            self.assertIsNone(state["finished_epoch"])
            self.assertEqual(1, len(popen.calls))

    def test_background_autonomy_does_not_block_foreground_swarm(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            heartbeat = root / "heartbeat.json"
            autonomy = ScheduledJob(
                "autonomy",
                ("autonomy", "cycle"),
                60,
                240,
                True,
            )
            swarm = ScheduledJob("swarm", ("swarm", "tick"), 60, 10)
            popen = FakePopen(pid=778)
            calls = []

            def runner(argv, **kwargs):
                calls.append(list(argv))
                return subprocess.CompletedProcess(argv, 0, "ok", "")

            result = tick(
                root,
                heartbeat,
                jobs=(autonomy, swarm),
                runner=runner,
                popen=popen,
                now_epoch=100.0,
                integration_backlog=1,
            )

            self.assertEqual(["autonomy", "swarm"], result["ran"])
            self.assertTrue(
                result["state"]["last_runs"]["autonomy"]["running"]
            )
            self.assertEqual(
                0,
                result["state"]["last_runs"]["swarm"]["rc"],
            )
            self.assertEqual([["swarm", "tick"]], calls)
            self.assertEqual(1, len(popen.calls))

    def test_housekeeping_lane_serializes_without_blocking_foreground(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            heartbeat = root / "heartbeat.json"
            autonomy = ScheduledJob(
                "autonomy",
                ("autonomy", "cycle"),
                60,
                240,
                True,
                "autonomy",
            )
            first = ScheduledJob(
                "health_snapshot",
                ("health",),
                600,
                120,
                True,
                "maintenance",
            )
            second = ScheduledJob(
                "maintenance",
                ("maintain",),
                3600,
                1200,
                True,
                "maintenance",
            )
            quick = ScheduledJob("swarm", ("swarm", "tick"), 60, 10)
            popen = FakePopen(pid=790)
            foreground = []

            def runner(argv, **kwargs):
                foreground.append(list(argv))
                return subprocess.CompletedProcess(argv, 0, "ok", "")

            first_tick = tick(
                root,
                heartbeat,
                jobs=(autonomy, first, second, quick),
                runner=runner,
                popen=popen,
                now_epoch=100.0,
                integration_backlog=1,
            )
            self.assertEqual(
                ["autonomy", "health_snapshot", "swarm"],
                first_tick["ran"],
            )
            self.assertEqual([["swarm", "tick"]], foreground)
            self.assertEqual(2, len(popen.calls))
            self.assertTrue(
                background_lane_busy(
                    second,
                    (autonomy, first, second, quick),
                    first_tick["state"],
                )
            )

            def not_our_child(_pid, _flags):
                raise ChildProcessError

            second_tick = tick(
                root,
                heartbeat,
                jobs=(autonomy, first, second, quick),
                runner=runner,
                popen=popen,
                waitpid_fn=not_our_child,
                pid_alive_fn=lambda _pid: True,
                now_epoch=101.0,
                integration_backlog=1,
            )
            self.assertEqual([], second_tick["ran"])
            self.assertEqual(2, len(popen.calls))

            third_tick = tick(
                root,
                heartbeat,
                jobs=(autonomy, first, second, quick),
                runner=runner,
                popen=popen,
                waitpid_fn=lambda pid, _flags: (pid, 0),
                now_epoch=120.0,
                integration_backlog=0,
            )
            self.assertEqual(["maintenance"], third_tick["ran"])
            self.assertEqual(3, len(popen.calls))

    def test_running_background_autonomy_is_not_relaunched_after_restart(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            heartbeat = root / "heartbeat.json"
            heartbeat.write_text(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "updated_epoch": 100.0,
                        "last_runs": {
                            "autonomy": {
                                "argv": ["autonomy", "cycle"],
                                "pid": 779,
                                "running": True,
                                "started_epoch": 90.0,
                                "timeout_seconds": 240,
                            }
                        },
                    }
                )
            )
            autonomy = ScheduledJob(
                "autonomy",
                ("autonomy", "cycle"),
                60,
                240,
                True,
            )
            popen = FakePopen(pid=780)

            def not_our_child(_pid, _flags):
                raise ChildProcessError

            result = tick(
                root,
                heartbeat,
                jobs=(autonomy,),
                popen=popen,
                waitpid_fn=not_our_child,
                pid_alive_fn=lambda _pid: True,
                now_epoch=110.0,
                integration_backlog=1,
            )

            self.assertEqual([], result["ran"])
            self.assertTrue(
                result["state"]["last_runs"]["autonomy"]["running"]
            )
            self.assertEqual([], popen.calls)

    def test_background_completion_is_reaped(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            job = ScheduledJob(
                "autonomy",
                ("autonomy", "cycle"),
                60,
                240,
                True,
            )
            state = {
                "pid": 781,
                "running": True,
                "started_epoch": 100.0,
                "timeout_seconds": 240,
            }
            result = refresh_background_run(
                root,
                job,
                state,
                now_epoch=120.0,
                waitpid_fn=lambda pid, flags: (pid, 0),
            )
            self.assertFalse(result["running"])
            self.assertEqual(0, result["rc"])
            self.assertEqual(20.0, result["duration_seconds"])
            self.assertEqual(120.0, result["finished_epoch"])

    def test_background_timeout_escalates_term_then_kill(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            job = ScheduledJob(
                "autonomy",
                ("autonomy", "cycle"),
                60,
                10,
                True,
            )
            state = {
                "pid": 782,
                "running": True,
                "started_epoch": 100.0,
                "timeout_seconds": 10,
                "terminate_sent_epoch": None,
                "kill_sent_epoch": None,
            }
            signals = []

            first = refresh_background_run(
                root,
                job,
                state,
                now_epoch=111.0,
                waitpid_fn=lambda _pid, _flags: (0, 0),
                killpg_fn=lambda pid, sig: signals.append((pid, sig)),
            )
            self.assertEqual([(782, signal.SIGTERM)], signals)
            self.assertEqual(111.0, first["terminate_sent_epoch"])
            self.assertIsNone(first["kill_sent_epoch"])

            second = refresh_background_run(
                root,
                job,
                first,
                now_epoch=122.0,
                waitpid_fn=lambda _pid, _flags: (0, 0),
                killpg_fn=lambda pid, sig: signals.append((pid, sig)),
            )
            self.assertEqual(
                [
                    (782, signal.SIGTERM),
                    (782, signal.SIGKILL),
                ],
                signals,
            )
            self.assertEqual(122.0, second["kill_sent_epoch"])

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

    def test_background_autonomy_does_not_block_foreground_jobs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            heartbeat = root / "heartbeat.json"
            popen = FakePopen(pid=7001)
            foreground_calls = []

            def runner(argv, **kwargs):
                foreground_calls.append(list(argv))
                return subprocess.CompletedProcess(argv, 0, "ok", "")

            autonomy = ScheduledJob(
                "autonomy",
                ("autonomy",),
                60,
                240,
                True,
            )
            swarm = ScheduledJob("swarm", ("swarm",), 60, 10)

            result = tick(
                root,
                heartbeat,
                jobs=(autonomy, swarm),
                runner=runner,
                popen=popen,
                now_epoch=100.0,
                integration_backlog=1,
            )

            self.assertEqual(["autonomy", "swarm"], result["ran"])
            self.assertEqual(1, len(popen.calls))
            self.assertEqual([["swarm"]], foreground_calls)
            self.assertTrue(
                result["state"]["last_runs"]["autonomy"]["running"]
            )
            self.assertEqual(
                0,
                result["state"]["last_runs"]["swarm"]["rc"],
            )

    def test_running_background_autonomy_is_not_relaunched(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            heartbeat = root / "heartbeat.json"
            heartbeat.write_text(
                json.dumps(
                    {
                        "last_runs": {
                            "autonomy": {
                                "pid": 7001,
                                "running": True,
                                "started_epoch": 100.0,
                                "timeout_seconds": 240,
                            }
                        }
                    }
                )
            )
            popen = FakePopen(pid=7002)
            autonomy = ScheduledJob(
                "autonomy",
                ("autonomy",),
                60,
                240,
                True,
            )

            result = tick(
                root,
                heartbeat,
                jobs=(autonomy,),
                popen=popen,
                waitpid_fn=lambda pid, flags: (0, 0),
                now_epoch=120.0,
                integration_backlog=1,
            )

            self.assertEqual([], result["ran"])
            self.assertEqual([], popen.calls)
            self.assertTrue(
                result["state"]["last_runs"]["autonomy"]["running"]
            )

    def test_background_completion_is_reaped_with_rc_and_duration(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            heartbeat = root / "heartbeat.json"
            heartbeat.write_text(
                json.dumps(
                    {
                        "last_runs": {
                            "autonomy": {
                                "pid": 7001,
                                "running": True,
                                "started_epoch": 100.0,
                                "timeout_seconds": 240,
                            }
                        }
                    }
                )
            )
            autonomy = ScheduledJob(
                "autonomy",
                ("autonomy",),
                60,
                240,
                True,
            )

            result = tick(
                root,
                heartbeat,
                jobs=(autonomy,),
                waitpid_fn=lambda pid, flags: (pid, 0),
                now_epoch=130.0,
                integration_backlog=0,
            )

            run = result["state"]["last_runs"]["autonomy"]
            self.assertFalse(run["running"])
            self.assertEqual(0, run["rc"])
            self.assertEqual(30.0, run["duration_seconds"])
            self.assertEqual([], result["ran"])

    def test_background_timeout_escalates_term_then_kill(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            job = ScheduledJob(
                "autonomy",
                ("autonomy",),
                60,
                10,
                True,
            )
            state = {
                "pid": 7001,
                "running": True,
                "started_epoch": 100.0,
                "timeout_seconds": 10,
            }
            signals = []

            first = refresh_background_run(
                root,
                job,
                state,
                now_epoch=111.0,
                waitpid_fn=lambda pid, flags: (0, 0),
                killpg_fn=lambda pid, sig: signals.append((pid, sig)),
            )
            self.assertEqual([(7001, signal.SIGTERM)], signals)
            self.assertEqual(111.0, first["terminate_sent_epoch"])
            self.assertTrue(first["running"])

            second = refresh_background_run(
                root,
                job,
                first,
                now_epoch=122.0,
                waitpid_fn=lambda pid, flags: (0, 0),
                killpg_fn=lambda pid, sig: signals.append((pid, sig)),
            )
            self.assertEqual(
                [
                    (7001, signal.SIGTERM),
                    (7001, signal.SIGKILL),
                ],
                signals,
            )
            self.assertEqual(122.0, second["kill_sent_epoch"])
            self.assertTrue(second["running"])

    def test_restart_with_live_inherited_pid_does_not_duplicate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            heartbeat = root / "heartbeat.json"
            heartbeat.write_text(
                json.dumps(
                    {
                        "last_runs": {
                            "autonomy": {
                                "pid": 7001,
                                "running": True,
                                "started_epoch": 100.0,
                                "timeout_seconds": 240,
                            }
                        }
                    }
                )
            )
            popen = FakePopen(pid=7002)
            autonomy = ScheduledJob(
                "autonomy",
                ("autonomy",),
                60,
                240,
                True,
            )

            def inherited_waitpid(pid, flags):
                raise ChildProcessError()

            result = tick(
                root,
                heartbeat,
                jobs=(autonomy,),
                popen=popen,
                waitpid_fn=inherited_waitpid,
                pid_alive_fn=lambda pid: True,
                now_epoch=120.0,
                integration_backlog=1,
            )

            self.assertEqual([], result["ran"])
            self.assertEqual([], popen.calls)
            self.assertTrue(
                result["state"]["last_runs"]["autonomy"]["running"]
            )

    def test_direct_child_pids_reads_proc_status(self):
        with tempfile.TemporaryDirectory() as td:
            proc = Path(td)
            for pid, parent in ((101, 42), (102, 42), (103, 7)):
                entry = proc / str(pid)
                entry.mkdir()
                (entry / "status").write_text(
                    f"Name:\ttest\nPid:\t{pid}\nPPid:\t{parent}\n"
                )
            self.assertEqual(
                (101, 102),
                direct_child_pids(42, proc_root=proc),
            )

    def test_reload_if_idle_defers_when_supervisor_has_child(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            heartbeat = root / "heartbeat.json"
            heartbeat.write_text(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "updated_epoch": time.time(),
                        "updated_at": "now",
                    }
                )
            )
            result = reload_if_idle(
                root,
                root / "logres-supervisor",
                heartbeat,
                child_pids_fn=lambda pid: (7001,),
                kill_fn=lambda pid, sig: self.fail("must not signal busy supervisor"),
            )
            self.assertEqual("deferred", result["reload"])
            self.assertEqual([7001], result["children"])
            self.assertTrue(result["healthy"])

    def test_reload_if_idle_replaces_idle_supervisor(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            heartbeat = root / "heartbeat.json"
            old_pid = os.getpid()
            heartbeat.write_text(
                json.dumps(
                    {
                        "pid": old_pid,
                        "updated_epoch": time.time(),
                        "updated_at": "now",
                    }
                )
            )
            signals = []

            def fake_ensure(root, executable, heartbeat_path, **kwargs):
                return {
                    "started": True,
                    "healthy": True,
                    "pid": 9001,
                    "alive": True,
                }

            result = reload_if_idle(
                root,
                root / "logres-supervisor",
                heartbeat,
                child_pids_fn=lambda pid: (),
                kill_fn=lambda pid, sig: signals.append((pid, sig)),
                alive_fn=lambda pid: False,
                ensure_fn=fake_ensure,
            )
            self.assertEqual([(old_pid, signal.SIGTERM)], signals)
            self.assertEqual("reloaded", result["reload"])
            self.assertEqual(9001, result["new_pid"])
            self.assertTrue(result["healthy"])

    def test_reload_if_idle_is_idempotent_after_replacement(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            heartbeat = root / "heartbeat.json"
            heartbeat.write_text(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "updated_epoch": time.time(),
                        "updated_at": "now",
                    }
                )
            )
            result = reload_if_idle(
                root,
                root / "logres-supervisor",
                heartbeat,
                expected_pid=12345,
            )
            self.assertEqual("already-replaced", result["reload"])
            self.assertEqual(os.getpid(), result["new_pid"])
            self.assertTrue(result["healthy"])

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
