import sqlite3
import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db, seed_task
from logres_knowledge import refresh_graph
from logres_optimizer import (
    engine_success_rate,
    rank_task_ids,
    record_swarm_observations,
    score_ready_tasks,
)
from logres_route_store import ensure_route_schema
from logres_swarm import ensure_schema as ensure_swarm_schema


def add_discovery_table(conn):
    conn.execute(
        """create table brain_discoveries(
             id integer primary key,
             ts text not null,
             author text not null,
             task_id text,
             confidence text not null,
             subject text not null,
             summary text not null,
             artifact_path text,
             artifact_sha256 text,
             status text not null default 'OPEN'
           )"""
    )
    conn.commit()


class OptimizerTests(unittest.TestCase):
    def test_critical_path_unlocker_beats_short_leaf_inside_priority_band(self):
        conn = make_test_db()
        add_discovery_table(conn)
        seed_task(conn, task_id="A-UNLOCK", priority=0, work_type="research")
        seed_task(conn, task_id="B-LEAF", priority=0, work_type="research")
        seed_task(
            conn,
            task_id="Z-CHILD",
            priority=0,
            work_type="research",
            status="BLOCKED_DEP",
        )
        conn.execute(
            "update task_metadata set expected_minutes=20 where task_id='A-UNLOCK'"
        )
        conn.execute(
            "update task_metadata set expected_minutes=5 where task_id='B-LEAF'"
        )
        conn.execute(
            "update task_metadata set expected_minutes=150 where task_id='Z-CHILD'"
        )
        conn.execute(
            """insert into task_dependencies(task_id,depends_on,kind,rationale)
               values('Z-CHILD','A-UNLOCK','hard','critical')"""
        )
        conn.commit()
        refresh_graph(conn)

        ranked = rank_task_ids(
            conn,
            limit=2,
            work_type_filter={"research"},
        )

        self.assertEqual("A-UNLOCK", ranked[0])
        self.assertEqual("B-LEAF", ranked[1])

    def test_information_gap_prioritizes_under_resolved_research(self):
        conn = make_test_db()
        add_discovery_table(conn)
        seed_task(conn, task_id="A-GAP", priority=0, work_type="research")
        seed_task(conn, task_id="B-KNOWN", priority=0, work_type="research")
        conn.execute(
            """insert into brain_discoveries(
                 id,ts,author,task_id,confidence,subject,summary,status
               ) values(1,'now','finder','B-KNOWN','CONFIRMED',
                        'confirmed','Global proof','OPEN')"""
        )
        conn.commit()
        refresh_graph(conn)

        ranked = score_ready_tasks(
            conn,
            work_type_filter={"research"},
        )

        self.assertEqual("A-GAP", ranked[0].task_id)
        self.assertGreater(
            ranked[0].knowledge_gap,
            ranked[1].knowledge_gap,
        )

    def test_engine_learning_ignores_infra_failures_and_values_bounded_research(self):
        conn = make_test_db()
        add_discovery_table(conn)
        refresh_graph(conn)
        conn.execute(
            """insert into optimizer_observations(
                 task_id,engine,work_type,outcome
               ) values('I1','research','research','INFRA_FAILURE')"""
        )
        conn.execute(
            """insert into optimizer_observations(
                 task_id,engine,work_type,outcome
               ) values('R1','research','research','BLOCKED')"""
        )
        conn.execute(
            """insert into optimizer_observations(
                 task_id,engine,work_type,outcome
               ) values('R2','research','research','DONE')"""
        )
        conn.commit()

        rate = engine_success_rate(
            conn,
            engine="research",
            work_type="research",
        )

        self.assertAlmostEqual(0.825, rate, places=3)

    def test_swarm_observations_are_idempotent(self):
        conn = make_test_db()
        add_discovery_table(conn)
        ensure_route_schema(conn)
        ensure_swarm_schema(conn)
        seed_task(
            conn,
            task_id="R1",
            work_type="research",
            status="DONE",
        )
        conn.execute(
            """insert into swarm_jobs(
                 task_id,worker_id,engine,state,pid,started_at,updated_at,finished_at
               ) values('R1','auto-research-1','research','DONE',123,
                        '2026-09-24 08:00:00','2026-09-24 08:01:00',
                        '2026-09-24 08:01:00')"""
        )
        conn.execute(
            """insert into api_usage(
                 route_job_id,ai_run_id,task_id,artifact_sha,model,
                 input_tokens,cached_input_tokens,output_tokens,reasoning_tokens,
                 estimated_cost_usd,status,created_at
               ) values(null,null,'R1',?,'gpt-5.6-luna',
                        100,0,50,0,0.001,'PASS',datetime('now'))""",
            ("a" * 64,),
        )
        conn.commit()

        self.assertEqual(1, record_swarm_observations(conn))
        self.assertEqual(0, record_swarm_observations(conn))
        row = conn.execute(
            """select outcome,duration_seconds,estimated_cost_usd,source_job_id
                 from optimizer_observations"""
        ).fetchone()
        self.assertEqual("DONE", row[0])
        self.assertAlmostEqual(60.0, row[1], places=1)
        self.assertAlmostEqual(0.001, row[2], places=6)
        self.assertIsNotNone(row[3])


if __name__ == "__main__":
    unittest.main()
