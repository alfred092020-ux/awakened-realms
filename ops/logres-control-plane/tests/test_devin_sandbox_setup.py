import contextlib
import importlib.machinery
import importlib.util
import io
import json
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
REPO_ROOT = CONTROL_ROOT.parents[1]
SCRIPT = CONTROL_ROOT / "bin" / "logres-devin-sandbox-setup"
PROFILE = CONTROL_ROOT / "apparmor" / "usr.bin.bwrap.logres"
sys.path.insert(0, str(REPO_ROOT / "scripts" / "logres"))


def load_module():
    name = "test_logres_devin_sandbox_setup"
    loader = importlib.machinery.SourceFileLoader(name, str(SCRIPT))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class Proc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def make_runner(calls, behavior=None):
    def runner(argv, **kwargs):
        argv = [str(a) for a in argv]
        calls.append(argv)
        if behavior is not None:
            return behavior(argv)
        return Proc()

    return runner


def silent(fn, *args, **kwargs):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*args, **kwargs)
    return rc, buf.getvalue()


RESIDUE_PROFILE = """\
abi <abi/4.0>,
include <tunables/global>

profile bwrap /usr/bin/bwrap flags=(unconfined) {
  userns,
}
"""


class ModuleFixture(unittest.TestCase):
    """Loads the tool fresh per test and points every host path into tmp."""

    def setUp(self):
        self.module = load_module()
        self.td = tempfile.TemporaryDirectory()
        root = Path(self.td.name)
        self.addCleanup(self.td.cleanup)
        self.appd = root / "apparmor.d"
        self.appd.mkdir()
        self.source = root / "usr.bin.bwrap.logres"
        self.source.write_text(PROFILE.read_text())
        self.sys_profiles = root / "sys_profiles"
        self.sysctl = root / "sysctl"
        self.sysctl.write_text("1\n")

        saved = {}
        for key in (
            "PROFILE_SOURCE",
            "PROFILE_DIR",
            "PROFILE_TARGET",
            "SYS_PROFILES",
            "SYSCTL_NODE",
            "PARSER",
            "AA_STATUS",
        ):
            saved[key] = getattr(self.module, key)
        saved["_is_root"] = self.module._is_root
        self.addCleanup(self._restore, saved)

        self.module.PROFILE_SOURCE = self.source
        self.module.PROFILE_DIR = self.appd
        self.module.PROFILE_TARGET = self.appd / self.source.name
        self.module.SYS_PROFILES = self.sys_profiles
        self.module.SYSCTL_NODE = self.sysctl
        self.module.PARSER = "apparmor_parser"
        self.module.AA_STATUS = "aa-status"
        self.module._is_root = lambda: True

        self.devin = root / "devin"
        self.devin.write_text("#!/bin/sh\n# fake devin binary for tests\n")
        self.devin.chmod(0o755)

    def _restore(self, saved):
        for key, value in saved.items():
            setattr(self.module, key, value)

    def enforce(self, mode="enforce"):
        self.sys_profiles.write_text(f"logres-devin-bwrap ({mode})\n")

    def install_good_state(self):
        self.module.PROFILE_TARGET.write_text(self.source.read_text())
        self.module.PROFILE_TARGET.chmod(0o644)
        self.enforce()


class ProfileContentTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.text = PROFILE.read_text()

    def test_versioned_profile_is_a_confined_userns_grant(self):
        self.assertIn("abi <abi/4.0>", self.text)
        headers = [
            h
            for h in self.module.profile_headers(self.text)
            if h["attachment"] == "/usr/bin/bwrap"
        ]
        self.assertEqual(1, len(headers))
        self.assertEqual("logres-devin-bwrap", headers[0]["name"])
        self.assertFalse(headers[0]["flags"])
        self.assertNotIn("flags=(unconfined)", self.text)
        self.assertEqual([], self.module.validate_profile_text(self.text))
        self.assertNotIn("include <abstractions/base>", self.text)

    def test_profile_grants_userns_and_namespace_ops_only(self):
        self.assertRegex(self.text, r"(?m)^\s*userns,\s*$")
        for rule in ("mount,", "remount,", "umount,", "pivot_root,"):
            self.assertIn(rule, self.text)

    def test_profile_does_not_pass_userns_to_payload(self):
        # The payload must exec unconfined (Ux): inheriting the profile (ix)
        # would extend the userns/mount grant into sandboxed commands.
        self.assertRegex(self.text, r"(?m)^\s*/\*\*\s+Ux,\s*$")
        self.assertNotRegex(self.text, r"(?m)^\s*/\*\*\s+(i|p|c)(x|ux),")

    def test_profile_carries_no_credential_material(self):
        lowered = self.text.lower()
        for needle in ("api_key", "secret", "bearer", "token="):
            self.assertNotIn(needle, lowered)
        for value in (
            self.module.CRED_VALUE,
            self.module.CHECKOUT_VALUE,
        ):
            self.assertNotIn(value, self.text)

    def test_validate_rejects_unconfined_flag(self):
        bad = self.text.replace(
            "profile logres-devin-bwrap /usr/bin/bwrap {",
            "profile logres-devin-bwrap /usr/bin/bwrap flags=(unconfined) {",
        )
        errors = self.module.validate_profile_text(bad)
        self.assertTrue(any("unconfined" in e for e in errors))

    def test_validate_rejects_complain_flag(self):
        bad = self.text.replace(
            "profile logres-devin-bwrap /usr/bin/bwrap {",
            "profile logres-devin-bwrap /usr/bin/bwrap flags=(complain) {",
        )
        errors = self.module.validate_profile_text(bad)
        self.assertTrue(any("complain" in e for e in errors))

    def test_validate_rejects_missing_userns(self):
        bad = self.text.replace("  userns,\n", "")
        errors = self.module.validate_profile_text(bad)
        self.assertTrue(any("userns" in e for e in errors))

    def test_validate_rejects_wrong_attachment(self):
        bad = self.text.replace("/usr/bin/bwrap", "/usr/bin/notbwrap")
        errors = self.module.validate_profile_text(bad)
        self.assertTrue(any("attaches" in e for e in errors))

    def test_profile_headers_parses_bare_attachment_form(self):
        headers = self.module.profile_headers(RESIDUE_PROFILE)
        self.assertEqual(1, len(headers))
        self.assertEqual("bwrap", headers[0]["name"])
        self.assertEqual("/usr/bin/bwrap", headers[0]["attachment"])
        self.assertIn("unconfined", headers[0]["flags"])


class ConflictDetectionTests(ModuleFixture):
    def test_find_conflicting_files_flags_bwrap_residue_only(self):
        residue = self.appd / "bwrap"
        residue.write_text(RESIDUE_PROFILE)
        unrelated = self.appd / "usr.bin.someother"
        unrelated.write_text("profile other /usr/bin/other {\n}\n")
        (self.appd / self.source.name).write_text(self.source.read_text())

        conflicts = self.module.find_conflicting_profile_files(self.appd)

        self.assertEqual([str(residue)], conflicts)


