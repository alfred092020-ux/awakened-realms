import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db, seed_task
from logres_copilot import CopilotJobRecord
from logres_copilot_router import reconcile_copilot_job
from logres_route_store import RouteSpec, claim_route, ensure_route_schema, transition_route


class FakeGitHub:
    def __init__(self):
        self.list_prs_result = []

    def list_prs(self, repo):
        return self.list_prs_result


class FakeCommandRunner:
    def __init__(self, scope_rc=0, gate_rc=0):
        self.scope_rc = scope_rc
        self.gate_rc = gate_rc
        self.scope_calls = []
        self.gate_calls = []
        self.reconcile_calls = []
        self.regression_calls = []
        self.conflict_calls = []

    def scope_check(self, task_id, branch):
        self.scope_calls.append([task_id, branch])
        return self.scope_rc

    def fast_gate(self, branch):
        self.gate_calls.append(["logres-gate", "fast", branch])
        return self.gate_rc

    def coordinator_reconcile(self, conn, task_id, branch, sha):
        self.reconcile_calls.append([task_id, branch, sha])
        conn.execute(
            "insert into verification(ref,sha,mode,status,duration_sec,ran_at,details) values(?,?,?,'PASS',0,datetime('now'),'fake')",
            (branch, sha, "fast"),
        )
        conn.execute(
            "insert into integration_queue(task_id,sha,branch,status,verification_mode,queued_at,updated_at,note) values(?,?,?,'READY_FOR_PREFLIGHT','fast',datetime('now'),datetime('now'),'fake coordinator')",
            (task_id, sha, branch),
        )
        conn.commit()
        return 0

    def capture_regression(self, task_id, branch, sha):
        self.regression_calls.append([task_id, branch, sha])

    def post_scope_conflict(self, task_id, branch, sha):
        self.conflict_calls.append([task_id, branch, sha])
def seed_pr_ready_job(conn, base_sha="b" * 40, candidate_sha="c" * 40):
    ensure_route_schema(conn)
    seed_task(conn, task_id="T1", status="READY")
    conn.execute(
        "insert into task_scopes(task_id,path_prefix) values(?,?)",
        ("T1", "src/a.ts"),
    )
    route = claim_route(
        conn,
        RouteSpec(
            dedupe_key="copilot:T1",
            route_kind="COPILOT",
            task_id="T1",
            base_sha=base_sha,
        ),
    )
    transition_route(conn, route.id, "NEW", "ROUTED")
    transition_route(conn, route.id, "ROUTED", "ASSIGNING")
    transition_route(conn, route.id, "ASSIGNING", "ACTIVE")
    transition_route(conn, route.id, "ACTIVE", "PR_READY")
    conn.execute(
        """insert into copilot_jobs(
             route_job_id,task_id,issue_number,pr_number,branch,base_sha,
             candidate_sha,state,last_error,created_at,updated_at
           ) values(?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))""",
        (
            route.id,
            "T1",
            7,
            9,
            "copilot/t1",
            base_sha,
            candidate_sha,
            "PR_READY",
            None,
        ),
    )
    conn.commit()
    return CopilotJobRecord(
        id=1,
        route_job_id=route.id,
        task_id="T1",
        issue_number=7,
        pr_number=9,
        branch="copilot/t1",
        base_sha=base_sha,
        candidate_sha=candidate_sha,
        state="PR_READY",
        last_error=None,
    )
