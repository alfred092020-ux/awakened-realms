import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db, seed_event, seed_task, test_config
from logres_ai_router import run_ai_cycle
from logres_copilot_router import dispatch_task, reconcile_copilot_job
from logres_route_store import ensure_route_schema


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


if __name__ == "__main__":
    unittest.main()