class InstallTests(ModuleFixture):
    def test_install_writes_file_and_loads_enforce(self):
        calls = []
        self.enforce()
        report = self.module.install_profile(make_runner(calls))

        self.assertTrue(report["ok"])
        self.assertEqual(
            self.source.read_text(), self.module.PROFILE_TARGET.read_text()
        )
        mode = stat.S_IMODE(self.module.PROFILE_TARGET.stat().st_mode)
        self.assertEqual(0o644, mode)
        self.assertEqual(0, mode & (stat.S_IWGRP | stat.S_IWOTH))
        self.assertEqual(
            {"installed": str(self.module.PROFILE_TARGET), "mode": "0o644"},
            report["steps"][0],
        )
        self.assertIn(
            ["apparmor_parser", "-p", str(self.module.PROFILE_TARGET)], calls
        )
        self.assertIn(
            ["apparmor_parser", "-r", "-W", str(self.module.PROFILE_TARGET)],
            calls,
        )

    def test_install_is_idempotent_when_already_enforced(self):
        calls = []
        self.install_good_state()
        report = self.module.install_profile(make_runner(calls))

        self.assertTrue(report["ok"])
        self.assertIn("already", report["note"])
        self.assertEqual([], calls)

    def test_install_rewrites_matching_enforced_0600_as_0644(self):
        calls = []
        self.install_good_state()
        self.module.PROFILE_TARGET.chmod(0o600)

        report = self.module.install_profile(make_runner(calls))

        self.assertTrue(report["ok"])
        mode = stat.S_IMODE(self.module.PROFILE_TARGET.stat().st_mode)
        self.assertEqual(0o644, mode)
        self.assertEqual(0, mode & (stat.S_IWGRP | stat.S_IWOTH))
        self.assertIn(
            ["apparmor_parser", "-r", "-W", str(self.module.PROFILE_TARGET)],
            calls,
        )

    def test_install_fails_closed_on_conflicting_profile_file(self):
        residue = self.appd / "bwrap"
        residue.write_text(RESIDUE_PROFILE)
        residue_bytes = residue.read_bytes()
        calls = []
        self.enforce()

        with self.assertRaises(self.module.SetupError) as ctx:
            self.module.install_profile(make_runner(calls))

        report = ctx.exception.report
        self.assertEqual([str(residue)], report["conflicting_profile_files"])
        self.assertIn("fail-closed", report["error"])
        # Fails before writing/loading the candidate: no runner calls at
        # all, no candidate file, and the conflict survives byte-for-byte.
        self.assertEqual([], calls)
        self.assertFalse(self.module.PROFILE_TARGET.exists())
        self.assertEqual(residue_bytes, residue.read_bytes())

    def test_install_fails_closed_on_conflict_even_when_already_enforced(self):
        residue = self.appd / "bwrap"
        residue.write_text(RESIDUE_PROFILE)
        residue_bytes = residue.read_bytes()
        self.install_good_state()
        calls = []

        with self.assertRaises(self.module.SetupError) as ctx:
            self.module.install_profile(make_runner(calls))

        self.assertEqual(
            [str(residue)], ctx.exception.report["conflicting_profile_files"]
        )
        self.assertEqual([], calls)
        self.assertEqual(residue_bytes, residue.read_bytes())
        # Our own previously installed target is left untouched as well.
        self.assertEqual(
            self.source.read_text(), self.module.PROFILE_TARGET.read_text()
        )

    def test_install_dry_run_reports_conflict_without_mutation(self):
        residue = self.appd / "bwrap"
        residue.write_text(RESIDUE_PROFILE)
        residue_bytes = residue.read_bytes()
        calls = []

        report = self.module.install_profile(make_runner(calls), dry_run=True)

        self.assertFalse(report["ok"])
        self.assertTrue(report["dry_run"])
        self.assertEqual([str(residue)], report["conflicting_profile_files"])
        self.assertIn("fail-closed", report["error"])
        self.assertEqual([], calls)
        self.assertFalse(self.module.PROFILE_TARGET.exists())
        self.assertEqual(residue_bytes, residue.read_bytes())

    def test_install_never_unlinks_or_unloads_conflicts(self):
        residue = self.appd / "bwrap"
        residue.write_text(RESIDUE_PROFILE)
        calls = []
        self.enforce()
        with self.assertRaises(self.module.SetupError):
            self.module.install_profile(make_runner(calls))
        forbidden = [
            argv
            for argv in calls
            if str(residue) in argv or "-R" in argv
        ]
        self.assertEqual([], forbidden)
        self.assertTrue(residue.exists())

    def test_install_fails_closed_on_parser_load_error(self):
        calls = []

        def behavior(argv):
            if "-r" in argv:
                return Proc(1, "", "AppArmor parser error")
            return Proc()

        with self.assertRaises(self.module.SetupError):
            self.module.install_profile(make_runner(calls, behavior))

        self.assertFalse(self.module.PROFILE_TARGET.exists())
        self.assertIn(
            ["apparmor_parser", "-R", str(self.module.PROFILE_TARGET)], calls
        )

    def test_install_fails_closed_when_enforce_not_reached(self):
        calls = []
        # Kernel policy stays empty: -r "succeeded" but profile never enforced.
        with self.assertRaisesRegex(self.module.SetupError, "enforce"):
            self.module.install_profile(make_runner(calls))

        self.assertFalse(self.module.PROFILE_TARGET.exists())

    def test_install_rejects_invalid_source_without_host_changes(self):
        self.source.write_text("profile x /usr/bin/other {\n}\n")
        calls = []
        with self.assertRaises(self.module.SetupError):
            self.module.install_profile(make_runner(calls))
        self.assertEqual([], calls)
        self.assertFalse(self.module.PROFILE_TARGET.exists())

    def test_install_requires_root(self):
        self.module._is_root = lambda: False
        with self.assertRaisesRegex(self.module.SetupError, "requires root"):
            self.module.install_profile(make_runner([]))
        self.assertFalse(self.module.PROFILE_TARGET.exists())

    def test_install_dry_run_makes_no_changes(self):
        self.module._is_root = lambda: False
        calls = []
        report = self.module.install_profile(make_runner(calls), dry_run=True)
        self.assertTrue(report["ok"])
        self.assertTrue(report["dry_run"])
        self.assertIn(
            f"write {self.module.PROFILE_TARGET} (mode 0644)", report["plan"]
        )
        self.assertFalse(self.module.PROFILE_TARGET.exists())

    def test_install_never_touches_userns_sysctl(self):
        calls = []
        self.enforce()
        self.module.install_profile(make_runner(calls))
        self.assertEqual("1\n", self.sysctl.read_text())
        self.assertFalse(
            any("sysctl" in argv[0] or "systemctl" in argv[0] for argv in calls)
        )


