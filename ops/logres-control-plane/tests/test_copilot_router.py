import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db, seed_active_lease, seed_task, test_config
from logres_copilot import CopilotPacket, PolicyError, build_assignment, build_issue_body
from logres_copilot_router import copilot_eligibility, dispatch_task
from logres_route_store import ensure_route_schema


class FakeGitHub:
    def __init__(self):
        self.issue_create_calls = 0
        self.assignment_calls = 0
        self.issues = []
        self.assignments = []

    def create_issue(self, repo, title, body):
        self.issue_create_calls += 1
        number = 100 + self.issue_create_calls
        self.issues.append({"number": number, "repo": repo, "title": title, "body": body})
        return number

    def assign_copilot(self, repo, issue_number, payload):
        self.assignment_calls += 1
        self.assignments.append(
            {"repo": repo, "issue_number": issue_number, "payload": payload}
        )
def add_scope(conn, task_id, path):
    conn.execute(
        "insert into task_scopes(task_id,path_prefix) values(?,?)",
        (task_id, path),
    )
    conn.commit()


class CopilotRouterTests(unittest.TestCase):
    def test_research_task_is_not_copilot_eligible(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(conn, task_id="T1", work_type="research", status="READY")
        add_scope(conn, "T1", "src/research")
        result = copilot_eligibility(conn, "T1", "b" * 40, test_config())
        self.assertFalse(result.allowed)
        self.assertIn("work_type", result.reason)

    def test_missing_acceptance_criteria_is_rejected(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(
            conn,
            task_id="T1",
            work_type="implementation",
            status="READY",
            acceptance=(),
        )
        add_scope(conn, "T1", "src/a.ts")
        result = copilot_eligibility(conn, "T1", "b" * 40, test_config())
        self.assertFalse(result.allowed)
        self.assertIn("acceptance", result.reason)

    def test_missing_scope_is_rejected(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(conn, task_id="T1", work_type="implementation", status="READY")
        result = copilot_eligibility(conn, "T1", "b" * 40, test_config())
        self.assertFalse(result.allowed)
        self.assertIn("scope", result.reason)
    def test_active_overlap_is_rejected(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(
            conn,
            task_id="T1",
            work_type="implementation",
            status="READY",
            concurrency_key="field",
        )
        add_scope(conn, "T1", "src/game/field")
        seed_task(
            conn,
            task_id="ACTIVE",
            work_type="implementation",
            status="ACTIVE",
            concurrency_key="field",
        )
        add_scope(conn, "ACTIVE", "src/game/field/render")
        seed_active_lease(
            conn,
            task_id="ACTIVE",
            chat_id="builder",
            branch="worker/active",
        )
        conn.execute(
            "insert into claims(path_prefix,task_id,owner,branch,created_at,note) values(?,?,?,?,datetime('now'),'')",
            ("src/game/field/render", "ACTIVE", "builder", "worker/active"),
        )
        conn.commit()

        result = copilot_eligibility(conn, "T1", "b" * 40, test_config())
        self.assertFalse(result.allowed)
        self.assertIn("overlap", result.reason)

    def test_main_can_never_be_target(self):
        packet = CopilotPacket(
            task_id="T1",
            title="Bounded helper",
            base_sha="b" * 40,
            evidence_summary="CONFIRMED ORIGINAL: fixture",
            allowed_files=("src/a.ts",),
            forbidden_files=("main",),
            acceptance=("unit test passes",),
            tests=("npm test -- test-a",),
        )
        with self.assertRaises(PolicyError):
            build_assignment(packet, base_branch="main")
    def test_assignment_forces_integration_base_and_policy(self):
        packet = CopilotPacket(
            task_id="T1",
            title="Implement bounded helper",
            base_sha="b" * 40,
            evidence_summary="CONFIRMED ORIGINAL: fixture",
            allowed_files=("src/a.ts",),
            forbidden_files=("main",),
            acceptance=("unit test passes",),
            tests=("npm test -- test-a",),
        )
        payload = build_assignment(packet, base_branch="feat/logres-reconstruction")
        self.assertEqual(
            "feat/logres-reconstruction",
            payload["agent_assignment"]["base_branch"],
        )
        instructions = payload["agent_assignment"]["custom_instructions"]
        self.assertIn("Never modify main", instructions)
        self.assertIn("Do not self-merge", instructions)
        body = build_issue_body(packet)
        self.assertIn("Task ID: T1", body)
        self.assertIn("src/a.ts", body)
        self.assertIn("BLOCKED_EVIDENCE", body)

    def test_dispatch_is_disabled_by_default(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(conn, task_id="T1")
        add_scope(conn, "T1", "src/a.ts")
        github = FakeGitHub()
        with self.assertRaises(PolicyError):
            dispatch_task(conn, "T1", "b" * 40, test_config(), github)
        self.assertEqual(0, github.issue_create_calls)

    def test_same_task_revision_and_base_sha_reuses_existing_job(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(
            conn,
            task_id="T1",
            evidence_policy="CONFIRMED ORIGINAL Global evidence required",
        )
        add_scope(conn, "T1", "src/a.ts")
        config = test_config()
        config["routing"]["copilot_dispatch_enabled"] = True
        github = FakeGitHub()

        first = dispatch_task(conn, "T1", "b" * 40, config, github)
        second = dispatch_task(conn, "T1", "b" * 40, config, github)

        self.assertEqual(first.route_job_id, second.route_job_id)
        self.assertEqual(1, github.issue_create_calls)
        self.assertEqual(1, github.assignment_calls)
        self.assertEqual(first.job.id, second.job.id)


if __name__ == "__main__":
    unittest.main()
