import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TAKEOVER = REPO_ROOT / "ops/logres-control-plane/bin/logres-lead-takeover"
INTEGRATION = "feat/logres-reconstruction"


def run(cmd, cwd=None, env=None, check=True):
    return subprocess.run(
        cmd, cwd=cwd, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check,
    )


def git(repo, *args):
    return run(["git", *args], cwd=repo).stdout.strip()


class LeadContinuityTests(unittest.TestCase):
    def make_fixture(self, root: Path):
        origin = root / "origin.git"
        repo = root / "repo"
        run(["git", "init", "--bare", str(origin)])
        run(["git", "init", "-b", INTEGRATION, str(repo)])
        git(repo, "config", "user.email", "test@example.com")
        git(repo, "config", "user.name", "Test")
        (repo / "README.md").write_text("base\n")
        git(repo, "add", "README.md")
        git(repo, "commit", "-m", "base")
        git(repo, "remote", "add", "origin", str(origin))
        git(repo, "push", "-u", "origin", INTEGRATION)
        git(repo, "branch", "worker/legacy")
        integration_sha = git(repo, "rev-parse", "HEAD")

        control = root / "control"
        bindir = root / "bin"
        control.mkdir()
        bindir.mkdir()
        db = control / "control.sqlite"
        self.make_db(db)
        (control / "LEAD_ACTION.txt").write_text("Integrate verified work\n")
        self.make_stubs(bindir)

        env = os.environ.copy()
        env.update({
            "LOGRES_ROOT": str(root),
            "LOGRES_REPO_ROOT": str(repo),
            "LOGRES_CONTROL_DB": str(db),
            "LOGRES_INTEGRATION_LOCK": str(root / "integration.lock"),
        })
        return repo, db, env, integration_sha

    def make_db(self, path: Path):
        c = sqlite3.connect(path)
        c.executescript("""
        create table meta(key text primary key,value text not null);
        create table tasks(
          id text primary key,status text,title text,note text,
          branch text,owner text,updated_at text);
        create table brain_task_leases(
          task_id text primary key,chat_id text,branch text,
          lease_until_epoch real,acquired_at text,renewed_at text,
          progress integer,note text);
        create table claims(
          path_prefix text primary key,task_id text,owner text,
          branch text,created_at text,note text);
        create table brain_members(
          chat_id text primary key,status text,last_seen_epoch real);
        """)
        c.execute(
            "insert into tasks values(?,?,?,?,?,?,?)",
            ("LEGACY-1", "ACTIVE", "Legacy lead work", "", "worker/legacy", "lead", "now"),
        )
        c.execute(
            "insert into brain_task_leases values(?,?,?,?,?,?,?,?)",
            ("LEGACY-1", "lead", "worker/legacy", 9999999999, "now", "now", 50, ""),
        )
        c.execute(
            "insert into claims values(?,?,?,?,?,?)",
            ("src/legacy", "LEGACY-1", "lead", "worker/legacy", "now", ""),
        )
        c.execute("insert into brain_members values('lead','ACTIVE',0)")
        c.commit()
        c.close()

    def make_stubs(self, bindir: Path):
        scripts = {
            "logres-coordinator": "#!/bin/sh\n[ \"$1\" = plan ] && echo plan || exit 0\n",
            "logres-merge-train": "#!/bin/sh\necho train-empty\n",
            "logres-integration-pager": "#!/bin/sh\nexit 0\n",
            "logres-merge-preflight": "#!/bin/sh\necho preflight-none\n",
            "logres-brain": "#!/bin/sh\n[ \"$1\" = digest ] && echo brain-digest\nexit 0\n",
            "logres-stale-work-recover": "#!/bin/sh\necho recovery-unused\n",
        }
        for name, body in scripts.items():
            path = bindir / name
            path.write_text(body)
            path.chmod(0o755)
    def test_readiness_check_is_non_mutating(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _, db, env, sha = self.make_fixture(root)
            p = run([sys.executable, str(TAKEOVER)], env=env, check=False)

            self.assertEqual(0, p.returncode, p.stderr)
            self.assertIn("LEAD_TAKEOVER_CHECK PASS", p.stdout)
            self.assertIn(f"integration={sha}", p.stdout)
            c = sqlite3.connect(db)
            self.assertEqual(
                ("ACTIVE", "lead"),
                c.execute("select status,owner from tasks where id='LEGACY-1'").fetchone(),
            )
            self.assertIsNotNone(
                c.execute("select 1 from brain_task_leases where task_id='LEGACY-1'").fetchone()
            )
            self.assertIsNone(c.execute("select value from meta where key='lead_generation'").fetchone())
            c.close()
            self.assertFalse((root / "control/LEAD_TAKEOVER.txt").exists())

    def test_apply_requeues_legacy_lead_work_and_writes_packet(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo, db, env, sha = self.make_fixture(root)
            p = run([sys.executable, str(TAKEOVER), "--apply"], env=env, check=False)

            self.assertEqual(0, p.returncode, p.stderr)
            self.assertIn("LEAD_TAKEOVER_READY generation=1", p.stdout)
            c = sqlite3.connect(db)
            row = c.execute(
                "select status,owner,branch,note from tasks where id='LEGACY-1'"
            ).fetchone()
            self.assertEqual(("READY", None, "worker/legacy"), row[:3])
            self.assertIn("failover", row[3].lower())
            self.assertIsNone(
                c.execute("select 1 from brain_task_leases where task_id='LEGACY-1'").fetchone()
            )
            self.assertIsNone(c.execute("select 1 from claims where task_id='LEGACY-1'").fetchone())
            self.assertEqual(
                "1", c.execute("select value from meta where key='lead_generation'").fetchone()[0]
            )
            c.close()
            packet = (root / "control/LEAD_TAKEOVER.txt").read_text()
            self.assertIn(f"integration={sha}", packet)
            self.assertIn("task=LEGACY-1", packet)
            self.assertEqual(INTEGRATION, git(repo, "branch", "--show-current"))
            self.assertIn("worker/legacy", git(repo, "branch", "--list", "worker/legacy"))

    def test_dirty_integration_blocks_failover_without_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo, db, env, _ = self.make_fixture(root)
            (repo / "dirty.txt").write_text("dirty\n")
            p = run([sys.executable, str(TAKEOVER), "--apply"], env=env, check=False)

            self.assertNotEqual(0, p.returncode)
            self.assertIn("integration worktree is dirty", p.stderr + p.stdout)
            c = sqlite3.connect(db)
            self.assertEqual(
                ("ACTIVE", "lead"),
                c.execute("select status,owner from tasks where id='LEGACY-1'").fetchone(),
            )
            self.assertIsNotNone(
                c.execute("select 1 from brain_task_leases where task_id='LEGACY-1'").fetchone()
            )
            c.close()


if __name__ == "__main__":
    unittest.main()
