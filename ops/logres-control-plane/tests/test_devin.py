import json
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
LIB_DIR = CONTROL_ROOT / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db, seed_active_lease
from logres_devin import (
    ATTEMPT_REF_PREFIX,
    DEFAULT_EXECUTION_MODE,
    DEFAULT_MODEL,
    DEFAULT_PERMISSION_MODE,
    DEVIN_NATIVE_SANDBOX,
    ISOLATION_ENV_VAR,
    LEASE_DEADLINE,
    LEASE_LOST,
    DevinAgentError,
    LeaseLostError,
    assert_worker_lease,
    attempt_ref_name,
    build_devin_argv,
    build_prompt,
    devin_models_report,
    ensure_isolated_worktree,
    ensure_scoped,
    ensure_worker_branch,
    lease_owned,
    make_lease_renewer,
    parse_models_report,
    parse_verify_specs,
    preserve_failed_attempt,
    redact,
    redact_file,
    resolve_execution_isolation,
    run_child_with_lease,
    run_verification,
    select_model,
    snapshot_attempt,
    terminate_process_group,
    worktree_branch,
)

MODELS_REPORT = json.dumps(
    {
        "families": [
            {
                "family_label": "SWE-2",
                "family_uid": "swe-2",
                "slug": "swe-2",
                "aliases": ["swe"],
                "variants": [
                    {"model_uid": "swe-2-high", "cost_tier": "Free"},
                    {"model_uid": "swe-2-medium", "cost_tier": "Free"},
                    {"model_uid": "swe-2-max", "cost_tier": "Free"},
                ],
            },
            {
                "family_label": "Claude X",
                "family_uid": "claude-x",
                "slug": "claude-x",
                "aliases": ["opus"],
                "variants": [
                    {"model_uid": "claude-x-low", "cost_tier": "Med cost"},
                    {"model_uid": "claude-x-max", "cost_tier": "High cost"},
                ],
            },
            {
                "family_label": "Mixed",
                "family_uid": "mixed",
                "slug": "mixed",
                "aliases": [],
                "variants": [
                    {"model_uid": "mix-free", "cost_tier": "Free"},
                    {"model_uid": "mix-paid", "cost_tier": "Low cost"},
                ],
            },
        ]
    }
)


class FakeProc:
    def __init__(self, waits, pid=4242):
        self.waits = list(waits)
        self.pid = pid
        self.terminated = False
        self.killed = False

    def wait(self, timeout=None):
        item = self.waits.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


def git_run(argv, **kwargs):
    return subprocess.run(
        [str(a) for a in argv],
        text=True,
        capture_output=True,
        check=False,
        **kwargs,
    )


def git_out(worktree: Path, *args) -> str:
    proc = git_run(["git", "-C", str(worktree), *args])
    if proc.returncode:
        raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr}")
    return proc.stdout.strip()


def make_git_worktree(tmp: str) -> Path:
    wt = Path(tmp) / "wt"
    wt.mkdir()
    git_run(["git", "-C", str(wt), "init", "-b", "worker/test"])
    (wt / ".gitignore").write_text("ignored.log\n")
    (wt / "tracked.txt").write_text("v1\n")
    git_run(["git", "-C", str(wt), "add", "."])
    git_run(
        [
            "git", "-C", str(wt),
            "-c", "user.name=test",
            "-c", "user.email=test@example.invalid",
            "commit", "-m", "init",
        ]
    )
    return wt


