import sqlite3
import sys
import unittest
from pathlib import Path

CONTROL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTROL_ROOT / "lib"))

from logres_capability_broker import (
    audit_unused,
    ensure_schema,
    recommend,
    record_usage,
    report,
    seed_defaults,
    set_health,
)


class CapabilityBrokerTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(":memory:")
        self.c.row_factory = sqlite3.Row
        ensure_schema(self.c)
        self.c.executescript(
            """
            create table tasks(
              id text primary key,priority integer,lane text,title text,
              status text,branch text,owner text,note text,updated_at text
            );
            create table task_scopes(
              task_id text not null,path_prefix text not null,
              primary key(task_id,path_prefix)
            );
            """
        )
        seed_defaults(self.c)

    def tearDown(self):
        self.c.close()

    def add_task(self, task_id, title, lane="control-plane", note="", scopes=()):
        self.c.execute(
            "insert into tasks values(?,?,?,?,?,?,?,?,datetime('now'))",
            (task_id, 0, lane, title, "ACTIVE", "", "worker", note),
        )
        for scope in scopes:
            self.c.execute("insert into task_scopes values(?,?)", (task_id, scope))
        self.c.commit()

    def test_repo_task_prefers_github(self):
        self.add_task(
            "REPO-001",
            "Inspect GitHub repository branch and commit history",
            scopes=("src/game/battle",),
        )
        out = recommend(self.c, "REPO-001")
        self.assertTrue(out["use_tool"])
        self.assertEqual("github", out["ready"][0]["capability"]["capability_id"])

    def test_vm_task_prefers_remote_desktop(self):
        self.add_task(
            "VM-001",
            "Inspect Oracle VM runtime logs and restart process",
            scopes=("ops/logres-control-plane",),
        )
        out = recommend(self.c, "VM-001")
        ids = [x["capability"]["capability_id"] for x in out["ready"]]
        self.assertEqual("remote-desktop", ids[0])

    def test_unknown_provider_is_recommended_for_connection_check_not_claimed_ready(self):
        self.add_task(
            "DOC-001",
            "Read the Google Drive design document and compare spreadsheet data",
        )
        out = recommend(self.c, "DOC-001")
        self.assertFalse(any(
            x["capability"]["capability_id"] == "google-drive"
            for x in out["ready"]
        ))
        self.assertTrue(any(
            x["capability"]["capability_id"] == "google-drive"
            for x in out["needs_connection_check"]
        ))

    def test_disconnected_capability_is_excluded(self):
        self.add_task("FIGMA-001", "Review Figma UI component design")
        set_health(
            self.c,
            "figma",
            connection_state="DISCONNECTED",
            health="UNHEALTHY",
        )
        out = recommend(self.c, "FIGMA-001")
        self.assertFalse(any(
            x["capability"]["capability_id"] == "figma"
            for x in out["recommended"]
        ))

    def test_usage_telemetry_changes_report(self):
        record_usage(
            self.c,
            capability_id="github",
            outcome="SUCCESS",
            useful=True,
            task_id="REPO-001",
            action="repo_read",
            latency_ms=120,
        )
        github = next(x for x in report(self.c) if x["capability_id"] == "github")
        self.assertEqual(1, github["stats"]["uses"])
        self.assertEqual(1.0, github["stats"]["success_rate"])
        self.assertEqual(1.0, github["stats"]["useful_rate"])

    def test_unused_audit_surfaces_relevant_never_used_tool(self):
        self.add_task("DB-001", "Inspect Supabase Postgres database schema and SQL")
        rows = audit_unused(self.c, min_score=3.0)
        match = [x for x in rows if x["task_id"] == "DB-001" and x["capability_id"] == "supabase"]
        self.assertTrue(match)
        self.assertTrue(match[0]["needs_connection_check"])

    def test_unused_audit_skips_generated_regression_noise(self):
        self.add_task("REG-CANDIDATE-XYZ", "Research current web documentation")
        rows = audit_unused(self.c, min_score=2.0)
        self.assertFalse(any(x["task_id"] == "REG-CANDIDATE-XYZ" for x in rows))

    def test_substring_collisions_do_not_create_false_tool_matches(self):
        self.add_task("ARTIFACT-001", "Reconcile artifact scheduler runtime state")
        out = recommend(self.c, "ARTIFACT-001", min_score=2.0)
        ids = {x["capability"]["capability_id"] for x in out["recommended"]}
        self.assertNotIn("image-generation", ids)
        self.assertNotIn("google-calendar", ids)

    def test_no_material_match_does_not_force_tool(self):
        self.add_task("THINK-001", "Reason about deterministic finite state machine invariants")
        out = recommend(self.c, "THINK-001", min_score=4.0)
        self.assertFalse(out["use_tool"])


if __name__ == "__main__":
    unittest.main()
