import fcntl
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin/logres-phone-qa"


class PhoneInputArbitrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.lock = self.base / "qa.lock"
        self.fakebin = self.base / "bin"
        self.fakebin.mkdir()
        self.ssh_log = self.base / "ssh.log"
        (self.fakebin / "ss").write_text("#!/bin/sh\nexit 0\n")
        (self.fakebin / "ssh").write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" >> \"$FAKE_SSH_LOG\"\n"
            "case \"$*\" in\n"
            "  *'_adb-tls-connect'*) echo 5555 ;;\n"
            "  *'adb devices'*) echo '127.0.0.1:5555' ;;\n"
            "esac\n"
        )
        os.chmod(self.fakebin / "ss", 0o755)
        os.chmod(self.fakebin / "ssh", 0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def env(self):
        env = os.environ.copy()
        env["PATH"] = f"{self.fakebin}:{env['PATH']}"
        env["FAKE_SSH_LOG"] = str(self.ssh_log)
        env["LOGRES_PHONE_QA_LOCK_PATH"] = str(self.lock)
        env["LOGRES_PHONE_QA_KEY"] = str(self.base / "fake-key")
        return env

    def run_script(self, *args, env=None, pass_fds=()):
        return subprocess.run(
            [str(SCRIPT), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env or self.env(),
            pass_fds=pass_fds,
            check=False,
        )

    def test_canonical_transport_exists(self):
        self.assertTrue(SCRIPT.is_file(), "canonical logres-phone-qa is missing")

    def test_deployment_manifest_includes_canonical_transport(self):
        import sys
        repo_root = ROOT.parents[1]
        sys.path.insert(0, str(repo_root / "scripts/logres"))
        try:
            from deploy_control_plane import MANIFEST
            self.assertIn("bin/logres-phone-qa", MANIFEST)
        finally:
            sys.path.pop(0)

    def test_external_tap_is_rejected_while_hardware_qa_owns_lock(self):
        self.lock.touch()
        with self.lock.open("r+") as owner:
            fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_script("shell", "PATH=/system/bin:/system/xbin input tap 540 1960")
        self.assertEqual(75, result.returncode, result.stderr)
        self.assertIn("PHONE_QA_BUSY", result.stderr)
        self.assertFalse(self.ssh_log.exists())

    def test_forged_unlocked_fd_cannot_impersonate_hardware_qa_owner(self):
        self.lock.touch()
        with self.lock.open("r+") as owner, self.lock.open("r+") as impostor:
            fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.set_inheritable(impostor.fileno(), True)
            env = self.env()
            env["LOGRES_PHONE_QA_LOCK_FD"] = str(impostor.fileno())
            result = self.run_script(
                "shell", "input tap 540 1995",
                env=env, pass_fds=(impostor.fileno(),),
            )
        self.assertEqual(75, result.returncode, result.stderr)
        self.assertFalse(self.ssh_log.exists())

    def test_read_only_prefix_cannot_smuggle_a_second_mutating_command(self):
        self.lock.touch()
        with self.lock.open("r+") as owner:
            fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_script(
                "shell", "dumpsys battery; input tap 540 1960"
            )
        self.assertEqual(75, result.returncode, result.stderr)
        self.assertFalse(self.ssh_log.exists())

    def test_inherited_owner_fd_allows_hardware_qa_mutation(self):
        self.lock.touch()
        with self.lock.open("r+") as owner:
            fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.set_inheritable(owner.fileno(), True)
            env = self.env()
            env["LOGRES_PHONE_QA_LOCK_FD"] = str(owner.fileno())
            result = self.run_script(
                "shell", "input tap 540 1916",
                env=env, pass_fds=(owner.fileno(),),
            )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("input tap 540 1916", self.ssh_log.read_text())

    def test_read_only_status_remains_available_while_lock_is_held(self):
        self.lock.touch()
        with self.lock.open("r+") as owner:
            fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_script("status")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("ssh=ok", result.stdout)


if __name__ == "__main__":
    unittest.main()
