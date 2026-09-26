import json
import os
import sqlite3
import sys
import time
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
LIB_DIR = CONTROL_ROOT / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db, seed_task
from logres_route_store import ensure_route_schema
import logres_swarm
from logres_swarm import (
    ACTIVE_COPILOT_STATES,
    available_devin_worker_ids,
    classify_engine,
    create_job,
    devin_worker_ids,
    ensure_schema,
    prior_failures,
    ready_tasks,
    mark_job_running,
    reconcile_jobs,
    select_implementation_tasks,
    select_research_tasks,
    swarm_capacity,
)


class SwarmTests(unittest.TestCase):
    def setUp(self):
        self.conn = make_test_db()
        self.conn.row_factory = sqlite3.Row
        ensure_route_schema(self.conn)
        ensure_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_swarm_tick_keeps_user_supervisor_alive(self):
        script = (CONTROL_ROOT / "bin" / "logres-swarm").read_text()
        self.assertIn('SUPERVISOR = str(ROOT / "bin/logres-supervisor")', script)
        self.assertIn('[SUPERVISOR, "ensure"]', script)

    def test_swarm_status_exposes_resource_broker_placement_hints(self):
        script = (CONTROL_ROOT / "bin" / "logres-swarm").read_text()
        self.assertIn(
            "from logres_resource_broker import infer_task_workload, plan_workload",
            script,
        )
        self.assertIn('"placement_hints"', script)
        self.assertIn('"selected_lane": plan.selected_lane', script)

    def test_classifies_research_and_implementation_engines(self):
        self.assertEqual("research", classify_engine({"work_type": "research"}))
        self.assertEqual("research", classify_engine({"work_type": "evidence"}))
        self.assertEqual(
            "copilot",
            classify_engine({"work_type": "implementation"}),
        )
        self.assertEqual("manual", classify_engine({"work_type": "manual"}))

    def test_capacity_counts_human_leases_and_copilot_jobs(self):
        now = time.time()
        seed_task(self.conn, task_id="R1", status="ACTIVE", work_type="research")
        self.conn.execute(
            """insert into brain_task_leases(
                 task_id,chat_id,branch,lease_until_epoch,acquired_at,
                 renewed_at,progress,note
               ) values(?,?,?,?,datetime('now'),datetime('now'),0,'')""",
            ("R1", "finder", "worker/finder-r1", now + 3600),
        )
        self.conn.execute(
            """insert into route_jobs(
                 id,dedupe_key,task_id,route_kind,state,created_at,updated_at
               ) values(1,'c1','C1','COPILOT','PR_READY',datetime('now'),datetime('now'))"""
        )
        self.conn.execute(
            """insert into copilot_jobs(
                 route_job_id,task_id,branch,base_sha,candidate_sha,state,
                 created_at,updated_at
               ) values(1,'C1','copilot/c1',?,?,'PR_READY',datetime('now'),datetime('now'))""",
            ("a" * 40, "b" * 40),
        )
        self.conn.commit()

        cap = swarm_capacity(
            self.conn,
            {"swarm": {"max_workers": 6}},
        )

        self.assertEqual(1, cap.active_leases)
        self.assertEqual(1, cap.active_copilot)
        self.assertEqual(4, cap.free_slots)

    def test_current_copilot_lifecycle_vocabulary_is_live_capacity(self):
        self.assertEqual(
            {"ASSIGNING", "ACTIVE", "PR_READY", "VERIFYING"},
            set(ACTIVE_COPILOT_STATES),
        )

    def test_capacity_reaches_zero_with_four_leases_and_two_live_copilot_jobs(self):
        now = time.time()
        for index in range(4):
            task_id = f"L{index + 1}"
            seed_task(
                self.conn,
                task_id=task_id,
                status="ACTIVE",
                work_type="manual",
            )
            self.conn.execute(
                """insert into brain_task_leases(
                     task_id,chat_id,branch,lease_until_epoch,acquired_at,
                     renewed_at,progress,note
                   ) values(?,?,?,?,datetime('now'),datetime('now'),0,'')""",
                (
                    task_id,
                    f"worker-{index + 1}",
                    f"worker/{task_id.lower()}",
                    now + 3600,
                ),
            )

        for route_id, state in ((101, "ASSIGNING"), (102, "VERIFYING")):
            self.conn.execute(
                """insert into copilot_jobs(
                     route_job_id,task_id,branch,base_sha,candidate_sha,state,
                     created_at,updated_at
                   ) values(?,?,?,?,?,?,datetime('now'),datetime('now'))""",
                (
                    route_id,
                    f"C{route_id}",
                    f"copilot/c{route_id}",
                    "a" * 40,
                    None,
                    state,
                ),
            )
        self.conn.commit()

        cap = swarm_capacity(
            self.conn,
            {"swarm": {"max_workers": 6}},
        )

        self.assertEqual(4, cap.active_leases)
        self.assertEqual(2, cap.active_copilot)
        self.assertEqual(0, cap.free_slots)

    def test_obsolete_copilot_states_do_not_consume_capacity(self):
        for route_id, state in ((201, "ISSUE_CREATED"), (202, "ASSIGNED")):
            self.conn.execute(
                """insert into copilot_jobs(
                     route_job_id,task_id,branch,base_sha,candidate_sha,state,
                     created_at,updated_at
                   ) values(?,?,?,?,?,?,datetime('now'),datetime('now'))""",
                (
                    route_id,
                    f"OLD{route_id}",
                    f"copilot/old{route_id}",
                    "a" * 40,
                    None,
                    state,
                ),
            )
        self.conn.commit()

        cap = swarm_capacity(
            self.conn,
            {"swarm": {"max_workers": 6}},
        )

        self.assertEqual(0, cap.active_copilot)
        self.assertEqual(6, cap.free_slots)

    def test_ready_task_owned_by_live_copilot_is_not_dispatchable(self):
        seed_task(
            self.conn,
            task_id="COPILOT-OWNED",
            status="READY",
            work_type="implementation",
        )
        seed_task(
            self.conn,
            task_id="NORMAL",
            status="READY",
            work_type="implementation",
        )
        self.conn.execute(
            """insert into copilot_jobs(
                 route_job_id,task_id,branch,base_sha,candidate_sha,state,
                 created_at,updated_at
               ) values(301,'COPILOT-OWNED','copilot/owned',?,?,'ACTIVE',
                        datetime('now'),datetime('now'))""",
            ("a" * 40, None),
        )
        self.conn.commit()

        ids = [task["id"] for task in ready_tasks(self.conn)]

        self.assertNotIn("COPILOT-OWNED", ids)
        self.assertIn("NORMAL", ids)

    def test_select_research_respects_concurrency_key_and_claim_conflict(self):
        for task_id in ("R1", "R2", "R3"):
            seed_task(
                self.conn,
                task_id=task_id,
                status="READY",
                work_type="research",
            )
        self.conn.execute(
            "update task_metadata set concurrency_key='same' where task_id in ('R1','R2')"
        )
        self.conn.execute(
            "insert into task_scopes(task_id,path_prefix) values('R1','evidence/a')"
        )
        self.conn.execute(
            "insert into task_scopes(task_id,path_prefix) values('R2','evidence/b')"
        )
        self.conn.execute(
            "insert into task_scopes(task_id,path_prefix) values('R3','evidence/c')"
        )
        self.conn.execute(
            """insert into claims(path_prefix,task_id,owner,branch,created_at,note)
               values('evidence/c','OTHER','x','worker/x',datetime('now'),'')"""
        )
        self.conn.commit()

        selected = select_research_tasks(self.conn, 3)
        ids = [row["id"] for row in selected]

        self.assertEqual(1, len(ids))
        self.assertIn(ids[0], {"R1", "R2"})

    def test_infrastructure_failures_do_not_consume_research_retry_budget(self):
        seed_task(
            self.conn,
            task_id="R1",
            status="READY",
            work_type="research",
        )
        self.conn.execute(
            """insert into swarm_jobs(
                 task_id,worker_id,engine,state,pid,artifact_path,last_error
               ) values('R1','auto-research-1','research','FAILED',101,null,
                        'missing credential')"""
        )
        self.conn.execute(
            """insert into swarm_jobs(
                 task_id,worker_id,engine,state,pid,artifact_path,last_error
               ) values('R1','auto-research-2','research','FAILED',102,
                        '/tmp/semantic.json','semantic failure')"""
        )
        self.conn.commit()

        self.assertEqual(1, prior_failures(self.conn, "R1"))

    def test_dead_swarm_process_is_marked_failed(self):
        seed_task(
            self.conn,
            task_id="R1",
            status="ACTIVE",
            work_type="research",
        )
        job_id = create_job(self.conn, "R1", "auto-research-1", "research")
        self.conn.execute(
            "update swarm_jobs set state='RUNNING',pid=? where id=?",
            (99999999, job_id),
        )
        self.conn.commit()

        stale = reconcile_jobs(self.conn)

        self.assertEqual([job_id], stale)
        row = self.conn.execute(
            "select state,last_error from swarm_jobs where id=?",
            (job_id,),
        ).fetchone()
        self.assertEqual("FAILED", row["state"])
        self.assertIn("exited", row["last_error"])


    def test_patch_worker_is_reported_without_double_counting_capacity(self):
        now = time.time()
        seed_task(
            self.conn,
            task_id="I1",
            status="ACTIVE",
            work_type="implementation",
        )
        self.conn.execute(
            """insert into brain_task_leases(
                 task_id,chat_id,branch,lease_until_epoch,acquired_at,
                 renewed_at,progress,note
               ) values(?,?,?,?,datetime('now'),datetime('now'),0,'')""",
            ("I1", "auto-patch-1", "worker/auto-patch-1-i1", now + 3600),
        )
        job_id = create_job(self.conn, "I1", "auto-patch-1", "openai-patch")
        self.conn.execute(
            "update swarm_jobs set state='RUNNING',pid=? where id=?",
            (os.getpid(), job_id),
        )
        self.conn.commit()

        cap = swarm_capacity(
            self.conn,
            {"swarm": {"max_workers": 6}},
        )

        self.assertEqual(1, cap.active_leases)
        self.assertEqual(1, cap.active_patch)
        self.assertEqual(0, cap.active_research)
        self.assertEqual(5, cap.free_slots)

    def test_select_implementation_requires_scopes_and_avoids_claims(self):
        for task_id in ("I1", "I2", "I3"):
            seed_task(
                self.conn,
                task_id=task_id,
                status="READY",
                work_type="implementation",
            )
        self.conn.execute(
            "insert into task_scopes(task_id,path_prefix) values('I1','src/a')"
        )
        self.conn.execute(
            "insert into task_scopes(task_id,path_prefix) values('I3','src/c')"
        )
        self.conn.execute(
            """insert into claims(path_prefix,task_id,owner,branch,created_at,note)
               values('src/c','OTHER','x','worker/x',datetime('now'),'')"""
        )
        self.conn.commit()

        selected = select_implementation_tasks(self.conn, 3)
        ids = [row["id"] for row in selected]

        self.assertEqual(["I1"], ids)
        self.assertNotIn("I2", ids)
        self.assertNotIn("I3", ids)

    def test_engine_specific_retry_budget_separates_patch_from_research(self):
        seed_task(
            self.conn,
            task_id="I1",
            status="READY",
            work_type="implementation",
        )
        self.conn.execute(
            """insert into swarm_jobs(
                 task_id,worker_id,engine,state,pid,artifact_path,last_error
               ) values('I1','auto-research-1','research','FAILED',101,
                        '/tmp/research.json','semantic failure')"""
        )
        self.conn.execute(
            """insert into swarm_jobs(
                 task_id,worker_id,engine,state,pid,artifact_path,last_error
               ) values('I1','auto-patch-1','openai-patch','FAILED',102,
                        '/tmp/patch.json','gate failure')"""
        )
        self.conn.commit()

        self.assertEqual(2, prior_failures(self.conn, "I1"))
        self.assertEqual(
            1,
            prior_failures(self.conn, "I1", engine="openai-patch"),
        )

    def test_devin_capacity_is_informational_not_double_counted(self):
        now = time.time()
        seed_task(
            self.conn,
            task_id="D1",
            status="ACTIVE",
            work_type="implementation",
        )
        self.conn.execute(
            """insert into brain_task_leases(
                 task_id,chat_id,branch,lease_until_epoch,acquired_at,
                 renewed_at,progress,note
               ) values(?,?,?,?,datetime('now'),datetime('now'),0,'')""",
            ("D1", "auto-devin-1", "worker/auto-devin-1-d1", now + 3600),
        )
        job_id = create_job(
            self.conn,
            "D1",
            "auto-devin-1",
            "devin",
            branch="worker/auto-devin-1-d1",
            model="swe-2-max",
            verification="devin-agent-artifact",
        )
        mark_job_running(
            self.conn,
            job_id,
            os.getpid(),
            session_id="harness-pid:test",
        )

        cap = swarm_capacity(self.conn, {"swarm": {"max_workers": 6}})

        self.assertEqual(1, cap.active_leases)
        self.assertEqual(1, cap.active_devin)
        self.assertEqual(5, cap.free_slots)

    def test_devin_worker_pool_honors_config_and_live_leases(self):
        cfg = {"router": {"workers": 3}}
        self.assertEqual(
            ["auto-devin-1", "auto-devin-2", "auto-devin-3"],
            devin_worker_ids(cfg),
        )
        now = time.time()
        seed_task(
            self.conn,
            task_id="D-BUSY",
            status="ACTIVE",
            work_type="implementation",
        )
        self.conn.execute(
            """insert into brain_task_leases(
                 task_id,chat_id,branch,lease_until_epoch,acquired_at,
                 renewed_at,progress,note
               ) values(?,?,?,?,datetime('now'),datetime('now'),0,'')""",
            ("D-BUSY", "auto-devin-2", "worker/d-busy", now + 3600),
        )
        self.conn.commit()

        self.assertEqual(
            ["auto-devin-1", "auto-devin-3"],
            available_devin_worker_ids(self.conn, cfg),
        )

    def test_devin_job_persists_branch_model_session_and_verification(self):
        job_id = create_job(
            self.conn,
            "D1",
            "auto-devin-1",
            "devin",
            branch="worker/d1",
            model="swe-2-max",
            verification="devin-agent-artifact",
        )
        mark_job_running(
            self.conn,
            job_id,
            os.getpid(),
            session_id="harness-pid:123",
        )
        row = self.conn.execute(
            """select engine,branch,model,session_id,verification,state,pid
                 from swarm_jobs where id=?""",
            (job_id,),
        ).fetchone()
        self.assertEqual("devin", row["engine"])
        self.assertEqual("worker/d1", row["branch"])
        self.assertEqual("swe-2-max", row["model"])
        self.assertEqual("harness-pid:123", row["session_id"])
        self.assertEqual("devin-agent-artifact", row["verification"])
        self.assertEqual("RUNNING", row["state"])
        self.assertEqual(os.getpid(), row["pid"])

    def test_isolation_certificate_gate_requires_current_head_and_runtime_sha(self):
        gate = getattr(logres_swarm, "isolation_certificate_gate", None)
        self.assertTrue(callable(gate), "missing isolation_certificate_gate")
        head = "a" * 40
        certificate = {"production_ready": True, "integration_sha": head}
        runtime = {"integration_sha": head}
        self.assertEqual((True, None), gate(certificate, head, runtime))
        self.assertEqual(
            (False, "isolation_certificate_stale"),
            gate({**certificate, "integration_sha": "b" * 40}, head, runtime),
        )
        self.assertEqual(
            (False, "isolation_runtime_stale"),
            gate(certificate, head, {"integration_sha": "c" * 40}),
        )
        self.assertEqual(
            (False, "isolation_certificate_stale"),
            gate({"production_ready": True}, head, runtime),
        )
        self.assertEqual(
            (False, "isolation_not_certified"),
            gate({"production_ready": False, "integration_sha": head}, head, runtime),
        )

    def test_swarm_script_enforces_certificate_sha_freshness(self):
        script = (CONTROL_ROOT / "bin" / "logres-swarm").read_text()
        for needle in (
            "isolation_certificate_gate",
            "runtime-deployment.json",
            '"rev-parse", "HEAD"',
            'result["blocked"] = certificate_blocker',
        ):
            self.assertIn(needle, script)

    def test_swarm_script_has_fail_closed_devin_lane(self):
        script = (CONTROL_ROOT / "bin" / "logres-swarm").read_text()
        for needle in (
            'DEVIN_AGENT = str(ROOT / "bin/logres-devin-agent")',
            'DEVIN_ISOLATE = str(ROOT / "bin/logres-devin-isolate")',
            'NEXUS = str(ROOT / "bin/logres-nexus")',
            "production-certified.json",
            '"isolation_not_certified"',
            "devin_models_report",
            "select_model(report, requested_model, allow_paid=False)",
            '"prepare"',
            '"preflight"',
            'nexus_logres_devin_network_provision',
            'nexus_logres_devin_network_teardown',
            'nexus_logres_devin_transient_start',
            'nexus_logres_devin_transient_stop',
            '"permissionMode": permission_mode',
            'session_id=f"systemd:{unit}"',
        ):
            self.assertIn(needle, script)
        self.assertNotIn('"--allow-paid"', script)
        self.assertNotIn('DEVIN_ISOLATE,\n                "start"', script)
        self.assertNotIn('sudo -n', script)

    def test_swarm_stale_devin_cleanup_uses_typed_stop_then_network_teardown(self):
        script = (CONTROL_ROOT / "bin" / "logres-swarm").read_text()
        stop = script.index('nexus_logres_devin_transient_stop')
        teardown = script.index('nexus_logres_devin_network_teardown')
        self.assertLess(stop, teardown)
        self.assertIn('cleanup_devin_isolation', script)

    def test_devin_worker_config_is_conservative(self):
        cfg = json.loads(
            (CONTROL_ROOT / "config" / "devin_workers.json").read_text()
        )
        router = cfg["router"]
        self.assertTrue(router["enabled"])
        self.assertEqual(2, router["workers"])
        self.assertEqual(2, router["max_active"])
        self.assertEqual("swe-2-max", router["model"])
        self.assertEqual("smart", router["permission_mode"])
        self.assertEqual("unattended", router["execution_mode"])
        self.assertTrue(router["sandbox"])
        self.assertFalse(router["allow_paid"])
        self.assertTrue(router["require_production_certificate"])

    def test_swarm_script_has_bounded_patch_lane(self):
        script = (CONTROL_ROOT / "bin" / "logres-swarm").read_text()
        self.assertIn('PATCH_AGENT = str(ROOT / "bin/logres-patch-agent")', script)
        self.assertIn('WORKER_START = str(ROOT / "bin/logres-worker-start")', script)
        self.assertIn("select_implementation_tasks", script)
        self.assertIn('"/usr/bin/timeout"', script)
        self.assertIn('"openai-patch"', script)

if __name__ == "__main__":
    unittest.main()
