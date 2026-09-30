import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_throughput import (
    metric_slo_status,
    percentile,
    summarize_recent,
    summarize_window,
)


class ThroughputTests(unittest.TestCase):
    def test_percentile_uses_nearest_rank(self):
        self.assertIsNone(percentile([], 0.95))
        self.assertEqual(1.0, percentile([1, 2, 3, 4], 0))
        self.assertEqual(4.0, percentile([1, 2, 3, 4], 0.95))

    def test_window_filters_by_completion_time(self):
        now = 10_000.0
        samples = [
            (now - 3700, 999),
            (now - 3500, 80),
            (now - 1000, 20),
            (now - 10, 10),
        ]
        summary = summarize_window(samples, now_epoch=now, window_seconds=1200)
        self.assertEqual(2, summary["samples"])
        self.assertEqual(15.0, summary["median_seconds"])
        self.assertEqual(20.0, summary["p95_seconds"])

    def test_old_good_history_cannot_hide_recent_regression(self):
        now = 20_000.0
        samples = {
            "queue_ready_to_preflight_verified": [
                *[(now - 7200 - i, 20) for i in range(30)],
                (now - 300, 180),
                (now - 200, 190),
            ]
        }
        recent = summarize_recent(samples, now_epoch=now)
        self.assertEqual("FAIL", recent["20m"]["status"])
        metric = recent["20m"]["metrics"]["queue_ready_to_preflight_verified"]
        self.assertEqual("FAIL", metric["slo_status"])
        self.assertEqual(190.0, metric["p95_seconds"])

    def test_old_bad_history_cannot_hide_recent_improvement(self):
        now = 30_000.0
        samples = {
            "queue_ready_to_preflight_verified": [
                *[(now - 7200 - i, 500) for i in range(30)],
                (now - 300, 40),
                (now - 200, 50),
                (now - 100, 60),
            ]
        }
        recent = summarize_recent(samples, now_epoch=now)
        metric = recent["20m"]["metrics"]["queue_ready_to_preflight_verified"]
        self.assertEqual("PASS", metric["slo_status"])
        self.assertEqual(60.0, metric["p95_seconds"])

    def test_no_data_is_explicit(self):
        status = metric_slo_status(
            {"samples": 0, "p95_seconds": None},
            10,
        )
        self.assertEqual("NO_DATA", status)


if __name__ == "__main__":
    unittest.main()

class CoordinatorSelfAuditTests(unittest.TestCase):
    def test_self_audit_metrics_are_explicit_and_safe(self):
        from logres_throughput import coordinator_self_audit, SELF_AUDIT_METRICS
        out=coordinator_self_audit(verified_candidates=4,window_hours=2,verification_latencies=[10,20],integration_latencies=[2,4],dispatches=10,failed_dispatches=2,failures=4,repeated_failures=1,attempts=8,no_diff=1,stale_workers=2,unnecessary_repairs=1,used_slots=3,total_slots=10,recoveries=2,successful_recoveries=1,integrations=5,escaped_regressions=1,human_interventions=2)
        self.assertEqual(set(SELF_AUDIT_METRICS),set(out)); self.assertEqual(2,out['useful_verified_candidates_per_hour']); self.assertEqual(.3,out['resource_saturation'])
