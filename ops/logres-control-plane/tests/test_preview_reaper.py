import signal
import sys
import tempfile
import unittest
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_preview_reaper import (
    PreviewProcess,
    WorktreeState,
    decide_preview,
    git_worktree_safe,
    preview_worktree_from_command,
    process_still_matches,
    reap,
)


ROOT = "/home/ubuntu/logres/work/worker-test"
COMMAND = (
    f"node {ROOT}/node_modules/.bin/vite preview "
    "--host 127.0.0.1 --port 4199"
)


def process(*, age=10800, rss=100 * 1024 * 1024, root=ROOT):
    return PreviewProcess(
        pid=1234,
        age_seconds=age,
        rss_bytes=rss,
        command=COMMAND.replace(ROOT, root),
        worktree_path=root,
    )


def worktree(
    *,
    dirty=0,
    merged=True,
    branch="worker/test",
    root=ROOT,
):
    return WorktreeState(
        path=root,
        branch=branch,
        dirty_count=dirty,
        merged_into_integration=merged,
    )


class PreviewReaperDecisionTests(unittest.TestCase):
    def test_parses_only_vite_preview_command(self):
        self.assertEqual(
            ROOT,
            preview_worktree_from_command(COMMAND),
        )
        self.assertIsNone(
            preview_worktree_from_command(
                f"node {ROOT}/node_modules/.bin/vite build"
            )
        )
        self.assertIsNone(
            preview_worktree_from_command(
                f"python3 {ROOT}/scripts/logres/oracle_worker.py"
            )
        )

    def test_clean_merged_inactive_old_preview_is_eligible(self):
        decision = decide_preview(
            process(),
            worktree(),
            set(),
            min_age_seconds=7200,
        )
        self.assertTrue(decision.eligible)
        self.assertEqual("eligible", decision.reason)

    def test_dirty_worktree_is_protected(self):
        decision = decide_preview(
            process(),
            worktree(dirty=1),
            set(),
            min_age_seconds=7200,
        )
        self.assertFalse(decision.eligible)
        self.assertEqual("dirty", decision.reason)

    def test_unmerged_worktree_is_protected(self):
        decision = decide_preview(
            process(),
            worktree(merged=False),
            set(),
            min_age_seconds=7200,
        )
        self.assertFalse(decision.eligible)
        self.assertEqual("unmerged", decision.reason)

    def test_active_worktree_is_protected(self):
        decision = decide_preview(
            process(),
            worktree(),
            {"worker/test"},
            min_age_seconds=7200,
        )
        self.assertFalse(decision.eligible)
        self.assertEqual("active", decision.reason)

    def test_unknown_worktree_is_protected(self):
        decision = decide_preview(
            process(),
            None,
            set(),
            min_age_seconds=7200,
        )
        self.assertFalse(decision.eligible)
        self.assertEqual("unknown-worktree", decision.reason)

    def test_young_preview_is_protected(self):
        decision = decide_preview(
            process(age=600),
            worktree(),
            set(),
            min_age_seconds=7200,
        )
        self.assertFalse(decision.eligible)
        self.assertEqual("young", decision.reason)

    def test_path_mismatch_is_protected(self):
        decision = decide_preview(
            process(root="/tmp/other"),
            worktree(),
            set(),
            min_age_seconds=7200,
        )
        self.assertFalse(decision.eligible)
        self.assertEqual("path-mismatch", decision.reason)


class PreviewReaperApplyTests(unittest.TestCase):
    def _proc_root(self, command=COMMAND):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        proc = root / "1234"
        proc.mkdir()
        (proc / "cmdline").write_bytes(
            command.replace(" ", "\0").encode() + b"\0"
        )
        return temp, root

    def test_process_match_requires_same_pid_command_and_root(self):
        temp, proc_root = self._proc_root()
        try:
            self.assertTrue(
                process_still_matches(
                    process(),
                    proc_root,
                )
            )
            (proc_root / "1234" / "cmdline").write_bytes(
                b"node\0/tmp/other/node_modules/.bin/vite\0preview\0"
            )
            self.assertFalse(
                process_still_matches(
                    process(),
                    proc_root,
                )
            )
        finally:
            temp.cleanup()

    def test_signal_time_validator_can_veto_candidate(self):
        calls = []
        temp, proc_root = self._proc_root()
        try:
            result = reap(
                [process()],
                proc_root=proc_root,
                term_wait_seconds=0,
                eligible_fn=lambda _: False,
                kill_fn=lambda pid, sig: calls.append((pid, sig)),
                sleep_fn=lambda _: None,
            )
        finally:
            temp.cleanup()
        self.assertEqual([], calls)
        self.assertEqual(0, result["term_sent"])

    def test_git_safety_requires_clean_and_merged_head(self):
        calls = []

        class Result:
            def __init__(self, returncode=0, stdout=""):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = ""

        def clean_runner(argv, **kwargs):
            calls.append(argv)
            if "status" in argv:
                return Result(0, "")
            if "rev-parse" in argv:
                return Result(0, "abc123\n")
            if "merge-base" in argv:
                return Result(0, "")
            return Result(1, "")

        self.assertTrue(
            git_worktree_safe(
                ROOT,
                Path("/repo"),
                runner=clean_runner,
            )
        )

        def dirty_runner(argv, **kwargs):
            if "status" in argv:
                return Result(0, " M file.ts\n")
            return Result(0, "")

        self.assertFalse(
            git_worktree_safe(
                ROOT,
                Path("/repo"),
                runner=dirty_runner,
            )
        )

    def test_already_exited_process_is_not_signaled(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            result = reap(
                [process()],
                proc_root=Path(tmp),
                term_wait_seconds=0,
                kill_fn=lambda pid, sig: calls.append((pid, sig)),
                sleep_fn=lambda _: None,
            )
        self.assertEqual([], calls)
        self.assertEqual(0, result["term_sent"])
        self.assertEqual(0, result["kill_sent"])

    def test_matching_survivor_gets_term_then_kill(self):
        calls = []
        temp, proc_root = self._proc_root()
        try:
            result = reap(
                [process()],
                proc_root=proc_root,
                term_wait_seconds=0,
                kill_fn=lambda pid, sig: calls.append((pid, sig)),
                sleep_fn=lambda _: None,
            )
        finally:
            temp.cleanup()

        self.assertEqual(
            [
                (1234, signal.SIGTERM),
                (1234, signal.SIGKILL),
            ],
            calls,
        )
        self.assertEqual(1, result["term_sent"])
        self.assertEqual(1, result["survived_term"])
        self.assertEqual(1, result["kill_sent"])
        self.assertEqual(100 * 1024 * 1024, result["rss_bytes"])


if __name__ == "__main__":
    unittest.main()
