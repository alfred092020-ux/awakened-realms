from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from logres_phone_local_ai import (
    PhoneLocalAI,
    classify_statistical,
    parse_label,
    safety_decision,
    should_query_local_ai,
)


class FakeTransport:
    def __init__(
        self,
        *,
        sensor_output: str = "2800000 31500\n",
        remote_result: dict | None = None,
        python_ready: bool = True,
        timeout_classifier: bool = False,
    ):
        self.sensor_output = sensor_output
        self.remote_result = remote_result or {
            "label": "STUCK",
            "raw_label": "STUCK",
            "confidence": 0.91,
            "margin": 0.42,
            "reason": "classified",
            "executed": True,
            "mem_available_kb": 2_800_000,
            "battery_temp_millic": 31_500,
        }
        self.python_ready = python_ready
        self.timeout_classifier = timeout_classifier
        self.calls: list[str] = []

    def run(self, command: str, *, timeout: float):
        self.calls.append(command)

        # Combined classify transaction.
        if (
            "MemAvailable" in command
            and "phone-local-classifier.py" in command
            and "expected=" in command
        ):
            if self.timeout_classifier:
                raise subprocess.TimeoutExpired(
                    cmd=["ssh"],
                    timeout=timeout,
                )

            parts = self.sensor_output.strip().split()
            mem = int(parts[0]) if len(parts) >= 1 else 0
            temp = int(parts[1]) if len(parts) >= 2 else 0

            if not self.python_ready:
                value = {
                    "label": "UNKNOWN",
                    "raw_label": "UNKNOWN",
                    "confidence": 0.0,
                    "margin": 0.0,
                    "reason": "termux_python_unavailable",
                    "executed": False,
                    "mem_available_kb": mem,
                    "battery_temp_millic": temp,
                }
            elif mem < 700 * 1024:
                value = {
                    "label": "UNKNOWN",
                    "raw_label": "UNKNOWN",
                    "confidence": 0.0,
                    "margin": 0.0,
                    "reason": "low_memory",
                    "executed": False,
                    "mem_available_kb": mem,
                    "battery_temp_millic": temp,
                }
            elif temp > 42_000:
                value = {
                    "label": "UNKNOWN",
                    "raw_label": "UNKNOWN",
                    "confidence": 0.0,
                    "margin": 0.0,
                    "reason": "battery_hot",
                    "executed": False,
                    "mem_available_kb": mem,
                    "battery_temp_millic": temp,
                }
            else:
                value = dict(self.remote_result)
                value.setdefault(
                    "mem_available_kb",
                    mem,
                )
                value.setdefault(
                    "battery_temp_millic",
                    temp,
                )
                value.setdefault(
                    "executed",
                    True,
                )

            return subprocess.CompletedProcess(
                ["ssh"],
                0,
                json.dumps(value),
                "",
            )

        # Status path still checks sensors and Python separately.
        if "MemAvailable" in command:
            return subprocess.CompletedProcess(
                ["ssh"],
                0,
                self.sensor_output,
                "",
            )

        if "command -v python" in command:
            return subprocess.CompletedProcess(
                ["ssh"],
                0 if self.python_ready else 1,
                "",
                "",
            )

        raise AssertionError(
            f"unexpected command: {command}",
        )


def write_config(root: Path, *, enabled: bool = True) -> None:
    path = root / "control/android-device/phone-local-ai.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "enabled": enabled,
            "max_observation_chars": 4000,
            "classifier": {
                "min_confidence": 0.64,
                "min_margin": 0.10,
                "timeout_seconds": 5,
                "runner_path": "/data/data/com.termux/files/home/.cache/logres/phone-local-classifier.py",
            },
            "safety": {
                "max_battery_temp_c": 42.0,
                "min_mem_available_mb": 700,
            },
            "ssh": {
                "host": "127.0.0.1",
                "port": 22023,
                "user": "phone",
                "key_path": "/tmp/key",
            },
        }),
        encoding="utf-8",
    )


