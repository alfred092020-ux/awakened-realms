import os
import sqlite3
import sys
import time
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db, seed_task
from logres_route_store import ensure_route_schema
from logres_swarm import (
    classify_engine,
    create_job,
    ensure_schema,
    prior_failures,
    reconcile_jobs,
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


if __name__ == "__main__":
    unittest.main()
