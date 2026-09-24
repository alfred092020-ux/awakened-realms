import json
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_copilot import SubprocessCommandRunner, SubprocessGitHubRunner


class CopilotSubprocessAdapterTests(unittest.TestCase):
    @patch("logres_copilot.subprocess.run")
    def test_github_pr_list_uses_bounded_metadata_query(self, run):
        run.return_value = SimpleNamespace(
            returncode=0,
            stdout=json.dumps([
                {
                    "number": 9,
                    "headRefName": "copilot/t1",
                    "headRefOid": "c" * 40,
                    "baseRefName": "feat/logres-reconstruction",
                    "isDraft": True,
                    "body": "Closes #7",
                }
            ]),
        )
        prs = SubprocessGitHubRunner().list_prs("alfred092020-ux/awakened-realms")
        self.assertEqual(9, prs[0]["number"])
        argv = run.call_args.args[0]
        self.assertEqual(["gh", "pr", "list"], argv[:3])
        self.assertIn("number,headRefName,headRefOid,baseRefName,isDraft,body", argv)

    @patch("logres_copilot.subprocess.run")
    def test_command_runner_reuses_existing_scope_gate_and_coordinator(self, run):
        run.side_effect = [
            SimpleNamespace(returncode=0, stdout="", stderr=""),
            SimpleNamespace(returncode=0, stdout="c" * 40 + "\n", stderr=""),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
        ]
        runner = SubprocessCommandRunner()

        @contextmanager
        def fake_verification_worktree(ref):
            self.assertEqual("origin/copilot/t1", ref)
            yield Path("/tmp/fake-copilot-wt")

        runner.verification_worktree = fake_verification_worktree

        ref = runner.prepare_ref("copilot/t1")
        self.assertEqual("origin/copilot/t1", ref)
        self.assertEqual("c" * 40, runner.resolve_sha(ref))
        self.assertEqual(0, runner.scope_check("T1", ref))
        self.assertEqual(0, runner.fast_gate(ref))
        self.assertEqual(0, runner.coordinator_reconcile(None, "T1", ref, "c" * 40))

        calls = [call.args[0] for call in run.call_args_list]
        self.assertIn(
            [
                "git", "-C", "/home/ubuntu/logres/src/awakened-realms",
                "fetch", "origin",
                "+refs/heads/copilot/t1:refs/remotes/origin/copilot/t1",
            ],
            calls,
        )
        self.assertIn(
            [
                "git", "-C", "/home/ubuntu/logres/src/awakened-realms",
                "rev-parse", ref,
            ],
            calls,
        )
        self.assertIn(
            ["/home/ubuntu/logres/bin/logres-scope-check", "T1", ref],
            calls,
        )
        gate_call = next(
            call for call in run.call_args_list
            if call.args[0][:2] == ["/home/ubuntu/logres/bin/logres-gate", "fast"]
        )
        self.assertEqual(
            ["/home/ubuntu/logres/bin/logres-gate", "fast", ref],
            gate_call.args[0],
        )
        self.assertEqual(Path("/tmp/fake-copilot-wt"), gate_call.kwargs["cwd"])
        self.assertIn(
            ["/home/ubuntu/logres/bin/logres-coordinator", "reconcile"],
            calls,
        )

    @patch("logres_copilot.subprocess.run")
    def test_command_runner_routes_failures_to_existing_helpers(self, run):
        run.return_value = SimpleNamespace(returncode=0, stdout="", stderr="")
        runner = SubprocessCommandRunner()
        runner.capture_regression("T1", "origin/copilot/t1", "c" * 40)
        runner.post_scope_conflict("T1", "origin/copilot/t1", "c" * 40)

        calls = [call.args[0] for call in run.call_args_list]
        regression = calls[0]
        self.assertEqual(
            "/home/ubuntu/logres/bin/logres-regression-capture",
            regression[0],
        )
        self.assertIn("--kind", regression)
        self.assertIn("copilot-fast-gate", regression)
        brain = calls[1]
        self.assertEqual("/home/ubuntu/logres/bin/logres-brain", brain[0])
        self.assertIn("CONFLICT", brain)
        self.assertIn("T1", brain)

    @patch("logres_copilot.subprocess.run")
    def test_resolve_sha_uses_git_rev_parse(self, run):
        run.return_value = SimpleNamespace(
            returncode=0,
            stdout=("c" * 40) + "\n",
            stderr="",
        )
        runner = SubprocessCommandRunner()
        sha = runner.resolve_sha("origin/copilot/t1")
        self.assertEqual("c" * 40, sha)
        self.assertEqual(
            [
                "git", "-C", "/home/ubuntu/logres/src/awakened-realms",
                "rev-parse", "origin/copilot/t1",
            ],
            run.call_args.args[0],
        )


if __name__ == "__main__":
    unittest.main()