class PhoneLocalAITests(unittest.TestCase):
    def test_parse_label_accepts_exact_single_label(self):
        self.assertEqual("ACTIVE", parse_label("ACTIVE\n"))
        self.assertEqual("STUCK", parse_label("answer: STUCK"))

    def test_parse_label_fails_closed_on_multiple_labels(self):
        self.assertEqual(
            "UNKNOWN",
            parse_label("ACTIVE or STUCK"),
        )

    def test_only_ambiguous_deterministic_state_queries_ai(self):
        self.assertTrue(
            should_query_local_ai("AMBIGUOUS"),
        )
        for state in (
            "ACTIVE",
            "ENDED",
            "STUCK",
            "RATE_LIMITED",
            "WAITING_USER",
            "UNKNOWN",
        ):
            self.assertFalse(
                should_query_local_ai(state),
            )

    def test_statistical_classifier_matches_holdout_states(self):
        cases = {
            "ACTIVE": {
                "visible_text": "The Worked for counter moved forward and the answer gained more text.",
                "stop_present": True,
                "worked_timer_advanced": True,
            },
            "ENDED": {
                "visible_text": "The answer is complete and generation control is gone.",
                "turn_ended_signal": True,
            },
            "STUCK": {
                "visible_text": "Stop is still visible but the response has not changed through the probe.",
                "stop_present": True,
            },
            "RATE_LIMITED": {
                "visible_text": "Request limit reached. Please retry in a little while.",
                "rate_limit_banner": True,
            },
            "WAITING_USER": {
                "visible_text": "There is already unsent text in the input box.",
                "user_draft": True,
            },
            "UNKNOWN": {
                "visible_text": "No Stop button, but tool execution may still be in progress.",
                "turn_heartbeat_fresh": True,
            },
        }

        for expected, observation in cases.items():
            with self.subTest(expected=expected):
                result = classify_statistical(
                    observation,
                )
                self.assertEqual(
                    expected,
                    result["label"],
                )
                self.assertGreaterEqual(
                    result["confidence"],
                    0.64,
                )

    def test_statistical_classifier_keeps_conflicting_state_unknown(self):
        result = classify_statistical({
            "visible_text": "Signals disagree and I cannot tell whether tool work is still running.",
            "turn_heartbeat_fresh": True,
        })
        self.assertEqual(
            "UNKNOWN",
            result["label"],
        )

    def test_safety_gate_accepts_healthy_phone(self):
        self.assertEqual(
            (True, "ok"),
            safety_decision(
                mem_available_kb=2_800_000,
                battery_temp_millic=31_500,
                min_mem_available_mb=700,
                max_battery_temp_c=42.0,
            ),
        )

    def test_safety_gate_rejects_missing_sensor_low_memory_and_heat(self):
        self.assertEqual(
            (False, "sensor_unavailable"),
            safety_decision(
                mem_available_kb=None,
                battery_temp_millic=31_500,
                min_mem_available_mb=700,
                max_battery_temp_c=42.0,
            ),
        )
        self.assertEqual(
            (False, "low_memory"),
            safety_decision(
                mem_available_kb=500_000,
                battery_temp_millic=31_500,
                min_mem_available_mb=700,
                max_battery_temp_c=42.0,
            ),
        )
        self.assertEqual(
            (False, "battery_hot"),
            safety_decision(
                mem_available_kb=2_800_000,
                battery_temp_millic=43_000,
                min_mem_available_mb=700,
                max_battery_temp_c=42.0,
            ),
        )

    def test_deterministic_authority_skips_phone_entirely(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_config(root)
            transport = FakeTransport()
            ai = PhoneLocalAI(
                root,
                transport=transport,
            )
            result = ai.classify(
                {"anything": True},
                deterministic_state="ACTIVE",
            )
            self.assertEqual(
                "UNKNOWN",
                result["label"],
            )
            self.assertFalse(
                result["queried"],
            )
            self.assertEqual(
                "deterministic_authority",
                result["reason"],
            )
            self.assertEqual(
                [],
                transport.calls,
            )

    def test_ambiguous_state_runs_phone_classifier(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_config(root)
            transport = FakeTransport(
                remote_result={
                    "label": "ENDED",
                    "raw_label": "ENDED",
                    "confidence": 0.88,
                    "margin": 0.31,
                    "reason": "classified",
                },
            )
            ai = PhoneLocalAI(
                root,
                transport=transport,
            )
            result = ai.classify(
                {
                    "visible_text": "The turn is complete.",
                    "turn_ended_signal": True,
                },
                deterministic_state="AMBIGUOUS",
            )
            self.assertEqual(
                "ENDED",
                result["label"],
            )
            self.assertTrue(
                result["queried"],
            )
            self.assertEqual(
                "classified",
                result["reason"],
            )
            self.assertEqual(
                1,
                len(transport.calls),
            )
            self.assertIn(
                "phone-local-classifier.py",
                transport.calls[0],
            )
            self.assertIn(
                "expected=",
                transport.calls[0],
            )

    def test_timeout_fails_closed_to_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_config(root)
            ai = PhoneLocalAI(
                root,
                transport=FakeTransport(
                    timeout_classifier=True,
                ),
            )
            result = ai.classify(
                {"visible_text": "unclear"},
                deterministic_state="AMBIGUOUS",
            )
            self.assertEqual(
                "UNKNOWN",
                result["label"],
            )
            self.assertFalse(
                result["queried"],
            )
            self.assertEqual(
                "timeout",
                result["reason"],
            )

    def test_hot_phone_fails_closed_before_classifier(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_config(root)
            transport = FakeTransport(
                sensor_output="2800000 43000\n",
            )
            ai = PhoneLocalAI(
                root,
                transport=transport,
            )
            result = ai.classify(
                {"visible_text": "unclear"},
                deterministic_state="AMBIGUOUS",
            )
            self.assertEqual(
                "UNKNOWN",
                result["label"],
            )
            self.assertFalse(
                result["queried"],
            )
            self.assertEqual(
                "battery_hot",
                result["reason"],
            )
            self.assertEqual(
                1,
                len(transport.calls),
            )

    def test_default_config_is_disabled_and_contains_no_credentials(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads(
            (
                root
                / "config/phone_local_ai.default.json"
            ).read_text()
        )
        self.assertFalse(config["enabled"])
        self.assertEqual("", config["ssh"]["user"])
        self.assertEqual("", config["ssh"]["key_path"])
        self.assertNotIn("openai", json.dumps(config).lower())


if __name__ == "__main__":
    unittest.main()

