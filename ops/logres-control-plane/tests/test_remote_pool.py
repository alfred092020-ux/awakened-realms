import fcntl
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_remote_pool import (
    PoolError,
    RemotePool,
    count_worker_process_lines,
    WorkerSpec,
    ensure_exact_sha,
    ensure_safe_npm_script,
    exclusive_lock,
    normalize_health,
    select_auto_target,
    store_collected_result,
    targets_for,
    validate_summary,
    verification_ref,
)


SHA = "a" * 40


class RemotePoolPureTests(unittest.TestCase):
    def test_requires_full_immutable_sha(self):
        self.assertEqual(SHA, ensure_exact_sha(SHA))
        with self.assertRaises(PoolError):
            ensure_exact_sha("feat/logres-reconstruction")
        with self.assertRaises(PoolError):
            ensure_exact_sha("a" * 12)

    def test_only_bounded_verification_scripts_are_allowed(self):
        for script in (
            "test",
            "test:unit",
            "verify",
            "verify:all",
            "build",
            "typecheck",
            "lint",
        ):
            self.assertEqual(script, ensure_safe_npm_script(script))

        for script in (
            "deploy",
            "build:deploy",
            "release",
            "publish",
            "push",
            "merge",
            "test;git-push",
            "dev",
        ):
            with self.assertRaises(PoolError):
                ensure_safe_npm_script(script)

    def test_routing_is_deterministic(self):
        self.assertEqual(("heavy",), targets_for("heavy"))
        self.assertEqual(("light",), targets_for("light"))
        self.assertEqual(("heavy", "light"), targets_for("both"))
        self.assertEqual((), targets_for("auto"))
        with self.assertRaises(PoolError):
            targets_for("unknown")

    def test_global_sync_lock_is_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "pool.lock"
            with exclusive_lock(lock_path):
                with lock_path.open("a+") as second:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(
                            second.fileno(),
                            fcntl.LOCK_EX | fcntl.LOCK_NB,
                        )

    def test_worker_counter_ignores_probe_and_pgrep_processes(self):
        lines = [
            "10 python3 -c active_workers oracle_worker.py probe",
            "11 pgrep -af oracle_worker.py",
            "12 python3 scripts/logres/oracle_worker.py /srv/logres/jobs/proof.json",
        ]
        self.assertEqual(1, count_worker_process_lines(lines))

    def test_health_reports_capacity_and_auto_prefers_free_capacity(self):
        heavy = WorkerSpec("heavy", "h1", "heavy", 2)
        light = WorkerSpec("light", "h2", "light", 1)
        base = {
            "hostname": "worker",
            "cpu_count": 4,
            "memory_total_bytes": 8,
            "memory_available_bytes": 7,
            "disk_free_bytes": 100,
            "node_version": "v22.22.2",
            "npm_version": "10.9.7",
            "checkout_sha": SHA,
        }
        heavy_row = normalize_health(
            heavy,
            {**base, "active_workers": 0},
        )
        light_row = normalize_health(
            light,
            {**base, "cpu_count": 2, "active_workers": 0},
        )
        self.assertEqual(2, heavy_row["available_slots"])
        self.assertEqual("heavy", select_auto_target([light_row, heavy_row]))

        heavy_busy = normalize_health(
            heavy,
            {**base, "active_workers": 1},
        )
        self.assertEqual(
            "light",
            select_auto_target([heavy_busy, light_row]),
        )

    def test_collected_result_preserves_machine_and_verification_metadata(self):
        spec = WorkerSpec("heavy", "209.50.63.78", "SJO heavy", 2)
        summary = {
            "schema": 1,
            "job_id": "proof-heavy",
            "source_sha": SHA,
            "status": "success",
            "exit_code": 0,
            "duration_seconds": 12.5,
            "kind": "npm",
            "error": None,
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = store_collected_result(
                Path(tmp),
                "proof",
                spec,
                summary,
                npm_script="test",
            )
            payload = json.loads(path.read_text())
        self.assertEqual("heavy", payload["role"])
        self.assertEqual("209.50.63.78", payload["host"])
        self.assertEqual(SHA, payload["source_sha"])
        self.assertEqual(12.5, payload["duration_seconds"])
        self.assertEqual(0, payload["exit_code"])
        self.assertEqual("test", payload["npm_script"])

    def test_summary_must_match_exact_sha_and_job(self):
        summary = {
            "job_id": "proof-heavy",
            "source_sha": SHA,
            "status": "success",
            "exit_code": 0,
        }
        self.assertEqual(
            summary,
            validate_summary(
                summary,
                expected_sha=SHA,
                expected_job_id="proof-heavy",
            ),
        )
        with self.assertRaises(PoolError):
            validate_summary(
                summary,
                expected_sha="b" * 40,
                expected_job_id="proof-heavy",
            )
        with self.assertRaises(PoolError):
            validate_summary(
                summary,
                expected_sha=SHA,
                expected_job_id="other",
            )


class BundleCapturePool(RemotePool):
    def __init__(self, root: Path):
        workers = {
            "heavy": WorkerSpec("heavy", "h1", "heavy", 1),
            "light": WorkerSpec("light", "h2", "light", 1),
        }
        super().__init__(
            root=root,
            ssh_key=root / "key",
            artifact_root=root / "artifacts",
            workers=workers,
            lock_path=root / "pool.lock",
        )
        self.bundle_heads = []

    def _sync_one(
        self,
        spec: WorkerSpec,
        bundle: Path,
        sha: str,
        verify_ref: str,
    ) -> None:
        heads = subprocess.check_output(
            ["git", "bundle", "list-heads", str(bundle)],
            text=True,
        )
        self.bundle_heads.append(heads)


class RemotePoolExactShaSyncTests(unittest.TestCase):
    def test_dangling_commit_is_bundled_under_temporary_private_ref(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(
                ["git", "-C", str(root), "config", "user.email", "test@example.invalid"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "config", "user.name", "Test"],
                check=True,
            )
            (root / "file.txt").write_text("base\n")
            subprocess.run(["git", "-C", str(root), "add", "file.txt"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "commit", "-q", "-m", "base"],
                check=True,
            )
            tree = subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD^{tree}"],
                text=True,
            ).strip()
            parent = subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                text=True,
            ).strip()
            dangling = subprocess.check_output(
                ["git", "-C", str(root), "commit-tree", tree, "-p", parent],
                input="dangling exact sha\n",
                text=True,
            ).strip()
            self.assertNotEqual(parent, dangling)
            pool = BundleCapturePool(root)
            self.assertEqual(dangling, pool.sync(dangling))
            ref = verification_ref(dangling)
            self.assertEqual(2, len(pool.bundle_heads))
            self.assertTrue(
                all(f"{dangling} {ref}" in heads for heads in pool.bundle_heads)
            )
            local_ref = subprocess.run(
                ["git", "-C", str(root), "show-ref", "--verify", ref],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(0, local_ref.returncode)


class FakePool(RemotePool):
    def __init__(self, failures=()):
        super().__init__(
            root=Path("/tmp/repo"),
            ssh_key=Path("/tmp/key"),
            artifact_root=Path("/tmp/artifacts"),
        )
        self.failures = set(failures)
        self.calls = []
        self.synced = []
        self.cleaned = []

    def sync(self, sha: str) -> str:
        sha = ensure_exact_sha(sha)
        self.synced.append(sha)
        return sha

    def cleanup_verify_ref(self, sha: str) -> None:
        self.cleaned.append(sha)

    def _run_one(self, role: str, job: str, script: str, sha: str) -> dict:
        self.calls.append(role)
        if role in self.failures:
            raise PoolError(f"{role} failed")
        return {
            "role": role,
            "host": self.workers[role].host,
            "summary": {
                "job_id": f"{job}-{role}",
                "source_sha": sha,
                "status": "success",
                "exit_code": 0,
            },
        }

    def health(self):
        return [
            {
                "role": "heavy",
                "reachable": True,
                "active_workers": 0,
                "available_slots": 2,
                "max_slots": 2,
                "cpu_count": 4,
            },
            {
                "role": "light",
                "reachable": True,
                "active_workers": 0,
                "available_slots": 1,
                "max_slots": 1,
                "cpu_count": 2,
            },
        ]


class RemotePoolPolicyTests(unittest.TestCase):
    def test_reassignable_verification_fails_over_once(self):
        pool = FakePool(failures={"heavy"})
        result = pool.run(
            "heavy",
            "proof",
            "test",
            SHA,
            reassignable=True,
            retries=1,
        )
        self.assertEqual(["heavy", "light"], pool.calls)
        self.assertEqual("light", result[0]["role"])
        self.assertEqual([SHA], pool.cleaned)

    def test_non_reassignable_work_never_fails_over(self):
        pool = FakePool(failures={"heavy"})
        with self.assertRaises(PoolError):
            pool.run(
                "heavy",
                "proof",
                "test",
                SHA,
                reassignable=False,
                retries=1,
            )
        self.assertEqual(["heavy"], pool.calls)
        self.assertEqual([SHA], pool.cleaned)

    def test_both_fans_out_to_both_workers(self):
        pool = FakePool()
        result = pool.run("both", "proof", "build", SHA)
        self.assertEqual({"heavy", "light"}, set(pool.calls))
        self.assertEqual(
            {"heavy", "light"},
            {row["role"] for row in result},
        )

    def test_auto_uses_capacity_policy(self):
        pool = FakePool()
        result = pool.run("auto", "proof", "build", SHA)
        self.assertEqual(["heavy"], pool.calls)
        self.assertEqual("heavy", result[0]["role"])

    def test_mutating_script_is_denied_before_remote_execution(self):
        pool = FakePool()
        with self.assertRaises(PoolError):
            pool.run("heavy", "bad", "build:deploy", SHA)
        self.assertEqual([], pool.calls)
        self.assertEqual([], pool.synced)


if __name__ == "__main__":
    unittest.main()
