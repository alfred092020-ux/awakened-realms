from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from logres_chat_watchdog import recovery_action, visible_activity_digest


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

    def test_real_content_change_counts_as_progress(self):
        a = '<hierarchy><node text="Alpha" content-desc="" /></hierarchy>'
        b = '<hierarchy><node text="Beta" content-desc="" /></hierarchy>'
        self.assertNotEqual(visible_activity_digest(a), visible_activity_digest(b))

    def test_source_has_no_paid_openai_api_path(self):
        source = (ROOT / "lib/logres_chat_watchdog.py").read_text()
        self.assertNotIn("api.openai.com", source)
        self.assertNotIn("OPENAI_API_KEY", source)
        self.assertNotIn("from openai", source)
        self.assertNotIn("import openai", source)


if __name__ == "__main__":
    unittest.main()
