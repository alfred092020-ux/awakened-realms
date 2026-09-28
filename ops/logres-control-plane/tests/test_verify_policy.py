import importlib.util
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
SCRIPT = CONTROL_ROOT / "bin" / "logres-verify-farm"
REPO_ROOT = CONTROL_ROOT.parents[1]
VISUAL_VERIFIER = REPO_ROOT / "scripts" / "logres" / "verify_visual_checkpoint.py"
BEHAVIOR_VERIFIER = REPO_ROOT / "scripts" / "logres" / "verify_behavior_checkpoint.py"
BEHAVIOR_E2E = REPO_ROOT / "e2e" / "logres-behavioral-checkpoint.spec.mjs"


def load_visual_verifier():
    spec = importlib.util.spec_from_file_location(
        "verify_visual_checkpoint_test",
        VISUAL_VERIFIER,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_behavior_verifier():
    spec = importlib.util.spec_from_file_location(
        "verify_behavior_checkpoint_test",
        BEHAVIOR_VERIFIER,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


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


def repo_head():
    return subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], text=True
    ).strip()


def run_real_performance_selftest(*, benchmark_rc, pressure_rc, control_rc):
    env = policy_env(
        LOGRES_REPO_ROOT=str(REPO_ROOT),
        LOGRES_CONTROL_BIN="/bin/true",
        LOGRES_VERIFY_FARM_PERF_SELFTEST="1",
        LOGRES_VERIFY_FARM_SELFTEST_BENCHMARK_RC=str(benchmark_rc),
        LOGRES_VERIFY_FARM_SELFTEST_PRESSURE_RC=str(pressure_rc),
        LOGRES_VERIFY_FARM_SELFTEST_CONTROL_RC=str(control_rc),
        LOGRES_REMOTE_VERIFY_ENABLED="0",
    )
    return subprocess.run(
        [str(SCRIPT), repo_head()], text=True, capture_output=True, env=env, check=False
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
            'npm run test:e2e -- "${shared_e2e_specs[@]}" --workers="$E2E_WORKERS"',
            text,
        )
        self.assertIn(
            'npm run test:e2e -- "$PERF_SPEC_REL" --workers=1',
            text,
        )
        self.assertIn(
            "! -name 'logres-performance.spec.mjs'",
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
        self.assertIn(
            'CORRECTNESS_POLICY="${LOGRES_CORRECTNESS_POLICY:-/home/ubuntu/logres/config/correctness_policy.json}"',
            text,
        )


    def test_performance_gate_is_mandatory_and_isolated_from_parallel_e2e(self):
        text = SCRIPT.read_text()
        self.assertIn(
            "! -name 'logres-performance.spec.mjs'",
            text,
        )
        self.assertIn(
            'npm run test:e2e -- "$PERF_SPEC_REL" --workers=1',
            text,
        )
        self.assertIn('PERF_LOG=', text)
        self.assertIn('tail -120 "$PERF_LOG"', text)
        self.assertIn('--log "$PERF_LOG"', text)
        self.assertIn('performance_log=$PERF_LOG', text)

    def test_performance_lane_uses_fresh_exact_sha_worktree_after_shared_e2e(self):
        text = SCRIPT.read_text()
        self.assertIn('PERF_WT="$ROOT/verify-farm-$STAMP-performance"', text)
        self.assertIn('git -C "$BASE" worktree add --detach "$PERF_WT" "$SHA"', text)
        self.assertIn('prepare_deps "$PERF_WT"', text)
        self.assertIn('hydrate "$PERF_WT"', text)
        self.assertIn('cd "$PERF_WT"', text)
        self.assertIn('git -C "$BASE" worktree remove --force "$PERF_WT"', text)
        perf_block = text[text.index('performance_rc=0'):text.index('if (( performance_rc == 75 )); then')]
        self.assertNotIn('cd "$E2E_WT"\n      npm run test:e2e -- "$PERF_SPEC_REL"', perf_block)

    def test_performance_lane_setup_failure_cannot_fall_through_to_benchmark(self):
        text = SCRIPT.read_text()
        perf_block = text[text.index('performance_rc=0'):text.index('if (( performance_rc == 75 )); then')]
        self.assertIn(
            'if (( performance_rc == 0 )); then\n    host_rc=0',
            perf_block,
        )
        self.assertIn(
            'npm run test:e2e -- "$PERF_SPEC_REL" --workers=1',
            perf_block,
        )

    def test_performance_host_contention_defers_without_false_failure(self):
        text = SCRIPT.read_text()
        self.assertIn('performance_host_ready()', text)
        self.assertIn('PERF_MAX_CPU_PSI_AVG10="0.5"', text)
        self.assertIn('LOGRES_PERF_HOST_SETTLE_ATTEMPTS', text)
        self.assertIn('LOGRES_PERF_HOST_SETTLE_SLEEP_SEC', text)
        self.assertIn('LOGRES_PERF_HOST_READY_CONSECUTIVE', text)
        self.assertIn('/proc/pressure/cpu', text)
        self.assertIn('ready_streak=', text)
        self.assertIn('time.sleep(sleep_sec)', text)
        self.assertIn('performance_rc=75', text)
        self.assertIn('if (( performance_rc == 75 )); then', text)
        self.assertIn('exit 75', text)
        self.assertIn('no verification verdict recorded', text)
        self.assertLess(
            text.index('wait "$e2e_pid" || e2e_rc=$?'),
            text.index('performance_host_ready >>"$PERF_LOG"'),
        )
        candidate_perf_index = text.index(
            'npm run test:e2e -- "$PERF_SPEC_REL" --workers=1',
            text.index('performance_rc=0'),
        )
        self.assertLess(
            text.index('performance_host_ready >>"$PERF_LOG"'),
            candidate_perf_index,
        )
        self.assertIn('latest_release_control_sha()', text)
        self.assertIn('run_performance_control()', text)
        self.assertIn("milestone_id='RELEASE-1.0'", text)
        self.assertIn('env -u LOGRES_VERIFY_SHA', text)
        self.assertIn('PERF_CONTROL_LOG=', text)
        self.assertIn('certified release control FAIL; timing environment is inconclusive', text)
        self.assertIn('performance_control_log=$PERF_CONTROL_LOG', text)

    def test_candidate_failure_survives_successful_release_control(self):
        text = SCRIPT.read_text()
        start = text.index('resolve_performance_control_outcome()')
        end = text.index('run_local_tests()', start)
        helper = text[start:end]
        script = helper + r'''
PERF_LOG=/tmp/perf-outcome-test.log
run_performance_control() { return "$CONTROL_RC"; }
CONTROL_RC=0
performance_rc=0
resolve_performance_control_outcome 17
printf 'control-pass=%s\n' "$performance_rc"
CONTROL_RC=1
performance_rc=0
resolve_performance_control_outcome 17
printf 'control-fail=%s\n' "$performance_rc"
CONTROL_RC=2
performance_rc=0
resolve_performance_control_outcome 17
printf 'control-unavailable=%s\n' "$performance_rc"
'''
        proc = subprocess.run(
            ['bash', '-c', script], text=True, capture_output=True, check=False
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn('control-pass=17', proc.stdout)
        self.assertIn('control-fail=75', proc.stdout)
        self.assertIn('control-unavailable=17', proc.stdout)

    def test_performance_measurement_outcome_executes_full_decision_matrix(self):
        text = SCRIPT.read_text()
        control_start = text.index('resolve_performance_control_outcome()')
        control_end = text.index('run_local_tests()', control_start)
        helpers = text[control_start:control_end]
        script = helpers + r'''PERF_LOG=/tmp/perf-measurement-outcome-test.log
run_performance_control() { return "$CONTROL_RC"; }
probe() {
  local label="$1" benchmark="$2" pressure="$3" control="$4"
  CONTROL_RC="$control"
  performance_rc=0
  resolve_performance_measurement_outcome "$benchmark" "$pressure"
  printf '%s=%s\n' "$label" "$performance_rc"
}
probe quiet-pass 0 1 0
probe candidate-fail-control-pass 17 1 0
probe candidate-fail-control-fail 17 1 1
probe candidate-fail-control-unavailable 17 1 2
probe contention 17 0 0
probe validator-fail 17 2 0
'''
        proc = subprocess.run(
            ['bash', '-c', script], text=True, capture_output=True, check=False
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn('quiet-pass=0', proc.stdout)
        self.assertIn('candidate-fail-control-pass=17', proc.stdout)
        self.assertIn('candidate-fail-control-fail=75', proc.stdout)
        self.assertIn('candidate-fail-control-unavailable=17', proc.stdout)
        self.assertIn('contention=75', proc.stdout)
        self.assertIn('validator-fail=2', proc.stdout)

    def test_performance_monitor_stop_terminates_live_monitor_and_clears_pid(self):
        text = SCRIPT.read_text()
        start = text.index('performance_host_monitor_stop()')
        end = text.index('performance_pressure_invalid()', start)
        helper = text[start:end]
        script = helper + r'''sleep 30 &
PERF_PRESSURE_PID=$!
PERF_PRESSURE_MONITOR_RC=99
performance_host_monitor_stop
printf 'pid=%s rc=%s\n' "$PERF_PRESSURE_PID" "$PERF_PRESSURE_MONITOR_RC"
'''
        proc = subprocess.run(
            ['bash', '-c', script], text=True, capture_output=True, check=False,
            timeout=5,
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn('pid= rc=0', proc.stdout)

    def test_real_verify_farm_executes_performance_verdict_matrix(self):
        cases = (
            (0, 1, 0, 0),
            (17, 1, 0, 17),
            (17, 1, 1, 75),
            (17, 1, 2, 17),
            (0, 0, 0, 75),
            (0, 2, 0, 2),
        )
        for benchmark_rc, pressure_rc, control_rc, expected in cases:
            with self.subTest(
                benchmark_rc=benchmark_rc, pressure_rc=pressure_rc, control_rc=control_rc
            ):
                proc = run_real_performance_selftest(
                    benchmark_rc=benchmark_rc,
                    pressure_rc=pressure_rc,
                    control_rc=control_rc,
                )
                self.assertEqual(expected, proc.returncode, proc.stderr)
                self.assertIn(
                    f"VERIFY_FARM SELFTEST performance_rc={expected}", proc.stdout
                )

    def test_real_verify_farm_cleanup_stops_monitor_on_exit_failure_and_term(self):
        for mode, expected_rc in (("success", 0), ("fail", 2), ("term", 143)):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as td:
                pid_file = Path(td) / "monitor.pid"
                env = policy_env(
                    LOGRES_REPO_ROOT=str(REPO_ROOT),
                    LOGRES_CONTROL_BIN="/bin/true",
                    LOGRES_VERIFY_FARM_CLEANUP_SELFTEST=mode,
                    LOGRES_VERIFY_FARM_SELFTEST_PID_FILE=str(pid_file),
                    LOGRES_REMOTE_VERIFY_ENABLED="0",
                )
                proc = subprocess.run(
                    [str(SCRIPT), repo_head()],
                    text=True, capture_output=True, env=env, check=False,
                )
                self.assertEqual(expected_rc, proc.returncode, proc.stderr)
                monitor_pid = int(pid_file.read_text().strip())
                with self.assertRaises(ProcessLookupError):
                    os.kill(monitor_pid, 0)

    def test_performance_outer_settle_budget_covers_four_minute_quiet_window(self):
        text = SCRIPT.read_text()
        attempts = re.search(
            r'PERF_HOST_SETTLE_ATTEMPTS="\$\{LOGRES_PERF_HOST_SETTLE_ATTEMPTS:-([0-9]+)\}"',
            text,
        )
        sleep_sec = re.search(
            r'PERF_HOST_SETTLE_SLEEP_SEC="\$\{LOGRES_PERF_HOST_SETTLE_SLEEP_SEC:-([0-9]+)\}"',
            text,
        )
        self.assertIsNotNone(attempts)
        self.assertIsNotNone(sleep_sec)
        self.assertGreaterEqual(int(attempts.group(1)) * int(sleep_sec.group(1)), 240)
        self.assertIn('PERF_MAX_CPU_PSI_AVG10="0.5"', text)
        self.assertIn('PERF_MAX_LOAD_PER_CPU="0.2"', text)
        self.assertIn('PERF_HOST_READY_CONSECUTIVE="${LOGRES_PERF_HOST_READY_CONSECUTIVE:-2}"', text)

    def test_performance_host_ready_requires_both_psi_and_load_to_be_quiet(self):
        text = SCRIPT.read_text()
        start = text.index('performance_host_ready()')
        code_start = text.index("<<'PY2'\n", start) + len("<<'PY2'\n")
        code_end = text.index('\nPY2\n}', code_start)
        probe = text[code_start:code_end]
        with tempfile.TemporaryDirectory() as td:
            psi = Path(td) / 'cpu.pressure'
            psi.write_text('some avg10=0.100 avg60=0.100 avg300=0.100 total=1\n')
            probe = probe.replace(
                'psi = Path("/proc/pressure/cpu")',
                f'psi = Path({str(psi)!r})',
            )
            probe = probe.replace(
                'load1 = os.getloadavg()[0]',
                'load1 = 4.2',
            )
            probe = probe.replace(
                'cpus = os.cpu_count() or 1',
                'cpus = 14',
            )
            proc = subprocess.run(
                ['python3', '-c', probe, '0.5', '0.2', '1', '0', '1'],
                text=True, capture_output=True, check=False,
            )
        self.assertEqual(75, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn('psi_avg10=0.100', proc.stdout)
        self.assertIn('load_per_cpu=0.300', proc.stdout)

    def test_performance_midrun_host_contention_defers_measurement(self):
        text = SCRIPT.read_text()
        self.assertIn('PERF_PRESSURE_LOG=', text)
        self.assertIn('performance_host_monitor_start()', text)
        self.assertIn('performance_host_monitor_stop()', text)
        self.assertIn('performance_pressure_invalid()', text)
        self.assertIn('benchmark invalidated by host contention', text)
        self.assertIn('PERF_MAX_CPU_PSI_AVG10', text)
        self.assertIn('psi_avg10=', text)
        self.assertIn('load_per_cpu=', text)
        self.assertIn('psi_value > psi_limit or load_value > load_limit', text)
        perf_block = text[text.index('performance_rc=0'):text.index('if (( performance_rc == 75 )); then')]
        benchmark = perf_block.index('npm run test:e2e -- "$PERF_SPEC_REL" --workers=1')
        self.assertLess(perf_block.index('performance_host_monitor_start'), benchmark)
        self.assertGreater(perf_block.index('performance_host_monitor_stop'), benchmark)
        self.assertGreater(perf_block.index('performance_pressure_invalid'), benchmark)

    def test_performance_midrun_pressure_evidence_fails_closed_when_unavailable_or_malformed(self):
        text = SCRIPT.read_text()
        start = text.index('performance_pressure_invalid()')
        end = text.index('remote_enabled()', start)
        block = text[start:end]
        self.assertIn('psi_available=([01])', block)
        self.assertIn('malformed += 1', block)
        self.assertIn('psi_unavailable += 1', block)
        self.assertIn('if malformed or psi_unavailable or inconsistent or limit_mismatch:', block)
        self.assertIn('raise SystemExit(2)', block)

    def test_performance_midrun_monitor_uses_same_dual_quiet_thresholds(self):
        text = SCRIPT.read_text()
        self.assertIn('PERF_MAX_CPU_PSI_AVG10="0.5"', text)
        self.assertIn('PERF_MAX_LOAD_PER_CPU="0.2"', text)
        self.assertNotIn('LOGRES_PERF_MAX_CPU_PSI_AVG10', text)
        self.assertNotIn('LOGRES_PERF_MAX_LOAD_PER_CPU', text)

    def test_performance_midrun_monitor_death_fails_closed(self):
        text = SCRIPT.read_text()
        self.assertIn('PERF_PRESSURE_MONITOR_RC=0', text)
        stop_start = text.index('performance_host_monitor_stop()')
        stop_end = text.index('performance_pressure_invalid()', stop_start)
        stop_block = text[stop_start:stop_end]
        self.assertIn('kill -0 "$pid"', stop_block)
        self.assertIn('PERF_PRESSURE_MONITOR_RC=2', stop_block)
        self.assertIn('wait "$pid"', stop_block)
        self.assertIn('143)', stop_block)
        validator_start = stop_end
        validator_end = text.index('remote_enabled()', validator_start)
        validator = text[validator_start:validator_end]
        self.assertIn('monitor_rc = int(sys.argv[2])', validator)
        self.assertIn('if monitor_rc != 0:', validator)
        self.assertIn('raise SystemExit(2)', validator)

    def test_performance_monitor_requires_ready_sample_before_benchmark(self):
        text = SCRIPT.read_text()
        start = text.index('performance_host_monitor_start()')
        end = text.index('performance_host_monitor_stop()', start)
        block = text[start:end]
        self.assertIn('PERF_PRESSURE_MONITOR_READY=0', block)
        self.assertIn('kill -0 "$PERF_PRESSURE_PID"', block)
        self.assertIn('-s "$PERF_PRESSURE_LOG"', block)
        self.assertIn('PERF_PRESSURE_MONITOR_READY=1', block)
        self.assertIn('return 2', block)

    def test_performance_pressure_evidence_must_cover_benchmark_interval(self):
        text = SCRIPT.read_text()
        start = text.index('performance_pressure_invalid()')
        end = text.index('remote_enabled()', start)
        block = text[start:end]
        self.assertIn('benchmark_start = float(sys.argv[5])', block)
        self.assertIn('benchmark_end = float(sys.argv[6])', block)
        self.assertIn('sample_sec = float(sys.argv[7])', block)
        self.assertIn('sample_time = float(match.group(1))', block)
        self.assertIn('coverage_gap', block)
        self.assertIn('coverage_start_gap', block)
        self.assertIn('coverage_end_gap', block)
        self.assertIn('minimum_samples = max(2,', block)
        self.assertIn('len(window_samples) < minimum_samples', block)
        self.assertIn('if coverage_invalid:', block)
        self.assertIn('raise SystemExit(2)', block)

    def test_performance_pressure_validator_rejects_partial_benchmark_coverage(self):
        text = SCRIPT.read_text()
        block_start = text.index('performance_pressure_invalid()')
        code_start = text.index("<<'PY2' || validator_rc=$?\n", block_start) + len("<<'PY2' || validator_rc=$?\n")
        code_end = text.index('\nPY2\n  case "$validator_rc"', code_start)
        validator = text[code_start:code_end]
        with tempfile.TemporaryDirectory() as td:
            pressure = Path(td) / 'pressure.log'
            pressure.write_text(
                '100.000 psi_avg10=0.100 psi_max=0.500 psi_available=1 '
                'load_per_cpu=0.100 load_max=0.200 over=0\n'
                '100.250 psi_avg10=0.100 psi_max=0.500 psi_available=1 '
                'load_per_cpu=0.100 load_max=0.200 over=0\n'
            )
            proc = subprocess.run(
                [
                    'python3', '-c', validator, str(pressure), '0', '0.5', '0.2',
                    '100.0', '110.0', '0.25', '1',
                ],
                text=True, capture_output=True, check=False,
            )
        self.assertEqual(2, proc.returncode)
        self.assertIn('coverage incomplete', proc.stdout)

    def test_performance_pressure_validator_rejects_single_sample_even_for_short_interval(self):
        text = SCRIPT.read_text()
        block_start = text.index('performance_pressure_invalid()')
        code_start = text.index("<<'PY2' || validator_rc=$?\n", block_start) + len("<<'PY2' || validator_rc=$?\n")
        code_end = text.index('\nPY2\n  case "$validator_rc"', code_start)
        validator = text[code_start:code_end]
        with tempfile.TemporaryDirectory() as td:
            pressure = Path(td) / 'pressure.log'
            pressure.write_text(
                '100.100 psi_avg10=0.100 psi_max=0.500 psi_available=1 '
                'load_per_cpu=0.100 load_max=0.200 over=0\n'
            )
            proc = subprocess.run(
                [
                    'python3', '-c', validator, str(pressure), '0', '0.5', '0.2',
                    '100.0', '100.2', '0.25', '1',
                ],
                text=True, capture_output=True, check=False,
            )
        self.assertEqual(2, proc.returncode)
        self.assertIn('coverage incomplete', proc.stdout)

    def test_performance_pressure_validator_accepts_dense_quiet_coverage(self):
        text = SCRIPT.read_text()
        block_start = text.index('performance_pressure_invalid()')
        code_start = text.index("<<'PY2' || validator_rc=$?\n", block_start) + len("<<'PY2' || validator_rc=$?\n")
        code_end = text.index('\nPY2\n  case "$validator_rc"', code_start)
        validator = text[code_start:code_end]
        with tempfile.TemporaryDirectory() as td:
            pressure = Path(td) / 'pressure.log'
            lines = []
            for index in range(9):
                ts = 100.0 + index * 0.25
                lines.append(
                    f'{ts:.3f} psi_avg10=0.100 psi_max=0.500 psi_available=1 '
                    'load_per_cpu=0.100 load_max=0.200 over=0'
                )
            pressure.write_text('\n'.join(lines) + '\n')
            proc = subprocess.run(
                [
                    'python3', '-c', validator, str(pressure), '0', '0.5', '0.2',
                    '100.1', '101.9', '0.25', '1',
                ],
                text=True, capture_output=True, check=False,
            )
        self.assertEqual(10, proc.returncode)
        self.assertIn('samples=9', proc.stdout)
        self.assertIn('over=0', proc.stdout)

    def test_performance_pressure_validator_rejects_out_of_order_samples(self):
        text = SCRIPT.read_text()
        block_start = text.index('performance_pressure_invalid()')
        code_start = text.index("<<'PY2' || validator_rc=$?\n", block_start) + len("<<'PY2' || validator_rc=$?\n")
        code_end = text.index('\nPY2\n  case "$validator_rc"', code_start)
        validator = text[code_start:code_end]
        with tempfile.TemporaryDirectory() as td:
            pressure = Path(td) / 'pressure.log'
            pressure.write_text(
                '100.100 psi_avg10=0.100 psi_max=0.500 psi_available=1 load_per_cpu=0.100 load_max=0.200 over=0\n'
                '100.050 psi_avg10=0.100 psi_max=0.500 psi_available=1 load_per_cpu=0.100 load_max=0.200 over=0\n'
                '100.200 psi_avg10=0.100 psi_max=0.500 psi_available=1 load_per_cpu=0.100 load_max=0.200 over=0\n'
            )
            proc = subprocess.run(
                ['python3', '-c', validator, str(pressure), '0', '0.5', '0.2',
                 '100.0', '100.25', '0.25', '1'],
                text=True, capture_output=True, check=False,
            )
        self.assertEqual(2, proc.returncode)
        self.assertIn('timestamps not strictly increasing', proc.stdout)

    def test_performance_pressure_validator_does_not_count_out_of_window_samples(self):
        text = SCRIPT.read_text()
        block_start = text.index('performance_pressure_invalid()')
        code_start = text.index("<<'PY2' || validator_rc=$?\n", block_start) + len("<<'PY2' || validator_rc=$?\n")
        code_end = text.index('\nPY2\n  case "$validator_rc"', code_start)
        validator = text[code_start:code_end]
        with tempfile.TemporaryDirectory() as td:
            pressure = Path(td) / 'pressure.log'
            pressure.write_text(
                '99.900 psi_avg10=0.100 psi_max=0.500 psi_available=1 load_per_cpu=0.100 load_max=0.200 over=0\n'
                '100.300 psi_avg10=0.100 psi_max=0.500 psi_available=1 load_per_cpu=0.100 load_max=0.200 over=0\n'
            )
            proc = subprocess.run(
                ['python3', '-c', validator, str(pressure), '0', '0.5', '0.2',
                 '100.0', '100.2', '0.25', '1'],
                text=True, capture_output=True, check=False,
            )
        self.assertEqual(2, proc.returncode)
        self.assertIn('coverage incomplete', proc.stdout)

    def test_performance_pressure_validator_reserves_quiet_exit_code_and_maps_crashes_fail_closed(self):
        text = SCRIPT.read_text()
        start = text.index('performance_pressure_invalid()')
        end = text.index('remote_enabled()', start)
        block = text[start:end]
        self.assertIn('raise SystemExit(10)', block)
        self.assertIn('10)', block)
        self.assertIn('return 1', block)
        self.assertIn('*)', block)
        self.assertIn('return 2', block)

    def test_performance_pressure_shell_exit_contract_is_unambiguous(self):
        text = SCRIPT.read_text()
        fn_start = text.index('performance_pressure_invalid() {')
        fn_end = text.index('\n\nremote_enabled()', fn_start)
        function = text[fn_start:fn_end]

        def run_case(lines):
            with tempfile.TemporaryDirectory() as td:
                pressure = Path(td) / 'pressure.log'
                pressure.write_text('\n'.join(lines) + '\n')
                shell = f'''
set -u
PERF_PRESSURE_LOG="$1"
PERF_PRESSURE_MONITOR_RC=0
PERF_MAX_CPU_PSI_AVG10=0.5
PERF_MAX_LOAD_PER_CPU=0.2
PERF_BENCHMARK_START=100.1
PERF_BENCHMARK_END=101.9
PERF_PRESSURE_SAMPLE_SEC=0.25
PERF_PRESSURE_MONITOR_READY=1
{function}
rc=0
performance_pressure_invalid >/dev/null 2>&1 || rc=$?
printf '%s\n' "$rc"
'''
                proc = subprocess.run(
                    ['bash', '-c', shell, 'bash', str(pressure)],
                    text=True, capture_output=True, check=False,
                )
            self.assertEqual(0, proc.returncode)
            return int(proc.stdout.strip().splitlines()[-1])

        quiet = [
            f'{100.0 + i * 0.25:.3f} psi_avg10=0.100 psi_max=0.500 psi_available=1 '
            'load_per_cpu=0.100 load_max=0.200 over=0'
            for i in range(9)
        ]
        contention = list(quiet)
        contention[4] = (
            '101.000 psi_avg10=0.600 psi_max=0.500 psi_available=1 '
            'load_per_cpu=0.100 load_max=0.200 over=1'
        )
        crashed = list(quiet)
        crashed[4] = (
            '101.000 psi_avg10=.. psi_max=0.500 psi_available=1 '
            'load_per_cpu=0.100 load_max=0.200 over=0'
        )

        self.assertEqual(1, run_case(quiet))
        self.assertEqual(1, run_case(contention))
        self.assertEqual(2, run_case(crashed))

    def test_performance_pressure_validator_treats_benchmark_self_load_as_audit_evidence(self):
        text = SCRIPT.read_text()
        block_start = text.index('performance_pressure_invalid()')
        code_start = text.index("<<'PY2' || validator_rc=$?\n", block_start) + len("<<'PY2' || validator_rc=$?\n")
        code_end = text.index('\nPY2\n  case "$validator_rc"', code_start)
        validator = text[code_start:code_end]
        with tempfile.TemporaryDirectory() as td:
            pressure = Path(td) / 'pressure.log'
            lines = []
            for index in range(9):
                ts = 100.0 + index * 0.25
                lines.append(
                    f'{ts:.3f} psi_avg10=0.800 psi_max=0.500 psi_available=1 '
                    'load_per_cpu=0.300 load_max=0.200 over=1'
                )
            pressure.write_text('\n'.join(lines) + '\n')
            proc = subprocess.run(
                [
                    'python3', '-c', validator, str(pressure), '0', '0.5', '0.2',
                    '100.1', '101.9', '0.25', '1',
                ],
                text=True, capture_output=True, check=False,
            )
        self.assertEqual(10, proc.returncode)
        self.assertIn('over=7', proc.stdout)

    def test_performance_pressure_validator_requires_monitor_ready_token(self):
        text = SCRIPT.read_text()
        start = text.index('performance_pressure_invalid()')
        end = text.index('remote_enabled()', start)
        block = text[start:end]
        self.assertIn('monitor_ready = int(sys.argv[8])', block)
        self.assertIn('if monitor_ready != 1:', block)

    def test_performance_pressure_monitor_serializes_round_trip_precision(self):
        text = SCRIPT.read_text()
        start = text.index("performance_host_monitor_start()")
        end = text.index("performance_pressure_invalid()", start)
        block = text[start:end]
        self.assertIn("psi_avg10={psi_value!r}", block)
        self.assertIn("load_per_cpu={load_value!r}", block)
        self.assertIn("psi_max={psi_limit!r}", block)
        self.assertIn("load_max={load_limit!r}", block)

    def test_performance_midrun_validator_recomputes_over_and_rejects_inconsistency(self):
        text = SCRIPT.read_text()
        start = text.index('performance_pressure_invalid()')
        end = text.index('remote_enabled()', start)
        block = text[start:end]
        self.assertIn('configured_psi_max = float(sys.argv[3])', block)
        self.assertIn('configured_load_max = float(sys.argv[4])', block)
        self.assertIn('expected_over = int(', block)
        self.assertIn('psi_value > configured_psi_max or', block)
        self.assertIn('load_value > configured_load_max', block)
        self.assertIn('limit_mismatch += int(psi_max != configured_psi_max)', block)
        self.assertIn('limit_mismatch += int(load_max != configured_load_max)', block)
        self.assertIn('inconsistent += int(flag != expected_over)', block)
        self.assertIn(
            'if malformed or psi_unavailable or inconsistent or limit_mismatch:',
            block,
        )
        self.assertIn('raise SystemExit(2)', block)

    def test_canonical_farm_exports_exact_sha_for_visual_truth(self):
        text = SCRIPT.read_text()
        self.assertIn('export LOGRES_VERIFY_SHA="$SHA"', text)
        self.assertIn('export LOGRES_RECORD_VISUAL_TRUTH=1', text)
        self.assertIn('export LOGRES_REQUIRE_VISUAL_TRUTH_RECORD=1', text)

    def test_behavior_e2e_is_bootstrap_safe_but_prefers_canonical_output(self):
        text = BEHAVIOR_E2E.read_text()
        self.assertIn("process.env.LOGRES_BEHAVIOR_TRACE_OUT ||", text)
        self.assertIn("testInfo.outputPath('logres-behavior-trace.json')", text)
        self.assertNotIn("LOGRES_BEHAVIOR_TRACE_OUT is required", text)

    def test_canonical_farm_exports_and_persists_behavior_truth(self):
        text = SCRIPT.read_text()
        self.assertIn('export LOGRES_BEHAVIOR_TRACE_OUT="$E2E_WT/.logres-behavior-trace.json"', text)
        self.assertIn('--sha "$SHA"', text)
        self.assertIn('verify_behavior_checkpoint.py', text)
        self.assertIn('behavior_rc', text)

    def test_behavior_verifier_propagates_exact_sha_and_pass(self):
        module = load_behavior_verifier()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            observed = root / "observed.json"
            observed.write_text(json.dumps(module.EXPECTED))
            recorder = root / "recorder.py"
            args_log = root / "args.json"
            recorder.write_text(
                "#!/usr/bin/env python3\n"
                "import json,os,sys\n"
                "open(os.environ['ARG_LOG'],'w').write(json.dumps(sys.argv[1:]))\n"
                "print(json.dumps({'id':1,'verdict':'PASS','divergence':{}}))\n"
            )
            recorder.chmod(0o755)
            with patch.dict(os.environ, {"ARG_LOG": str(args_log)}, clear=False):
                result = module.record_behavior_truth(
                    observed,
                    sha="a" * 40,
                    recorder=str(recorder),
                )
            self.assertEqual("PASS", result["verdict"])
            args = json.loads(args_log.read_text())
            self.assertIn("a" * 40, args)
            self.assertIn(module.CHECKPOINT, args)
            self.assertIn("--expected", args)
            self.assertIn("--observed", args)

    def test_behavior_verifier_preserves_divergence_fail(self):
        module = load_behavior_verifier()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            observed = root / "observed.json"
            changed = dict(module.EXPECTED)
            changed["events"] = ["FIELD_READY", "BATTLE_ACTIVE"]
            observed.write_text(json.dumps(changed))
            recorder = root / "recorder.py"
            recorder.write_text(
                "#!/usr/bin/env python3\n"
                "import json\n"
                "print(json.dumps({'id':2,'verdict':'FAIL','divergence':{'event_mismatches':[1]}}))\n"
            )
            recorder.chmod(0o755)
            result = module.record_behavior_truth(
                observed,
                sha="b" * 40,
                recorder=str(recorder),
            )
            self.assertEqual("FAIL", result["verdict"])
            self.assertTrue(result["record"]["divergence"]["event_mismatches"])

    def test_behavior_verifier_retries_transient_sqlite_lock_then_passes(self):
        module = load_behavior_verifier()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            observed = root / "observed.json"
            observed.write_text(json.dumps(module.EXPECTED))
            calls = []
            sleeps = []

            def runner(argv, **kwargs):
                calls.append(list(argv))
                if len(calls) == 1:
                    return subprocess.CompletedProcess(
                        argv,
                        1,
                        "",
                        "sqlite3.OperationalError: database is locked",
                    )
                return subprocess.CompletedProcess(
                    argv,
                    0,
                    json.dumps(
                        {
                            "id": 3,
                            "verdict": "PASS",
                            "divergence": {},
                        }
                    ),
                    "",
                )

            result = module.record_behavior_truth(
                observed,
                sha="d" * 40,
                recorder="/tmp/fake-recorder",
                runner=runner,
                sleeper=sleeps.append,
            )

            self.assertEqual("PASS", result["verdict"])
            self.assertEqual(2, len(calls))
            self.assertEqual(
                [module.RECORDER_LOCK_BACKOFF_SECONDS],
                sleeps,
            )

    def test_behavior_verifier_nonzero_recorder_exit_fails_closed(self):
        module = load_behavior_verifier()
        with tempfile.TemporaryDirectory() as td:
            observed = Path(td) / "observed.json"
            observed.write_text(json.dumps(module.EXPECTED))

            def runner(argv, **kwargs):
                return subprocess.CompletedProcess(
                    argv,
                    1,
                    "",
                    "permission denied",
                )

            with self.assertRaisesRegex(
                RuntimeError,
                "behavior truth recorder failed: permission denied",
            ):
                module.record_behavior_truth(
                    observed,
                    sha="e" * 40,
                    recorder="/tmp/fake-recorder",
                    runner=runner,
                    sleeper=lambda _: None,
                )

    def test_behavior_trace_recorder_is_isolated_from_canonical_control_db(self):
        text = SCRIPT.read_text()
        self.assertIn(
            'BEHAVIOR_TRACE_DB="$ROOT/verify-farm-$STAMP-behavior-trace.sqlite"',
            text,
        )
        self.assertIn(
            'BEHAVIOR_TRACE_WRAPPER="$ROOT/verify-farm-$STAMP-behavior-trace-recorder"',
            text,
        )
        self.assertIn(
            'export LOGRES_BEHAVIOR_TRACE_BIN="$BEHAVIOR_TRACE_WRAPPER"',
            text,
        )
        self.assertIn(
            "merge_behavior_trace_records.py",
            text,
        )
        self.assertIn(
            '--source "$BEHAVIOR_TRACE_DB"',
            text,
        )
        self.assertIn(
            '--target "$CANONICAL_CONTROL_DB"',
            text,
        )

    def test_behavior_trace_merge_uses_full_bounded_contention_budget(self):
        text = SCRIPT.read_text()
        self.assertIn(
            'BEHAVIOR_TRACE_MERGE_TIMEOUT_MS="${LOGRES_BEHAVIOR_TRACE_MERGE_TIMEOUT_MS:-15000}"',
            text,
        )

    def test_behavior_trace_merge_failure_fails_verification_closed(self):
        text = SCRIPT.read_text()
        merge_start = text.index(
            "if ! merge_behavior_trace_isolation; then"
        )
        visual_start = text.index(
            "if ! merge_visual_truth_isolation; then"
        )
        self.assertLess(merge_start, visual_start)
        block = text[merge_start:visual_start]
        self.assertIn(
            "VERIFY_FARM FAIL behavior trace merge failed closed",
            block,
        )
        self.assertIn("preserve_behavior_trace_failure", block)
        self.assertIn("exit 1", block)
        self.assertIn(
            "behavior_trace_merge_log=$BEHAVIOR_TRACE_MERGE_LOG",
            text,
        )

    def test_behavior_verifier_missing_observed_trace_fails_closed(self):
        module = load_behavior_verifier()
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "missing.json"
            with self.assertRaises(FileNotFoundError):
                module.record_behavior_truth(
                    missing,
                    sha="c" * 40,
                    recorder="/bin/false",
                )

    def test_visual_truth_recorder_is_isolated_from_canonical_control_db(self):
        text = SCRIPT.read_text()
        self.assertIn(
            'VISUAL_TRUTH_DB="$ROOT/verify-farm-$STAMP-visual-truth.sqlite"',
            text,
        )
        self.assertIn(
            'CANONICAL_CONTROL_DB="${LOGRES_CANONICAL_CONTROL_DB:-/home/ubuntu/logres/control/control.sqlite}"',
            text,
        )
        self.assertIn(
            'LOGRES_CONTROL_DB="$VISUAL_TRUTH_DB" \
    "$VISUAL_TRUTH_REAL_BIN" init',
            text,
        )
        self.assertIn(
            'export LOGRES_VISUAL_TRUTH_BIN="$VISUAL_TRUTH_WRAPPER"',
            text,
        )
        self.assertIn(
            """printf 'export LOGRES_CONTROL_DB=%q\n' "$VISUAL_TRUTH_DB" """.strip(),
            text,
        )
        self.assertNotIn(
            'export LOGRES_CONTROL_DB="$CANONICAL_CONTROL_DB"',
            text,
        )

    def test_isolated_truth_merge_occurs_only_after_successful_e2e(self):
        text = SCRIPT.read_text()
        wait_index = text.index('wait "$e2e_pid" || e2e_rc=$?')
        behavior_index = text.index('behavior_rc=0')
        failure_index = text.index(
            'if (( test_rc != 0 || e2e_rc != 0 || performance_rc != 0 || behavior_rc != 0 )); then'
        )
        merge_index = text.index('if ! merge_visual_truth_isolation; then')
        pass_index = text.index('VERIFY_FARM PASS ref=')
        self.assertLess(wait_index, behavior_index)
        self.assertLess(behavior_index, failure_index)
        self.assertLess(failure_index, merge_index)
        self.assertLess(merge_index, pass_index)
        self.assertIn('--source "$VISUAL_TRUTH_DB"', text)
        self.assertIn('--target "$CANONICAL_CONTROL_DB"', text)
        self.assertIn(
            '--busy-timeout-ms "$VISUAL_TRUTH_MERGE_TIMEOUT_MS"',
            text,
        )

    def test_visual_truth_merge_uses_standard_wait_then_durable_spool(self):
        text = SCRIPT.read_text()
        self.assertIn(
            'VISUAL_TRUTH_MERGE_TIMEOUT_MS="${LOGRES_VISUAL_TRUTH_MERGE_TIMEOUT_MS:-15000}"',
            text,
        )
        self.assertIn(
            'VISUAL_TRUTH_SPOOL_DIR="${LOGRES_VISUAL_TRUTH_SPOOL_DIR:-/home/ubuntu/logres/control/visual-truth-spool}"',
            text,
        )
        self.assertIn(
            '--spool-dir "$VISUAL_TRUTH_SPOOL_DIR"',
            text,
        )
        self.assertIn(
            '--busy-timeout-ms "$VISUAL_TRUTH_MERGE_TIMEOUT_MS"',
            text,
        )

    def test_visual_truth_merge_failure_fails_verification_closed(self):
        text = SCRIPT.read_text()
        self.assertIn(
            'VERIFY_FARM FAIL visual truth merge failed closed',
            text,
        )
        merge_start = text.index(
            'if ! merge_visual_truth_isolation; then'
        )
        fail_block = text[
            merge_start:
            text.index(
                'dur=$(( $(date +%s)-START ))',
                merge_start,
            )
        ]
        self.assertIn('exit 1', fail_block)
        self.assertIn(
            'preserve_visual_truth_failure',
            fail_block,
        )
        self.assertIn(
            'preserved_isolated_visual_truth=',
            fail_block,
        )
        self.assertIn(
            'visual_truth_merge_log=$VISUAL_TRUTH_MERGE_LOG',
            text,
        )

    def test_structural_truth_records_review_or_fail_never_pass(self):
        module = load_visual_verifier()
        for passed, expected in ((True, "REVIEW"), (False, "FAIL")):
            with self.subTest(passed=passed), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                recorder = root / "recorder.py"
                args_log = root / "args.json"
                recorder.write_text(
                    "#!/usr/bin/env python3\n"
                    "import json,os,sys\n"
                    "open(os.environ['ARG_LOG'],'w').write(json.dumps(sys.argv[1:]))\n"
                    "print(json.dumps({'id': 7}))\n"
                )
                recorder.chmod(0o755)
                image = root / "checkpoint.png"
                image.write_bytes(b"placeholder")
                result = {
                    "pass": passed,
                    "metrics": {"width": 720, "height": 1280},
                    "provenance": {"layout": "SUPPORTED_INFERENCE"},
                    "failures": [] if passed else ["structural failure"],
                }
                with patch.dict(
                    os.environ,
                    {
                        "LOGRES_RECORD_VISUAL_TRUTH": "1",
                        "LOGRES_REQUIRE_VISUAL_TRUTH_RECORD": "1",
                        "LOGRES_VERIFY_SHA": "a" * 40,
                        "LOGRES_VISUAL_TRUTH_BIN": str(recorder),
                        "ARG_LOG": str(args_log),
                    },
                    clear=False,
                ):
                    recorded = module.record_visual_truth(
                        "title",
                        image,
                        result,
                    )
                self.assertTrue(recorded["recorded"])
                self.assertEqual(expected, recorded["verdict"])
                args = json.loads(args_log.read_text())
                self.assertIn(expected, args)
                self.assertNotIn("PASS", args)


if __name__ == "__main__":
    unittest.main()
