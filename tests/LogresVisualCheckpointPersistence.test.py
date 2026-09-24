import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "logres"
    / "verify_visual_checkpoint.py"
)
SPEC = importlib.util.spec_from_file_location(
    "logres_visual_checkpoint",
    SCRIPT,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

SHA = "a" * 40
RESULT = {
    "pass": True,
    "metrics": {
        "width": 720,
        "height": 1280,
        "dark_ratio": 0.1,
    },
    "provenance": {"layout": "TEST"},
    "failures": [],
}


class VisualCheckpointPersistenceTests(unittest.TestCase):
    def recorder_env(self, recorder: Path, **extra):
        env = {
            "LOGRES_RECORD_VISUAL_TRUTH": "1",
            "LOGRES_REQUIRE_VISUAL_TRUTH_RECORD": "",
            "LOGRES_VERIFY_SHA": SHA,
            "LOGRES_VISUAL_TRUTH_BIN": str(recorder),
            "LOGRES_VISUAL_TRUTH_TIMEOUT_SECONDS": "0.25",
        }
        env.update(extra)
        return mock.patch.dict(os.environ, env, clear=False)

    def test_disabled_recording_does_not_spawn(self):
        with mock.patch.dict(
            os.environ,
            {"LOGRES_RECORD_VISUAL_TRUTH": ""},
            clear=False,
        ), mock.patch.object(
            MODULE.subprocess,
            "run",
        ) as run:
            result = MODULE.record_visual_truth(
                "title",
                Path("title.png"),
                RESULT,
            )
        self.assertEqual(
            {"recorded": False, "reason": "DISABLED"},
            result,
        )
        run.assert_not_called()

    def test_success_uses_bounded_timeout(self):
        with tempfile.TemporaryDirectory() as td:
            recorder = Path(td) / "recorder"
            recorder.write_text("#!/bin/sh\n")
            with self.recorder_env(recorder), mock.patch.object(
                MODULE.subprocess,
                "run",
                return_value=SimpleNamespace(
                    returncode=0,
                    stdout='{"id": 7}',
                    stderr="",
                ),
            ) as run:
                result = MODULE.record_visual_truth(
                    "field",
                    Path("field.png"),
                    RESULT,
                )

        self.assertTrue(result["recorded"])
        self.assertEqual({"id": 7}, result["record"])
        self.assertEqual(0.25, run.call_args.kwargs["timeout"])

    def test_optional_timeout_preserves_structural_result(self):
        with tempfile.TemporaryDirectory() as td:
            recorder = Path(td) / "recorder"
            recorder.write_text("#!/bin/sh\n")
            with self.recorder_env(recorder), mock.patch.object(
                MODULE.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired(
                    cmd=["recorder"],
                    timeout=0.25,
                ),
            ):
                result = MODULE.record_visual_truth(
                    "battle",
                    Path("battle.png"),
                    RESULT,
                )

        self.assertFalse(result["recorded"])
        self.assertEqual("RECORDER_TIMEOUT", result["reason"])
        self.assertIn("0.25s", result["error"])

    def test_required_timeout_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            recorder = Path(td) / "recorder"
            recorder.write_text("#!/bin/sh\n")
            with self.recorder_env(
                recorder,
                LOGRES_REQUIRE_VISUAL_TRUTH_RECORD="1",
            ), mock.patch.object(
                MODULE.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired(
                    cmd=["recorder"],
                    timeout=0.25,
                ),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "timed out after 0.25s",
                ):
                    MODULE.record_visual_truth(
                        "title",
                        Path("title.png"),
                        RESULT,
                    )


if __name__ == "__main__":
    unittest.main()
