import json
import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_ai_common import brain_post_dedupe_key
from logres_reconcile import SQLiteAICache
from logres_route_store import RouteJob


class CaptureRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()


class AIBrainDedupeTests(unittest.TestCase):
    def test_recovery_uses_same_artifact_question_dedupe_key(self):
        artifact_sha = "a" * 64
        question = "What is supported?"
        route = RouteJob(
            id=7,
            dedupe_key="ai-route",
            source_event_id=10,
            task_id="T1",
            route_kind="AI",
            state="AI_VALIDATED",
            attempt_count=0,
            artifact_sha=artifact_sha,
            question_sha=None,
            base_sha=None,
            external_ref=None,
            parent_route_id=None,
            resolution_type=None,
            last_error=None,
            meta_json=json.dumps({"question": question}),
            created_at="now",
            updated_at="now",
        )
        capture = CaptureRunner()
        cache = SQLiteAICache(brain_executable="logres-brain", runner=capture)
        cache.ensure_brain_post(
            route,
            {
                "result": {
                    "summary": "x",
                    "confidence": "UNRESOLVED",
                    "findings": [],
                    "contradictions": [],
                    "unresolved": [],
                    "recommended_next_search": "y",
                }
            },
        )

        argv = capture.calls[0][0]
        index = argv.index("--dedupe")
        self.assertEqual(
            brain_post_dedupe_key(artifact_sha, question),
            argv[index + 1],
        )

    def test_cli_wrapper_uses_shared_dedupe_helper(self):
        wrapper = (TEST_DIR.parent / "bin" / "logres-ai").read_text()
        self.assertIn("brain_post_dedupe_key", wrapper)
        self.assertIn('"--dedupe"', wrapper)


if __name__ == "__main__":
    unittest.main()
