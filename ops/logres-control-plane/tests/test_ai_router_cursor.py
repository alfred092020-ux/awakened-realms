import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
LIB_DIR = CONTROL_ROOT / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db, seed_event, seed_route, seed_task
from logres_route_store import ensure_route_schema


class AIRouterCursorTests(unittest.TestCase):
    def test_pending_new_ai_route_keeps_cursor_before_its_event(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "control.sqlite"
            cfg = root / "autoflow.json"
            conn = make_test_db(str(db))
            ensure_route_schema(conn)
            seed_task(conn, task_id="T1", work_type="research", status="ACTIVE")
            seed_event(
                conn,
                event_id=10,
                task_id="T1",
                artifact_path="/tmp/pending.txt",
                artifact_sha="a" * 64,
                meta={"artifact_bytes": 74000, "kind": "native_trace"},
            )
            seed_route(
                conn,
                state="NEW",
                dedupe_key="ai:pending",
                route_kind="AI",
                task_id="T1",
                source_event_id=10,
            )
            seed_event(
                conn,
                event_id=20,
                task_id="T1",
                artifact_path="/tmp/later.txt",
                artifact_sha="b" * 64,
                meta={"artifact_bytes": 80, "kind": "symbol_lookup"},
            )
            conn.close()

            cfg.write_text(json.dumps({
                "routing": {
                    "ai_dispatch_enabled": False,
                    "copilot_dispatch_enabled": False,
                    "copilot_mode": "report_only",
                },
                "openai": {
                    "budget_usd": 10.0,
                    "auto_model": None,
                    "model_rates_per_million": {},
                },
            }))
            script = CONTROL_ROOT / "bin" / "logres-ai-router"
            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--dry-run",
                    "--db",
                    str(db),
                    "--config",
                    str(cfg),
                ],
                capture_output=True,
                text=True,
                env={**os.environ, "LOGRES_LOCK_DIR": str(root / "locks")},
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(2, payload["processed"])

    def test_cli_resumes_after_highest_processed_event_when_since_is_omitted(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "control.sqlite"
            cfg = root / "autoflow.json"
            conn = make_test_db(str(db))
            ensure_route_schema(conn)
            seed_task(conn, task_id="T1", work_type="research", status="ACTIVE")
            seed_event(
                conn,
                event_id=10,
                task_id="T1",
                artifact_path="/tmp/old.txt",
                artifact_sha="a" * 64,
                meta={"artifact_bytes": 80, "kind": "symbol_lookup"},
            )
            seed_route(
                conn,
                state="SKIPPED_DETERMINISTIC",
                dedupe_key="event:10:SKIP_DETERMINISTIC",
                route_kind="DETERMINISTIC",
                task_id="T1",
                source_event_id=10,
            )
            seed_event(
                conn,
                event_id=20,
                task_id="T1",
                artifact_path="/tmp/new.txt",
                artifact_sha="b" * 64,
                meta={"artifact_bytes": 80, "kind": "symbol_lookup"},
            )
            conn.close()

            cfg.write_text(
                json.dumps(
                    {
                        "routing": {
                            "ai_dispatch_enabled": False,
                            "copilot_dispatch_enabled": False,
                            "copilot_mode": "report_only",
                        },
                        "openai": {
                            "budget_usd": 10.0,
                            "auto_model": None,
                            "model_rates_per_million": {},
                        },
                    }
                )
            )
            script = CONTROL_ROOT / "bin" / "logres-ai-router"
            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--dry-run",
                    "--db",
                    str(db),
                    "--config",
                    str(cfg),
                ],
                capture_output=True,
                text=True,
                env={**os.environ, "LOGRES_LOCK_DIR": str(root / "locks")},
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(1, payload["processed"])


if __name__ == "__main__":
    unittest.main()
