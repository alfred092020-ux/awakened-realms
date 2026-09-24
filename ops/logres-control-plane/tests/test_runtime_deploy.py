import importlib.machinery
import importlib.util
import json
import shutil
import subprocess
import tempfile
import types
import unittest
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
SCRIPT = TEST_DIR.parent / "bin" / "logres-runtime-deploy"


def load_module():
    name = "test_logres_runtime_deploy"
    loader = importlib.machinery.SourceFileLoader(name, str(SCRIPT))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


runtime = load_module()


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=True,
    )
    return proc.stdout.strip()


def init_repo(root: Path) -> tuple[Path, str]:
    repo = root / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "config", "user.name", "Test")
    git(repo, "checkout", "-q", "-b", runtime.INTEGRATION_BRANCH)
    (repo / "marker.txt").write_text("clean\n")
    source = repo / "ops" / "logres-control-plane" / "bin"
    source.mkdir(parents=True)
    (source / "fake-helper").write_text("helper-v1\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "fixture")
    return repo, git(repo, "rev-parse", "HEAD")
class RuntimeDeployTests(unittest.TestCase):
    def test_rejects_non_full_sha(self):
        with self.assertRaises(runtime.RuntimeDeployError):
            runtime.ensure_exact_sha("abc123")

    def test_rejects_sha_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            repo, _ = init_repo(Path(td))
            wrong = "a" * 40
            with self.assertRaisesRegex(
                runtime.RuntimeDeployError,
                "source/head mismatch",
            ):
                runtime.validate_integration_source(repo, wrong)

    def test_rejects_dirty_integration_worktree(self):
        with tempfile.TemporaryDirectory() as td:
            repo, sha = init_repo(Path(td))
            (repo / "marker.txt").write_text("dirty\n")
            with self.assertRaisesRegex(
                runtime.RuntimeDeployError,
                "worktree is dirty",
            ):
                runtime.validate_integration_source(repo, sha)

    def test_success_deploys_hashes_and_writes_stamp(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo, sha = init_repo(root)
            target = root / "runtime"
            stamp = root / "stamp.json"

            def fake_deploy(source_root, target_root, dry_run=False):
                source = source_root / "bin" / "fake-helper"
                destination = target_root / "bin" / "fake-helper"
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                return [
                    types.SimpleNamespace(
                        source=source,
                        destination=destination,
                        mode=0o755,
                    )
                ]

            def runner(argv, **kwargs):
                argv = [str(x) for x in argv]
                if argv and argv[0] == "git":
                    return subprocess.run(argv, **kwargs)
                self.assertEqual(
                    [
                        str(target / "bin" / "logres-autonomy-cron"),
                        "install",
                    ],
                    argv,
                )
                return subprocess.CompletedProcess(argv, 0, "ok\n", "")

            payload = runtime.deploy_runtime(
                repo,
                target,
                sha,
                stamp_path=stamp,
                deploy_fn=fake_deploy,
                runner=runner,
            )

            self.assertEqual(sha, payload["integration_sha"])
            self.assertEqual(1, payload["file_count"])
            self.assertTrue(stamp.is_file())
            saved = json.loads(stamp.read_text())
            self.assertEqual(sha, saved["integration_sha"])
            self.assertEqual(
                runtime.sha256_file(
                    repo
                    / "ops"
                    / "logres-control-plane"
                    / "bin"
                    / "fake-helper"
                ),
                saved["files"]["bin/fake-helper"],
            )

    def test_cron_failure_aborts_before_stamp(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo, sha = init_repo(root)
            target = root / "runtime"
            stamp = root / "stamp.json"

            def fake_deploy(source_root, target_root, dry_run=False):
                source = source_root / "bin" / "fake-helper"
                destination = target_root / "bin" / "fake-helper"
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                return [
                    types.SimpleNamespace(
                        source=source,
                        destination=destination,
                        mode=0o755,
                    )
                ]

            def runner(argv, **kwargs):
                argv = [str(x) for x in argv]
                if argv and argv[0] == "git":
                    return subprocess.run(argv, **kwargs)
                return subprocess.CompletedProcess(
                    argv,
                    1,
                    "",
                    "cron failed",
                )

            with self.assertRaisesRegex(
                runtime.RuntimeDeployError,
                "cron reconciliation failed",
            ):
                runtime.deploy_runtime(
                    repo,
                    target,
                    sha,
                    stamp_path=stamp,
                    deploy_fn=fake_deploy,
                    runner=runner,
                )
            self.assertFalse(stamp.exists())


if __name__ == "__main__":
    unittest.main()
