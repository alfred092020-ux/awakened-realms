import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import test_config
from logres_route_policy import classify_evidence_event, implementation_allowed


class RoutePolicyTests(unittest.TestCase):
    def test_confirmed_global_can_implement(self):
        self.assertTrue(
            implementation_allowed(
                "CONFIRMED ORIGINAL",
                "CONFIRMED ORIGINAL Global evidence required",
                "CONFIRMED_GLOBAL_2017",
            )
        )

    def test_supported_inference_requires_explicit_policy(self):
        self.assertFalse(
            implementation_allowed(
                "SUPPORTED INFERENCE",
                "CONFIRMED ORIGINAL Global evidence required",
                "CONFIRMED_GLOBAL_2017",
            )
        )
        self.assertTrue(
            implementation_allowed(
                "SUPPORTED INFERENCE",
                "allow-supported-inference",
                "CONFIRMED_GLOBAL_2017",
            )
        )

    def test_later_jp_never_unlocks_global_implementation(self):
        self.assertFalse(
            implementation_allowed(
                "CONFIRMED ORIGINAL",
                "allow-supported-inference",
                "CONFIRMED_CURRENT_JP",
            )
        )

    def test_small_symbol_lookup_stays_deterministic(self):
        event = {
            "event_type": "EVIDENCE",
            "artifact_path": "/tmp/symbol.txt",
            "artifact_sha256": "a" * 64,
            "meta_json": '{"artifact_bytes":80,"kind":"symbol_lookup"}',
        }
        decision = classify_evidence_event(
            event,
            {"id": "T1", "priority": 1},
            {"work_type": "research", "evidence_policy": "Global evidence required"},
            test_config(),
        )
        self.assertEqual("SKIP_DETERMINISTIC", decision.route)


if __name__ == "__main__":
    unittest.main()
