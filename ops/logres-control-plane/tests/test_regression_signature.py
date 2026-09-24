import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_regression_signature import (
    normalize_failure_text,
    semantic_fingerprint,
    semantic_signature,
)


class RegressionSignatureTests(unittest.TestCase):
    def test_behavior_trace_missing_output_is_stable_family(self):
        a = """
        Error: LOGRES_BEHAVIOR_TRACE_OUT is required
        1 failed
        """
        b = """
        /dev/shm/logres/verify-farm-20260924T164835-e2e/foo
        Error: LOGRES_BEHAVIOR_TRACE_OUT is required
        1 failed
        """

        self.assertEqual(
            semantic_fingerprint("candidate-verify", a)[0],
            semantic_fingerprint("candidate-verify", b)[0],
        )
        self.assertIn(
            "behavior-trace-output-required",
            semantic_signature("candidate-verify", a),
        )

    def test_visual_truth_sqlite_lock_ignores_checkpoint_sha_and_path(self):
        a = """
        Error: Visual checkpoint title failed.
        Command ['/home/ubuntu/logres/bin/logres-visual-truth', 'record',
        '66291adb29a1fcdfe5c8ad5b8948ce39b5b1c39d', 'title',
        '/dev/shm/logres/verify-farm-20260924T191040-e2e/title.png']
        RuntimeError: visual truth recording failed:
        sqlite3.OperationalError: database is locked
        """
        b = """
        Error: Visual checkpoint field failed.
        Command ['/home/ubuntu/logres/bin/logres-visual-truth', 'record',
        '80b7df5f2b429fcbe0e18756d2088227e8b5df96', 'field',
        '/dev/shm/logres/verify-farm-20260924T191926-e2e/field.png']
        sqlite3.OperationalError: database is locked
        """

        self.assertEqual(
            semantic_fingerprint("candidate-verify", a)[0],
            semantic_fingerprint("candidate-verify", b)[0],
        )
        self.assertIn(
            "visual-truth-sqlite-locked",
            semantic_signature("candidate-verify", a),
        )

    def test_visual_truth_timeout_is_stable_family(self):
        a = """
        subprocess.TimeoutExpired: Command
        ['/home/ubuntu/logres/bin/logres-visual-truth','record','a'*40]
        timed out after 8.0 seconds
        RuntimeError: visual truth recording timed out after 8s
        """
        b = """
        Error: Visual checkpoint field failed
        subprocess.TimeoutExpired: Command
        ['/home/ubuntu/logres/bin/logres-visual-truth','record','b'*40]
        timed out after 12.0 seconds
        """

        self.assertEqual(
            semantic_fingerprint("candidate-verify", a)[0],
            semantic_fingerprint("candidate-verify", b)[0],
        )

    def test_generic_distinct_failures_remain_distinct(self):
        a = "AssertionError: expected player hp 100 received 90"
        b = "TypeError: cannot read properties of undefined"

        self.assertNotEqual(
            semantic_fingerprint("candidate-verify", a)[0],
            semantic_fingerprint("candidate-verify", b)[0],
        )

    def test_normalizer_removes_volatile_sha_worktree_time_and_port(self):
        raw = (
            "/home/ubuntu/logres/work/worker-123/foo "
            "abcdef0123456789abcdef0123456789abcdef01 "
            "12.3s http://127.0.0.1:4174/a"
        )
        normalized = normalize_failure_text(raw)
        self.assertIn("<WORKTREE>", normalized)
        self.assertIn("<SHA>", normalized)
        self.assertIn("<TIME>", normalized)
        self.assertIn("<PORT>", normalized)


if __name__ == "__main__":
    unittest.main()
