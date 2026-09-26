from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

import logres_factory_metrics as fm


def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


SCHEMA = """
create table task_scopes(task_id text, path_prefix text);
create table integration_queue(task_id text, status text, queued_at real,
                               verified_at real, integrated_at real,
                               updated_at real);
create table task_state_history(task_id text, status text, ts_epoch real);
create table lease_history(task_id text, action text, ts_epoch real);
create table brain_task_leases(task_id text, branch text,
                               lease_until_epoch real);
create table regressions(status text);
"""

NOW = 1_000_000.0


def seeded_conn():
    conn = make_conn()
    conn.executescript(SCHEMA)
    conn.executemany(
        "insert into task_scopes values(?,?)",
        [("g1", "game/world/level.py"), ("i1", "ops/logres-control-plane/bin/x"),
         ("u1", "docs/notes.md")],
    )
    conn.executemany(
        "insert into integration_queue values(?,?,?,?,?,?)",
        [("g1", "INTEGRATED", NOW - 100, NOW - 50, NOW - 40, NOW - 40),
         ("i1", "INTEGRATED", NOW - 70000, NOW - 69000, NOW - 68000, NOW - 68000),
         ("u1", "INTEGRATED", NOW - 200000, NOW - 199000, NOW - 198000, NOW - 198000),
         ("pend", "PREFLIGHT_VERIFIED", NOW - 500, NOW - 300, None, NOW - 300)],
    )
    conn.executemany(
        "insert into task_state_history values(?,?,?)",
        [("t1", "READY", NOW - 600), ("t1", "DONE", NOW - 100),
         ("t2", "READY", NOW - 300), ("t2", "DONE", NOW - 50)],
    )
    conn.executemany(
        "insert into lease_history values(?,?,?)",
        [("t1", "ACQUIRE", NOW - 500), ("t2", "ACQUIRE", NOW - 250),
         ("t2", "ACQUIRE", NOW - 200)],
    )
    conn.executemany(
        "insert into brain_task_leases values(?,?,?)",
        [("t1", "worker/a", NOW + 600), ("t2", "worker/b", NOW - 10)],
    )
    conn.executemany("insert into regressions values(?)",
                     [("OPEN",), ("OPEN",), ("CLOSED",)])
    return conn


class TestClassification(unittest.TestCase):
    def test_game_vs_infra(self):
        cfg = fm.load_config()
        self.assertEqual(fm.classify_scope("game/x.py", cfg), "game")
        self.assertEqual(fm.classify_scope("ops/logres-control-plane/bin/x", cfg),
                         "infra")
        self.assertEqual(fm.classify_scope("random/thing", cfg), "unknown")


class TestFormulas(unittest.TestCase):
    def setUp(self):
        self.conn = seeded_conn()
        self.cfg = fm.load_config()

    def test_integrations_split_by_domain(self):
        m = fm.m_integrations(self.conn, self.cfg, NOW)
        self.assertEqual(m["status"], "ok")
        self.assertEqual(m["value"]["hour"], {"game": 1, "infra": 0, "unknown": 0})
        self.assertEqual(m["value"]["day"]["game"], 1)
        self.assertEqual(m["value"]["day"]["infra"], 1)

    def test_ready_to_lease_latency(self):
        m = fm.m_ready_to_lease(self.conn, self.cfg, NOW)
        self.assertEqual(m["status"], "ok")
        # t1: 100s, t2: 50s -> sorted [50,100]
        self.assertEqual(m["value"]["median"], 100)
        self.assertEqual(m["value"]["samples"], 2)

    def test_work_latency(self):
        m = fm.m_work_latency(self.conn, self.cfg, NOW)
        self.assertEqual(m["status"], "ok")
        # t1: 400s, t2: 150s
        self.assertEqual(m["value"]["samples"], 2)
        self.assertEqual(m["value"]["median"], 400)

    def test_verifier_queue_latency(self):
        m = fm.m_verifier_queue(self.conn, self.cfg, NOW)
        self.assertEqual(m["status"], "ok")
        # pend: 200s; integrated rows lack verified_at? they have it
        self.assertGreaterEqual(m["value"]["samples"], 1)

    def test_retries(self):
        m = fm.m_retries(self.conn, self.cfg, NOW)
        self.assertEqual(m["value"]["tasks_leased"], 2)
        self.assertEqual(m["value"]["retried_tasks"], 1)

    def test_rework(self):
        m = fm.m_rework(self.conn, self.cfg, NOW)
        self.assertEqual(m["status"], "ok")
        self.assertEqual(m["value"]["regressions_open"], 2)
        self.assertEqual(m["value"]["done_tasks"], 2)
        self.assertEqual(m["value"]["rework_rate"], 0)

    def test_utilization(self):
        m = fm.m_utilization(self.conn, self.cfg, NOW)
        self.assertEqual(m["value"]["active_workers"], 1)
        self.assertAlmostEqual(m["value"]["utilization"], 0.25)

    def test_verifier_saturation(self):
        m = fm.m_verifier_saturation(self.conn, self.cfg, NOW)
        self.assertEqual(m["value"]["backlog"], 1)
        self.assertAlmostEqual(m["value"]["saturation"], 1 / 8)