class ModelPolicyTests(unittest.TestCase):
    def setUp(self):
        self.report = parse_models_report(MODELS_REPORT)

    def test_default_model_is_swe_2_max_when_reported_free(self):
        self.assertEqual("swe-2-max", DEFAULT_MODEL)
        self.assertEqual("swe-2-max", select_model(self.report, None))
        self.assertEqual("swe-2-max", select_model(self.report, ""))
        self.assertEqual("swe-2-max", select_model(self.report, "swe-2-max"))

    def test_free_family_alias_resolves(self):
        self.assertEqual("swe", select_model(self.report, "swe"))
        self.assertEqual("swe-2-high", select_model(self.report, "swe-2-high"))

    def test_paid_model_refused_without_explicit_opt_in(self):
        for model in ("claude-x-max", "claude-x-low", "claude-x", "opus", "mixed"):
            with self.assertRaises(DevinAgentError) as ctx:
                select_model(self.report, model)
            self.assertIn("paid", str(ctx.exception))

    def test_paid_model_allowed_only_with_explicit_opt_in(self):
        self.assertEqual(
            "claude-x-max",
            select_model(self.report, "claude-x-max", allow_paid=True),
        )
        self.assertEqual(
            "mixed",
            select_model(self.report, "mixed", allow_paid=True),
        )

    def test_unknown_model_is_refused(self):
        with self.assertRaises(DevinAgentError) as ctx:
            select_model(self.report, "no-such-model")
        self.assertIn("not reported", str(ctx.exception))

    def test_family_without_variants_is_refused(self):
        report = {"variants": {}, "families": {"ghost": []}}
        with self.assertRaises(DevinAgentError) as ctx:
            select_model(report, "ghost")
        self.assertIn("not reported", str(ctx.exception))

    def test_models_report_requires_valid_json(self):
        with self.assertRaises(DevinAgentError) as ctx:
            parse_models_report("not json at all")
        self.assertIn("valid JSON", str(ctx.exception))

    def test_models_report_handles_missing_cost_tier(self):
        report = parse_models_report(
            json.dumps(
                {
                    "families": [
                        {
                            "slug": "bare",
                            "variants": [{"model_uid": "bare-1"}],
                        }
                    ]
                }
            )
        )
        with self.assertRaises(DevinAgentError) as ctx:
            select_model(report, "bare-1")
        self.assertIn("paid", str(ctx.exception))

    def test_devin_models_report_uses_json_subcommand(self):
        calls = []

        def run(argv, **kwargs):
            calls.append((argv, kwargs))
            return SimpleNamespace(returncode=0, stdout=MODELS_REPORT, stderr="")

        report = devin_models_report(run, "devin")
        argv = calls[0][0]
        self.assertEqual(["devin", "models", "list", "--format", "json"], argv)
        self.assertIn("swe-2-max", report["variants"])

    def test_devin_models_report_fails_closed_on_error(self):
        def run(argv, **kwargs):
            return SimpleNamespace(returncode=1, stdout="", stderr="denied")

        with self.assertRaises(DevinAgentError) as ctx:
            devin_models_report(run, "devin")
        self.assertIn("devin models list failed", str(ctx.exception))


class RedactionTests(unittest.TestCase):
    def test_bearer_and_authorization_tokens_are_redacted(self):
        text = "Authorization: Bearer abcdef1234567890XYZ"
        out = redact(text)
        self.assertNotIn("abcdef1234567890XYZ", out)
        self.assertIn("Bearer [REDACTED]", out)

    def test_key_value_tokens_are_redacted(self):
        cases = [
            "api_key=abcdef1234567890",
            "api_key: abcdef1234567890",
            'token="abcdef1234567890"',
            '{"session_token":"abcdef1234567890"}',
            "password=hunter2hunter2",
            "client_secret: 9f8e7d6c5b4a",
        ]
        for text in cases:
            out = redact(text)
            self.assertIn("[REDACTED]", out, text)
            self.assertNotIn("abcdef1234567890", out, text)

    def test_prefixed_tokens_are_redacted(self):
        cases = [
            "key sk-proj-abc1234567890 leaked",
            "github_pat_11ABCDEFG0abcdef",
            "ghp_abcdefghijklmnop123",
            "xoxb-1234567890-abcdefghijkl",
        ]
        for text in cases:
            out = redact(text)
            self.assertIn("[REDACTED]", out, text)
            for fragment in ("sk-proj-abc1234567890", "github_pat_11ABCDEFG0abcdef", "ghp_abcdefghijklmnop123", "xoxb-1234567890-abcdefghijkl"):
                self.assertNotIn(fragment, out)

    def test_jwt_is_redacted(self):
        jwt = (
            "eyJhbGciOiJIUzI1NiJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "abcdefghijklmnop123456"
        )
        out = redact("token " + jwt + " end")
        self.assertNotIn("eyJhbGciOiJIUzI1NiJ9", out)
        self.assertIn("[REDACTED]", out)

    def test_git_sha_and_sha256_survive_redaction(self):
        sha = "a" * 40
        digest = "b" * 64
        out = redact(f"candidate {sha} packet {digest}")
        self.assertIn(sha, out)
        self.assertIn(digest, out)

    def test_long_mixed_tokens_redacted_but_words_survive(self):
        token = "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6"
        out = redact("leaked " + token + " done")
        self.assertNotIn(token, out)
        self.assertIn("[REDACTED]", out)
        prose = redact("the worker packet handler returned READY")
        self.assertIn("worker packet handler", prose)

    def test_redact_file_writes_only_redacted_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "raw.log"
            dst = Path(tmp) / "out" / "final.log"
            src.write_text("ok api_key=abcdef1234567890 done")
            redact_file(src, dst)
            text = dst.read_text()
            self.assertNotIn("abcdef1234567890", text)
            self.assertIn("[REDACTED]", text)


