import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
CONTROL_ROOT = TEST_DIR.parent
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db, seed_task
from logres_workspace_gc import (
    POLICY,
    apply_plan,
    db_revalidate,
    eligibility,
    plan_records,
)


def git(*args, cwd=None):
    return subprocess.check_output(
        ["git", *args],
        cwd=cwd,
        text=True,
    ).strip()


class WorkspaceGcEligibilityTests(unittest.TestCase):
    def setUp(self):
        self.work_root = Path("/tmp/logres-test-root/work")
        self.base = {
            "path": str(self.work_root / "worker-safe"),
            "branch": "worker/safe",
            "task_id": "SAFE",
            "task_status": "DONE",
            "active_lease": False,
            "dirty": False,
            "unique_commits": 3,
            "integrated": True,
            "protected": False,
        }

    def test_clean_integrated_terminal_is_eligible_even_with_unique_branch_commit(self):
        result = eligibility(
            self.base,
            work_root=self.work_root,
        )
        self.assertTrue(result.eligible)
        self.assertEqual("ARCHIVE_CANDIDATE", result.reason)

    def test_dirty_never_removed(self):
        record = {**self.base, "dirty": True}
        result = eligibility(record, work_root=self.work_root)
        self.assertFalse(result.eligible)
        self.assertEqual("DIRTY", result.reason)

    def test_active_lease_never_removed(self):
        record = {**self.base, "active_lease": True}
        result = eligibility(record, work_root=self.work_root)
        self.assertFalse(result.eligible)
        self.assertEqual("ACTIVE", result.reason)

    def test_unintegrated_never_removed(self):
        record = {**self.base, "integrated": False}
        result = eligibility(record, work_root=self.work_root)
        self.assertFalse(result.eligible)
        self.assertEqual("NOT_INTEGRATED", result.reason)

    def test_outside_managed_root_never_removed(self):
        record = {**self.base, "path": "/tmp/some-other-tree"}
        result = eligibility(record, work_root=self.work_root)
        self.assertFalse(result.eligible)
        self.assertEqual(
            "OUTSIDE_MANAGED_WORK_ROOT",
            result.reason,
        )

    def test_protected_branch_never_removed(self):
        record = {
            **self.base,
            "branch": "feat/logres-reconstruction",
        }
        result = eligibility(record, work_root=self.work_root)
        self.assertFalse(result.eligible)
        self.assertEqual("PROTECTED", result.reason)

    def test_plan_is_bounded_and_non_destructive(self):
        records = [
            {
                **self.base,
                "path": str(self.work_root / f"worker-{index}"),
                "branch": f"worker/{index}",
                "task_id": f"T{index}",
            }
            for index in range(10)
        ]

        plan = plan_records(
            records,
            work_root=self.work_root,
            limit=3,
        )

        self.assertEqual(POLICY, plan["policy"])
        self.assertEqual(3, len(plan["selected"]))
        self.assertEqual(10, plan["eligible_total"])


class WorkspaceGcDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.conn = make_test_db()
        seed_task(
            self.conn,
            task_id="SAFE",
            status="DONE",
            work_type="implementation",
        )
        self.conn.execute(
            """insert into integration_queue(
                 task_id,sha,branch,status,verification_mode,
                 queued_at,updated_at,note,integrated_at
               ) values(
                 'SAFE',?,'worker/safe','INTEGRATED','full-e2e',
                 'now','now','integrated','now'
               )""",
            ("a" * 40,),
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_db_revalidation_requires_terminal_integrated_without_lease(self):
        result = db_revalidate(
            self.conn,
            {"task_id": "SAFE"},
        )
        self.assertTrue(result.eligible)

    def test_db_revalidation_rejects_new_lease(self):
        self.conn.execute(
            """insert into brain_task_leases(
                 task_id,chat_id,lease_until_epoch,acquired_at,renewed_at,
                 progress,note
               ) values('SAFE','worker',9999999999,'now','now',0,'live')"""
        )
        self.conn.commit()

        result = db_revalidate(
            self.conn,
            {"task_id": "SAFE"},
        )

        self.assertFalse(result.eligible)
        self.assertEqual("LEASE_APPEARED", result.reason)


class WorkspaceGcGitIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.work_root = self.root / "work"
        self.work_root.mkdir()
        self.repo.mkdir()

        subprocess.run(
            ["git", "init", "-b", "main"],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
        )
        git("config", "user.email", "test@example.com", cwd=self.repo)
        git("config", "user.name", "Test", cwd=self.repo)
        (self.repo / "README").write_text("base\n")
        git("add", "README", cwd=self.repo)
        git("commit", "-m", "base", cwd=self.repo)
        git(
            "branch",
            "feat/logres-reconstruction",
            cwd=self.repo,
        )
        git("branch", "worker/safe", cwd=self.repo)

        self.worktree = self.work_root / "worker-safe"
        git(
            "worktree",
            "add",
            str(self.worktree),
            "worker/safe",
            cwd=self.repo,
        )
        (self.worktree / "unique.txt").write_text("unique\n")
        git("add", "unique.txt", cwd=self.worktree)
        git("commit", "-m", "unique worker commit", cwd=self.worktree)
        self.branch_sha = git(
            "rev-parse",
            "worker/safe",
            cwd=self.repo,
        )

        self.conn = make_test_db()
        seed_task(
            self.conn,
            task_id="SAFE",
            status="DONE",
            work_type="implementation",
        )
        self.conn.execute(
            """update tasks
                  set branch='worker/safe'
                where id='SAFE'"""
        )
        self.conn.execute(
            """insert into integration_queue(
                 task_id,sha,branch,status,verification_mode,
                 queued_at,updated_at,note,integrated_at
               ) values(
                 'SAFE',?,'worker/safe','INTEGRATED','full-e2e',
                 'now','now','equivalent integrated result','now'
               )""",
            (self.branch_sha,),
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def record(self):
        return {
            "path": str(self.worktree),
            "branch": "worker/safe",
            "task_id": "SAFE",
            "task_status": "DONE",
            "active_lease": False,
            "dirty": False,
            "unique_commits": 1,
            "integrated": True,
            "protected": False,
        }

    def test_apply_removes_worktree_but_preserves_branch_exact_sha(self):
        report = apply_plan(
            self.conn,
            self.repo,
            [self.record()],
            work_root=self.work_root,
            limit=1,
        )

        self.assertEqual(1, report["removed"])
        self.assertEqual(0, report["branch_preservation_failures"])
        self.assertFalse(self.worktree.exists())
        after = git(
            "rev-parse",
            "worker/safe",
            cwd=self.repo,
        )
        self.assertEqual(self.branch_sha, after)
        self.assertEqual(
            POLICY,
            report["policy"],
        )
        self.assertFalse(report["safety"]["delete_local_branch"])
        self.assertFalse(report["safety"]["delete_remote_branch"])
        self.assertFalse(report["safety"]["force_remove"])

    def test_dirty_race_is_skipped_by_live_revalidation(self):
        (self.worktree / "dirty.txt").write_text("dirty\n")

        report = apply_plan(
            self.conn,
            self.repo,
            [self.record()],
            work_root=self.work_root,
            limit=1,
        )

        self.assertEqual(0, report["removed"])
        self.assertEqual(1, report["failed_or_skipped"])
        self.assertTrue(self.worktree.exists())
        self.assertEqual(
            "DIRTY_AT_APPLY",
            report["results"][0]["reason"],
        )


class WorkspaceGcMaintenanceTests(unittest.TestCase):
    def test_maintenance_runs_bounded_safe_workspace_gc(self):
        maintain = (
            CONTROL_ROOT / "bin" / "logres-maintain"
        ).read_text()
        self.assertIn(
            "logres-workspace-gc apply --limit 25",
            maintain,
        )


class WorkspaceGcSourceSafetyTests(unittest.TestCase):
    def test_cli_has_no_branch_deletion_or_force_option(self):
        cli = (
            CONTROL_ROOT / "bin" / "logres-workspace-gc"
        ).read_text()
        lib = (
            CONTROL_ROOT / "lib" / "logres_workspace_gc.py"
        ).read_text()

        self.assertNotIn("branch -D", cli)
        self.assertNotIn("push --delete", cli)
        self.assertNotIn("branch -D", lib)
        self.assertNotIn("push --delete", lib)
        self.assertIn(
            '["git", "-C", str(repo), "worktree", "remove", str(path)]',
            lib,
        )


if __name__ == "__main__":
    unittest.main()
