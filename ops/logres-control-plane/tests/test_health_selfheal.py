import fcntl
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
SYNC = CONTROL_ROOT / "bin" / "logres-sync-health"
INDEX = CONTROL_ROOT / "bin" / "logres-code-index"
SNAPSHOT = CONTROL_ROOT / "bin" / "logres-health-snapshot"


class HealthSelfHealTests(unittest.TestCase):
    def test_sync_health_retries_transient_brain_database_locks(self):
        text = SYNC.read_text()
        self.assertIn("retry_locked=False", text)
        self.assertIn('"database is locked" in detail', text)
        self.assertIn("attempts=6", text)
        self.assertIn("0.20 * (2 ** attempt)", text)

    def test_code_index_has_status_mode_and_single_flight_lock(self):
        text = INDEX.read_text()
        self.assertIn("LOGRES_CODE_INDEX_LOCK", text)
        self.assertIn("LOCK_EX|fcntl.LOCK_NB", text)
        self.assertIn('mode in ("status","--status")', text)
        self.assertIn("code_index_busy", text)
        self.assertIn("os.replace(tmp,DB)", text)

    def test_code_index_busy_is_successful_noop(self):
        with tempfile.TemporaryDirectory() as td:
            lock = Path(td) / "code-index.lock"
            db = Path(td) / "index.sqlite"
            with lock.open("a+") as handle:
                fcntl.flock(
                    handle.fileno(),
                    fcntl.LOCK_EX | fcntl.LOCK_NB,
                )
                env = os.environ.copy()
                env["LOGRES_CODE_INDEX_LOCK"] = str(lock)
                env["LOGRES_CODE_INDEX_DB"] = str(db)
                env["LOGRES_REPO_ROOT"] = str(
                    Path("/home/ubuntu/logres/src/awakened-realms")
                )
                proc = subprocess.run(
                    [str(INDEX)],
                    text=True,
                    capture_output=True,
                    env=env,
                    check=False,
                    timeout=20,
                )
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("code_index_busy", proc.stdout)
        self.assertFalse(db.exists())

    def test_code_index_status_detects_missing_index_without_rebuild(self):
        with tempfile.TemporaryDirectory() as td:
            env = os.environ.copy()
            env["LOGRES_CODE_INDEX_DB"] = str(Path(td) / "missing.sqlite")
            env["LOGRES_CODE_INDEX_LOCK"] = str(Path(td) / "lock")
            env["LOGRES_REPO_ROOT"] = str(
                Path("/home/ubuntu/logres/src/awakened-realms")
            )
            proc = subprocess.run(
                [str(INDEX), "status"],
                text=True,
                capture_output=True,
                env=env,
                check=False,
                timeout=20,
            )
        self.assertEqual(1, proc.returncode)
        self.assertIn("code_index_stale", proc.stdout)
        self.assertIn("indexed=missing", proc.stdout)

    def test_health_snapshot_is_fail_transparent(self):
        text = SNAPSHOT.read_text()
        self.assertIn("logres-doctor", text)
        self.assertIn("exit $rc", text)


if __name__ == "__main__":
    unittest.main()
