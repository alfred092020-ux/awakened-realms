from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from logres_chat_watchdog import (
    ChatPeerWatchdog,
    contract_gate_action,
    composer_text,
    contract_probe_action,
    expired_running_no_stop_probe_action,
    phone_ai_recovery_action,
    recovery_action,
    response_tail_digest,
    same_run_probe_action,
    ui_rate_limited,
    visible_activity_digest,
    visible_chat_text,
    worked_timer_seconds,
)


class MutableClock:
    def __init__(self, value: float):
        self.value = float(value)

    def __call__(self) -> float:
        return self.value


class FakePhoneAI:
    def __init__(self, result=None, *, raises=False):
        self.result = result or {
            "label": "UNKNOWN",
            "queried": True,
            "confidence": 0.9,
            "margin": 0.4,
            "reason": "classified",
        }
        self.raises = raises
        self.calls = []

    def classify(self, observation, *, deterministic_state):
        self.calls.append(
            {
                "observation": observation,
                "deterministic_state": deterministic_state,
            }
        )
        if self.raises:
            raise RuntimeError("synthetic classifier failure")
        return dict(self.result)


class FakeBridgeTransport:
    def __init__(self):
        self.shell_calls = []

    def shell(self, command):
        self.shell_calls.append(command)
        return ""


class FakeBridge:
    COMPLETED_XML = (
        '<hierarchy>'
        '<node package="com.openai.chatgpt" '
        'text="Completed answer" content-desc="" bounds="[0,0][20,20]" />'
        '<node package="com.openai.chatgpt" '
        'text="Copy" content-desc="" bounds="[0,20][20,40]" />'
        '</hierarchy>'
    )
    WORKING_XML_1 = (
        '<hierarchy>'
        '<node package="com.openai.chatgpt" '
        'text="Worked for 1s" content-desc="" bounds="[0,0][20,20]" />'
        '<node package="com.openai.chatgpt" '
        'text="" content-desc="Stop" bounds="[0,20][20,40]" />'
        '<node package="com.openai.chatgpt" '
        'text="Working answer" content-desc="" bounds="[0,40][20,60]" />'
        '</hierarchy>'
    )
    WORKING_XML_2 = (
        '<hierarchy>'
        '<node package="com.openai.chatgpt" '
        'text="Worked for 2s" content-desc="" bounds="[0,0][20,20]" />'
        '<node package="com.openai.chatgpt" '
        'text="" content-desc="Stop" bounds="[0,20][20,40]" />'
        '<node package="com.openai.chatgpt" '
        'text="Working answer grew" content-desc="" bounds="[0,40][20,60]" />'
        '</hierarchy>'
    )
    DRAFT_XML = (
        '<hierarchy>'
        '<node package="com.openai.chatgpt" '
        'class="android.widget.EditText" '
        'text="unsent user draft" content-desc="" bounds="[0,0][40,40]" />'
        '</hierarchy>'
    )
    RATE_LIMIT_XML = (
        '<hierarchy>'
        '<node package="com.openai.chatgpt" '
        'text="Too many requests. Try again later." '
        'content-desc="" bounds="[0,0][40,40]" />'
        '</hierarchy>'
    )

    def __init__(self, xml_sequence):
        self.xml_sequence = list(xml_sequence)
        self.index = 0
        self.sent = False
        self.send_calls = []
        self.transport = FakeBridgeTransport()

    def wake(self):
        return {"result": "NATIVE_EXACT_CHAT"}

    def _ui_xml(self):
        if self.sent:
            return self.WORKING_XML_1
        if not self.xml_sequence:
            return self.COMPLETED_XML
        index = min(
            self.index,
            len(self.xml_sequence) - 1,
        )
        value = self.xml_sequence[index]
        self.index += 1
        return value

    def send(self, message_key, command_id):
        self.send_calls.append(
            (message_key, command_id)
        )
        self.sent = True
        return {"result": "SENT"}


