import importlib.util
import json
import os
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
            'if (( test_rc != 0 || e2e_rc != 0 || behavior_rc != 0 )); then'
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
