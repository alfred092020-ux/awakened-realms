import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db, seed_ai_run, seed_route, seed_task, test_config
from logres_reconcile import backpressure, reconcile_routes
from logres_route_store import ensure_route_schema


VALID_RESULT = {
    "summary": "cached result",
    "confidence": "UNRESOLVED",
    "findings": [],
    "contradictions": [],
    "unresolved": ["callback"],
    "recommended_next_search": "xref callback",
}


class FakeAICache:
    def __init__(self, record=None):
        self.record = record
        self.openai_calls = 0
        self.brain_posts = 0

    def recover(self, conn, route):
        return self.record

    def ensure_brain_post(self, route, record):
        self.brain_posts += 1


class FakeCommandRunner:
    pass


class RouteReconcileTests(unittest.TestCase):
    def test_ai_completed_before_brain_post_is_recovered_without_second_call(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(conn, task_id="T1", work_type="research", status="ACTIVE")
        route_id = seed_route(
            conn,
            state="AI_RUNNING",
            dedupe_key="x",
            route_kind="AI",
            task_id="T1",
        )
        conn.execute(
            "update route_jobs set artifact_sha=?,meta_json=? where id=?",
            ("a" * 64, json.dumps({"question": "q", "provenance": "CONFIRMED_GLOBAL_2017"}), route_id),
        )
        conn.commit()
        seed_ai_run(conn, artifact_sha="a" * 64, question="q", status="PASS")
        ai_cache = FakeAICache(
            {"ai_run_id": 1, "result": VALID_RESULT, "model": "gpt-5.6-luna"}
        )

        result = reconcile_routes(
            conn,
            ai_cache=ai_cache,
            github=Mock(),
            command_runner=FakeCommandRunner(),
            config=test_config(),
            current_integration_sha="b" * 40,
        )[0]

        self.assertEqual("BRAIN_POSTED", result.state)
        self.assertEqual(0, ai_cache.openai_calls)
        self.assertEqual(1, ai_cache.brain_posts)
        stored = conn.execute(
            "select state from route_jobs where id=?", (route_id,)
        ).fetchone()[0]
        self.assertEqual("BRAIN_POSTED", stored)

    def test_existing_copilot_issue_is_adopted_after_crash(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(conn, task_id="T1", status="READY")
        route_id = seed_route(
            conn,
            state="ASSIGNING",
            dedupe_key="copilot:T1",
            route_kind="COPILOT",
            task_id="T1",
            external_ref=None,
        )
        conn.execute(
            "update route_jobs set base_sha=? where id=?",
            ("b" * 40, route_id),
        )
        conn.commit()
        github = Mock()
        github.search_issue.return_value = {
            "number": 42,
            "state": "open",
            "title": "[Copilot] T1",
        }
        github.create_issue_calls = 0

        result = reconcile_routes(
            conn,
            ai_cache=FakeAICache(),
            github=github,
            command_runner=FakeCommandRunner(),
            config=test_config(),
            current_integration_sha="b" * 40,
        )[0]

        self.assertEqual("ACTIVE", result.state)
        self.assertEqual(42, result.issue_number)
        self.assertEqual(0, github.create_issue_calls)
        self.assertEqual(
            1,
            conn.execute(
                "select count(*) from copilot_jobs where route_job_id=? and issue_number=42",
                (route_id,),
            ).fetchone()[0],
        )

    def test_superseded_task_route_is_closed_without_external_work(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(conn, task_id="T1", status="SUPERSEDED")
        route_id = seed_route(
            conn,
            state="ACTIVE",
            dedupe_key="copilot:T1:old",
            route_kind="COPILOT",
            task_id="T1",
        )

        result = reconcile_routes(
            conn,
            ai_cache=FakeAICache(),
            github=Mock(),
            command_runner=FakeCommandRunner(),
            config=test_config(),
            current_integration_sha="b" * 40,
        )[0]

        self.assertEqual("SUPERSEDED", result.state)
        self.assertEqual(
            "SUPERSEDED",
            conn.execute("select state from route_jobs where id=?", (route_id,)).fetchone()[0],
        )

    def test_five_ready_merges_pause_new_copilot_dispatch(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        for i in range(5):
            conn.execute(
                "insert into integration_queue(task_id,sha,branch,status,queued_at,updated_at,note) values(?,?,?,?,datetime('now'),datetime('now'),'')",
                (f"T{i}", f"{i:040d}", f"worker/t{i}", "READY_FOR_INTEGRATION"),
            )
        conn.commit()

        state = backpressure(conn, test_config())
        self.assertTrue(state.copilot_paused)
        self.assertFalse(state.ai_research_paused)
        self.assertEqual(5, state.ready_for_integration)

    def test_verification_backlog_pauses_implementation_not_research(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        for i in range(4):
            conn.execute(
                "insert into route_jobs(dedupe_key,route_kind,state,created_at,updated_at) values(?,?,?,datetime('now'),datetime('now'))",
                (f"verify:{i}", "VERIFY", "VERIFYING"),
            )
        conn.commit()

        state = backpressure(conn, test_config())
        self.assertTrue(state.copilot_paused)
        self.assertFalse(state.ai_research_paused)
        self.assertEqual(4, state.verification_backlog)


if __name__ == "__main__":
    unittest.main()