class TestUnavailable(unittest.TestCase):
    def test_missing_tables(self):
        conn = make_conn()
        snap = fm.collect_metrics(conn, fm.load_config(), now=NOW,
                                  run_cmd=lambda a: None)
        for name in ("ready_to_lease_latency", "work_latency",
                     "verifier_queue_latency", "retries_recoveries",
                     "verified_integrations", "verifier_saturation",
                     "worker_utilization", "branch_age",
                     "devin_model_quota", "critical_path_completion"):
            self.assertEqual(snap["metrics"][name]["status"], "unavailable", name)
            self.assertIsNone(snap["metrics"][name]["value"])
            self.assertTrue(snap["metrics"][name]["reason"])
        self.assertTrue(snap["unavailable"])

    def test_devin_nonzero_exit(self):
        class R:
            returncode = 1
            stdout = ""
        m = fm.m_devin(None, fm.load_config(), NOW, run_cmd=lambda a: R())
        self.assertEqual(m["status"], "unavailable")

    def test_devin_ok(self):
        class R:
            returncode = 0
            stdout = '{"families":[{"variants":[{"model_uid":"swe-2-max","cost_tier":"Free"}]}]}'
        m = fm.m_devin(None, fm.load_config(), NOW, run_cmd=lambda a: R())
        self.assertEqual(m["status"], "ok")
        self.assertEqual(m["value"]["free_variants"], 1)


class TestBaseline(unittest.TestCase):
    def _snap(self, v):
        return {"metrics": {"m": {"status": "ok", "value": {"x": v}},
                            "n": {"status": "ok", "value": {"x": 10}}}}

    def test_stable_and_changed(self):
        cur = self._snap(100)
        base = self._snap(100)
        res = fm.compare_baseline(cur, base, 0.05)
        self.assertEqual(res["m"], "stable")
        base2 = self._snap(200)
        res2 = fm.compare_baseline(cur, base2, 0.05)
        self.assertEqual(res2["m"], "changed")
        self.assertEqual(fm.compare_baseline(cur, None)["m"], "no_baseline")


class TestNoSubjectiveScoring(unittest.TestCase):
    def test_no_score_grade_fields(self):
        conn = seeded_conn()
        snap = fm.collect_metrics(conn, fm.load_config(), now=NOW,
                                  run_cmd=lambda a: None)
        blob = str(snap).lower()
        for banned in ("self_score", "confidence_score", "'grade'", "subjective"):
            self.assertNotIn(banned, blob)

    def test_timeseries_lines(self):
        conn = seeded_conn()
        snap = fm.collect_metrics(conn, fm.load_config(), now=NOW,
                                  run_cmd=lambda a: None)
        lines = fm.timeseries_lines(snap)
        self.assertEqual(len(lines), len(snap["metrics"]))
        import json
        rec = json.loads(lines[0])
        self.assertIn("ts", rec)
        self.assertIn("metric", rec)
        self.assertIn("value", rec)


if __name__ == "__main__":
    unittest.main()
