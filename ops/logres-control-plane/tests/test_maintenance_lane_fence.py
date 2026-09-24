import fcntl
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
BIN = CONTROL_ROOT / "bin"
HELPERS = (
    "logres-autopilot-watch",
    "logres-lead-snapshot",
    "logres-health-snapshot",
    "logres-maintain",
)


class MaintenanceLaneFenceTests(unittest.TestCase):
    def test_all_slow_helpers_share_same_lane_contract(self):
        for name in HELPERS:
            with self.subTest(name=name):
                text = (BIN / name).read_text()
                self.assertIn(
                    "LOGRES_MAINTENANCE_LANE_LOCK",
                    text,
                )
                self.assertIn(
                    "/tmp/logres-maintenance-lane.lock",
                    text,
                )

    def test_busy_lane_makes_all_helpers_exit_cleanly(self):
        with tempfile.TemporaryDirectory() as td:
            lock_path = Path(td) / "maintenance.lock"
            with lock_path.open("a+") as handle:
                fcntl.flock(
                    handle.fileno(),
                    fcntl.LOCK_EX | fcntl.LOCK_NB,
                )
                env = os.environ.copy()
                env["LOGRES_MAINTENANCE_LANE_LOCK"] = str(lock_path)
                for name in HELPERS:
                    with self.subTest(name=name):
                        result = subprocess.run(
                            [str(BIN / name)],
                            env=env,
                            text=True,
                            capture_output=True,
                            timeout=5,
                            check=False,
                        )
                        self.assertEqual(
                            0,
                            result.returncode,
                            result.stderr or result.stdout,
                        )

    def test_maintain_is_versioned_with_expected_core_actions(self):
        text = (BIN / "logres-maintain").read_text()
        for marker in (
            "logres-worktree-gc --apply --age-hours 24",
            "git -C \"$BASE\" maintenance run --auto",
            "logres-control-backup --dated",
            "logres-doctor || true",
        ):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