class RemoveTests(ModuleFixture):
    def test_remove_unloads_and_deletes(self):
        self.install_good_state()
        calls = []

        def behavior(argv):
            if "-R" in argv:
                self.sys_profiles.write_text("")
            return Proc()

        report = self.module.remove_profile(make_runner(calls, behavior))

        self.assertTrue(report["ok"])
        self.assertFalse(self.module.PROFILE_TARGET.exists())
        self.assertIn(
            ["apparmor_parser", "-R", str(self.module.PROFILE_TARGET)], calls
        )

    def test_remove_is_idempotent_when_absent(self):
        calls = []
        self.sys_profiles.write_text("")
        report = self.module.remove_profile(make_runner(calls))
        self.assertTrue(report["ok"])
        self.assertIn(
            ["apparmor_parser", "-R", str(self.module.PROFILE_SOURCE)], calls
        )

    def test_remove_fails_if_profile_still_loaded(self):
        self.install_good_state()
        calls = []
        with self.assertRaisesRegex(self.module.SetupError, "still loaded"):
            self.module.remove_profile(make_runner(calls))

    def test_remove_dry_run_makes_no_changes(self):
        self.install_good_state()
        report = self.module.remove_profile(make_runner([]), dry_run=True)
        self.assertTrue(report["ok"])
        self.assertTrue(self.module.PROFILE_TARGET.exists())

    def test_remove_preserves_conflicting_profile_files(self):
        self.install_good_state()
        residue = self.appd / "bwrap"
        residue.write_text(RESIDUE_PROFILE)
        residue_bytes = residue.read_bytes()
        calls = []

        def behavior(argv):
            if "-R" in argv:
                self.sys_profiles.write_text("")
            return Proc()

        report = self.module.remove_profile(make_runner(calls, behavior))

        self.assertTrue(report["ok"])
        self.assertFalse(self.module.PROFILE_TARGET.exists())
        self.assertEqual([str(residue)], report["conflicting_profile_files"])
        # The conflict file is never unloaded or unlinked: only our own
        # PROFILE_TARGET appears in the -R argv list.
        self.assertEqual(residue_bytes, residue.read_bytes())
        self.assertFalse(any(str(residue) in argv for argv in calls))
        self.assertIn(
            ["apparmor_parser", "-R", str(self.module.PROFILE_TARGET)], calls
        )


