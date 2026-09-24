import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db, seed_ai_run, seed_event, seed_task, test_config
from logres_ai_router import (
    DEFAULT_QUESTION,
    route_ai_result,
    route_event,
    run_ai_cycle,
    SubprocessBrainRunner,
)
from logres_route_policy import classify_evidence_event
from logres_route_store import RouteSpec, claim_route, ensure_route_schema


class FakeAIRunner:
    def __init__(self, result=None):
        self.calls = 0
        self.result = result or {
            "summary": "ok",
            "confidence": "UNRESOLVED",
            "findings": [],
            "contradictions": [],
            "unresolved": ["callback"],
            "recommended_next_search": "xref callback",
        }

    def run(self, **kwargs):
        self.calls += 1
        return {
            "cached": False,
            "model": "gpt-5-mini",
            "artifact_sha": kwargs["artifact_sha"],
            "result": self.result,
            "usage": None,
            "ai_run_id": 1,
        }
class FlakyAIRunner:
    def __init__(self):
        self.calls = 0

    def run(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("transient transport failure before API usage")
        return {
            "cached": False,
            "model": "gpt-5-mini",
            "artifact_sha": kwargs["artifact_sha"],
            "result": {
                "summary": "retry ok",
                "confidence": "UNRESOLVED",
                "findings": [],
                "contradictions": [],
                "unresolved": ["follow-up"],
                "recommended_next_search": "deterministic follow-up",
            },
            "usage": None,
            "ai_run_id": 1,
        }


class FakeBrainRunner:
    def __init__(self):
        self.events = []

    def post(self, **kwargs):
        self.events.append(kwargs)


class CaptureCommand:
    def __init__(self):
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        return type("Completed", (), {"returncode": 0})()


class AIRouterTests(unittest.TestCase):
    def test_subprocess_brain_runner_builds_deduplicated_conflict_command(self):
        capture = CaptureCommand()
        brain = SubprocessBrainRunner(
            executable="/x/logres-brain",
            runner=capture,
        )
        brain.post(
            event_type="EVIDENCE_CONFLICT",
            task_id="T1",
            subject="Conflict",
            body="A conflicts with B",
            dedupe_key="route:7:conflict",
            priority="HIGH",
        )
        argv = capture.calls[0][0]
        self.assertEqual("/x/logres-brain", argv[0])
        self.assertIn("EVIDENCE_CONFLICT", argv)
        self.assertIn("--dedupe", argv)
        self.assertIn("route:7:conflict", argv)

    def test_large_global_native_artifact_routes_to_ai(self):
        event = {
            "event_type": "EVIDENCE",
            "artifact_path": "/x/global-native.txt",
            "artifact_sha256": "a" * 64,
            "meta_json": (
                '{"artifact_bytes":74000,"kind":"native_trace",'
                '"provenance":"CONFIRMED_GLOBAL_2017"}'
            ),
        }
        decision = classify_evidence_event(
            event,
            {"id": "T1", "priority": 0},
            {"work_type": "research", "evidence_policy": "Global evidence required"},
            test_config(),
        )
        self.assertEqual("AI", decision.route)

    def test_duplicate_artifact_question_uses_cache_without_ai_call(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(conn, task_id="T1", work_type="research")
        seed_event(
            conn,
            event_id=10,
            task_id="T1",
            artifact_path="/tmp/native.txt",
            artifact_sha="a" * 64,
            meta={
                "artifact_bytes": 74000,
                "kind": "native_trace",
                "provenance": "CONFIRMED_GLOBAL_2017",
            },
        )
        seed_ai_run(conn, "a" * 64, DEFAULT_QUESTION, status="PASS")
        fake_ai = FakeAIRunner()

        job = route_event(
            conn,
            source_event_id=10,
            config=test_config(),
            dry_run=False,
            ai_runner=fake_ai,
        )

        self.assertEqual("DUPLICATE_CACHE", job.state)
        self.assertEqual(0, fake_ai.calls)
    def test_supported_inference_does_not_unlock_strict_global_task(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(
            conn,
            task_id="T1",
            work_type="implementation",
            evidence_policy="CONFIRMED ORIGINAL Global evidence required",
        )
        parent = claim_route(
            conn,
            RouteSpec(dedupe_key="parent", route_kind="AI", task_id="T1"),
        )
        result = {
            "confidence": "SUPPORTED INFERENCE",
            "summary": "indirect",
            "findings": [],
            "contradictions": [],
            "unresolved": [],
            "recommended_next_search": "trace callback",
        }

        decision = route_ai_result(
            conn,
            parent.id,
            result,
            {"id": "T1", "priority": 0},
            {
                "work_type": "implementation",
                "evidence_policy": "CONFIRMED ORIGINAL Global evidence required",
            },
            provenance="CONFIRMED_GLOBAL_2017",
        )

        self.assertEqual("REVIEW_REQUIRED", decision.route)

    def test_version_sensitive_creates_one_crosscheck_child(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(
            conn,
            task_id="T1",
            work_type="research",
            evidence_policy="Global evidence required",
        )
        parent = claim_route(
            conn,
            RouteSpec(dedupe_key="parent-vs", route_kind="AI", task_id="T1"),
        )
        result = {
            "confidence": "VERSION SENSITIVE",
            "summary": "JP-only",
            "findings": [],
            "contradictions": [],
            "unresolved": ["Global cross-check"],
            "recommended_next_search": "Global native xref",
        }
        args = (
            conn,
            parent.id,
            result,
            {"id": "T1", "priority": 0},
            {"work_type": "research", "evidence_policy": "Global evidence required"},
        )
        first = route_ai_result(*args, provenance="CONFIRMED_CURRENT_JP")
        second = route_ai_result(*args, provenance="CONFIRMED_CURRENT_JP")

        self.assertEqual(first.child_task_id, second.child_task_id)
        self.assertIsNotNone(first.child_task_id)
        self.assertEqual(
            1,
            conn.execute(
                "select count(*) from tasks where id=?",
                (first.child_task_id,),
            ).fetchone()[0],
        )

    def test_terminal_task_evidence_is_skipped_without_ai_or_child(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(conn, task_id="T1", priority=0, work_type="research", status="DONE")
        seed_event(
            conn,
            event_id=20,
            task_id="T1",
            artifact_sha="d" * 64,
            meta={
                "artifact_bytes": 90000,
                "kind": "native_trace",
                "provenance": "CONFIRMED_GLOBAL_2017",
            },
        )
        fake_ai = FakeAIRunner()

        job = route_event(conn, 20, test_config(), False, fake_ai)

        self.assertEqual("SKIPPED_DETERMINISTIC", job.state)
        self.assertEqual(0, fake_ai.calls)
        self.assertEqual(
            0,
            conn.execute(
                "select count(*) from tasks "
                "where note='Autoflow research child from AI evidence routing.'"
            ).fetchone()[0],
        )

    def test_hardware_blocked_task_does_not_spawn_evidence_loop(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(
            conn,
            task_id="T1",
            priority=0,
            work_type="research",
            status="BLOCKED_EVIDENCE",
        )
        conn.execute(
            "update tasks set note='Awaiting real-device proof; no ADB device attached' "
            "where id='T1'"
        )
        conn.commit()
        seed_event(
            conn,
            event_id=21,
            task_id="T1",
            artifact_sha="e" * 64,
            meta={
                "artifact_bytes": 90000,
                "kind": "native_trace",
                "provenance": "CONFIRMED_GLOBAL_2017",
            },
        )
        fake_ai = FakeAIRunner()

        job = route_event(conn, 21, test_config(), False, fake_ai)

        self.assertEqual("SKIPPED_DETERMINISTIC", job.state)
        self.assertEqual(0, fake_ai.calls)

    def test_dispatch_disabled_leaves_route_new(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(conn, task_id="T1", work_type="research")
        seed_event(
            conn,
            event_id=11,
            task_id="T1",
            artifact_sha="b" * 64,
            meta={"artifact_bytes": 50000, "kind": "native_trace"},
        )
        fake_ai = FakeAIRunner()
        job = route_event(conn, 11, test_config(), False, fake_ai)

        self.assertEqual("NEW", job.state)
        self.assertEqual(0, fake_ai.calls)
    def test_enabled_dispatch_without_priced_auto_model_fails_closed(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(conn, task_id="T1", work_type="research")
        seed_event(
            conn,
            event_id=12,
            task_id="T1",
            artifact_sha="c" * 64,
            meta={"artifact_bytes": 50000, "kind": "native_trace"},
        )
        config = test_config()
        config["routing"]["ai_dispatch_enabled"] = True
        fake_ai = FakeAIRunner()

        job = route_event(conn, 12, config, False, fake_ai)

        self.assertEqual("NEW", job.state)
        self.assertEqual(0, fake_ai.calls)
        decision = conn.execute(
            "select decision from route_decisions where route_job_id=? order by id desc limit 1",
            (job.id,),
        ).fetchone()[0]
        self.assertEqual("BUDGET_UNKNOWN", decision)

    def test_enabled_priced_dispatch_completes_once(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(conn, task_id="T1", priority=0, work_type="research")
        with tempfile.TemporaryDirectory() as td:
            artifact = Path(td) / "native.txt"
            artifact.write_text("Global native evidence")
            sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
            seed_event(
                conn,
                event_id=13,
                task_id="T1",
                artifact_path=str(artifact),
                artifact_sha=sha,
                meta={
                    "artifact_bytes": artifact.stat().st_size + 5000,
                    "kind": "native_trace",
                    "provenance": "CONFIRMED_GLOBAL_2017",
                },
            )
            config = test_config()
            config["routing"]["ai_dispatch_enabled"] = True
            config["openai"]["auto_model"] = "gpt-5-mini"
            config["openai"]["model_rates_per_million"] = {
                "gpt-5-mini": {"input": 1.0, "cached_input": 0.5, "output": 2.0}
            }
            fake_ai = FakeAIRunner()
            job = route_event(conn, 13, config, False, fake_ai)

        self.assertEqual("COMPLETE", job.state)
        self.assertEqual(1, fake_ai.calls)

    def test_zero_cost_transient_ai_failure_retries_once(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(conn, task_id="T1", priority=0, work_type="research")
        with tempfile.TemporaryDirectory() as td:
            artifact = Path(td) / "retry.txt"
            artifact.write_text("Global transient retry evidence")
            sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
            seed_event(
                conn,
                event_id=15,
                task_id="T1",
                artifact_path=str(artifact),
                artifact_sha=sha,
                meta={
                    "artifact_bytes": 6000,
                    "kind": "native_trace",
                    "provenance": "CONFIRMED_GLOBAL_2017",
                },
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
            fake_ai = FlakyAIRunner()

            with self.assertRaisesRegex(RuntimeError, "transient transport"):
                route_event(conn, 15, config, False, fake_ai)

            failed = conn.execute(
                "select id,state,attempt_count from route_jobs "
                "where source_event_id=15"
            ).fetchone()
            self.assertEqual("FAILED_BOUNDED", failed[1])
            self.assertEqual(1, failed[2])
            self.assertEqual(
                0,
                conn.execute(
                    "select count(*) from api_usage where route_job_id=?",
                    (failed[0],),
                ).fetchone()[0],
            )

            job = route_event(conn, 15, config, False, fake_ai)

        self.assertEqual("COMPLETE", job.state)
        self.assertEqual(2, fake_ai.calls)
        self.assertEqual(
            1,
            conn.execute(
                "select count(*) from route_decisions "
                "where route_job_id=? and decision='AI_ZERO_COST_RETRY'",
                (job.id,),
            ).fetchone()[0],
        )

    def test_contradiction_emits_one_brain_conflict_event(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(conn, task_id="T1", priority=0, work_type="research")
        with tempfile.TemporaryDirectory() as td:
            artifact = Path(td) / "conflict.txt"
            artifact.write_text("conflicting global evidence")
            sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
            seed_event(
                conn,
                event_id=14,
                task_id="T1",
                artifact_path=str(artifact),
                artifact_sha=sha,
                meta={
                    "artifact_bytes": 6000,
                    "kind": "native_trace",
                    "provenance": "CONFIRMED_GLOBAL_2017",
                },
            )
            config = test_config()
            config["routing"]["ai_dispatch_enabled"] = True
            config["openai"]["auto_model"] = "gpt-5-mini"
            config["openai"]["model_rates_per_million"] = {
                "gpt-5-mini": {"input": 1.0, "cached_input": 0.5, "output": 2.0}
            }
            fake_ai = FakeAIRunner(
                result={
                    "summary": "conflict",
                    "confidence": "UNRESOLVED",
                    "findings": [],
                    "contradictions": ["A conflicts with B"],
                    "unresolved": [],
                    "recommended_next_search": "xref both callsites",
                }
            )
            brain = FakeBrainRunner()
            cycle = run_ai_cycle(conn, fake_ai, brain, config, limit=10)

        self.assertEqual(1, cycle.created_research_tasks)
        self.assertEqual(1, len(brain.events))
        self.assertEqual("EVIDENCE_CONFLICT", brain.events[0]["event_type"])
        self.assertEqual("T1", brain.events[0]["task_id"])


if __name__ == "__main__":
    unittest.main()
