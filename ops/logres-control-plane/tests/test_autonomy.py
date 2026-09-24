import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
LIB_DIR = CONTROL_ROOT / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db, seed_task
from logres_autonomy import (
    ResourceState,
    actionable_open_regressions,
    autonomy_apply_authorized,
    autonomy_decision,
    dynamic_batch_limit,
    integration_backlog,
    load_state,
    parse_route_failures,
    rank_ready_tasks,
    record_failure,
    record_success,
)


def config(enabled=True):
    return {
        "autonomy": {
            "enabled": enabled,
            "auto_preflight_enabled": enabled,
            "auto_apply_preflight_enabled": enabled,
            "max_preflight_batch": 4,
            "circuit_breaker_failures": 2,
            "min_free_memory_gib": 12.0,
            "min_free_disk_gib": 30.0,
            "max_load_per_cpu": 1.25,
        }
    }


class AutonomyTests(unittest.TestCase):
    def test_fail_closed_default_blocks_automation(self):
        resources = ResourceState(
            cpus=8,
            load1=0.2,
            memory_available_gib=64,
            disk_free_gib=120,
        )
        decision = autonomy_decision(
            {},
            {"tripped": False},
            resources,
            doctor_ok=True,
            route_failures=0,
            open_regressions=0,
            ready_count=3,
        )
        self.assertFalse(decision.allowed)
        self.assertIn("autonomy disabled", decision.reasons)

    def test_clean_underloaded_machine_uses_full_configured_batch(self):
        resources = ResourceState(
            cpus=16,
            load1=1.0,
            memory_available_gib=64,
            disk_free_gib=140,
        )
        decision = autonomy_decision(
            config(),
            {"tripped": False},
            resources,
            doctor_ok=True,
            route_failures=0,
            open_regressions=0,
            ready_count=6,
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(4, decision.batch_limit)

    def test_open_regression_is_telemetry_by_default_not_a_repair_deadlock(self):
        resources = ResourceState(
            cpus=8,
            load1=0.2,
            memory_available_gib=64,
            disk_free_gib=120,
        )
        decision = autonomy_decision(
            config(),
            {"tripped": False},
            resources,
            doctor_ok=True,
            route_failures=0,
            open_regressions=2,
            ready_count=1,
        )
        self.assertTrue(decision.allowed)

        strict = config()
        strict["autonomy"]["block_on_open_regressions"] = True
        decision = autonomy_decision(
            strict,
            {"tripped": False},
            resources,
            doctor_ok=True,
            route_failures=0,
            open_regressions=2,
            ready_count=1,
        )
        self.assertFalse(decision.allowed)
        self.assertIn("open regressions=2", decision.reasons)

    def test_resource_pressure_fails_closed_and_reduces_batch(self):
        resources = ResourceState(
            cpus=8,
            load1=20.0,
            memory_available_gib=6,
            disk_free_gib=20,
        )
        decision = autonomy_decision(
            config(),
            {"tripped": False},
            resources,
            doctor_ok=True,
            route_failures=0,
            open_regressions=0,
            ready_count=4,
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(1, decision.batch_limit)
        self.assertTrue(any("memory" in x for x in decision.reasons))
        self.assertTrue(any("disk" in x for x in decision.reasons))
        self.assertTrue(any("load/cpu" in x for x in decision.reasons))

    def test_apply_authorization_requires_policy_capability_and_exact_preflight(self):
        cfg = config()
        env = {
            "LOGRES_AUTONOMY_APPLY": "1",
            "LOGRES_AUTONOMY_PREFLIGHT_ID": "42",
        }
        self.assertTrue(autonomy_apply_authorized(cfg, env, 42))
        self.assertFalse(autonomy_apply_authorized(cfg, env, 43))
        self.assertFalse(
            autonomy_apply_authorized(
                config(enabled=False),
                env,
                42,
            )
        )
        self.assertFalse(
            autonomy_apply_authorized(
                cfg,
                {"LOGRES_AUTONOMY_APPLY": "1"},
                42,
            )
        )

    def test_circuit_breaker_trips_and_success_resets(self):
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "state.json"
            first = record_failure(state_path, "one", 2)
            self.assertFalse(first["tripped"])
            second = record_failure(state_path, "two", 2)
            self.assertTrue(second["tripped"])
            self.assertEqual(2, second["consecutive_failures"])

            reset = record_success(state_path, preflight_id=9)
            self.assertFalse(reset["tripped"])
            self.assertEqual(0, reset["consecutive_failures"])
            self.assertEqual(9, reset["last_applied_preflight"])
            self.assertEqual(reset, load_state(state_path))

    def test_critical_path_ranking_beats_simple_task_id_order(self):
        conn = make_test_db()
        seed_task(conn, task_id="B-SHORT", priority=0)
        seed_task(conn, task_id="A-UNLOCK", priority=0)
        seed_task(
            conn,
            task_id="Z-DOWNSTREAM",
            priority=0,
            status="BLOCKED_DEP",
        )
        conn.execute(
            "update task_metadata set expected_minutes=10 where task_id='B-SHORT'"
        )
        conn.execute(
            "update task_metadata set expected_minutes=20 where task_id='A-UNLOCK'"
        )
        conn.execute(
            "update task_metadata set expected_minutes=120 where task_id='Z-DOWNSTREAM'"
        )
        conn.execute(
            "insert into task_dependencies(task_id,depends_on,kind,rationale) "
            "values('Z-DOWNSTREAM','A-UNLOCK','hard','critical path')"
        )
        conn.commit()

        ranked = rank_ready_tasks(conn, limit=2)

        self.assertEqual("A-UNLOCK", ranked[0])
        self.assertEqual("B-SHORT", ranked[1])

    def test_backlog_and_regression_counts_are_actionable_only(self):
        conn = make_test_db()
        conn.executescript(
            """
            create table regressions(
              id integer primary key,
              status text not null
            );
            insert into regressions(id,status) values(1,'OPEN');
            insert into regressions(id,status) values(2,'RESOLVED');
            insert into integration_queue(
              task_id,sha,branch,status,verification_mode,queued_at,updated_at,note
            ) values(
              'T1','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','worker/t1',
              'READY_FOR_PREFLIGHT','fast','now','now',''
            );
            insert into integration_queue(
              task_id,sha,branch,status,verification_mode,queued_at,updated_at,note
            ) values(
              'T2','bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb','worker/t2',
              'INTEGRATED','full-e2e','now','now',''
            );
            """
        )
        self.assertEqual(1, actionable_open_regressions(conn))
        self.assertEqual(1, integration_backlog(conn))

    def test_parse_route_failures(self):
        self.assertEqual(
            3,
            parse_route_failures(
                "ROUTER cursor=9 lag=0 active=1 failed=3"
            ),
        )
        self.assertEqual(0, parse_route_failures("healthy"))


if __name__ == "__main__":
    unittest.main()