class StatusTests(ModuleFixture):
    def args(self, **kw):
        base = dict(require_enforce=False, probe_bwrap=False)
        base.update(kw)
        return SimpleNamespace(**base)

    def test_status_reports_enforced_state(self):
        self.install_good_state()
        status = self.module.collect_status(make_runner([]))
        self.assertTrue(status["ok"])
        self.assertEqual("enforce", status["kernel_mode"])
        self.assertEqual(1, status["restrict_unprivileged_userns"])

    def test_require_enforce_passes_on_good_state(self):
        self.install_good_state()
        rc, _ = silent(self.module.cmd_status, self.args(require_enforce=True),
                       make_runner([]))
        self.assertEqual(0, rc)

    def test_require_enforce_fails_when_profile_absent(self):
        self.sys_profiles.write_text("")
        calls = []
        rc, _ = silent(
            self.module.cmd_status,
            self.args(require_enforce=True),
            make_runner(calls),
        )
        self.assertEqual(2, rc)

    def test_require_enforce_uses_functional_probe_when_kernel_unreadable(self):
        self.install_good_state()
        self.sys_profiles.unlink()
        calls = []

        def behavior(argv):
            if argv[0] == "aa-status":
                return Proc(1, "", "aa-status requires root")
            if argv[0] == "bwrap":
                return Proc(0)
            return Proc()

        rc, _ = silent(
            self.module.cmd_status,
            self.args(require_enforce=True),
            make_runner(calls, behavior),
        )
        self.assertEqual(0, rc)
        self.assertTrue(any(argv[0] == "bwrap" for argv in calls))

    def test_require_enforce_fails_when_functional_probe_fails(self):
        self.install_good_state()
        self.sys_profiles.unlink()

        def behavior(argv):
            return Proc(1, "", "denied")

        rc, _ = silent(
            self.module.cmd_status,
            self.args(require_enforce=True),
            make_runner([], behavior),
        )
        self.assertEqual(2, rc)

    def test_require_enforce_fails_on_complain_mode(self):
        self.install_good_state()
        self.enforce(mode="complain")
        rc, _ = silent(
            self.module.cmd_status,
            self.args(require_enforce=True),
            make_runner([]),
        )
        self.assertEqual(2, rc)

    def test_require_enforce_fails_when_sysctl_disabled(self):
        self.install_good_state()
        self.sysctl.write_text("0\n")
        rc, _ = silent(
            self.module.cmd_status,
            self.args(require_enforce=True),
            make_runner([]),
        )
        self.assertEqual(2, rc)

    def test_require_enforce_fails_on_installed_mismatch(self):
        self.install_good_state()
        self.module.PROFILE_TARGET.write_text("tampered\n")
        rc, _ = silent(
            self.module.cmd_status,
            self.args(require_enforce=True),
            make_runner([]),
        )
        self.assertEqual(2, rc)

    def test_require_enforce_fails_on_unreadable_installed_profile(self):
        self.install_good_state()
        self.module.PROFILE_TARGET.chmod(0)
        self.addCleanup(self.module.PROFILE_TARGET.chmod, 0o644)
        rc, _ = silent(
            self.module.cmd_status,
            self.args(require_enforce=True),
            make_runner([]),
        )
        self.assertEqual(2, rc)

    def test_status_reports_conflict_and_not_ok_even_when_enforced(self):
        self.install_good_state()
        residue = self.appd / "bwrap"
        residue.write_text(RESIDUE_PROFILE)

        status = self.module.collect_status(make_runner([]))

        self.assertEqual("enforce", status["kernel_mode"])
        self.assertTrue(status["installed_match"])
        self.assertEqual([str(residue)], status["conflicting_profile_files"])
        self.assertFalse(status["ok"])

    def test_require_enforce_fails_on_conflict_even_when_enforced(self):
        self.install_good_state()
        residue = self.appd / "bwrap"
        residue.write_text(RESIDUE_PROFILE)

        rc, out = silent(
            self.module.cmd_status,
            self.args(require_enforce=True),
            make_runner([]),
        )

        self.assertEqual(2, rc)
        self.assertIn(str(residue), out)


