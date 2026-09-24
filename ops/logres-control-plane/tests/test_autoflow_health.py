import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
LIB_DIR = CONTROL_ROOT / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db, test_config
from logres_reconcile import format_routes_status, route_status
from logres_route_store import ensure_route_schema


class AutoflowHealthTests(unittest.TestCase):
    def test_compact_status_reports_router_ai_copilot_and_backpressure(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        conn.execute(
            "insert into route_jobs(dedupe_key,route_kind,state,created_at,updated_at) values('ai-active','AI','AI_RUNNING',datetime('now'),datetime('now'))"
        )
        conn.execute(
            "insert into route_jobs(dedupe_key,route_kind,state,created_at,updated_at) values('cache','AI','DUPLICATE_CACHE',datetime('now'),datetime('now'))"
        )
        conn.execute(
            "insert into route_jobs(dedupe_key,route_kind,state,last_error,created_at,updated_at) values('failed','AI','FAILED_BOUNDED','x',datetime('now'),datetime('now'))"
        )
        conn.commit()

        status = route_status(conn, test_config())
        text = format_routes_status(status)

        self.assertIn("ROUTER", text)
        self.assertIn("OPENAI", text)
        self.assertIn("COPILOT", text)
        self.assertIn("BACKPRESSURE", text)
        self.assertIn("cache_hits=1", text)
        self.assertNotIn("api_key", text.lower())

    def test_versioned_scripts_expose_required_task7_hooks(self):
        watcher = (CONTROL_ROOT / "bin" / "logres-autopilot-watch").read_text()
        doctor = (CONTROL_ROOT / "bin" / "logres-doctor").read_text()
        lead = (CONTROL_ROOT / "bin" / "logres-lead").read_text()

        for helper in (
            "logres-route-reconcile",
            "logres-ai-router",
            "logres-copilot-router",
        ):
            self.assertIn(helper, watcher)
        self.assertIn("flock", watcher)

        for check in (
            "route_schema",
            "route_cursor",
            "route_failures",
            "openai_recent_success",
            "openai_budget_state",
            "copilot_auth",
            "copilot_active_jobs",
            "copilot_base_policy",
            "autoflow_source_deployed",
        ):
            self.assertIn(check, doctor)

        self.assertIn("routes)", lead)
        self.assertIn("logres-route-reconcile", lead)


if __name__ == "__main__":
    unittest.main()
