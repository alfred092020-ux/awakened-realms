import json
import subprocess
import unittest
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
SCRIPT = CONTROL_ROOT / "bin" / "logres-verify-farm"
CONFIG = CONTROL_ROOT / "config" / "autoflow.default.json"


class HybridVerifyTests(unittest.TestCase):
    def test_shell_is_syntactically_valid(self):
        result = subprocess.run(
            ["bash", "-n", str(SCRIPT)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_default_policy_is_fail_closed_for_remote_offload(self):
        cfg = json.loads(CONFIG.read_text())
        remote = cfg["remote_pool"]

        self.assertFalse(remote["enabled"])
        self.assertFalse(remote["hybrid_verify_enabled"])
        self.assertTrue(remote["local_e2e_authoritative"])

    def test_remote_lane_is_exact_sha_and_never_replaces_local_e2e(self):
        text = SCRIPT.read_text()

        self.assertIn(
            'SHA=$(git -C "$BASE" rev-parse "$REF")',
            text,
        )
        self.assertIn(
            '"$POOL_BIN" run heavy "$job" test "$SHA"',
            text,
        )
        self.assertIn(
            'npm run test:e2e',
            text,
        )
        self.assertIn(
            'remote unit-test lane unavailable/failed; falling back locally',
            text,
        )
        self.assertIn(
            'run_local_tests',
            text,
        )

    def test_remote_pool_has_no_merge_or_deploy_authority(self):
        pool = (CONTROL_ROOT / "lib" / "logres_remote_pool.py").read_text()

        self.assertIn("FORBIDDEN_SCRIPT_WORDS", pool)
        self.assertIn('"merge"', pool)
        self.assertIn('"deploy"', pool)
        self.assertIn("ensure_exact_sha", pool)


if __name__ == "__main__":
    unittest.main()