class CommandConstructionTests(ModuleFixture):
    def test_smoke_argv_uses_autonomous_sandbox(self):
        argv = self.module.build_smoke_argv(
            devin_bin="/usr/bin/devin",
            model="swe-2-max",
            config=Path("/tmp/cfg.json"),
            prompt=Path("/tmp/prompt.txt"),
            export=Path("/tmp/export.json"),
        )
        self.assertEqual(
            [
                "/usr/bin/devin",
                "-p",
                "--model",
                "swe-2-max",
                "--permission-mode",
                "autonomous",
                "--sandbox",
                "--respect-workspace-trust",
                "false",
                "--config",
                "/tmp/cfg.json",
                "--prompt-file",
                "/tmp/prompt.txt",
                "--export",
                "/tmp/export.json",
            ],
            argv,
        )

    def test_smoke_argv_carries_no_credential_material(self):
        argv = " ".join(
            self.module.build_smoke_argv(
                devin_bin="devin",
                model="m",
                config=Path("/c"),
                prompt=Path("/p"),
                export=Path("/e"),
            )
        )
        for value in (self.module.CRED_VALUE, self.module.CHECKOUT_VALUE):
            self.assertNotIn(value, argv)
        self.assertNotIn("token", argv.lower())

    def test_functional_probe_is_bounded_bwrap_true(self):
        argv = list(self.module.BWRAP_FUNCTIONAL_ARGV)
        self.assertEqual("bwrap", argv[0])
        self.assertIn("--unshare-all", argv)
        self.assertEqual("/bin/true", argv[-1])
        self.assertNotIn("sudo", argv)


class ProbeWorkspaceTests(ModuleFixture):
    def test_probe_workspace_sentinels_and_deny_rules(self):
        with tempfile.TemporaryDirectory() as td:
            probe = self.module.build_probe_workspace(Path(td))
            cred = probe["credential_sentinel"].read_text()
            guard = probe["checkout_sentinel"].read_text()
            self.assertIn(self.module.CRED_VALUE, cred)
            self.assertIn(self.module.CHECKOUT_VALUE, guard)
            self.assertIn("LOGRES_FAKE_DEVIN_TOKEN", cred)

            config = json.loads(probe["config"].read_text())
            deny = config["permissions"]["deny"]
            self.assertIn(
                f"Read({probe['credential_sentinel']})", deny
            )
            self.assertIn(
                f"Read({probe['checkout_sentinel']})", deny
            )
            self.assertIn(f"Read({probe['protected']}/**)", deny)
            self.assertIn("Exec(sudo *)", deny)
            self.assertEqual(
                ["logres-sandbox-probe.invalid"],
                config["sandbox"]["allowed_domains"],
            )
            self.assertIn("169.254.169.254", config["sandbox"]["denied_domains"])

            self.assertIn("sh probe.sh", probe["prompt"].read_text())
            script = probe["probe"].read_text()
            self.assertNotIn(self.module.CRED_VALUE, script)
            self.assertNotIn(self.module.CHECKOUT_VALUE, script)
            self.assertIn(str(probe["credential_sentinel"]), script)

    def test_probe_script_passes_shell_syntax_check(self):
        with tempfile.TemporaryDirectory() as td:
            probe = self.module.build_probe_workspace(Path(td))
            proc = subprocess.run(
                ["sh", "-n", str(probe["probe"])],
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, proc.returncode, proc.stderr)

    def test_probe_sentinels_live_only_under_probe_root(self):
        with tempfile.TemporaryDirectory() as td:
            probe = self.module.build_probe_workspace(Path(td))
            for key in ("credential_sentinel", "checkout_sentinel"):
                self.assertTrue(str(probe[key]).startswith(td))


