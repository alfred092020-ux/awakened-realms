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
