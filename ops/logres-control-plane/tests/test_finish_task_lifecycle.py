import unittest
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
FINISH = CONTROL_ROOT / "bin" / "logres-finish-task"
COORDINATOR = CONTROL_ROOT / "bin" / "logres-coordinator"


class FinishTaskLifecycleTests(unittest.TestCase):
    def test_finish_does_not_resolve_regression_before_integration(self):
        text = FINISH.read_text()
        self.assertNotIn(
            "update regressions set status='RESOLVED'",
            text,
        )
        self.assertIn(
            "Keep the regression OPEN until the repair SHA is actually",
            text,
        )
        self.assertIn(
            "/home/ubuntu/logres/bin/logres-coordinator reconcile",
            text,
        )

    def test_coordinator_resolves_only_from_integrated_repair_queue(self):
        text = (
            CONTROL_ROOT / "lib" / "logres_regression_reconcile.py"
        ).read_text()
        self.assertIn(
            "iq.status='INTEGRATED'",
            text,
        )
        self.assertIn(
            "set status='RESOLVED'",
            text,
        )

    def test_coordinator_does_not_suppress_open_done_repair(self):
        text = COORDINATOR.read_text()
        terminal_guard = (
            'if repair_task_regression_terminal(c,t["id"]):'
        )
        self.assertIn(terminal_guard, text)
        # OPEN regressions are intentionally false for the terminal predicate;
        # DONE repair tasks therefore continue into integration queue rebuild.
        regression_lib = (
            CONTROL_ROOT / "lib" / "logres_regression_reconcile.py"
        ).read_text()
        self.assertIn(
            "status in ('RESOLVED','SUPERSEDED')",
            regression_lib,
        )


if __name__ == "__main__":
    unittest.main()
