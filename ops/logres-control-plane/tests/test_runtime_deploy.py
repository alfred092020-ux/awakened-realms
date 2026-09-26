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
    (source / "logres-supervisor").write_text("supervisor-new\n")
    source_lib = repo / "ops" / "logres-control-plane" / "lib"
    source_lib.mkdir(parents=True)
    (source_lib / "logres_supervisor.py").write_text("library-new\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "fixture")
    return repo, git(repo, "rev-parse", "HEAD")


def deploy_supervisor_runtime(source_root, target_root, dry_run=False):
    items = []
    for relative, mode in (
        ("bin/logres-supervisor", 0o755),
        ("lib/logres_supervisor.py", 0o644),
    ):
        source = source_root / relative
        destination = target_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        items.append(
            types.SimpleNamespace(
                source=source,
                destination=destination,
                mode=mode,
            )
        )
    return items


def seed_old_supervisor(target: Path):
    (target / "bin").mkdir(parents=True, exist_ok=True)
    (target / "lib").mkdir(parents=True, exist_ok=True)
    (target / "bin" / "logres-supervisor").write_text("supervisor-old\n")
    (target / "lib" / "logres_supervisor.py").write_text("library-old\n")


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

    def test_runtime_deploy_lock_fails_closed_when_already_held(self):
        with tempfile.TemporaryDirectory() as td:
            lock_path = Path(td) / "runtime-deploy.lock"
            first = runtime.acquire_runtime_deploy_lock(lock_path)
            try:
                with self.assertRaisesRegex(
                    runtime.RuntimeDeployError,
                    "another runtime deployment holds",
                ):
                    runtime.acquire_runtime_deploy_lock(lock_path)
            finally:
                first.close()

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

            scheduler_calls = []

            def runner(argv, **kwargs):
                argv = [str(x) for x in argv]
                if argv and argv[0] == "git":
                    return subprocess.run(argv, **kwargs)
                scheduler_calls.append(argv)
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
            self.assertTrue(payload["cron_reconciled"])
            self.assertEqual("", payload["cron_diagnostic"])
            self.assertEqual(
                [
                    [str(target / "bin" / "logres-supervisor"), "ensure"],
                    [str(target / "bin" / "logres-autonomy-cron"), "install"],
                ],
                scheduler_calls,
            )
            self.assertEqual(
                "logres-supervisor",
                payload["scheduler"]["authoritative"],
            )
            self.assertEqual(
                "reconciled",
                payload["scheduler"]["legacy_cron"],
            )
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

    def test_changed_supervisor_runtime_requests_reload(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo, sha = init_repo(root)
            target = root / "runtime"
            stamp = root / "stamp.json"
            seed_old_supervisor(target)
            calls = []

            def runner(argv, **kwargs):
                argv = [str(x) for x in argv]
                if argv and argv[0] == "git":
                    return subprocess.run(argv, **kwargs)
                calls.append(argv)
                if argv[-1] == "reload":
                    return subprocess.CompletedProcess(
                        argv,
                        0,
                        json.dumps(
                            {"reload": "reloaded", "healthy": True}
                        ),
                        "",
                    )
                return subprocess.CompletedProcess(argv, 0, "ok\n", "")

            payload = runtime.deploy_runtime(
                repo,
                target,
                sha,
                stamp_path=stamp,
                deploy_fn=deploy_supervisor_runtime,
                runner=runner,
            )

            self.assertTrue(payload["scheduler"]["supervisor_runtime_changed"])
            self.assertEqual(
                "reloaded",
                payload["scheduler"]["supervisor_reload"],
            )
            self.assertEqual(
                [str(target / "bin" / "logres-supervisor"), "reload"],
                calls[0],
            )

    def test_changed_busy_supervisor_records_deferred_reload(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo, sha = init_repo(root)
            target = root / "runtime"
            stamp = root / "stamp.json"
            seed_old_supervisor(target)

            def runner(argv, **kwargs):
                argv = [str(x) for x in argv]
                if argv and argv[0] == "git":
                    return subprocess.run(argv, **kwargs)
                if argv[-1] == "reload":
                    return subprocess.CompletedProcess(
                        argv,
                        0,
                        json.dumps(
                            {
                                "reload": "deferred",
                                "healthy": True,
                                "watcher_pid": 999,
                            }
                        ),
                        "",
                    )
                return subprocess.CompletedProcess(argv, 0, "ok\n", "")

            payload = runtime.deploy_runtime(
                repo,
                target,
                sha,
                stamp_path=stamp,
                deploy_fn=deploy_supervisor_runtime,
                runner=runner,
            )

            self.assertTrue(payload["scheduler"]["supervisor_runtime_changed"])
            self.assertEqual(
                "deferred",
                payload["scheduler"]["supervisor_reload"],
            )
            self.assertTrue(stamp.exists())

    def test_changed_supervisor_reload_failure_aborts_before_stamp(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo, sha = init_repo(root)
            target = root / "runtime"
            stamp = root / "stamp.json"
            seed_old_supervisor(target)

            def runner(argv, **kwargs):
                argv = [str(x) for x in argv]
                if argv and argv[0] == "git":
                    return subprocess.run(argv, **kwargs)
                if argv[-1] == "reload":
                    return subprocess.CompletedProcess(
                        argv,
                        1,
                        "",
                        "replacement unhealthy",
                    )
                return subprocess.CompletedProcess(argv, 0, "ok\n", "")

            with self.assertRaisesRegex(
                runtime.RuntimeDeployError,
                "supervisor failed to reload",
            ):
                runtime.deploy_runtime(
                    repo,
                    target,
                    sha,
                    stamp_path=stamp,
                    deploy_fn=deploy_supervisor_runtime,
                    runner=runner,
                )
            self.assertFalse(stamp.exists())

    def test_cron_failure_is_deferred_when_supervisor_is_healthy(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo, sha = init_repo(root)
            target = root / "runtime"
            stamp = root / "stamp.json"
            scheduler_log = root / "autonomy-cron.log"
            scheduler_log.write_text("old bootstrap cycle\n")

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

            scheduler_calls = []

            def runner(argv, **kwargs):
                argv = [str(x) for x in argv]
                if argv and argv[0] == "git":
                    return subprocess.run(argv, **kwargs)
                scheduler_calls.append(argv)
                if argv[-1] == "ensure":
                    return subprocess.CompletedProcess(
                        argv, 0, "healthy\n", ""
                    )
                return subprocess.CompletedProcess(
                    argv, 1, "", "crontab permission denied"
                )

            now = scheduler_log.stat().st_mtime + 600
            payload = runtime.deploy_runtime(
                repo,
                target,
                sha,
                stamp_path=stamp,
                deploy_fn=fake_deploy,
                runner=runner,
                scheduler_log_path=scheduler_log,
                now_epoch=now,
            )

            self.assertTrue(stamp.exists())
            self.assertFalse(payload["cron_reconciled"])
            self.assertEqual("deferred", payload["scheduler"]["legacy_cron"])
            self.assertIn(
                "permission denied",
                payload["scheduler"]["legacy_cron_detail"],
            )
            self.assertEqual(600.0, payload["scheduler_age_seconds"])
            self.assertEqual(2, len(scheduler_calls))

    def test_supervisor_failure_aborts_before_stamp(self):
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
                    argv, 1, "", "supervisor failed"
                )

            with self.assertRaisesRegex(
                runtime.RuntimeDeployError,
                "supervisor failed to start",
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
