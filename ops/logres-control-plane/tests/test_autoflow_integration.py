import hashlib
import sqlite3
import importlib.machinery
import importlib.util
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db, seed_event, seed_task, test_config
from logres_ai_router import run_ai_cycle
from logres_ai_runner import automatic_api_allowed, budget_state
from logres_copilot_router import (
    PolicyError,
    _set_copilot_job_state,
    copilot_eligibility,
    dispatch_task,
    reconcile_copilot_job,
)
from logres_reconcile import backpressure
from logres_route_store import ensure_route_schema, transition_route


def load_control_script(name: str, filename: str):
    path = TEST_DIR.parent / "bin" / filename
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


coordinator = load_control_script("logres_coordinator_autoflow_test", "logres-coordinator")



def ensure_coordinator_runtime_tables(conn):
    conn.execute(
        "create table if not exists brain_members(chat_id text primary key,status text,last_seen_epoch real)"
    )
    conn.execute(
        "create table if not exists task_recovery(task_id text,status text)"
    )
    conn.commit()


class AutoflowDefaultConfigTests(unittest.TestCase):
    def test_autonomous_default_keeps_bounded_copilot_lane_available(self):
        config_path = TEST_DIR.parent / "config" / "autoflow.default.json"
        config = __import__("json").loads(config_path.read_text(encoding="utf-8"))
        self.assertTrue(config["routing"]["copilot_dispatch_enabled"])
        self.assertEqual(
            "bounded_implementation",
            config["routing"]["copilot_mode"],
        )
        self.assertGreaterEqual(int(config["copilot"]["max_active"]), 1)
        self.assertGreaterEqual(int(config["copilot"]["max_queued"]), 1)


class FakeAIRunner:
    def __init__(self, result):
        self.calls = 0
        self.result = result

    def run(self, **kwargs):
        self.calls += 1
        return {
            "cached": False,
            "model": "gpt-5-mini",
            "artifact_sha": kwargs["artifact_sha"],
            "result": self.result,
            "usage": None,
            "ai_run_id": self.calls,
        }


class FakeBrainRunner:
    def __init__(self):
        self.events = []

    def post(self, **kwargs):
        self.events.append(kwargs)


class FakeGitHub:
    def __init__(self):
        self.issue_create_calls = 0
        self.assignment_calls = 0
        self.list_prs_result = []

    def create_issue(self, repo, title, body):
        self.issue_create_calls += 1
        return 100 + self.issue_create_calls

    def assign_copilot(self, repo, issue_number, payload):
        self.assignment_calls += 1

    def list_prs(self, repo):
        return self.list_prs_result


class PausingGitHub(FakeGitHub):
    def __init__(self):
        super().__init__()
        self.issue_started = threading.Event()
        self.release_issue = threading.Event()

    def create_issue(self, repo, title, body):
        self.issue_started.set()
        if not self.release_issue.wait(2):
            raise RuntimeError("timed out waiting to release Copilot issue creation")
        return super().create_issue(repo, title, body)


class FakeCommandRunner:
    def __init__(self):
        self.gate_calls = []

    def scope_check(self, task_id, branch):
        return 0

    def fast_gate(self, branch):
        self.gate_calls.append(branch)
        return 0

    def coordinator_reconcile(self, conn, task_id, branch, sha):
        conn.execute(
            "insert into verification(ref,sha,mode,status,duration_sec,ran_at,details) "
            "values(?,?,?,'PASS',0,datetime('now'),'synthetic')",
            (branch, sha, "fast"),
        )
        conn.execute(
            "insert into integration_queue("
            "task_id,sha,branch,status,verification_mode,queued_at,updated_at,note"
            ") values(?,?,?,'READY_FOR_PREFLIGHT','fast',datetime('now'),datetime('now'),'synthetic')",
            (task_id, sha, branch),
        )
        conn.commit()
        return 0

    def capture_regression(self, task_id, branch, sha):
        raise AssertionError("regression capture should not run")

    def post_scope_conflict(self, task_id, branch, sha):
        raise AssertionError("scope conflict should not run")


