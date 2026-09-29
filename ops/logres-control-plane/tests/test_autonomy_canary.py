import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
LIB_DIR = CONTROL_ROOT / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_autonomy_canary import AUTONOMY_CANARY_VERSION, canary_status


class AutonomyCanaryTests(unittest.TestCase):
    def test_canary_version(self):
        self.assertEqual(3, AUTONOMY_CANARY_VERSION)

    def test_canary_status_is_ready(self):
        self.assertEqual("ready", canary_status())


if __name__ == "__main__":
    unittest.main()