class FakeWatchdog(ChatPeerWatchdog):
    def __init__(
        self,
        root,
        *,
        clock,
        phone_ai,
        bridge,
    ):
        super().__init__(
            root,
            clock=clock,
            sleeper=lambda _seconds: None,
            phone_ai=phone_ai,
        )
        self.fake_bridge = bridge
        self.audit_records = []

    def _brain_state(self, chat_id):
        return {
            "member_status": "ACTIVE",
            "last_activity_epoch": 0.0,
            "active_tasks": ["SYNTHETIC"],
        }

    def _bridge(self, target, common):
        return self.fake_bridge

    def audit(self, payload):
        self.audit_records.append(dict(payload))


class ChatWatchdogTests(unittest.TestCase):
    def test_fresh_chat_is_untouched(self):
        self.assertEqual(
            "FRESH",
            recovery_action(
                stale_age=299,
                stale_seconds=300,
                stop_present=False,
                digest_changed=False,
                stuck_age=0,
                stuck_seconds=300,
                cooldown_age=1000,
                cooldown_seconds=600,
            ),
        )

    def test_completed_idle_chat_gets_resume(self):
        self.assertEqual(
            "RESUME",
            recovery_action(
                stale_age=301,
                stale_seconds=300,
                stop_present=False,
                digest_changed=False,
                stuck_age=0,
                stuck_seconds=300,
                cooldown_age=1000,
                cooldown_seconds=600,
            ),
        )

    def test_working_chat_is_observed_before_stop(self):
        self.assertEqual(
            "OBSERVE",
            recovery_action(
                stale_age=600,
                stale_seconds=300,
                stop_present=True,
                digest_changed=False,
                stuck_age=299,
                stuck_seconds=300,
                cooldown_age=1000,
                cooldown_seconds=600,
            ),
        )

    def test_stuck_chat_is_stopped_then_resumed(self):
        self.assertEqual(
            "STOP_AND_RESUME",
            recovery_action(
                stale_age=700,
                stale_seconds=300,
                stop_present=True,
                digest_changed=False,
                stuck_age=301,
                stuck_seconds=300,
                cooldown_age=1000,
                cooldown_seconds=600,
            ),
        )

    def test_visible_progress_resets_stuck_observation(self):
        self.assertEqual(
            "OBSERVE",
            recovery_action(
                stale_age=700,
                stale_seconds=300,
                stop_present=True,
                digest_changed=True,
                stuck_age=700,
                stuck_seconds=300,
                cooldown_age=1000,
                cooldown_seconds=600,
            ),
        )

    def test_cooldown_prevents_recovery_loop(self):
        self.assertEqual(
            "COOLDOWN",
            recovery_action(
                stale_age=700,
                stale_seconds=300,
                stop_present=False,
                digest_changed=False,
                stuck_age=700,
                stuck_seconds=300,
                cooldown_age=100,
                cooldown_seconds=600,
            ),
        )

    def test_worked_timer_does_not_count_as_semantic_progress(self):
        a = (
            '<hierarchy><node text="Worked for 1m 5s" content-desc="" />'
            '<node text="Stable answer text" content-desc="" /></hierarchy>'
        )
        b = (
            '<hierarchy><node text="Worked for 1m 10s" content-desc="" />'
            '<node text="Stable answer text" content-desc="" /></hierarchy>'
        )
        self.assertEqual(visible_activity_digest(a), visible_activity_digest(b))

    def test_system_ui_clock_change_does_not_count_as_chat_progress(self):
        a = (
            '<hierarchy>'
            '<node package="com.android.systemui" text="9:39" content-desc="" />'
            '<node package="com.openai.chatgpt" text="Stable answer text" content-desc="" />'
            '</hierarchy>'
        )
        b = (
            '<hierarchy>'
            '<node package="com.android.systemui" text="9:44" content-desc="" />'
            '<node package="com.openai.chatgpt" text="Stable answer text" content-desc="" />'
            '</hierarchy>'
        )
        self.assertEqual(visible_activity_digest(a), visible_activity_digest(b))

    def test_systemd_watchdog_runtime_timeout_fits_recovery_and_cadence(self):
        service = (ROOT / 'systemd/logres-chat-watchdog.service').read_text()
        timeout_line = next(
            line for line in service.splitlines()
            if line.startswith('TimeoutStartSec=')
        )
        timeout_seconds = int(
            timeout_line.split('=', 1)[1].removesuffix('s')
        )
        self.assertGreaterEqual(timeout_seconds, 180)
        self.assertLess(timeout_seconds, 300)
        self.assertEqual(timeout_seconds, 240)

    def test_same_run_probe_leaves_semantically_progressing_chat_alone(self):
        self.assertEqual(
            "WORKING",
            same_run_probe_action(
                initial_stop_present=True,
                initial_digest="before",
                later_stop_present=True,
                later_digest="after",
            ),
        )

    def test_same_run_probe_stops_stalled_active_chat(self):
        self.assertEqual(
            "STOP_AND_RESUME",
            same_run_probe_action(
                initial_stop_present=True,
                initial_digest="same",
                later_stop_present=True,
                later_digest="same",
            ),
        )

    def test_same_run_probe_resumes_completed_chat(self):
        self.assertEqual(
            "RESUME",
            same_run_probe_action(
                initial_stop_present=True,
                initial_digest="same",
                later_stop_present=False,
                later_digest="same",
            ),
        )

    def test_watchdog_timer_checks_every_minute_for_five_minute_stale_sla(self):
        timer = (ROOT / "systemd/logres-chat-watchdog.timer").read_text()
        self.assertIn("OnBootSec=1min", timer)
        self.assertIn("OnUnitActiveSec=1min", timer)
        self.assertIn("AccuracySec=5s", timer)

        config = (ROOT / "config/chat_watchdog.default.json").read_text()
        self.assertNotIn('"stale_seconds"', config)
        self.assertIn('"stuck_probe_seconds": 15', config)
        self.assertIn('"cooldown_seconds": 300', config)

    def test_real_content_change_counts_as_progress(self):
        a = '<hierarchy><node text="Alpha" content-desc="" /></hierarchy>'
        b = '<hierarchy><node text="Beta" content-desc="" /></hierarchy>'
        self.assertNotEqual(visible_activity_digest(a), visible_activity_digest(b))

    def test_running_contract_resumes_immediately_when_turn_has_ended(self):
        self.assertEqual(
            "RESUME",
            contract_probe_action(
                contract_state="RUNNING",
                initial_stop_present=False,
                initial_worked_seconds=None,
                initial_tail_digest="same",
                later_stop_present=False,
                later_worked_seconds=None,
                later_tail_digest="same",
            ),
        )

    def test_non_running_contracts_never_auto_resume(self):
        for state in ("PAUSED", "WAITING_USER", "DONE"):
            self.assertEqual(
                "HOLD",
                contract_probe_action(
                    contract_state=state,
                    initial_stop_present=False,
                    initial_worked_seconds=None,
                    initial_tail_digest="same",
                    later_stop_present=False,
                    later_worked_seconds=None,
                    later_tail_digest="same",
                ),
            )

    def test_worked_timer_advance_proves_active_response(self):
        self.assertEqual(
            "WORKING",
            contract_probe_action(
                contract_state="RUNNING",
                initial_stop_present=True,
                initial_worked_seconds=65,
                initial_tail_digest="same",
                later_stop_present=True,
                later_worked_seconds=72,
                later_tail_digest="same",
            ),
        )

    def test_response_tail_advance_proves_active_response(self):
        self.assertEqual(
            "WORKING",
            contract_probe_action(
                contract_state="RUNNING",
                initial_stop_present=True,
                initial_worked_seconds=None,
                initial_tail_digest="before",
                later_stop_present=True,
                later_worked_seconds=None,
                later_tail_digest="after",
            ),
        )

    def test_running_contract_stops_only_when_timer_and_tail_are_frozen(self):
        self.assertEqual(
            "STOP_AND_RESUME",
            contract_probe_action(
                contract_state="RUNNING",
                initial_stop_present=True,
                initial_worked_seconds=65,
                initial_tail_digest="same",
                later_stop_present=True,
                later_worked_seconds=65,
                later_tail_digest="same",
            ),
        )

    def test_worked_timer_parser_handles_seconds_and_minutes(self):
        xml = (
            '<hierarchy>'
            '<node package="com.openai.chatgpt" text="Worked for 1m 5s" content-desc="" />'
            '</hierarchy>'
        )
        self.assertEqual(65, worked_timer_seconds(xml))

        xml_seconds = (
            '<hierarchy>'
            '<node package="com.openai.chatgpt" text="Worked for 42s" content-desc="" />'
            '</hierarchy>'
        )
        self.assertEqual(42, worked_timer_seconds(xml_seconds))

    def test_response_tail_ignores_worked_timer_but_not_answer_text(self):
        a = (
            '<hierarchy>'
            '<node package="com.openai.chatgpt" text="Worked for 1m 5s" content-desc="" />'
            '<node package="com.openai.chatgpt" text="Answer A" content-desc="" />'
            '</hierarchy>'
        )
        b = (
            '<hierarchy>'
            '<node package="com.openai.chatgpt" text="Worked for 1m 12s" content-desc="" />'
            '<node package="com.openai.chatgpt" text="Answer A" content-desc="" />'
            '</hierarchy>'
        )
        c = (
            '<hierarchy>'
            '<node package="com.openai.chatgpt" text="Worked for 1m 12s" content-desc="" />'
            '<node package="com.openai.chatgpt" text="Answer B" content-desc="" />'
            '</hierarchy>'
        )
        self.assertEqual(response_tail_digest(a), response_tail_digest(b))
        self.assertNotEqual(response_tail_digest(b), response_tail_digest(c))

    def test_rate_limit_banner_is_detected(self):
        xml = (
            '<hierarchy>'
            '<node package="com.openai.chatgpt" text="Too many requests" content-desc="" />'
            '</hierarchy>'
        )
        self.assertTrue(ui_rate_limited(xml))

    def test_rate_limit_banner_does_not_count_as_response_progress(self):
        a = (
            '<hierarchy>'
            '<node package="com.openai.chatgpt" text="Stable answer" content-desc="" />'
            '</hierarchy>'
        )
        b = (
            '<hierarchy>'
            '<node package="com.openai.chatgpt" text="Stable answer" content-desc="" />'
            '<node package="com.openai.chatgpt" text="Too many requests" content-desc="" />'
            '</hierarchy>'
        )
        self.assertEqual(response_tail_digest(a), response_tail_digest(b))

    def test_composer_text_requires_exactly_one_editor(self):
        self.assertEqual("resume", composer_text({"editor_text": ["resume"]}))
        self.assertEqual("", composer_text({"editor_text": []}))
        self.assertEqual("", composer_text({"editor_text": ["a", "b"]}))

    def test_default_config_uses_conservative_retry_and_rate_limit_backoff(self):
        import json
        config = json.loads(
            (ROOT / "config/chat_watchdog.default.json").read_text()
        )
        self.assertEqual(300, config["policy"]["cooldown_seconds"])
        self.assertEqual(600, config["policy"]["rate_limit_backoff_seconds"])
        self.assertEqual(15, config["policy"]["stuck_probe_seconds"])
        self.assertEqual(5, config["policy"]["ambiguity_probe_seconds"])
        self.assertFalse(
            config["policy"]["phone_local_ai_ambiguity_enabled"]
        )

    def test_fresh_running_heartbeat_skips_phone_check(self):
        self.assertEqual(
            "RUNNING_HEARTBEAT",
            contract_gate_action(
                contract_state="RUNNING",
                heartbeat_age=30,
                heartbeat_timeout_seconds=300,
                continuation_age=0,
                continuation_grace_seconds=30,
            ),
        )

    def test_stale_running_heartbeat_falls_back_to_phone_check(self):
        self.assertEqual(
            "PHONE_CHECK",
            contract_gate_action(
                contract_state="RUNNING",
                heartbeat_age=301,
                heartbeat_timeout_seconds=300,
                continuation_age=0,
                continuation_grace_seconds=30,
            ),
        )

    def test_continue_requested_uses_grace_then_phone_check(self):
        self.assertEqual(
            "CONTINUATION_GRACE",
            contract_gate_action(
                contract_state="CONTINUE_REQUESTED",
                heartbeat_age=0,
                heartbeat_timeout_seconds=300,
                continuation_age=10,
                continuation_grace_seconds=30,
            ),
        )
        self.assertEqual(
            "PHONE_CHECK",
            contract_gate_action(
                contract_state="CONTINUE_REQUESTED",
                heartbeat_age=0,
                heartbeat_timeout_seconds=300,
                continuation_age=31,
                continuation_grace_seconds=30,
            ),
        )

    def test_waiting_paused_done_are_holds(self):
        for state in ("WAITING_USER", "PAUSED", "DONE"):
            self.assertEqual(
                "HOLD",
                contract_gate_action(
                    contract_state=state,
                    heartbeat_age=999,
                    heartbeat_timeout_seconds=300,
                    continuation_age=999,
                    continuation_grace_seconds=30,
                ),
            )

    def test_continue_requested_is_resume_capable_in_native_probe(self):
        self.assertEqual(
            "RESUME",
            contract_probe_action(
                contract_state="CONTINUE_REQUESTED",
                initial_stop_present=False,
                initial_worked_seconds=None,
                initial_tail_digest="same",
                later_stop_present=False,
                later_worked_seconds=None,
                later_tail_digest="same",
            ),
        )

    def test_expired_running_no_stop_progress_is_working(self):
        self.assertEqual(
            "WORKING",
            expired_running_no_stop_probe_action(
                initial_tail_digest="before",
                later_stop_present=False,
                later_tail_digest="after",
            ),
        )

    def test_expired_running_new_stop_is_working(self):
        self.assertEqual(
            "WORKING",
            expired_running_no_stop_probe_action(
                initial_tail_digest="same",
                later_stop_present=True,
                later_tail_digest="same",
            ),
        )

    def test_expired_running_stable_no_stop_is_ambiguous(self):
        self.assertEqual(
            "AMBIGUOUS",
            expired_running_no_stop_probe_action(
                initial_tail_digest="same",
                later_stop_present=False,
                later_tail_digest="same",
            ),
        )

    def test_phone_ai_action_mapping_is_fail_closed(self):
        self.assertEqual(
            "AI_ACTIVE_HOLD",
            phone_ai_recovery_action(
                "ACTIVE",
                stop_count=0,
            ),
        )
        self.assertEqual(
            "RESUME",
            phone_ai_recovery_action(
                "ENDED",
                stop_count=0,
            ),
        )
        self.assertEqual(
            "AI_RATE_LIMITED",
            phone_ai_recovery_action(
                "RATE_LIMITED",
                stop_count=0,
            ),
        )
        self.assertEqual(
            "AI_WAITING_USER",
            phone_ai_recovery_action(
                "WAITING_USER",
                stop_count=0,
            ),
        )
        self.assertEqual(
            "AI_HOLD",
            phone_ai_recovery_action(
                "UNKNOWN",
                stop_count=0,
            ),
        )
        self.assertEqual(
            "AI_HOLD",
            phone_ai_recovery_action(
                "STUCK",
                stop_count=0,
            ),
        )
        self.assertEqual(
            "STOP_AND_RESUME",
            phone_ai_recovery_action(
                "STUCK",
                stop_count=1,
            ),
        )
        self.assertEqual(
            "AI_HOLD",
            phone_ai_recovery_action(
                "nonsense",
                stop_count=0,
            ),
        )

    def test_visible_chat_text_excludes_transient_timer_and_system_ui(self):
        xml = (
            '<hierarchy>'
            '<node package="com.android.systemui" text="9:41" content-desc="" />'
            '<node package="com.openai.chatgpt" text="Stop" content-desc="" />'
            '<node package="com.openai.chatgpt" text="Worked for 2m 3s" content-desc="" />'
            '<node package="com.openai.chatgpt" text="Completed answer" content-desc="" />'
            '<node package="com.openai.chatgpt" text="Copy" content-desc="" />'
            '</hierarchy>'
        )
        text = visible_chat_text(xml)
        self.assertNotIn("9:41", text)
        self.assertNotIn("Worked for", text)
        self.assertNotIn("Stop", text)
        self.assertIn("Completed answer", text)
        self.assertIn("Copy", text)

    def test_phone_ai_hook_is_narrow_and_advisory_in_source(self):
        source = (ROOT / "lib/logres_chat_watchdog.py").read_text()
        self.assertIn(
            'deterministic_state="AMBIGUOUS"',
            source,
        )
        self.assertIn(
            'contract_state == "RUNNING"',
            source,
        )
        self.assertIn(
            "heartbeat_age >= heartbeat_timeout",
            source,
        )
        self.assertIn(
            "not initial_stop",
            source,
        )
        self.assertIn(
            '"result": "PHONE_AI_HOLD"',
            source,
        )
        self.assertIn(
            '"result": "PHONE_AI_ACTIVE_HOLD"',
            source,
        )
        self.assertIn(
            '"label": "UNKNOWN"',
            source,
        )
        self.assertIn(
            '"classifier_error:"',
            source,
        )
        self.assertIn(
            '"action": "PHONE_AI_DECISION"',
            source,
        )

    def _runtime_watchdog(
        self,
        *,
        phone_ai_result=None,
        phone_ai_raises=False,
        xml_sequence=None,
    ):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / "control/android-device").mkdir(
            parents=True,
            exist_ok=True,
        )
        clock = MutableClock(1000)
        phone_ai = FakePhoneAI(
            phone_ai_result,
            raises=phone_ai_raises,
        )
        bridge = FakeBridge(
            xml_sequence
            or [
                FakeBridge.COMPLETED_XML,
                FakeBridge.COMPLETED_XML,
            ]
        )
        watchdog = FakeWatchdog(
            root,
            clock=clock,
            phone_ai=phone_ai,
            bridge=bridge,
        )
        watchdog.contracts.set_state(
            "master",
            "RUNNING",
            reason="synthetic test",
        )
        clock.value = 1401
        return temp, watchdog, phone_ai, bridge

    def _runtime_target(self):
        return {
            "chat_id": "master",
            "use_runtime_contract": True,
            "phone_local_ai_ambiguity_enabled": True,
            "resume_message": "Resume work.",
            "running_heartbeat_timeout_seconds": 300,
            "ambiguity_probe_seconds": 5,
        }

    def test_runtime_ambiguous_unknown_holds_without_send(self):
        temp, watchdog, phone_ai, bridge = self._runtime_watchdog(
            phone_ai_result={
                "label": "UNKNOWN",
                "queried": True,
                "confidence": 0.7,
                "margin": 0.2,
                "reason": "low_confidence",
            },
        )
        with temp:
            result = watchdog.tick_target(
                self._runtime_target(),
                {},
                {},
            )
        self.assertEqual(
            "PHONE_AI_HOLD",
            result["result"],
        )
        self.assertEqual(1, len(phone_ai.calls))
        self.assertEqual("AMBIGUOUS", phone_ai.calls[0]["deterministic_state"])
        self.assertEqual([], bridge.send_calls)
        self.assertEqual([], bridge.transport.shell_calls)

    def test_runtime_classifier_exception_holds_without_send(self):
        temp, watchdog, phone_ai, bridge = self._runtime_watchdog(
            phone_ai_raises=True,
        )
        with temp:
            result = watchdog.tick_target(
                self._runtime_target(),
                {},
                {},
            )
        self.assertEqual(
            "PHONE_AI_HOLD",
            result["result"],
        )
        self.assertEqual(1, len(phone_ai.calls))
        self.assertEqual([], bridge.send_calls)
        self.assertEqual([], bridge.transport.shell_calls)
        self.assertEqual(
            "UNKNOWN",
            result["phone_ai"]["label"],
        )
        self.assertTrue(
            str(result["phone_ai"]["reason"]).startswith(
                "classifier_error:"
            )
        )

    def test_runtime_ai_ended_may_resume_without_pressing_stop(self):
        temp, watchdog, phone_ai, bridge = self._runtime_watchdog(
            phone_ai_result={
                "label": "ENDED",
                "queried": True,
                "confidence": 0.95,
                "margin": 0.7,
                "reason": "classified",
            },
        )
        with temp:
            result = watchdog.tick_target(
                self._runtime_target(),
                {},
                {},
            )
        self.assertEqual(
            "RESPONDING",
            result["result"],
        )
        self.assertEqual("RESUME", result["action"])
        self.assertEqual(1, len(phone_ai.calls))
        self.assertEqual(1, len(bridge.send_calls))
        self.assertEqual([], bridge.transport.shell_calls)

    def test_runtime_user_draft_guard_bypasses_phone_ai(self):
        temp, watchdog, phone_ai, bridge = self._runtime_watchdog(
            xml_sequence=[
                FakeBridge.DRAFT_XML,
            ],
        )
        with temp:
            result = watchdog.tick_target(
                self._runtime_target(),
                {},
                {},
            )
        self.assertEqual(
            "USER_DRAFT_HOLD",
            result["result"],
        )
        self.assertEqual([], phone_ai.calls)
        self.assertEqual([], bridge.send_calls)
        self.assertEqual([], bridge.transport.shell_calls)

    def test_runtime_rate_limit_guard_bypasses_phone_ai(self):
        temp, watchdog, phone_ai, bridge = self._runtime_watchdog(
            xml_sequence=[
                FakeBridge.RATE_LIMIT_XML,
            ],
        )
        with temp:
            result = watchdog.tick_target(
                self._runtime_target(),
                {},
                {},
            )
        self.assertEqual(
            "RATE_LIMITED",
            result["result"],
        )
        self.assertEqual([], phone_ai.calls)
        self.assertEqual([], bridge.send_calls)
        self.assertEqual([], bridge.transport.shell_calls)

    def test_runtime_native_progress_bypasses_phone_ai(self):
        temp, watchdog, phone_ai, bridge = self._runtime_watchdog(
            xml_sequence=[
                FakeBridge.WORKING_XML_1,
                FakeBridge.WORKING_XML_2,
            ],
        )
        with temp:
            result = watchdog.tick_target(
                self._runtime_target(),
                {},
                {},
            )
        self.assertEqual(
            "WORKING",
            result["result"],
        )
        self.assertEqual([], phone_ai.calls)
        self.assertEqual([], bridge.send_calls)

    def test_runtime_fresh_contract_bypasses_phone_and_bridge(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / "control/android-device").mkdir(
            parents=True,
            exist_ok=True,
        )
        clock = MutableClock(1000)
        phone_ai = FakePhoneAI()
        bridge = FakeBridge(
            [FakeBridge.COMPLETED_XML],
        )
        watchdog = FakeWatchdog(
            root,
            clock=clock,
            phone_ai=phone_ai,
            bridge=bridge,
        )
        watchdog.contracts.set_state(
            "master",
            "RUNNING",
            reason="fresh synthetic test",
        )
        with temp:
            result = watchdog.tick_target(
                self._runtime_target(),
                {},
                {},
            )
        self.assertEqual(
            "RUNNING_HEARTBEAT",
            result["result"],
        )
        self.assertEqual([], phone_ai.calls)
        self.assertEqual(0, bridge.index)
        self.assertEqual([], bridge.send_calls)

    def test_source_has_no_paid_openai_api_path(self):
        source = (ROOT / "lib/logres_chat_watchdog.py").read_text()
        self.assertNotIn("api.openai.com", source)
        self.assertNotIn("OPENAI_API_KEY", source)
        self.assertNotIn("from openai", source)
        self.assertNotIn("import openai", source)


if __name__ == "__main__":
    unittest.main()
