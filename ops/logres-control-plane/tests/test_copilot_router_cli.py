import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
REPO_ROOT = CONTROL_ROOT.parents[1]
LIB_DIR = CONTROL_ROOT / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db, seed_task, test_config
from logres_route_store import ensure_route_schema


class CopilotRouterCLITests(unittest.TestCase):
    def test_dry_run_reports_candidate_without_dispatch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db_path = root / "control.sqlite"
            config_path = root / "autoflow.json"
            conn = make_test_db(str(db_path))
            ensure_route_schema(conn)
            seed_task(
                conn,
                task_id="T1",
                work_type="implementation",
                status="READY",
                evidence_policy="CONFIRMED ORIGINAL Global evidence required",
            )
            conn.execute(
                "insert into task_scopes(task_id,path_prefix) values(?,?)",
                ("T1", "src/a.ts"),
            )
            conn.commit()
            conn.close()
            config_path.write_text(json.dumps(test_config()))

            env = os.environ.copy()
            env["LOGRES_CONTROL_DB"] = str(db_path)
            env["LOGRES_AUTOFLOW_CONFIG"] = str(config_path)
            env["LOGRES_INTEGRATION_SHA"] = "b" * 40
            script = CONTROL_ROOT / "bin" / "logres-copilot-router"
            result = subprocess.run(
                [sys.executable, str(script), "--dry-run", "--task", "T1"],
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["dry_run"])
            self.assertEqual("T1", payload["task_id"])
            self.assertTrue(payload["eligible"])
            self.assertFalse(payload["dispatch_enabled"])
            self.assertEqual("b" * 40, payload["integration_sha"])



    def test_dispatch_disabled_non_dry_run_exits_cleanly(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db_path = root / "control.sqlite"
            config_path = root / "autoflow.json"
            conn = make_test_db(str(db_path))
            ensure_route_schema(conn)
            conn.close()
            config_path.write_text(json.dumps(test_config()))

            env = os.environ.copy()
            env["LOGRES_CONTROL_DB"] = str(db_path)
            env["LOGRES_AUTOFLOW_CONFIG"] = str(config_path)
            env["LOGRES_INTEGRATION_SHA"] = "b" * 40
            script = CONTROL_ROOT / "bin" / "logres-copilot-router"
            result = subprocess.run(
                [sys.executable, str(script)],
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(0, payload["dispatched"])
            self.assertFalse(payload["dispatch_enabled"])
            self.assertEqual("dispatch disabled", payload["reason"])


if __name__ == "__main__":
    unittest.main()
