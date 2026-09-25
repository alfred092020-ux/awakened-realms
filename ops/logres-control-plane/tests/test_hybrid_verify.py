import json
import subprocess
import unittest
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
SCRIPT = CONTROL_ROOT / "bin" / "logres-verify-farm"
CONFIG = CONTROL_ROOT / "config" / "autoflow.default.json"


class HybridVerifyTests(unittest.TestCase):
    def test_shell_is_syntactically_valid(self):
        result = subprocess.run(
            ["bash", "-n", str(SCRIPT)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_default_policy_is_fail_closed_for_remote_offload(self):
        cfg = json.loads(CONFIG.read_text())
        remote = cfg["remote_pool"]

        self.assertFalse(remote["enabled"])
        self.assertFalse(remote["hybrid_verify_enabled"])
        self.assertTrue(remote["local_e2e_authoritative"])

    def test_remote_lane_is_exact_sha_and_never_replaces_local_e2e(self):
        text = SCRIPT.read_text()

        self.assertIn(
            'SHA=$(git -C "$BASE" rev-parse "$REF")',
            text,
        )
        self.assertIn(
            '"$POOL_BIN" run auto "$job" test "$SHA"',
            text,
        )
        self.assertIn(
            'npm run test:e2e',
            text,
        )
        self.assertIn(
            'adaptive remote unit-test lane started',
            text,
        )
        self.assertIn(
            'remote unit-test lane unavailable/failed; falling back locally',
            text,
        )
        self.assertIn(
            'run_local_tests',
            text,
        )

    def test_unit_cache_never_replaces_local_private_e2e(self):
        text = SCRIPT.read_text()
        self.assertIn('CACHE_MODE="unit"', text)
        self.assertIn('if cache_hit; then', text)
        self.assertIn('VERIFY_PATH="cache-test+local-build-e2e"', text)
        self.assertIn('cache_store_pass', text)
        shared_cmd = 'npm run test:e2e -- "${shared_e2e_specs[@]}" --workers="$E2E_WORKERS"'
        perf_cmd = 'npm run test:e2e -- "$PERF_SPEC_REL" --workers=1'
        self.assertIn(shared_cmd, text)
        self.assertIn(perf_cmd, text)
        self.assertLess(
            text.index(shared_cmd),
            text.index('if cache_hit; then'),
        )
        self.assertGreater(
            text.index(perf_cmd),
            text.index('e2e_rc=0'),
        )
        cache_block = text[
            text.index('if cache_hit; then'):
            text.index('e2e_rc=0')
        ]
        self.assertNotIn('exit 0', cache_block)
        self.assertIn('wait "$e2e_pid"', text)

    def test_performance_waits_for_shared_e2e_and_unit_lane_before_measurement(self):
        text = SCRIPT.read_text()
        self.assertLess(
            text.index('wait "$e2e_pid" || e2e_rc=$?'),
            text.index('performance_rc=0'),
        )
        self.assertIn('performance_host_ready', text)
        self.assertIn('performance_rc == 75', text)

    def test_cache_dimensions_fail_closed_and_are_exact_sha_keyed(self):
        text = SCRIPT.read_text()
        self.assertIn('--source-sha "$SHA"', text)
        self.assertIn('--lock-hash "$lock_hash"', text)
        self.assertIn('--config-hash "$config_hash"', text)
        self.assertIn('--evidence-version "$evidence_version"', text)
        self.assertIn('--env-hash "$env_hash"', text)
        self.assertIn('--mode "$CACHE_MODE"', text)
        self.assertIn('[[ -s "$PRIVATE_ANCHOR" ]] || return 0', text)

    def test_remote_pool_has_no_merge_or_deploy_authority(self):
        pool = (CONTROL_ROOT / "lib" / "logres_remote_pool.py").read_text()

        self.assertIn("FORBIDDEN_SCRIPT_WORDS", pool)
        self.assertIn('"merge"', pool)
        self.assertIn('"deploy"', pool)
        self.assertIn("ensure_exact_sha", pool)


if __name__ == "__main__":
    unittest.main()