class BranchGuardTests(unittest.TestCase):
    def test_protected_branches_are_hard_refused(self):
        for branch in (
            "main",
            "feat/logres-reconstruction",
            "refs/heads/main",
            "refs/heads/feat/logres-reconstruction",
        ):
            with self.assertRaises(DevinAgentError) as ctx:
                ensure_worker_branch(branch)
            self.assertIn("refusing", str(ctx.exception))

    def test_non_branch_refs_are_refused(self):
        with self.assertRaises(DevinAgentError):
            ensure_worker_branch("refs/tags/v1")
        with self.assertRaises(DevinAgentError):
            ensure_worker_branch("")

    def test_worker_branch_passes_and_normalizes(self):
        self.assertEqual(
            "worker/devin-1",
            ensure_worker_branch("worker/devin-1"),
        )
        self.assertEqual(
            "worker/devin-1",
            ensure_worker_branch(" refs/heads/worker/devin-1 "),
        )

    def test_isolated_worktree_refuses_primary_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "base"
            work = Path(tmp) / "work"
            base.mkdir()
            work.mkdir()
            with self.assertRaises(DevinAgentError) as ctx:
                ensure_isolated_worktree(base, base)
            self.assertIn("primary checkout", str(ctx.exception))
            self.assertEqual(work.resolve(), ensure_isolated_worktree(work, base))
            with self.assertRaises(DevinAgentError):
                ensure_isolated_worktree(Path(tmp) / "missing", base)

    def test_worktree_branch_uses_git_show_current(self):
        calls = []

        def run(argv, **kwargs):
            calls.append(argv)
            return SimpleNamespace(returncode=0, stdout="worker/t1\n", stderr="")

        self.assertEqual("worker/t1", worktree_branch(run, Path("/tmp/wt")))
        self.assertEqual(
            ["git", "-C", "/tmp/wt", "branch", "--show-current"], calls[0]
        )


class CommandConstructionTests(unittest.TestCase):
    def test_print_mode_command_shape(self):
        argv = build_devin_argv(
            prompt_file=Path("/tmp/prompt.txt"),
            export_path=Path("/tmp/session.json"),
        )
        self.assertEqual("devin", argv[0])
        self.assertIn("-p", argv)
        self.assertEqual(
            "swe-2-max", argv[argv.index("--model") + 1]
        )
        self.assertEqual(
            "smart", argv[argv.index("--permission-mode") + 1]
        )
        self.assertEqual(
            "/tmp/prompt.txt", argv[argv.index("--prompt-file") + 1]
        )
        self.assertEqual(
            "false", argv[argv.index("--respect-workspace-trust") + 1]
        )
        self.assertEqual(
            "/tmp/session.json", argv[argv.index("--export") + 1]
        )
        self.assertNotIn("--cloud", argv)

    def test_default_permission_mode_is_smart_and_configurable(self):
        self.assertEqual("smart", DEFAULT_PERMISSION_MODE)
        argv = build_devin_argv(
            prompt_file=Path("/p"),
            permission_mode="accept-edits",
        )
        self.assertEqual(
            "accept-edits", argv[argv.index("--permission-mode") + 1]
        )

    def test_unknown_permission_mode_is_refused(self):
        with self.assertRaises(DevinAgentError) as ctx:
            build_devin_argv(prompt_file=Path("/p"), permission_mode="bogus")
        self.assertIn("unsupported permission mode", str(ctx.exception))

    def test_secrets_never_appear_in_argv(self):
        secret = "sk-proj-abc1234567890"
        argv = build_devin_argv(
            prompt_file=Path("/tmp/prompt.txt"),
            model="swe-2-max",
            extra=["--config", "/tmp/devin.json"],
        )
        self.assertNotIn(secret, argv)
        self.assertTrue(all(secret not in item for item in argv))

    def test_verify_specs_default_and_parsing(self):
        self.assertEqual(
            [["gate", "fast"]],
            parse_verify_specs([], ["gate", "fast"]),
        )
        self.assertEqual(
            [["python3", "-m", "unittest", "tests.test_devin"]],
            parse_verify_specs(
                ["python3 -m unittest tests.test_devin"], ["gate", "fast"]
            ),
        )
        specs = parse_verify_specs(
            ["pytest -q tests/a.py", "npm run lint"], ["gate", "fast"]
        )
        self.assertEqual(2, len(specs))
        self.assertEqual(["pytest", "-q", "tests/a.py"], specs[0])


