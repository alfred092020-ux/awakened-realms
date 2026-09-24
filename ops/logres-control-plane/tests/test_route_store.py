import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db
from logres_route_store import (
    RouteSpec,
    StateConflict,
    append_decision,
    claim_route,
    ensure_route_schema,
    find_active_child,
    transition_route,
)


class RouteStoreTests(unittest.TestCase):
    def test_claim_route_is_idempotent_for_dedupe_key(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        first = claim_route(
            conn,
            RouteSpec(dedupe_key="e:10:ai", route_kind="AI", source_event_id=10),
        )
        second = claim_route(
            conn,
            RouteSpec(dedupe_key="e:10:ai", route_kind="AI", source_event_id=10),
        )
        self.assertEqual(first.id, second.id)
        self.assertEqual(
            1, conn.execute("select count(*) from route_jobs").fetchone()[0]
        )

    def test_compare_and_swap_transition_rejects_stale_state(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        job = claim_route(conn, RouteSpec(dedupe_key="x", route_kind="AI"))
        moved = transition_route(conn, job.id, "NEW", "ROUTED", task_id="T1")
        self.assertEqual("ROUTED", moved.state)
        with self.assertRaises(StateConflict):
            transition_route(conn, job.id, "NEW", "AI_RUNNING")

    def test_find_active_child_prevents_unresolved_loop(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        parent = claim_route(conn, RouteSpec(dedupe_key="parent", route_kind="AI"))
        child = claim_route(
            conn,
            RouteSpec(
                dedupe_key="child",
                route_kind="RESEARCH",
                parent_route_id=parent.id,
                resolution_type="UNRESOLVED",
            ),
        )
        found = find_active_child(conn, parent.id, "UNRESOLVED")
        self.assertIsNotNone(found)
        self.assertEqual(child.id, found.id)

    def test_claim_route_retries_transient_writer_lock(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "routes.sqlite"
            holder = sqlite3.connect(
                path,
                timeout=0,
                check_same_thread=False,
            )
            holder.row_factory = sqlite3.Row
            contender = sqlite3.connect(path, timeout=0)
            contender.row_factory = sqlite3.Row
            ensure_route_schema(holder)
            ensure_route_schema(contender)

            holder.execute("begin immediate")

            def release():
                time.sleep(0.08)
                holder.commit()

            thread = threading.Thread(target=release)
            thread.start()
            try:
                job = claim_route(
                    contender,
                    RouteSpec(
                        dedupe_key="lock-retry",
                        route_kind="COPILOT",
                        task_id="T1",
                    ),
                )
            finally:
                thread.join(timeout=2)
                holder.close()
                contender.close()

        self.assertEqual("NEW", job.state)
        self.assertEqual("lock-retry", job.dedupe_key)

    def test_non_lock_operational_error_is_not_retried(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        conn.close()

        with self.assertRaises(sqlite3.ProgrammingError):
            claim_route(
                conn,
                RouteSpec(
                    dedupe_key="closed",
                    route_kind="AI",
                ),
            )

    def test_append_decision_is_auditable(self):
        conn = make_test_db()
        ensure_route_schema(conn)
        job = claim_route(conn, RouteSpec(dedupe_key="audit", route_kind="AI"))
        decision_id = append_decision(
            conn, job.id, "ROUTE_AI", "large native trace", task_id="T1"
        )
        row = conn.execute(
            "select decision,reason,task_id from route_decisions where id=?",
            (decision_id,),
        ).fetchone()
        self.assertEqual(("ROUTE_AI", "large native trace", "T1"), tuple(row))


if __name__ == "__main__":
    unittest.main()
