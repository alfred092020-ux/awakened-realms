from __future__ import annotations

import fcntl
import json
import os
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from logres_chat_wake import (
    ChatWakeBridge,
    inspect_chat_ui,
    validate_target_url,
)


class FakeTransport:
    def __init__(self, health="STATE=READY\nADB_STATE=device\n"):
        self.health_text = health
        self.shell_calls: list[str] = []
        self.xml_values: list[str] = []
        self.foreground = (
            "topResumedActivity=ActivityRecord{x u0 "
            "com.openai.chatgpt/.MainActivity t1}"
        )

    def health(self):
        return self.health_text

    def shell(self, command):
        self.shell_calls.append(command)
        if command.startswith("uiautomator dump"):
            if not self.xml_values:
                raise AssertionError("fake UI XML exhausted")
            return self.xml_values.pop(0)
        if "topResumedActivity" in command or "mResumedActivity" in command:
            return self.foreground
        return "ok"


def ui_xml(
    *,
    label="Logres",
    editor_bounds="[100,1800][760,2100]",
    send_bounds="[800,1900][1000,2100]",
    draft="",
):
    return (
        '<hierarchy><node package="com.openai.chatgpt" class="android.view.View" '
        f'text="{label}" content-desc="" enabled="true" clickable="false" '
        'bounds="[100,100][900,220]" />'
        '<node package="com.openai.chatgpt" class="android.widget.EditText" '
        f'text="{draft}" content-desc="Message" enabled="true" clickable="true" '
        f'bounds="{editor_bounds}" />'
        '<node package="com.openai.chatgpt" class="android.widget.Button" text="" '
        'content-desc="Send" enabled="true" clickable="true" '
        f'bounds="{send_bounds}" /></hierarchy>'
    )


class ChatWakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "control/android-device").mkdir(parents=True)
        (self.root / "config").mkdir(parents=True)
        self.now = 1000.0
        self.transport = FakeTransport()
        self.hw_lock = self.root / "hardware.lock"
        self.bridge_lock = self.root / "bridge.lock"
        self.bridge = ChatWakeBridge(
            self.root,
            transport=self.transport,
            clock=lambda: self.now,
            sleeper=lambda _seconds: None,
            hardware_lock_path=self.hw_lock,
            bridge_lock_path=self.bridge_lock,
        )
        self.write_config()

    def tearDown(self):
        self.tmp.cleanup()

    def write_config(self, **overrides):
        value = {
            "enabled": True,
            "target_name": "Logres",
            "target_url": "https://chatgpt.com/c/abcDEF_123",
            "target_semantic_labels": ["Logres"],
            "min_interval_seconds": 60,
            "settle_seconds": 0,
            "allow_low_battery_wake": False,
            "low_battery_wake_floor_percent": 10,
            "approved_messages": {
                "continue": "Continue Logres work.",
                "status": "Status",
            },
        }
        value.update(overrides)
        self.bridge.runtime_config.write_text(json.dumps(value))

    def prime_open(self, *, composer_bounds="[100,1800][760,2100]"):
        self.transport.xml_values.append(
            ui_xml(editor_bounds=composer_bounds)
        )

    def prime_send(self, *, composer_bounds="[100,1800][760,2100]",
                   send_bounds="[800,1900][1000,2100]"):
        self.transport.xml_values.extend([
            ui_xml(editor_bounds=composer_bounds, send_bounds=send_bounds),
            ui_xml(editor_bounds=composer_bounds, send_bounds=send_bounds),
            ui_xml(editor_bounds=composer_bounds, send_bounds=send_bounds),
        ])

    def test_target_url_is_exact_chat_only(self):
        self.assertEqual(
            validate_target_url("https://chatgpt.com/c/abcDEF_123"),
            "https://chatgpt.com/c/abcDEF_123",
        )
        for bad in (
            "https://example.com/c/abcDEF_123",
            "https://chatgpt.com/",
            "https://chatgpt.com/c/x?foo=bar",
        ):
            with self.assertRaises(ValueError):
                validate_target_url(bad)

    def test_assistant_message_text_does_not_become_fake_composer(self):
        xml = (
            '<hierarchy>'
            '<node package="com.openai.chatgpt" class="android.widget.TextView" '
            'text="Send a message when ready" content-desc="" enabled="true" '
            'clickable="false" bounds="[10,10][500,100]" />'
            '<node package="com.openai.chatgpt" class="android.widget.EditText" '
            'text="" content-desc="" enabled="true" clickable="true" '
            'bounds="[100,1800][760,2100]" />'
            '</hierarchy>'
        )
        result = inspect_chat_ui(xml, [])
        self.assertEqual(["[100,1800][760,2100]"], result["editor_bounds"])

    def test_semantic_ui_finds_stop_control(self):
        xml = (
            '<hierarchy>'
            '<node package="com.openai.chatgpt" class="android.view.View" '
            'text="" content-desc="Stop" enabled="true" clickable="true" '
            'bounds="[900,1900][1000,2100]" />'
            '</hierarchy>'
        )
        result = inspect_chat_ui(xml, [])
        self.assertEqual(["[900,1900][1000,2100]"], result["stop_bounds"])

    def test_semantic_ui_finds_label_composer_and_send(self):
        result = inspect_chat_ui(
            ui_xml(
                editor_bounds="[11,22][111,122]",
                send_bounds="[201,202][301,302]",
            ),
            ["Logres"],
        )
        self.assertEqual(["Logres"], result["label_matches"])
        self.assertEqual(["[11,22][111,122]"], result["editor_bounds"])
        self.assertEqual(["[201,202][301,302]"], result["send_bounds"])

    def test_dry_run_never_touches_phone(self):
        result = self.bridge.dry_run("continue")
        self.assertEqual("DRY_RUN", result["result"])
        self.assertEqual("continue", result["command_key"])
        self.assertEqual([], self.transport.shell_calls)

    def test_pause_blocks_wake(self):
        self.bridge.pause()
        result = self.bridge.wake()
        self.assertEqual("PAUSED", result["result"])
        self.assertEqual([], self.transport.shell_calls)

    def test_hardware_qa_lock_defers_without_phone_mutation(self):
        descriptor = os.open(self.hw_lock, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.bridge.wake()
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
        self.assertEqual("DEFERRED_QA_BUSY", result["result"])
        self.assertEqual([], self.transport.shell_calls)

    def test_power_block_defers(self):
        self.transport.health_text = (
            "STATE=POWER_BLOCK\nBATTERY_LEVEL=14\nADB_STATE=device\n"
        )
        result = self.bridge.wake()
        self.assertEqual("DEFERRED_POWER_BLOCK", result["result"])
        self.assertEqual([], self.transport.shell_calls)

    def test_low_battery_wake_allows_above_hard_floor(self):
        self.write_config(
            allow_low_battery_wake=True,
            low_battery_wake_floor_percent=10,
        )
        self.transport.health_text = (
            "STATE=POWER_BLOCK\nBATTERY_LEVEL=18\nADB_STATE=device\n"
        )
        config = self.bridge._validate_config(
            self.bridge.load_config(),
        )
        result, health = self.bridge._preflight(
            config,
            {},
        )
        self.assertEqual("READY", result)
        self.assertEqual("18", health["BATTERY_LEVEL"])

    def test_low_battery_wake_still_blocks_below_hard_floor(self):
        self.write_config(
            allow_low_battery_wake=True,
            low_battery_wake_floor_percent=10,
        )
        self.transport.health_text = (
            "STATE=POWER_BLOCK\nBATTERY_LEVEL=9\nADB_STATE=device\n"
        )
        config = self.bridge._validate_config(
            self.bridge.load_config(),
        )
        result, health = self.bridge._preflight(
            config,
            {},
        )
        self.assertEqual(
            "DEFERRED_CRITICAL_BATTERY",
            result,
        )
        self.assertEqual("9", health["BATTERY_LEVEL"])

    def test_thermal_block_remains_absolute_when_low_battery_wake_enabled(self):
        self.write_config(
            allow_low_battery_wake=True,
            low_battery_wake_floor_percent=10,
        )
        self.transport.health_text = (
            "STATE=THERMAL_BLOCK\nBATTERY_LEVEL=18\nADB_STATE=device\n"
        )
        config = self.bridge._validate_config(
            self.bridge.load_config(),
        )
        result, _health = self.bridge._preflight(
            config,
            {},
        )
        self.assertEqual(
            "DEFERRED_THERMAL_BLOCK",
            result,
        )

    def test_native_exact_chat_uses_deep_link_and_semantic_verification(self):
        self.prime_open()
        result = self.bridge.wake()
        self.assertEqual("NATIVE_EXACT_CHAT", result["result"])
        calls = "\\n".join(self.transport.shell_calls)
        self.assertIn("pm enable com.openai.chatgpt", calls)
        self.assertIn("KEYCODE_WAKEUP", calls)
        self.assertIn("https://chatgpt.com/c/abcDEF_123", calls)
        self.assertIn("com.openai.chatgpt/.MainActivity", calls)
        self.assertIn("uiautomator dump", calls)

    def test_semantic_send_targets_dynamic_bounds_not_fixed_coordinates(self):
        self.prime_send(
            composer_bounds="[10,20][110,120]",
            send_bounds="[300,400][500,600]",
        )
        result = self.bridge.send("continue", "cmd-001")
        self.assertEqual("SENT", result["result"])
        calls = self.transport.shell_calls
        self.assertIn("input tap 60 70", calls)
        self.assertIn("input tap 400 500", calls)
        self.assertFalse(any("input tap 540 " in call for call in calls))
        self.assertTrue(any("input text" in call for call in calls))

    def test_unknown_message_key_is_rejected_before_phone_access(self):
        with self.assertRaisesRegex(ValueError, "not approved"):
            self.bridge.send("arbitrary", "cmd-001")
        self.assertEqual([], self.transport.shell_calls)

    def test_duplicate_and_rate_limit_are_persistent(self):
        self.prime_send()
        sent = self.bridge.send("continue", "cmd-001")
        self.assertEqual("SENT", sent["result"])

        duplicate = self.bridge.send("continue", "cmd-001")
        self.assertEqual("DUPLICATE", duplicate["result"])

        limited = self.bridge.send("status", "cmd-002")
        self.assertEqual("RATE_LIMITED", limited["result"])

        self.now += 61
        self.prime_send()
        sent_again = self.bridge.send("status", "cmd-002")
        self.assertEqual("SENT", sent_again["result"])

    def test_semantic_target_mismatch_fails_closed(self):
        self.transport.xml_values.append(ui_xml(label="Different Chat"))
        result = self.bridge.wake()
        self.assertEqual("SEMANTIC_TARGET_VERIFY_FAILED", result["result"])

    def test_existing_draft_fails_closed(self):
        self.transport.xml_values.extend([
            ui_xml(),
            ui_xml(draft="do not overwrite"),
        ])
        with self.assertRaisesRegex(RuntimeError, "existing draft"):
            self.bridge.send("continue", "cmd-003")

    def test_audit_is_append_only(self):
        config = self.bridge._validate_config(self.bridge.load_config())
        self.bridge.audit("wake", "ONE", config=config)
        first = self.bridge.audit_path.read_text()
        self.bridge.audit("wake", "TWO", config=config)
        second = self.bridge.audit_path.read_text()
        self.assertTrue(second.startswith(first))
        self.assertEqual(2, len(second.splitlines()))

    def test_source_has_no_paid_openai_api_path(self):
        source = (ROOT / "lib/logres_chat_wake.py").read_text()
        self.assertNotIn("api.openai.com", source)
        self.assertNotIn("OPENAI_API_KEY", source)
        self.assertNotIn("from openai", source)
        self.assertNotIn("import openai", source)


if __name__ == "__main__":
    unittest.main()
