import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
REPO_ROOT = TEST_DIR.parents[2]
sys.path.insert(0, str(TEST_DIR))

from fixtures import make_test_db, seed_event, seed_task


class AIRouterCLITests(unittest.TestCase):
    def test_dry_run_scans_event_without_external_dispatch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db_path = root / "control.sqlite"
            config_path = root / "autoflow.json"
            conn = make_test_db(str(db_path))
            seed_task(conn, task_id="T1", work_type="research")
            seed_event(
                conn,
                event_id=10,
                task_id="T1",
                artifact_path="/tmp/not-needed-in-dry-run.txt",
                artifact_sha="a" * 64,
                meta={"artifact_bytes": 50000, "kind": "native_trace"},
            )
            conn.close()
            config_path.write_text(
                json.dumps(
                    {
                        "routing": {
                            "ai_dispatch_enabled": False,
                            "copilot_dispatch_enabled": False,
                        },
                        "openai": {"model_rates_per_million": {}},
                    }
                )
            )

            script = REPO_ROOT / "ops" / "logres-control-plane" / "bin" / "logres-ai-router"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--dry-run",
                    "--db",
                    str(db_path),
                    "--config",
                    str(config_path),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(1, payload["processed"])
            check = sqlite3.connect(db_path)
            self.assertEqual(
                "NEW",
                check.execute("select state from route_jobs").fetchone()[0],
            )
            check.close()


if __name__ == "__main__":
    unittest.main()