class HeartbeatRecoveryTests(unittest.TestCase):
    def test_lease_is_renewed_while_child_runs_and_rc_preserved(self):
        proc = FakeProc(
            [
                subprocess.TimeoutExpired("devin", 1),
                subprocess.TimeoutExpired("devin", 1),
                7,
            ]
        )
        renew_calls = []
        with tempfile.TemporaryDirectory() as tmp:

            def popen(argv, **kwargs):
                return proc

            result = run_child_with_lease(
                ["devin", "-p"],
                log_path=Path(tmp) / "raw.log",
                renew=lambda: renew_calls.append(1),
                renew_seconds=0.01,
                popen=popen,
            )
        self.assertEqual(7, result["rc"])
        self.assertEqual(4242, result["pid"])
        self.assertEqual(3, result["renewals"])
        self.assertEqual(3, len(renew_calls))
        self.assertEqual(0, result["renew_failures"])

    def test_renewal_failures_are_counted_not_raised(self):
        proc = FakeProc([subprocess.TimeoutExpired("devin", 1), 0])
        calls = []

        def renew():
            calls.append(1)
            if len(calls) == 2:
                raise DevinAgentError("brain lease renewal failed")

        with tempfile.TemporaryDirectory() as tmp:
            result = run_child_with_lease(
                ["devin", "-p"],
                log_path=Path(tmp) / "raw.log",
                renew=renew,
                renew_seconds=0.01,
                popen=lambda argv, **kwargs: proc,
            )
        self.assertEqual(0, result["rc"])
        self.assertEqual(1, result["renewals"])
        self.assertEqual(1, result["renew_failures"])

    def test_interruption_terminates_child_and_propagates(self):
        proc = FakeProc([KeyboardInterrupt()])
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(KeyboardInterrupt):
                run_child_with_lease(
                    ["devin", "-p"],
                    log_path=Path(tmp) / "raw.log",
                    renew=lambda: None,
                    renew_seconds=0.01,
                    popen=lambda argv, **kwargs: proc,
                )
        self.assertTrue(proc.terminated)

    def test_child_output_lands_in_raw_log_for_later_redaction(self):
        class WritingProc(FakeProc):
            def wait(self, timeout=None):
                return 0

        def popen(argv, **kwargs):
            kwargs["stdout"].write(b"child output\n")
            kwargs["stdout"].flush()
            return WritingProc([])

        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "raw.log"
            result = run_child_with_lease(
                ["devin", "-p"],
                log_path=log,
                renew=lambda: None,
                renew_seconds=0.01,
                popen=popen,
            )
            self.assertEqual(0, result["rc"])
            self.assertIn("child output", log.read_text())

    def test_lease_renewer_invokes_brain_renew(self):
        calls = []

        def run(argv, **kwargs):
            calls.append(argv)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        renew = make_lease_renewer(run, "/bin/logres-brain", "w1", "T1", 120)
        renew()
        self.assertEqual(
            ["/bin/logres-brain", "renew", "w1", "T1", "--minutes", "120"],
            calls[0],
        )

    def test_lease_renewer_raises_on_failure(self):
        def run(argv, **kwargs):
            return SimpleNamespace(returncode=9, stdout="", stderr="")

        renew = make_lease_renewer(run, "/bin/logres-brain", "w1", "T1", 120)
        with self.assertRaises(DevinAgentError) as ctx:
            renew()
        self.assertIn("lease renewal failed", str(ctx.exception))

    def test_lease_ownership_matches_brain_lease_row(self):
        conn = make_test_db()
        seed_active_lease(
            conn, "T1", chat_id="auto-devin-1", branch="worker/auto-devin-1-t1"
        )
        self.assertTrue(
            lease_owned(conn, "T1", "auto-devin-1", "worker/auto-devin-1-t1")
        )
        self.assertFalse(lease_owned(conn, "T1", "auto-devin-1", "worker/other"))
        self.assertFalse(lease_owned(conn, "T1", "other", "worker/auto-devin-1-t1"))
        conn.close()


