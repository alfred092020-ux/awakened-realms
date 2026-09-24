import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from logres_engine_reconcile import apply, plan
from logres_route_store import VALID_TRANSITIONS


class ReconcileTests(unittest.TestCase):
    def db(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            create table tasks(
              id text primary key,
              status text
            );
            create table integration_queue(
              task_id text,
              sha text,
              status text
            );
            create table copilot_jobs(
              id integer primary key,
              route_job_id integer,
              task_id text,
              state text,
              branch text,
              candidate_sha text,
              updated_at text
            );
            create table route_jobs(
              id integer primary key,
              task_id text,
              state text,
              external_ref text,
              last_error text,
              updated_at text
            );
            create table swarm_jobs(
              id integer primary key,
              task_id text,
              state text,
              pid integer,
              artifact_path text,
              last_error text,
              updated_at text,
              finished_at text
            );
            create table brain_task_leases(
              task_id text primary key,
              chat_id text,
              branch text,
              lease_until_epoch real
            );
            """
        )
        return conn

    def add_copilot(
        self,
        conn,
        *,
        task_status="DONE",
        state="PR_READY",
        candidate="a" * 40,
        route_state="ACTIVE",
    ):
        conn.execute(
            "insert into tasks values('T',?)",
            (task_status,),
        )
        conn.execute(
            "insert into route_jobs values(10,'T',?,null,null,'now')",
            (route_state,),
        )
        conn.execute(
            """insert into copilot_jobs
               values(1,10,'T',?,'copilot/t',?,'now')""",
            (state, candidate),
        )

    def test_done_task_preserves_unintegrated_candidate(self):
        for state in ("PR_READY", "VERIFYING", "QUEUED"):
            with self.subTest(state=state):
                conn = self.db()
                self.add_copilot(
                    conn,
                    state=state,
                    route_state=state,
                )
                conn.execute(
                    """insert into integration_queue
                       values('T',?,'READY_FOR_PREFLIGHT')""",
                    ("a" * 40,),
                )

                self.assertEqual([], plan(conn))
                self.assertEqual([], apply(conn))
                self.assertEqual(
                    state,
                    conn.execute(
                        "select state from copilot_jobs where id=1"
                    ).fetchone()[0],
                )
                self.assertEqual(
                    state,
                    conn.execute(
                        "select state from route_jobs where id=10"
                    ).fetchone()[0],
                )

    def test_done_task_preserves_preassignment_without_candidate(self):
        conn = self.db()
        self.add_copilot(
            conn,
            state="ASSIGNING",
            candidate=None,
            route_state="ASSIGNING",
        )

        self.assertEqual([], plan(conn))
        apply(conn)

        self.assertEqual(
            "ASSIGNING",
            conn.execute(
                "select state from copilot_jobs where id=1"
            ).fetchone()[0],
        )
        self.assertEqual(
            "ASSIGNING",
            conn.execute(
                "select state from route_jobs where id=10"
            ).fetchone()[0],
        )

    def test_integrated_candidate_closes_copilot_and_route(self):
        conn = self.db()
        self.add_copilot(
            conn,
            state="QUEUED",
            route_state="QUEUED",
        )
        conn.execute(
            """insert into integration_queue
               values('T',?,'INTEGRATED')""",
            ("a" * 40,),
        )

        actions = apply(conn)

        self.assertEqual(
            "SUPERSEDED",
            conn.execute(
                "select state from copilot_jobs where id=1"
            ).fetchone()[0],
        )
        self.assertEqual(
            "SUPERSEDED",
            conn.execute(
                "select state from route_jobs where id=10"
            ).fetchone()[0],
        )
        self.assertEqual(
            {"candidate_resolved"},
            {
                item["reason"]
                for item in actions
                if item["engine"] in {"copilot", "route"}
            },
        )
        self.assertEqual([], apply(conn))

    def test_explicit_candidate_supersession_closes_pending_state(self):
        conn = self.db()
        self.add_copilot(
            conn,
            state="VERIFYING",
            route_state="VERIFYING",
        )
        conn.execute(
            """insert into integration_queue
               values('T',?,'SUPERSEDED')""",
            ("a" * 40,),
        )

        apply(conn)

        self.assertEqual(
            "SUPERSEDED",
            conn.execute(
                "select state from copilot_jobs where id=1"
            ).fetchone()[0],
        )
        self.assertEqual(
            "SUPERSEDED",
            conn.execute(
                "select state from route_jobs where id=10"
            ).fetchone()[0],
        )

    def test_preassignment_closes_after_task_integration_is_proven(self):
        conn = self.db()
        self.add_copilot(
            conn,
            state="ASSIGNING",
            candidate=None,
            route_state="ASSIGNING",
        )
        conn.execute(
            """insert into integration_queue
               values('T',?,'INTEGRATED')""",
            ("b" * 40,),
        )

        actions = apply(conn)

        self.assertEqual(
            "SUPERSEDED",
            conn.execute(
                "select state from copilot_jobs where id=1"
            ).fetchone()[0],
        )
        self.assertEqual(
            "SUPERSEDED",
            conn.execute(
                "select state from route_jobs where id=10"
            ).fetchone()[0],
        )
        self.assertEqual(
            {"task_integration_resolved"},
            {
                item["reason"]
                for item in actions
                if item["engine"] in {"copilot", "route"}
            },
        )

    def test_explicitly_obsolete_task_closes_without_queue_proof(self):
        for task_status in (
            "SUPERSEDED",
            "CANCELLED",
            "BLOCKED_EVIDENCE",
        ):
            with self.subTest(task_status=task_status):
                conn = self.db()
                self.add_copilot(
                    conn,
                    task_status=task_status,
                    state="ACTIVE",
                    candidate=None,
                    route_state="ROUTED",
                )
                apply(conn)
                self.assertEqual(
                    "SUPERSEDED",
                    conn.execute(
                        "select state from copilot_jobs where id=1"
                    ).fetchone()[0],
                )
                self.assertEqual(
                    "SUPERSEDED",
                    conn.execute(
                        "select state from route_jobs where id=10"
                    ).fetchone()[0],
                )

    def test_active_task_is_untouched(self):
        conn = self.db()
        self.add_copilot(
            conn,
            task_status="ACTIVE",
            state="PR_READY",
            route_state="ACTIVE",
        )
        self.assertEqual([], plan(conn))

    def test_terminal_lease_is_released(self):
        conn = self.db()
        conn.execute(
            "insert into tasks values('T','SUPERSEDED')"
        )
        conn.execute(
            "insert into brain_task_leases values('T','w','b',999)"
        )
        apply(conn)
        self.assertEqual(
            0,
            conn.execute(
                "select count(*) from brain_task_leases"
            ).fetchone()[0],
        )

    def test_route_store_exposes_legal_terminal_paths(self):
        for state in (
            "ASSIGNING",
            "ROUTED",
            "ACTIVE",
            "PR_READY",
            "VERIFYING",
            "QUEUED",
        ):
            with self.subTest(state=state):
                self.assertIn(
                    "SUPERSEDED",
                    VALID_TRANSITIONS[state],
                )


if __name__ == "__main__":
    unittest.main()