class TranscriptEvaluationTests(ModuleFixture):
    GOOD = (
        "LOGRES_SANDBOX_EXEC_OK\n"
        "LOGRES_SENTINEL_CRED_BLOCKED\n"
        "LOGRES_CHECKOUT_BLOCKED\n"
        "LOGRES_META_BLOCKED\n"
        "LOGRES_LOOP_BLOCKED\n"
        "LOGRES_PROBE_DONE\n"
    )

    def test_evaluate_all_blocked_passes(self):
        checks = self.module.evaluate_probe_transcript(self.GOOD)
        self.assertTrue(all(checks.values()), checks)

    def test_evaluate_detects_credential_leak(self):
        text = self.GOOD.replace(
            "LOGRES_SENTINEL_CRED_BLOCKED", "LOGRES_SENTINEL_CRED_LEAKED"
        ) + self.module.CRED_VALUE
        checks = self.module.evaluate_probe_transcript(text)
        self.assertFalse(checks["credential_sentinel_hidden"])
        self.assertFalse(all(checks.values()))

    def test_evaluate_detects_checkout_leak(self):
        text = self.GOOD.replace(
            "LOGRES_CHECKOUT_BLOCKED", "LOGRES_CHECKOUT_LEAKED"
        )
        checks = self.module.evaluate_probe_transcript(text)
        self.assertFalse(checks["checkout_sentinel_hidden"])

    def test_evaluate_detects_metadata_reached(self):
        text = self.GOOD.replace("LOGRES_META_BLOCKED", "LOGRES_META_REACHED")
        checks = self.module.evaluate_probe_transcript(text)
        self.assertFalse(checks["oci_metadata_blocked"])

    def test_evaluate_detects_loopback_reached(self):
        text = self.GOOD.replace("LOGRES_LOOP_BLOCKED", "LOGRES_LOOP_REACHED")
        checks = self.module.evaluate_probe_transcript(text)
        self.assertFalse(checks["host_loopback_blocked"])


