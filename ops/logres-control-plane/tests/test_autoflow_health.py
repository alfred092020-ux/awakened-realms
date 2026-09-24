import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
LIB_DIR = CONTROL_ROOT / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db, seed_task, test_config
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

    def test_route_failures_ignore_terminal_and_external_device_waits(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(conn, task_id="DONE-TASK", status="DONE")
        seed_task(conn, task_id="DEVICE-TASK", status="BLOCKED_EVIDENCE")
        conn.execute(
            "update tasks set note='Awaiting real-device proof; no ADB device attached' "
            "where id='DEVICE-TASK'"
        )
        for key, task_id in (
            ("failed-done", "DONE-TASK"),
            ("failed-device", "DEVICE-TASK"),
            ("failed-actionable", None),
        ):
            conn.execute(
                "insert into route_jobs(dedupe_key,task_id,route_kind,state,last_error,"
                "created_at,updated_at) values(?,?,?,'FAILED_BOUNDED','x',datetime('now'),datetime('now'))",
                (key, task_id, "AI"),
            )
        # Zero-cost transient AI failures are retryable and intentionally do
        # not poison health. Mark the unscoped fixture as retry-exhausted so
        # this test still proves one genuinely actionable bounded failure.
        conn.execute(
            "update route_jobs set attempt_count=2 "
            "where dedupe_key='failed-actionable'"
        )
        conn.commit()

        status = route_status(conn, test_config())

        self.assertEqual(1, status.failed)

    def test_integrated_copilot_candidates_are_not_reported_as_queued(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        for route_id, task_id, sha in (
            (1, "INTEGRATED-TASK", "a" * 40),
            (2, "WAITING-TASK", "b" * 40),
        ):
            conn.execute(
                "insert into route_jobs(id,dedupe_key,task_id,route_kind,state,"
                "created_at,updated_at) values(?,?,?,?,?,datetime('now'),datetime('now'))",
                (route_id, f"copilot:{task_id}", task_id, "COPILOT", "QUEUED"),
            )
            conn.execute(
                "insert into copilot_jobs(route_job_id,task_id,branch,base_sha,"
                "candidate_sha,state,created_at,updated_at) "
                "values(?,?,?,?,?,'QUEUED',datetime('now'),datetime('now'))",
                (route_id, task_id, f"copilot/{task_id.lower()}", "c" * 40, sha),
            )
        conn.execute(
            "insert into integration_queue(task_id,sha,branch,status,queued_at,"
            "updated_at,note,integrated_at) "
            "values(?,?,?,'INTEGRATED',datetime('now'),datetime('now'),'done',datetime('now'))",
            ("INTEGRATED-TASK", "a" * 40, "copilot/integrated-task"),
        )
        conn.commit()

        status = route_status(conn, test_config())

        self.assertEqual(1, status.copilot_queued)

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

        self.assertIn("SYSTEM_TOOL_DIRS", doctor)
        self.assertIn('Path("/usr/sbin")', doctor)
        self.assertIn("except FileNotFoundError", doctor)

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
            "runtime_deployment",
        ):
            self.assertIn(check, doctor)

        self.assertIn("routes)", lead)
        self.assertIn("logres-route-reconcile", lead)


if __name__ == "__main__":
    unittest.main()
