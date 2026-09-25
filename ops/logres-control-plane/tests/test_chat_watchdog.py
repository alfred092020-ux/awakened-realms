from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from logres_chat_watchdog import (
    composer_text,
    contract_probe_action,
    recovery_action,
    response_tail_digest,
    same_run_probe_action,
    ui_rate_limited,
    visible_activity_digest,
    worked_timer_seconds,
)


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

    def test_source_has_no_paid_openai_api_path(self):
        source = (ROOT / "lib/logres_chat_watchdog.py").read_text()
        self.assertNotIn("api.openai.com", source)
        self.assertNotIn("OPENAI_API_KEY", source)
        self.assertNotIn("from openai", source)
        self.assertNotIn("import openai", source)


if __name__ == "__main__":
    unittest.main()