class SmokeTests(ModuleFixture):
    def args(self, **kw):
        base = dict(
            devin_bin=str(self.devin),
            model="swe-2-max",
            timeout=30.0,
            keep_probe=False,
        )
        base.update(kw)
        return SimpleNamespace(**base)

    def fake_devin(self, transcript):
        def behavior(argv):
            if argv[0].endswith("devin"):
                export = Path(argv[argv.index("--export") + 1])
                export.write_text(transcript)
            return Proc()

        return behavior

    def test_smoke_fails_closed_without_install(self):
        calls = []
        rc, out = silent(
            self.module.cmd_smoke,
            self.args(),
            make_runner(calls),
        )
        self.assertEqual(2, rc)
        self.assertFalse(any(a[0].endswith("devin") for a in calls))

    def test_smoke_fails_closed_on_conflicting_profile_file(self):
        self.install_good_state()
        residue = self.appd / "bwrap"
        residue.write_text(RESIDUE_PROFILE)
        calls = []
        rc, out = silent(
            self.module.cmd_smoke, self.args(), make_runner(calls)
        )
        self.assertEqual(2, rc)
        self.assertIn(str(residue), out)
        self.assertFalse(any(a[0].endswith("devin") for a in calls))

    def test_smoke_fails_closed_when_kernel_mode_absent(self):
        self.install_good_state()
        self.sys_profiles.write_text("")
        calls = []
        rc, _ = silent(
            self.module.cmd_smoke, self.args(), make_runner(calls)
        )
        self.assertEqual(2, rc)
        self.assertFalse(any(a[0].endswith("devin") for a in calls))

    def test_smoke_passes_with_full_block_transcript(self):
        self.install_good_state()
        rc, out = silent(
            self.module.cmd_smoke,
            self.args(),
            make_runner([], self.fake_devin(TranscriptEvaluationTests.GOOD)),
        )
        self.assertEqual(0, rc)
        self.assertIn('"ok": true', out)

    def test_smoke_detects_sentinel_leak(self):
        self.install_good_state()
        text = TranscriptEvaluationTests.GOOD.replace(
            "LOGRES_SENTINEL_CRED_BLOCKED", "LOGRES_SENTINEL_CRED_LEAKED"
        )
        rc, out = silent(
            self.module.cmd_smoke,
            self.args(),
            make_runner([], self.fake_devin(text)),
        )
        self.assertEqual(1, rc)
        self.assertIn('"credential_sentinel_hidden": false', out)

    def test_smoke_detects_network_reach(self):
        self.install_good_state()
        text = TranscriptEvaluationTests.GOOD.replace(
            "LOGRES_META_BLOCKED", "LOGRES_META_REACHED"
        )
        rc, _ = silent(
            self.module.cmd_smoke,
            self.args(),
            make_runner([], self.fake_devin(text)),
        )
        self.assertEqual(1, rc)

    def test_smoke_fails_when_devin_binary_missing(self):
        self.install_good_state()
        rc, _ = silent(
            self.module.cmd_smoke,
            self.args(devin_bin="/nonexistent/devin-xyz"),
            make_runner([]),
        )
        self.assertEqual(2, rc)

    def test_smoke_runs_devin_when_kernel_state_unreadable(self):
        # No privilege to read kernel policy: the probe still runs because
        # devin --sandbox fails closed by itself when enforcement is absent.
        self.install_good_state()
        self.sys_profiles.unlink()

        def behavior(argv):
            if argv[0] == "aa-status":
                return Proc(1, "", "denied")
            if argv[0].endswith("devin"):
                export = Path(argv[argv.index("--export") + 1])
                export.write_text(TranscriptEvaluationTests.GOOD)
            return Proc()

        rc, _ = silent(self.module.cmd_smoke, self.args(), make_runner([], behavior))
        self.assertEqual(0, rc)

    def test_smoke_argv_never_contains_sentinel_values(self):
        self.install_good_state()
        seen = []
        rc, _ = silent(
            self.module.cmd_smoke,
            self.args(),
            make_runner(seen, self.fake_devin(TranscriptEvaluationTests.GOOD)),
        )
        self.assertEqual(0, rc)
        joined = " ".join(a for argv in seen for a in argv)
        self.assertNotIn(self.module.CRED_VALUE, joined)
        self.assertNotIn(self.module.CHECKOUT_VALUE, joined)


class DeploymentManifestTests(unittest.TestCase):
    def test_manifest_covers_new_runtime_files(self):
        import deploy_control_plane

        self.assertIn("bin/logres-devin-sandbox-setup", deploy_control_plane.MANIFEST)
        self.assertIn("apparmor/usr.bin.bwrap.logres", deploy_control_plane.MANIFEST)
        self.assertEqual(
            0o755,
            deploy_control_plane.MANIFEST["bin/logres-devin-sandbox-setup"][1],
        )
        self.assertEqual(
            0o600,
            deploy_control_plane.MANIFEST["apparmor/usr.bin.bwrap.logres"][1],
        )

    def test_deploy_dry_run_includes_new_files(self):
        import deploy_control_plane

        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "target"
            deployed = deploy_control_plane.deploy(
                CONTROL_ROOT, target, dry_run=True
            )
            destinations = {
                str(item.destination.relative_to(target)) for item in deployed
            }
            self.assertIn("bin/logres-devin-sandbox-setup", destinations)
            self.assertIn("apparmor/usr.bin.bwrap.logres", destinations)


if __name__ == "__main__":
    unittest.main()