class CopilotReturnPathTests(unittest.TestCase):
    def test_stale_base_requires_revalidation_not_auto_queue(self):
        conn = make_test_db()
        job = seed_pr_ready_job(conn, base_sha="a" * 40)
        commands = FakeCommandRunner()

        result = reconcile_copilot_job(
            job,
            gh_runner=FakeGitHub(),
            command_runner=commands,
            current_integration_sha="b" * 40,
            conn=conn,
        )

        self.assertEqual("VERIFYING", result.state)
        self.assertTrue(result.revalidation_required)
        self.assertEqual([], commands.gate_calls)
        self.assertEqual(
            0,
            conn.execute("select count(*) from integration_queue").fetchone()[0],
        )

    def test_forbidden_scope_is_terminal_scope_violation(self):
        conn = make_test_db()
        job = seed_pr_ready_job(conn)
        commands = FakeCommandRunner(scope_rc=1, gate_rc=0)

        result = reconcile_copilot_job(
            job,
            gh_runner=FakeGitHub(),
            command_runner=commands,
            current_integration_sha="b" * 40,
            conn=conn,
        )

        self.assertEqual("SCOPE_VIOLATION", result.state)
        self.assertEqual([], commands.gate_calls)
        self.assertEqual(1, len(commands.conflict_calls))

    def test_fast_gate_failure_captures_regression_and_never_queues(self):
        conn = make_test_db()
        job = seed_pr_ready_job(conn)
        commands = FakeCommandRunner(scope_rc=0, gate_rc=1)

        result = reconcile_copilot_job(
            job,
            gh_runner=FakeGitHub(),
            command_runner=commands,
            current_integration_sha="b" * 40,
            conn=conn,
        )

        self.assertEqual("FAILED_BOUNDED", result.state)
        self.assertEqual(1, len(commands.regression_calls))
        self.assertEqual(
            0,
            conn.execute("select count(*) from integration_queue").fetchone()[0],
        )

    def test_active_job_discovers_draft_pr_and_candidate_sha(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(conn, task_id="T1", status="READY")
        conn.execute(
            "insert into task_scopes(task_id,path_prefix) values(?,?)",
            ("T1", "src/a.ts"),
        )
        route = claim_route(
            conn,
            RouteSpec(
                dedupe_key="copilot:T1:active",
                route_kind="COPILOT",
                task_id="T1",
                base_sha="b" * 40,
            ),
        )
        transition_route(conn, route.id, "NEW", "ROUTED")
        transition_route(conn, route.id, "ROUTED", "ASSIGNING")
        transition_route(conn, route.id, "ASSIGNING", "ACTIVE")
        conn.execute(
            """insert into copilot_jobs(
                 route_job_id,task_id,issue_number,pr_number,branch,base_sha,
                 candidate_sha,state,last_error,created_at,updated_at
               ) values(?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))""",
            (
                route.id, "T1", 7, None, "copilot/t1", "b" * 40,
                None, "ACTIVE", None,
            ),
        )
        conn.commit()
        job = CopilotJobRecord(
            id=1,
            route_job_id=route.id,
            task_id="T1",
            issue_number=7,
            pr_number=None,
            branch="copilot/t1",
            base_sha="b" * 40,
            candidate_sha=None,
            state="ACTIVE",
            last_error=None,
        )
        github = FakeGitHub()
        github.list_prs_result = [
            {
                "number": 9,
                "headRefName": "copilot/t1",
                "headRefOid": "c" * 40,
                "baseRefName": "feat/logres-reconstruction",
                "isDraft": True,
                "body": "Closes #7",
            }
        ]

        result = reconcile_copilot_job(
            job,
            gh_runner=github,
            command_runner=FakeCommandRunner(),
            current_integration_sha="b" * 40,
            conn=conn,
        )

        self.assertEqual("QUEUED", result.state)
        stored = conn.execute(
            "select pr_number,candidate_sha from copilot_jobs where route_job_id=?",
            (route.id,),
        ).fetchone()
        self.assertEqual((9, "c" * 40), tuple(stored))


    def test_branch_move_supersedes_old_candidate_instead_of_mutating_sha(self):
        conn = make_test_db()
        job = seed_pr_ready_job(conn, candidate_sha="c" * 40)
        github = FakeGitHub()
        github.list_prs_result = [
            {
                "number": 9,
                "headRefName": "copilot/t1",
                "headRefOid": "d" * 40,
                "baseRefName": "feat/logres-reconstruction",
                "isDraft": True,
                "body": "Closes #7",
            }
        ]

        result = reconcile_copilot_job(
            job,
            gh_runner=github,
            command_runner=FakeCommandRunner(scope_rc=0, gate_rc=0),
            current_integration_sha="b" * 40,
            conn=conn,
        )

        self.assertEqual("QUEUED", result.state)
        self.assertNotEqual(job.route_job_id, result.route_job_id)
        old = conn.execute(
            "select state,candidate_sha from copilot_jobs where route_job_id=?",
            (job.route_job_id,),
        ).fetchone()
        self.assertEqual(("SUPERSEDED", "c" * 40), tuple(old))
        new = conn.execute(
            "select candidate_sha from copilot_jobs where route_job_id=?",
            (result.route_job_id,),
        ).fetchone()
        self.assertEqual("d" * 40, new[0])

    def test_green_candidate_uses_fast_gate_then_normal_queue(self):
        conn = make_test_db()
        job = seed_pr_ready_job(conn)
        commands = FakeCommandRunner(scope_rc=0, gate_rc=0)

        result = reconcile_copilot_job(
            job,
            gh_runner=FakeGitHub(),
            command_runner=commands,
            current_integration_sha="b" * 40,
            conn=conn,
        )

        self.assertEqual("QUEUED", result.state)
        self.assertEqual(
            [["logres-gate", "fast", "copilot/t1"]],
            commands.gate_calls,
        )
        self.assertEqual(
            1,
            conn.execute(
                "select count(*) from integration_queue where task_id=? and sha=?",
                ("T1", "c" * 40),
            ).fetchone()[0],
        )
        task = conn.execute(
            "select status,branch from tasks where id='T1'"
        ).fetchone()
        self.assertEqual(("DONE", "copilot/t1"), tuple(task))

    def test_active_job_adopts_matching_pr_and_queues_candidate(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        seed_task(conn, task_id="T1", status="READY")
        conn.execute(
            "insert into task_scopes(task_id,path_prefix) values(?,?)",
            ("T1", "src/a.ts"),
        )
        route = claim_route(
            conn,
            RouteSpec(
                dedupe_key="copilot:active:T1",
                route_kind="COPILOT",
                task_id="T1",
                base_sha="b" * 40,
            ),
        )
        transition_route(conn, route.id, "NEW", "ROUTED")
        transition_route(conn, route.id, "ROUTED", "ASSIGNING")
        transition_route(conn, route.id, "ASSIGNING", "ACTIVE")
        conn.execute(
            """insert into copilot_jobs(
                 route_job_id,task_id,issue_number,pr_number,branch,base_sha,
                 candidate_sha,state,last_error,created_at,updated_at
               ) values(?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))""",
            (route.id, "T1", 7, None, "copilot/t1", "b" * 40, None, "ACTIVE", None),
        )
        conn.commit()
        job = CopilotJobRecord(
            id=1,
            route_job_id=route.id,
            task_id="T1",
            issue_number=7,
            pr_number=None,
            branch="copilot/t1",
            base_sha="b" * 40,
            candidate_sha=None,
            state="ACTIVE",
            last_error=None,
        )
        github = FakeGitHub()
        github.list_prs_result = [{
            "number": 9,
            "headRefName": "copilot/t1",
            "headRefOid": "d" * 40,
            "baseRefName": "feat/logres-reconstruction",
            "isDraft": True,
            "body": "Closes #7",
        }]
        commands = FakeCommandRunner()

        result = reconcile_copilot_job(
            job, github, commands, "b" * 40, conn
        )

        self.assertEqual("QUEUED", result.state)
        self.assertEqual("d" * 40, result.candidate_sha)
        self.assertEqual(
            1,
            conn.execute(
                "select count(*) from integration_queue where task_id='T1' and sha=?",
                ("d" * 40,),
            ).fetchone()[0],
        )

    def test_moved_pr_supersedes_old_candidate_instead_of_mutating_it(self):
        conn = make_test_db()
        job = seed_pr_ready_job(conn, candidate_sha="c" * 40)
        github = FakeGitHub()
        github.list_prs_result = [{
            "number": 9,
            "headRefName": "copilot/t1",
            "headRefOid": "d" * 40,
            "baseRefName": "feat/logres-reconstruction",
            "isDraft": True,
            "body": "Closes #7",
        }]
        commands = FakeCommandRunner()

        result = reconcile_copilot_job(
            job, github, commands, "b" * 40, conn
        )

        self.assertEqual("QUEUED", result.state)
        self.assertEqual("d" * 40, result.candidate_sha)
        old = conn.execute(
            "select state,candidate_sha from copilot_jobs where route_job_id=?",
            (job.route_job_id,),
        ).fetchone()
        self.assertEqual(("SUPERSEDED", "c" * 40), tuple(old))
        self.assertEqual(
            0,
            conn.execute(
                "select count(*) from integration_queue where sha=?",
                ("c" * 40,),
            ).fetchone()[0],
        )
        self.assertEqual(
            1,
            conn.execute(
                "select count(*) from integration_queue where sha=?",
                ("d" * 40,),
            ).fetchone()[0],
        )

    def test_prepared_remote_ref_is_used_for_verification_and_queue(self):
        conn = make_test_db()
        job = seed_pr_ready_job(conn)

        class PreparingRunner(FakeCommandRunner):
            def __init__(self):
                super().__init__(scope_rc=0, gate_rc=0)
                self.prepare_calls = []

            def prepare_ref(self, branch):
                self.prepare_calls.append(branch)
                return f"origin/{branch}"

        commands = PreparingRunner()
        result = reconcile_copilot_job(
            job,
            gh_runner=FakeGitHub(),
            command_runner=commands,
            current_integration_sha="b" * 40,
            conn=conn,
        )

        self.assertEqual(["copilot/t1"], commands.prepare_calls)
        self.assertEqual(
            [["T1", "origin/copilot/t1"]],
            commands.scope_calls,
        )
        self.assertEqual(
            [["logres-gate", "fast", "origin/copilot/t1"]],
            commands.gate_calls,
        )
        self.assertEqual("origin/copilot/t1", result.branch)
        task = conn.execute(
            "select branch from tasks where id='T1'"
        ).fetchone()
        self.assertEqual("origin/copilot/t1", task[0])


if __name__ == "__main__":
    unittest.main()
