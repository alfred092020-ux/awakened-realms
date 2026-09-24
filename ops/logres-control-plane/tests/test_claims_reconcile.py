import sys
import unittest
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_claims_reconcile import claim_releasable


class ClaimsReconcileTests(unittest.TestCase):
    def test_terminal_and_blocked_states_release_without_live_lease(self):
        states = (
            "DONE",
            "READY",
            "RESOLVED",
            "INTEGRATED",
            "SUPERSEDED",
            "CANCELLED",
            "BLOCKED_DEP",
            "BLOCKED_EVIDENCE",
        )
        for status in states:
            with self.subTest(status=status):
                self.assertTrue(
                    claim_releasable(
                        status,
                        has_active_lease=False,
                    )
                )

    def test_live_lease_always_preserves_claim(self):
        for status in (
            "DONE",
            "READY",
            "SUPERSEDED",
            "CANCELLED",
            "BLOCKED_DEP",
        ):
            with self.subTest(status=status):
                self.assertFalse(
                    claim_releasable(
                        status,
                        has_active_lease=True,
                    )
                )

    def test_active_and_unknown_states_are_preserved(self):
        for status in ("ACTIVE", "UNKNOWN", "", None):
            with self.subTest(status=status):
                self.assertFalse(
                    claim_releasable(
                        status,
                        has_active_lease=False,
                    )
                )

    def test_status_matching_is_normalized(self):
        self.assertTrue(
            claim_releasable(
                " superseded ",
                has_active_lease=False,
            )
        )
        self.assertTrue(
            claim_releasable(
                "blocked_custom",
                has_active_lease=False,
            )
        )


if __name__ == "__main__":
    unittest.main()