class PromptAndVerificationTests(unittest.TestCase):
    def test_prompt_carries_branch_scope_and_finish_guardrails(self):
        prompt = build_prompt(
            task_id="DEVIN-CORE-INTEGRATION-001",
            worker_id="auto-devin-1",
            branch="worker/auto-devin-1",
            packet="PACKET BODY implement the thing",
            scopes=["ops/logres-control-plane", "src/game"],
            verify_commands=[["bin/logres-gate", "fast"]],
        )
        self.assertIn("DEVIN-CORE-INTEGRATION-001", prompt)
        self.assertIn("worker/auto-devin-1", prompt)
        self.assertIn("main", prompt)
        self.assertIn("feat/logres-reconstruction", prompt)
        self.assertIn("- ops/logres-control-plane", prompt)
        self.assertIn("bin/logres-gate fast", prompt)
        self.assertIn("PACKET BODY implement the thing", prompt)
        self.assertIn("uncommitted", prompt)
        self.assertIn("never", prompt.lower())

    def test_run_verification_stops_on_first_failure(self):
        calls = []

        def run(argv, **kwargs):
            calls.append(argv)
            rc = 0 if len(calls) == 1 else 3
            return SimpleNamespace(returncode=rc, stdout="out", stderr="err")

        results = run_verification(
            run, Path("/tmp/wt"), [["cmd1"], ["cmd2"], ["cmd3"]]
        )
        self.assertEqual(2, len(results))
        self.assertEqual(0, results[0]["rc"])
        self.assertEqual(3, results[1]["rc"])
        self.assertEqual([["cmd1"], ["cmd2"]], calls)

    def test_run_verification_redacts_output_tail(self):
        def run(argv, **kwargs):
            return SimpleNamespace(
                returncode=1, stdout="bad api_key=abcdef1234567890", stderr=""
            )

        results = run_verification(run, Path("/tmp/wt"), [["cmd"]])
        self.assertNotIn("abcdef1234567890", results[0]["tail"])
        self.assertIn("[REDACTED]", results[0]["tail"])

    def test_scoped_paths_gate(self):
        ensure_scoped(["src/a/x.py", "ops/y.py"], ["src/a", "ops"])
        with self.assertRaises(DevinAgentError) as ctx:
            ensure_scoped(["etc/passwd"], ["src/a"])
        self.assertIn("outside declared scopes", str(ctx.exception))
        with self.assertRaises(DevinAgentError):
            ensure_scoped(["src/a/x.py"], [])


class AttemptPreservationTests(unittest.TestCase):
    def test_attempt_ref_is_namespaced_and_sanitized(self):
        ref = attempt_ref_name(
            "DEVIN-CORE-INTEGRATION-001", "20260925T000000Z-verify"
        )
        self.assertTrue(
            ref.startswith(
                ATTEMPT_REF_PREFIX + "/DEVIN-CORE-INTEGRATION-001/"
            )
        )
        self.assertNotIn("refs/heads/", ref)
        hostile = attempt_ref_name("../evil task//x", "st amp")
        for part in hostile.split("/")[3:]:
            self.assertNotIn("..", part)
            self.assertRegex(part, r"^[A-Za-z0-9._-]+$")

    def test_snapshot_preserves_all_changes_without_moving_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            wt = make_git_worktree(tmp)
            head_before = git_out(wt, "rev-parse", "HEAD")
            (wt / "tracked.txt").write_text("v2 modified\n")
            (wt / "untracked.txt").write_text("new work\n")
            (wt / "nested").mkdir()
            (wt / "nested" / "deep.py").write_text("x = 1\n")
            (wt / "ignored.log").write_text("noise\n")
            attempt = snapshot_attempt(
                git_run, wt, "T-9", stage="verify", stamp="20260925T000000Z"
            )
            self.assertEqual(head_before, git_out(wt, "rev-parse", "HEAD"))
            self.assertEqual(head_before, attempt["parent_head"])
            self.assertEqual("verify", attempt["stage"])
            self.assertEqual("recovery-snapshot", attempt["kind"])
            self.assertEqual(
                attempt["sha"], git_out(wt, "rev-parse", "--verify", attempt["ref"])
            )
            tree_files = git_out(
                wt, "ls-tree", "-r", "--name-only", attempt["sha"]
            ).splitlines()
            self.assertIn("tracked.txt", tree_files)
            self.assertIn("untracked.txt", tree_files)
            self.assertIn("nested/deep.py", tree_files)
            self.assertNotIn("ignored.log", tree_files)
            self.assertEqual(
                "v2 modified", git_out(wt, "show", f"{attempt['sha']}:tracked.txt")
            )
            self.assertEqual(
                "new work", git_out(wt, "show", f"{attempt['sha']}:untracked.txt")
            )
            status = git_out(wt, "status", "--porcelain")
            self.assertIn("untracked.txt", status)

    def test_preserve_failed_attempt_leaves_clean_retryable_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            wt = make_git_worktree(tmp)
            (wt / "tracked.txt").write_text("broken attempt\n")
            (wt / "draft.py").write_text("partial = True\n")
            attempt = preserve_failed_attempt(
                git_run, wt, "T-9", stage="verify", stamp="20260925T010000Z"
            )
            self.assertEqual("", git_out(wt, "status", "--porcelain"))
            self.assertEqual(
                attempt["sha"], git_out(wt, "rev-parse", "--verify", attempt["ref"])
            )
            self.assertEqual(
                "partial = True", git_out(wt, "show", f"{attempt['sha']}:draft.py")
            )

    def test_attempt_snapshot_is_never_treated_as_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            wt = make_git_worktree(tmp)
            head_before = git_out(wt, "rev-parse", "HEAD")
            (wt / "tracked.txt").write_text("v2\n")
            attempt = snapshot_attempt(
                git_run, wt, "T-9", stage="verify", stamp="20260925T020000Z"
            )
            self.assertTrue(attempt["ref"].startswith(ATTEMPT_REF_PREFIX + "/"))
            self.assertFalse(attempt["ref"].startswith("refs/heads/"))
            self.assertNotEqual(head_before, attempt["sha"])
            self.assertEqual(head_before, git_out(wt, "rev-parse", "HEAD"))

    def test_snapshot_failure_refuses_to_discard_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            wt = make_git_worktree(tmp)
            (wt / "draft.py").write_text("partial = True\n")
            calls = []

            def bad_run(argv, **kwargs):
                calls.append([str(a) for a in argv])
                if "read-tree" in argv:
                    return SimpleNamespace(
                        returncode=1, stdout="", stderr="simulated index failure"
                    )
                return git_run(argv, **kwargs)

            with self.assertRaises(DevinAgentError) as ctx:
                preserve_failed_attempt(
                    bad_run, wt, "T-9", stage="verify", stamp="20260925T030000Z"
                )
            self.assertIn("snapshot", str(ctx.exception))
            self.assertTrue((wt / "draft.py").is_file())
            flattened = [a for argv in calls for a in argv]
            self.assertNotIn("restore", flattened)
            self.assertNotIn("clean", flattened)


