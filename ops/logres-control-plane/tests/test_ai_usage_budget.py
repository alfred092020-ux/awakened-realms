import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db, test_config
from logres_ai_runner import (
    analyze_artifact,
    automatic_api_allowed,
    budget_state,
    cli_summary,
    usage_from_response,
)
from logres_route_store import ensure_route_schema


VALID_RESULT = {
    "summary": "ok",
    "confidence": "UNRESOLVED",
    "findings": [],
    "contradictions": [],
    "unresolved": [],
    "recommended_next_search": "next",
}
class FakeModels:
    def list(self):
        return SimpleNamespace(data=[SimpleNamespace(id="gpt-5-mini")])


class FakeResponses:
    def __init__(self):
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(
            status="completed",
            incomplete_details=None,
            output_text=json.dumps(VALID_RESULT),
            usage=SimpleNamespace(
                input_tokens=1000,
                output_tokens=300,
                input_tokens_details=SimpleNamespace(cached_tokens=400),
                output_tokens_details=SimpleNamespace(reasoning_tokens=50),
            ),
        )


class FakeClient:
    def __init__(self):
        self.models = FakeModels()
        self.responses = FakeResponses()


RATES = {
    "gpt-5-mini": {
        "input": 1.0,
        "cached_input": 0.5,
        "output": 2.0,
    }
}
class AIUsageBudgetTests(unittest.TestCase):
    def test_usage_records_reasoning_cached_tokens_and_estimated_cost(self):
        response = FakeResponses().create()
        usage = usage_from_response(response, "gpt-5-mini", RATES)
        self.assertEqual(1000, usage.input_tokens)
        self.assertEqual(400, usage.cached_input_tokens)
        self.assertEqual(300, usage.output_tokens)
        self.assertEqual(50, usage.reasoning_tokens)
        self.assertAlmostEqual(0.0014, usage.estimated_cost_usd)

    def test_unknown_model_rate_blocks_automatic_spend(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        config = test_config()
        state = budget_state(conn, config, priority=1, model="gpt-5-mini")
        self.assertEqual("UNKNOWN", state)
        self.assertFalse(automatic_api_allowed(state, priority=1))
        self.assertFalse(automatic_api_allowed(state, priority=0))

    def test_cli_summary_exposes_usage_without_secret_material(self):
        out = {
            "cached": False,
            "model": "gpt-5-mini",
            "result": {"confidence": "UNRESOLVED", "summary": "x"},
            "usage": {
                "input_tokens": 10,
                "cached_input_tokens": 2,
                "output_tokens": 3,
                "reasoning_tokens": 0,
                "estimated_cost_usd": 0.00001,
            },
        }
        summary = cli_summary(out, Path("/tmp/result.json"))
        self.assertEqual(out["usage"], summary["usage"])
        self.assertEqual("/tmp/result.json", summary["result_path"])
        self.assertNotIn("api_key", json.dumps(summary).lower())

    def test_real_call_records_usage_and_cache_hit_does_not(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        client = FakeClient()
        with tempfile.TemporaryDirectory() as td:
            artifact = Path(td) / "artifact.txt"
            artifact.write_text("Global evidence sample")
            first = analyze_artifact(
                client,
                conn,
                artifact,
                "What is supported?",
                task_id="T1",
                route_job_id=None,
                rate_config=RATES,
            )
            second = analyze_artifact(
                client,
                conn,
                artifact,
                "What is supported?",
                task_id="T1",
                route_job_id=None,
                rate_config=RATES,
            )

        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(1, client.responses.calls)
        self.assertIsInstance(first["ai_run_id"], int)
        self.assertEqual(first["ai_run_id"], second["ai_run_id"])
        self.assertEqual(1, conn.execute("select count(*) from api_usage").fetchone()[0])
        usage = first["usage"]
        self.assertEqual(1000, usage["input_tokens"])
        self.assertEqual(400, usage["cached_input_tokens"])
        self.assertAlmostEqual(0.0014, usage["estimated_cost_usd"])
        self.assertIsNone(second["usage"])


if __name__ == "__main__":
    unittest.main()
