import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
SCRIPT = CONTROL_ROOT / "bin" / "logres-merge-train"


class MergeTrainAutonomyTests(unittest.TestCase):
    def run_apply(self, enabled: bool, token_id: str | None):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        db = root / "control.sqlite"
        sqlite3.connect(db).close()
        config = root / "autoflow.json"
        config.write_text(
            json.dumps(
                {
                    "autonomy": {
                        "enabled": enabled,
                        "auto_apply_preflight_enabled": enabled,
                    }
                }
            )
        )
        env = os.environ.copy()
        env.update(
            {
                "LOGRES_ROOT": str(root),
                "LOGRES_CONTROL_DB": str(db),
                "LOGRES_REPO_ROOT": str(root / "missing-repo"),
                "LOGRES_AUTOFLOW_CONFIG": str(config),
                "LOGRES_INTEGRATION_LOCK": str(root / "integration.lock"),
                "LOGRES_FETCH_LOCK": str(root / "fetch.lock"),
                "LOGRES_AUTONOMY_APPLY": "1",
            }
        )
        if token_id is not None:
            env["LOGRES_AUTONOMY_PREFLIGHT_ID"] = token_id
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "apply-preflight",
                "--actor",
                "autonomy",
                "42",
            ],
            capture_output=True,
            text=True,
            env=env,
        )

    def test_autonomy_actor_is_denied_when_runtime_policy_is_disabled(self):
        result = self.run_apply(enabled=False, token_id="42")
        self.assertNotEqual(0, result.returncode)
        self.assertIn(
            "policy-authorized 'autonomy'",
            result.stderr + result.stdout,
        )

    def test_autonomy_actor_requires_exact_preflight_capability(self):
        result = self.run_apply(enabled=True, token_id="41")
        self.assertNotEqual(0, result.returncode)
        self.assertIn(
            "policy-authorized 'autonomy'",
            result.stderr + result.stdout,
        )

    def test_authorized_autonomy_passes_actor_guard_before_repository_validation(self):
        result = self.run_apply(enabled=True, token_id="42")
        self.assertNotEqual(0, result.returncode)
        output = result.stderr + result.stdout
        self.assertNotIn("policy-authorized 'autonomy'", output)
        self.assertIn("git fetch origin failed", output)


if __name__ == "__main__":
    unittest.main()