class ExecutionIsolationTests(unittest.TestCase):
    def test_interactive_smart_remains_default_compat(self):
        self.assertEqual("interactive", DEFAULT_EXECUTION_MODE)
        contract = resolve_execution_isolation()
        self.assertEqual("interactive", contract["mode"])
        self.assertIsNone(contract["isolation"])
        self.assertFalse(contract["unattended"])
        argv = build_devin_argv(prompt_file=Path("/p"))
        self.assertNotIn("--sandbox", argv)

    def test_unattended_without_isolation_fails_closed(self):
        for kwargs in (
            {},
            {"permission_mode": "smart"},
            {"permission_mode": "dangerous"},
        ):
            with self.assertRaises(DevinAgentError) as ctx:
                build_devin_argv(
                    prompt_file=Path("/p"), execution_mode="unattended", **kwargs
                )
            self.assertIn("isolation", str(ctx.exception).lower())

    def test_smart_mode_is_not_unattended_isolation_proof(self):
        with self.assertRaises(DevinAgentError):
            resolve_execution_isolation(execution_mode="unattended")

    def test_unattended_accepts_devin_native_sandbox(self):
        argv = build_devin_argv(
            prompt_file=Path("/p"), execution_mode="unattended", sandbox=True
        )
        self.assertIn("--sandbox", argv)
        contract = resolve_execution_isolation(
            execution_mode="unattended", sandbox=True
        )
        self.assertTrue(contract["sandbox"])
        self.assertEqual(DEVIN_NATIVE_SANDBOX, contract["isolation"])

    def test_unattended_accepts_external_isolation_marker(self):
        marker = "systemd/logres-devin-worker@.service"
        contract = resolve_execution_isolation(
            execution_mode="unattended", isolation=marker
        )
        self.assertEqual(marker, contract["isolation"])
        self.assertFalse(contract["sandbox"])
        argv = build_devin_argv(
            prompt_file=Path("/p"), execution_mode="unattended", isolation=marker
        )
        self.assertNotIn("--sandbox", argv)

    def test_autonomous_mode_requires_sandbox(self):
        with self.assertRaises(DevinAgentError) as ctx:
            build_devin_argv(prompt_file=Path("/p"), permission_mode="autonomous")
        self.assertIn("--sandbox", str(ctx.exception))
        argv = build_devin_argv(
            prompt_file=Path("/p"), permission_mode="autonomous", sandbox=True
        )
        self.assertIn("--sandbox", argv)

    def test_invalid_mode_or_marker_is_refused(self):
        with self.assertRaises(DevinAgentError):
            resolve_execution_isolation(execution_mode="bogus")
        with self.assertRaises(DevinAgentError):
            resolve_execution_isolation(
                execution_mode="unattended", isolation="bad marker with spaces!!"
            )

    def test_isolation_marker_env_hook_name_is_stable(self):
        self.assertEqual(
            "LOGRES_DEVIN_EXECUTION_ISOLATION", ISOLATION_ENV_VAR
        )


