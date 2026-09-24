import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_autonomy import (
    AUTONOMY_CRON_LINE,
    AUTONOMY_CRON_MARKER,
    rewrite_crontab,
)


class AutonomyCronTests(unittest.TestCase):
    def test_install_replaces_legacy_preflight_cron_and_is_idempotent(self):
        before = """*/5 * * * * /home/ubuntu/logres/bin/logres-autopilot-watch
* * * * * flock -n /tmp/logres-merge-preflight.cron.lock /home/ubuntu/logres/bin/logres-merge-preflight run --max 4 --min-age 45 --min-count 2
*/10 * * * * /home/ubuntu/logres/bin/logres-control-backup
"""
        after = rewrite_crontab(before, install=True)

        self.assertNotIn("logres-merge-preflight run", after)
        self.assertIn(AUTONOMY_CRON_LINE, after)
        self.assertEqual(
            after,
            rewrite_crontab(after, install=True),
        )

    def test_remove_only_managed_autonomy_and_legacy_preflight_lines(self):
        before = (
            "1 2 * * * /bin/keep-me\n"
            + AUTONOMY_CRON_LINE
            + "\n* * * * * /home/ubuntu/logres/bin/logres-merge-preflight run\n"
        )
        after = rewrite_crontab(before, install=False)

        self.assertEqual("1 2 * * * /bin/keep-me\n", after)
        self.assertNotIn(AUTONOMY_CRON_MARKER, after)


if __name__ == "__main__":
    unittest.main()
