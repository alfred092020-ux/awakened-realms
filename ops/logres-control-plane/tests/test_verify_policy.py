import os
import subprocess
import unittest
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
SCRIPT = CONTROL_ROOT / "bin" / "logres-verify-farm"


def policy_env(**updates):
    env = os.environ.copy()
    env.pop("LOGRES_E2E_WORKERS", None)
    env.pop("LOGRES_CPU_COUNT_OVERRIDE", None)
    env.update(updates)
    return env


def read_workers(**env_updates):
    return subprocess.run(
        [str(SCRIPT), "--print-e2e-workers"],
        text=True,
        capture_output=True,
        env=policy_env(**env_updates),
        check=False,
    )


class VerifyFarmE2EPolicyTests(unittest.TestCase):
    def test_low_core_host_defaults_to_one_worker(self):
        result = read_workers(LOGRES_CPU_COUNT_OVERRIDE="7")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("1", result.stdout.strip())

    def test_eight_or_more_cores_defaults_to_three_workers(self):
        for cpus in ("8", "12", "64"):
            with self.subTest(cpus=cpus):
                result = read_workers(LOGRES_CPU_COUNT_OVERRIDE=cpus)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual("3", result.stdout.strip())

    def test_explicit_override_wins_within_bounded_range(self):
        for workers in ("1", "2", "3", "4"):
            with self.subTest(workers=workers):
                result = read_workers(
                    LOGRES_CPU_COUNT_OVERRIDE="1",
                    LOGRES_E2E_WORKERS=workers,
                )
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(workers, result.stdout.strip())

    def test_invalid_override_is_rejected_fail_closed(self):
        for workers in ("0", "5", "abc", "2.5", "-1"):
            with self.subTest(workers=workers):
                result = read_workers(LOGRES_E2E_WORKERS=workers)
                self.assertEqual(2, result.returncode)
                self.assertIn(
                    "LOGRES_E2E_WORKERS must be an integer from 1 through 4",
                    result.stderr,
                )

    def test_invalid_cpu_probe_falls_back_to_one_worker(self):
        result = read_workers(LOGRES_CPU_COUNT_OVERRIDE="not-a-number")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("1", result.stdout.strip())

    def test_parallelism_changes_scheduling_not_authority(self):
        text = SCRIPT.read_text()
        self.assertIn(
            'exec 9>/tmp/logres-verify-farm.lock',
            text,
        )
        self.assertIn(
            'SHA=$(git -C "$BASE" rev-parse "$REF")',
            text,
        )
        self.assertIn(
            'hydrate "$E2E_WT"',
            text,
        )
        self.assertIn(
            'npm run test:e2e -- --workers="$E2E_WORKERS"',
            text,
        )
        self.assertIn(
            'full-e2e "$status"',
            text,
        )
        self.assertIn(
            'E2E_VERIFY_TAG="e2e-w${E2E_WORKERS}"',
            text,
        )


if __name__ == "__main__":
    unittest.main()