class LeaseLossTests(unittest.TestCase):
    def test_authoritative_lease_loss_terminates_group_immediately(self):
        proc = FakeProc([subprocess.TimeoutExpired("devin", 1), -15])
        signals = []
        beats = []

        def renew():
            beats.append(1)
            if len(beats) == 2:
                raise LeaseLostError("brain reports lease lost: not lease owner for T1")

        with tempfile.TemporaryDirectory() as tmp:
            result = run_child_with_lease(
                ["devin", "-p"],
                log_path=Path(tmp) / "raw.log",
                renew=renew,
                renew_seconds=0.01,
                popen=lambda argv, **kwargs: proc,
                signal_group=lambda pid, sig: signals.append((pid, sig)),
            )
        self.assertEqual(LEASE_LOST, result["lease"]["status"])
        self.assertTrue(result["terminated"])
        self.assertEqual(-15, result["rc"])
        self.assertEqual([signal.SIGTERM], [s for _, s in signals])
        self.assertEqual(4242, signals[0][0])
        self.assertIn("not lease owner", result["lease"]["detail"])
        self.assertEqual(1, result["renewals"])

    def test_transient_renewal_failures_stop_before_lease_ttl(self):
        clock_now = [0.0]
        proc = FakeProc(
            [
                subprocess.TimeoutExpired("devin", 1),
                subprocess.TimeoutExpired("devin", 1),
                -15,
            ]
        )
        signals = []

        def renew():
            clock_now[0] += 40.0
            raise DevinAgentError("brain unreachable")

        with tempfile.TemporaryDirectory() as tmp:
            result = run_child_with_lease(
                ["devin", "-p"],
                log_path=Path(tmp) / "raw.log",
                renew=renew,
                renew_seconds=0.01,
                lease_ttl_seconds=100.0,
                lease_margin_seconds=10.0,
                popen=lambda argv, **kwargs: proc,
                signal_group=lambda pid, sig: signals.append((pid, sig)),
                clock=lambda: clock_now[0],
            )
        self.assertEqual(LEASE_DEADLINE, result["lease"]["status"])
        self.assertTrue(result["terminated"])
        self.assertEqual(3, result["renew_failures"])
        self.assertEqual(0, result["renewals"])
        self.assertIn(signal.SIGTERM, [s for _, s in signals])
        self.assertIn("brain unreachable", result["lease"]["detail"])
        self.assertLess(result["lease"]["deadline_seconds"], 100.0)

    def test_sigterm_then_sigkill_after_bounded_grace(self):
        proc = FakeProc(
            [
                subprocess.TimeoutExpired("devin", 1),
                -9,
            ]
        )
        signals = []

        def renew():
            raise LeaseLostError("not lease owner for T1")

        with tempfile.TemporaryDirectory() as tmp:
            result = run_child_with_lease(
                ["devin", "-p"],
                log_path=Path(tmp) / "raw.log",
                renew=renew,
                renew_seconds=0.01,
                term_grace_seconds=0.01,
                popen=lambda argv, **kwargs: proc,
                signal_group=lambda pid, sig: signals.append((pid, sig)),
            )
        self.assertEqual(LEASE_LOST, result["lease"]["status"])
        self.assertEqual(
            [signal.SIGTERM, signal.SIGKILL], [s for _, s in signals]
        )
        self.assertEqual(-9, result["rc"])

    def test_lease_result_reports_deadline_and_last_renewal(self):
        proc = FakeProc([0])
        with tempfile.TemporaryDirectory() as tmp:
            result = run_child_with_lease(
                ["devin", "-p"],
                log_path=Path(tmp) / "raw.log",
                renew=lambda: None,
                renew_seconds=0.01,
                lease_ttl_seconds=200.0,
                lease_margin_seconds=50.0,
                popen=lambda argv, **kwargs: proc,
            )
        lease = result["lease"]
        self.assertEqual("ok", lease["status"])
        self.assertEqual(150.0, lease["deadline_seconds"])
        self.assertEqual(200.0, lease["ttl_seconds"])
        self.assertIn("seconds_since_renewal", lease)

    def test_lease_renewer_classifies_authoritative_loss(self):
        def lost_run(argv, **kwargs):
            return SimpleNamespace(
                returncode=3, stdout="", stderr="not lease owner for T1"
            )

        renew = make_lease_renewer(lost_run, "/bin/logres-brain", "w1", "T1", 120)
        with self.assertRaises(LeaseLostError):
            renew()

        def owner_run(argv, **kwargs):
            return SimpleNamespace(
                returncode=1, stdout="", stderr="w1 does not own lease for T1"
            )

        renew = make_lease_renewer(owner_run, "/bin/logres-brain", "w1", "T1", 120)
        with self.assertRaises(LeaseLostError):
            renew()

    def test_lease_renewer_classifies_transient_errors(self):
        def flaky_run(argv, **kwargs):
            return SimpleNamespace(
                returncode=1, stdout="", stderr="database is locked"
            )

        renew = make_lease_renewer(flaky_run, "/bin/logres-brain", "w1", "T1", 120)
        with self.assertRaises(DevinAgentError) as ctx:
            renew()
        self.assertNotIsInstance(ctx.exception, LeaseLostError)
        self.assertIn("lease renewal failed", str(ctx.exception))

    def test_terminate_process_group_falls_back_when_group_signal_fails(self):
        proc = FakeProc([-15])
        calls = []

        def bad_signal(pid, sig):
            calls.append((pid, sig))
            raise ProcessLookupError("no such process group")

        rc = terminate_process_group(
            proc, grace_seconds=0.01, signal_group=bad_signal
        )
        self.assertTrue(proc.terminated)
        self.assertEqual(-15, rc)
        self.assertEqual([(4242, signal.SIGTERM)], calls)

    def test_stale_worker_refused_before_handoff(self):
        conn = make_test_db()
        seed_active_lease(conn, "T1", chat_id="w1", branch="worker/w1")

        def run_ok(argv, **kwargs):
            return SimpleNamespace(returncode=0, stdout="worker/w1\n", stderr="")

        assert_worker_lease(conn, run_ok, Path("/tmp/wt"), "T1", "w1", "worker/w1")

        def run_wrong_branch(argv, **kwargs):
            return SimpleNamespace(returncode=0, stdout="worker/other\n", stderr="")

        with self.assertRaises(LeaseLostError):
            assert_worker_lease(
                conn, run_wrong_branch, Path("/tmp/wt"), "T1", "w1", "worker/w1"
            )

        conn.execute("delete from brain_task_leases")
        conn.commit()
        with self.assertRaises(LeaseLostError) as ctx:
            assert_worker_lease(
                conn, run_ok, Path("/tmp/wt"), "T1", "w1", "worker/w1"
            )
        self.assertIn("no longer owns", str(ctx.exception))

        seed_active_lease(conn, "T2", chat_id="w1", branch="worker/w1")
        conn.execute(
            "update brain_task_leases set lease_until_epoch=? where task_id=?",
            (1.0, "T2"),
        )
        conn.commit()
        with self.assertRaises(LeaseLostError):
            assert_worker_lease(
                conn, run_ok, Path("/tmp/wt"), "T2", "w1", "worker/w1"
            )
        conn.close()


