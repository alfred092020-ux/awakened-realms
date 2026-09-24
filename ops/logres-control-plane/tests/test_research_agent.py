import json
import sqlite3
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db, seed_task
from logres_research_agent import (
    brain_confidence,
    build_prompt,
    can_complete,
    record_usage,
    run_research,
    task_context,
)


class FakeResponses:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class FakeClient:
    def __init__(self, response):
        self.responses = FakeResponses(response)


def result_json(status="DONE", checks=None):
    return json.dumps(
        {
            "summary": "bounded result",
            "confidence": "SUPPORTED INFERENCE",
            "completion_basis": "SUPPORTED_SYNTHESIS",
            "findings": ["finding"],
            "provenance": ["Global evidence kept separate"],
            "contradictions": [],
            "unresolved": [],
            "acceptance_checks": checks
            if checks is not None
            else [
                {
                    "criterion": "recover evidence",
                    "status": "PASS",
                    "evidence": "artifact A",
                }
            ],
            "sources": ["https://example.test/source"],
            "deterministic_searches": ["local index"],
            "recommended_next_search": "none",
            "task_status": status,
            "completion_note": "done",
        }
    )


class ResearchAgentTests(unittest.TestCase):
    def test_task_context_uses_production_ordinal_acceptance_schema(self):
        conn = make_test_db()
        conn.row_factory = sqlite3.Row
        seed_task(
            conn,
            task_id="T1",
            work_type="research",
            status="ACTIVE",
        )
        conn.execute("delete from task_acceptance where task_id='T1'")
        conn.execute(
            "insert into task_acceptance(task_id,ordinal,criterion) values(?,?,?)",
            ("T1", 2, "second"),
        )
        conn.execute(
            "insert into task_acceptance(task_id,ordinal,criterion) values(?,?,?)",
            ("T1", 1, "first"),
        )
        conn.commit()

        context = task_context(conn, "T1")

        self.assertEqual(["first", "second"], context["acceptance"])

    def test_completion_requires_every_acceptance_check_to_pass(self):
        good = json.loads(result_json())
        self.assertTrue(can_complete(good, 1))

        bad = json.loads(
            result_json(
                checks=[
                    {
                        "criterion": "recover evidence",
                        "status": "BLOCKED",
                        "evidence": "not recovered",
                    }
                ]
            )
        )
        self.assertFalse(can_complete(bad, 1))
        self.assertFalse(
            can_complete(json.loads(result_json(status="BLOCKED_EVIDENCE")), 1)
        )

    def test_prompt_contains_global_provenance_boundaries(self):
        context = {
            "task": {
                "id": "T1",
                "title": "Map lineage",
                "status": "ACTIVE",
                "note": "",
            },
            "metadata": {
                "work_type": "research",
                "evidence_policy": "Global evidence required",
                "expected_minutes": 30,
            },
            "acceptance": ["do not promote current JP"],
            "dependencies": [],
        }
        prompt = build_prompt(context, "LOCAL EVIDENCE")

        self.assertIn("Global evidence required", prompt)
        self.assertIn("do not promote current JP", prompt)
        self.assertIn("LOCAL EVIDENCE", prompt)

    def test_research_call_enables_web_search_and_strict_schema(self):
        response = SimpleNamespace(
            output_text=result_json(),
            output=[],
            usage=None,
        )
        client = FakeClient(response)

        result, returned = run_research(
            client,
            model="gpt-5.6-luna",
            prompt="task",
            web_search=True,
        )

        self.assertIs(returned, response)
        self.assertEqual("DONE", result["task_status"])
        call = client.responses.calls[0]
        self.assertEqual(
            [{"type": "web_search", "search_context_size": "medium"}],
            call["tools"],
        )
        self.assertTrue(call["text"]["format"]["strict"])
        self.assertEqual("medium", call["reasoning"]["effort"])

    def test_brain_confidence_mapping_uses_allowed_labels(self):
        self.assertEqual("CONFIRMED", brain_confidence("CONFIRMED ORIGINAL"))
        self.assertEqual("INFERENCE", brain_confidence("SUPPORTED INFERENCE"))
        self.assertEqual("MEDIUM", brain_confidence("RECONSTRUCTED"))
        self.assertEqual("LOW", brain_confidence("UNRESOLVED"))
        self.assertEqual(
            "VERSION_SENSITIVE",
            brain_confidence("VERSION SENSITIVE"),
        )

    def test_usage_is_recorded_in_shared_budget_ledger(self):
        conn = make_test_db()
        response = SimpleNamespace(
            usage=SimpleNamespace(
                input_tokens=1000,
                output_tokens=500,
                input_tokens_details=SimpleNamespace(cached_tokens=100),
                output_tokens_details=SimpleNamespace(reasoning_tokens=10),
            )
        )
        usage = record_usage(
            conn,
            response,
            model="gpt-5.6-luna",
            rate_config={
                "gpt-5.6-luna": {
                    "input": 0.2,
                    "cached_input": 0.02,
                    "output": 1.2,
                }
            },
            task_id="T1",
            artifact_sha="a" * 64,
        )

        self.assertGreater(usage["estimated_cost_usd"], 0)
        row = conn.execute(
            "select task_id,model,status from api_usage order by id desc limit 1"
        ).fetchone()
        self.assertEqual(("T1", "gpt-5.6-luna", "PASS"), tuple(row))


if __name__ == "__main__":
    unittest.main()
