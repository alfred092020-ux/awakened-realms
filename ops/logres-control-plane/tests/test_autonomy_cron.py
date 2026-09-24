import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_autonomy import (
    AUTONOMY_CRON_LINE,
    AUTONOMY_CRON_MARKER,
    MANAGED_RUNTIME_PATH,
    PREVIEW_REAPER_CRON_LINE,
    PREVIEW_REAPER_CRON_MARKER,
    SWARM_CRON_LINE,
    SWARM_CRON_MARKER,
    normalize_runtime_environment,
    rewrite_crontab,
)


class AutonomyCronTests(unittest.TestCase):
    def test_autonomy_normalizes_runtime_path_before_subprocess_work(self):
        script = (TEST_DIR.parent / "bin" / "logres-autonomy").read_text()
        self.assertIn("normalize_runtime_environment()", script)

    def test_runtime_path_covers_user_local_system_and_sbin_tools(self):
        for path in (
            "/home/ubuntu/logres/bin",
            "/home/ubuntu/.local/bin",
            "/usr/local/sbin",
            "/usr/local/bin",
            "/usr/sbin",
            "/usr/bin",
            "/sbin",
            "/bin",
        ):
            self.assertIn(path, MANAGED_RUNTIME_PATH.split(":"))

        env = {"PATH": "/custom/bin:/usr/bin"}
        normalize_runtime_environment(env)
        parts = env["PATH"].split(":")
        self.assertEqual(1, parts.count("/usr/bin"))
        self.assertIn("/custom/bin", parts)

    def test_managed_cron_lines_pin_runtime_path(self):
        expected = f"PATH={MANAGED_RUNTIME_PATH} "
        for line in (
            AUTONOMY_CRON_LINE,
            SWARM_CRON_LINE,
            PREVIEW_REAPER_CRON_LINE,
        ):
            self.assertIn(expected, line)

    def test_install_replaces_legacy_preflight_cron_and_is_idempotent(self):
        before = """*/5 * * * * /home/ubuntu/logres/bin/logres-autopilot-watch
* * * * * flock -n /tmp/logres-merge-preflight.cron.lock /home/ubuntu/logres/bin/logres-merge-preflight run --max 4 --min-age 45 --min-count 2
*/10 * * * * /home/ubuntu/logres/bin/logres-control-backup
"""
        after = rewrite_crontab(before, install=True)

        self.assertNotIn("logres-merge-preflight run", after)
        self.assertIn(AUTONOMY_CRON_LINE, after)
        self.assertIn(SWARM_CRON_LINE, after)
        self.assertIn(PREVIEW_REAPER_CRON_LINE, after)
        self.assertEqual(
            after,
            rewrite_crontab(after, install=True),
        )

    def test_remove_only_managed_autonomy_and_legacy_preflight_lines(self):
        before = (
            "1 2 * * * /bin/keep-me\n"
            + AUTONOMY_CRON_LINE
            + "\n"
            + SWARM_CRON_LINE
            + "\n"
            + PREVIEW_REAPER_CRON_LINE
            + "\n* * * * * /home/ubuntu/logres/bin/logres-merge-preflight run\n"
        )
        after = rewrite_crontab(before, install=False)

        self.assertEqual("1 2 * * * /bin/keep-me\n", after)
        self.assertNotIn(AUTONOMY_CRON_MARKER, after)
        self.assertNotIn(SWARM_CRON_MARKER, after)
        self.assertNotIn(PREVIEW_REAPER_CRON_MARKER, after)


if __name__ == "__main__":
    unittest.main()