class BinContractTests(unittest.TestCase):
    def test_bin_preserves_swarm_agent_argument_contract(self):
        script = (CONTROL_ROOT / "bin" / "logres-devin-agent").read_text()
        for flag in (
            '"--task"',
            '"--worker"',
            '"--job-id"',
            '"--branch"',
            '"--worktree"',
        ):
            self.assertIn(flag, script)
        self.assertIn("logres-finish-task", script)
        self.assertIn("ensure_swarm_schema", script)
        self.assertNotIn("merge", script.lower().replace("logres-merge", ""))

    def test_bin_has_no_secret_in_argv_or_credential_reads(self):
        script = (CONTROL_ROOT / "bin" / "logres-devin-agent").read_text()
        self.assertIn("--prompt-file", script)
        self.assertNotIn("read_text().strip()", script)
        for needle in ("api_key", "api-key", "credentials", ".config/devin"):
            self.assertNotIn(needle, script)

    def test_bin_exposes_isolation_contract_flags(self):
        script = (CONTROL_ROOT / "bin" / "logres-devin-agent").read_text()
        for flag in ('"--execution-mode"', '"--sandbox"', '"--isolation"'):
            self.assertIn(flag, script)
        self.assertIn("LOGRES_DEVIN_ISOLATION", script)
        self.assertIn("resolve_execution_isolation", script)
        self.assertIn("lease_ttl_seconds", script)
        self.assertIn("assert_worker_lease", script)

    def test_bin_preserves_failed_attempts_before_cleanup(self):
        script = (CONTROL_ROOT / "bin" / "logres-devin-agent").read_text()
        self.assertIn("preserve_failed_attempt", script)
        self.assertNotIn("clean_uncommitted", script)
        self.assertIn('"attempt"', script)


if __name__ == "__main__":
    unittest.main()