class AutoflowIntegrationTests(unittest.TestCase):
    def test_synthetic_artifact_routes_once_and_creates_one_research_child(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(
            conn,
            task_id="RE1",
            priority=0,
            status="ACTIVE",
            work_type="research",
            evidence_policy="Global evidence required",
        )

        with tempfile.TemporaryDirectory() as td:
            artifact = Path(td) / "global-native.txt"
            artifact.write_text("Global native trace\n" * 5000)
            artifact_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
            seed_event(
                conn,
                event_id=100,
                task_id="RE1",
                artifact_path=str(artifact),
                artifact_sha=artifact_sha,
                meta={
                    "artifact_bytes": artifact.stat().st_size,
                    "kind": "native_trace",
                    "provenance": "CONFIRMED_GLOBAL_2017",
                },
            )

            fake_ai = FakeAIRunner(
                {
                    "confidence": "UNRESOLVED",
                    "summary": "missing branch",
                    "findings": [],
                    "contradictions": [],
                    "unresolved": ["callback target"],
                    "recommended_next_search": "xref callback",
                }
            )
            config = test_config()
            config["routing"]["ai_dispatch_enabled"] = True
            config["openai"]["auto_model"] = "gpt-5-mini"
            config["openai"]["model_rates_per_million"] = {
                "gpt-5-mini": {
                    "input": 1.0,
                    "cached_input": 0.5,
                    "output": 2.0,
                }
            }
            brain = FakeBrainRunner()

            first = run_ai_cycle(conn, fake_ai, brain, config, limit=10)
            second = run_ai_cycle(conn, fake_ai, brain, config, limit=10)

        self.assertEqual(1, first.created_research_tasks)
        self.assertEqual(0, second.created_research_tasks)
        self.assertEqual(1, fake_ai.calls)
        self.assertEqual(
            1,
            conn.execute(
                "select count(*) from route_jobs where route_kind='AI'"
            ).fetchone()[0],
        )

    def test_synthetic_bounded_copilot_candidate_enters_normal_queue(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(
            conn,
            task_id="IMP1",
            priority=0,
            status="READY",
            work_type="implementation",
            evidence_policy="CONFIRMED ORIGINAL Global evidence required",
            acceptance=("targeted test passes",),
        )
        conn.execute(
            "insert into task_scopes(task_id,path_prefix) values(?,?)",
            ("IMP1", "src/a.ts"),
        )
        conn.commit()

        config = test_config()
        config["routing"]["copilot_dispatch_enabled"] = True
        config["routing"]["copilot_mode"] = "bounded_implementation"
        github = FakeGitHub()

        dispatched = dispatch_task(
            conn,
            "IMP1",
            "b" * 40,
            config,
            github,
        )
        self.assertEqual(1, github.issue_create_calls)
        self.assertEqual(1, github.assignment_calls)

        github.list_prs_result = [
            {
                "number": 9,
                "headRefName": dispatched.branch,
                "headRefOid": "c" * 40,
                "baseRefName": "feat/logres-reconstruction",
                "isDraft": True,
                "body": "Closes #101\nTask ID: IMP1",
            }
        ]
        commands = FakeCommandRunner()
        result = reconcile_copilot_job(
            dispatched.job,
            github,
            commands,
            current_integration_sha="b" * 40,
            conn=conn,
        )

        self.assertEqual("QUEUED", result.state)
        self.assertEqual(1, len(commands.gate_calls))
        self.assertEqual(
            1,
            conn.execute(
                "select count(*) from integration_queue where task_id=? and sha=?",
                ("IMP1", "c" * 40),
            ).fetchone()[0],
        )

    def test_worker_auto_cannot_lease_during_real_copilot_assigning_window(self):
        with tempfile.TemporaryDirectory() as td:
            db_path = str(Path(td) / "copilot-race.sqlite")
            seed = make_test_db(db_path)
            ensure_route_schema(seed)
            seed_task(
                seed,
                task_id="IMP-RACE",
                priority=0,
                status="READY",
                work_type="implementation",
                evidence_policy="CONFIRMED ORIGINAL Global evidence required",
                acceptance=("race guarded",),
            )
            seed.execute(
                "insert into task_scopes(task_id,path_prefix) values(?,?)",
                ("IMP-RACE", "src/race.ts"),
            )
            ensure_coordinator_runtime_tables(seed)
            seed.execute("insert into brain_members values('worker-auto','IDLE',0)")
            seed.commit()
            seed.close()

            config = test_config()
            config["routing"]["copilot_dispatch_enabled"] = True
            config["routing"]["copilot_mode"] = "bounded_implementation"
            github = PausingGitHub()
            dispatch_result = {}

            def run_dispatch():
                conn = sqlite3.connect(db_path, timeout=5)
                conn.row_factory = sqlite3.Row
                try:
                    dispatch_result["result"] = dispatch_task(
                        conn, "IMP-RACE", "b" * 40, config, github
                    )
                except Exception as exc:  # pragma: no cover - asserted below
                    dispatch_result["error"] = exc
                finally:
                    conn.close()

            thread = threading.Thread(target=run_dispatch)
            thread.start()
            self.assertTrue(github.issue_started.wait(1))

            worker = sqlite3.connect(db_path, timeout=5)
            worker.row_factory = sqlite3.Row
            self.assertEqual(
                "ASSIGNING",
                worker.execute(
                    "select state from route_jobs where task_id='IMP-RACE' and route_kind='COPILOT'"
                ).fetchone()[0],
            )
            self.assertEqual(0, worker.execute("select count(*) from copilot_jobs").fetchone()[0])
            args = SimpleNamespace(chat="worker-auto", task=None, minutes=60, max_active=6)
            with (
                mock.patch.object(coordinator, "reconcile", return_value=None),
                mock.patch.object(coordinator, "git_sha", return_value="b" * 40),
            ):
                with self.assertRaises(SystemExit) as raised:
                    coordinator.cmd_acquire(worker, args)
            self.assertEqual("NO_READY_WORK", str(raised.exception))
            self.assertIsNone(
                worker.execute(
                    "select task_id from brain_task_leases where task_id='IMP-RACE'"
                ).fetchone()
            )
            worker.close()

            github.release_issue.set()
            thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertNotIn("error", dispatch_result)
            self.assertEqual("ACTIVE", dispatch_result["result"].job.state)

    def test_worker_lease_winner_prevents_real_copilot_dispatch(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(
            conn, task_id="IMP-WORKER-FIRST", priority=0, status="READY",
            work_type="implementation", acceptance=("single owner",),
        )
        conn.execute(
            "insert into task_scopes(task_id,path_prefix) values(?,?)",
            ("IMP-WORKER-FIRST", "src/worker-first.ts"),
        )
        ensure_coordinator_runtime_tables(conn)
        conn.execute("insert into brain_members values('worker-auto','IDLE',0)")
        conn.commit()
        args = SimpleNamespace(chat="worker-auto", task="IMP-WORKER-FIRST", minutes=60, max_active=6)
        with (
            mock.patch.object(coordinator, "reconcile", return_value=None),
            mock.patch.object(coordinator, "git_sha", return_value="b" * 40),
        ):
            coordinator.cmd_acquire(conn, args)
        self.assertIsNotNone(
            conn.execute(
                "select task_id from brain_task_leases where task_id='IMP-WORKER-FIRST'"
            ).fetchone()
        )
        config = test_config()
        config["routing"]["copilot_dispatch_enabled"] = True
        config["routing"]["copilot_mode"] = "bounded_implementation"
        with self.assertRaises(PolicyError):
            dispatch_task(conn, "IMP-WORKER-FIRST", "b" * 40, config, FakeGitHub())
        self.assertEqual(0, conn.execute("select count(*) from copilot_jobs").fetchone()[0])

    def test_real_superseded_copilot_transition_restores_worker_eligibility(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        ensure_coordinator_runtime_tables(conn)
        seed_task(
            conn, task_id="IMP-TERM", priority=0, status="READY",
            work_type="implementation", acceptance=("terminal releases ownership",),
        )
        conn.execute(
            "insert into task_scopes(task_id,path_prefix) values(?,?)",
            ("IMP-TERM", "src/terminal.ts"),
        )
        conn.commit()
        config = test_config()
        config["routing"]["copilot_dispatch_enabled"] = True
        config["routing"]["copilot_mode"] = "bounded_implementation"
        dispatched = dispatch_task(conn, "IMP-TERM", "b" * 40, config, FakeGitHub())
        with mock.patch.object(coordinator, "git_sha", return_value="b" * 40):
            self.assertNotIn("IMP-TERM", [row["id"] for row in coordinator.ready_rows(conn)])
        transition_route(conn, dispatched.route_job_id, "ACTIVE", "SUPERSEDED")
        _set_copilot_job_state(conn, dispatched.route_job_id, "SUPERSEDED")
        with mock.patch.object(coordinator, "git_sha", return_value="b" * 40):
            self.assertIn("IMP-TERM", [row["id"] for row in coordinator.ready_rows(conn)])

    def test_combined_backpressure_pauses_implementation_and_unknown_ai_spend(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(conn, task_id="IMP2", status="READY", work_type="implementation")
        conn.execute(
            "insert into task_scopes(task_id,path_prefix) values(?,?)",
            ("IMP2", "src/b.ts"),
        )
        for index in range(5):
            conn.execute(
                "insert into integration_queue(task_id,sha,branch,status,queued_at,updated_at,note) "
                "values(?,?,?,?,datetime('now'),datetime('now'),'pressure')",
                (f"Q{index}", f"{index:040d}", f"worker/q{index}", "READY_FOR_INTEGRATION"),
            )
        for index in range(4):
            conn.execute(
                "insert into route_jobs(dedupe_key,route_kind,state,created_at,updated_at) "
                "values(?,?,?,datetime('now'),datetime('now'))",
                (f"verify:{index}", "VERIFY", "VERIFYING"),
            )
        conn.commit()

        config = test_config()
        config["routing"]["ai_dispatch_enabled"] = True
        config["routing"]["copilot_dispatch_enabled"] = True
        config["routing"]["copilot_mode"] = "bounded_implementation"
        config["openai"]["auto_model"] = "gpt-5.6-luna"
        config["openai"]["model_rates_per_million"] = {}

        pressure = backpressure(conn, config)
        eligibility = copilot_eligibility(conn, "IMP2", "b" * 40, config)
        state = budget_state(conn, config, priority=1, model="gpt-5.6-luna")

        self.assertTrue(pressure.copilot_paused)
        self.assertFalse(pressure.ai_research_paused)
        self.assertEqual(5, pressure.ready_for_integration)
        self.assertEqual(4, pressure.verification_backlog)
        self.assertFalse(eligibility.allowed)
        self.assertIn("backpressure", eligibility.reason)
        self.assertEqual("UNKNOWN", state)
        self.assertFalse(automatic_api_allowed(state, priority=1))


if __name__ == "__main__":
    unittest.main()
