import sqlite3
import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db, seed_task
from logres_frontier import (
    MAX_GENERATED_DEPTH,
    claim_frontier,
    ensure_schema,
    lineage_for_task,
    normalize_predicate,
    reconcile,
    register_child,
)


def mark_generated(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    note: str,
    milestone: str = "autoflow",
):
    conn.execute(
        "update tasks set note=? where id=?",
        (note, task_id),
    )
    conn.execute(
        "update task_metadata set milestone='autoflow',work_type='research' where task_id=?",
        (task_id,),
    )
    conn.commit()


class FrontierTests(unittest.TestCase):
    def setUp(self):
        self.conn = make_test_db()
        ensure_schema(self.conn)
        seed_task(
            self.conn,
            task_id="ROOT",
            work_type="research",
            status="READY",
        )

    def tearDown(self):
        self.conn.close()

    def test_predicate_normalization_ignores_event_and_hash_noise(self):
        a = normalize_predicate(
            "BLOCKER: ROOT needs proof from Brain event 123 sha abcdef1234567890",
            "ROOT",
        )
        b = normalize_predicate(
            "BLOCKER: ROOT needs proof from Brain event 999 sha deadbeef01234567",
            "ROOT",
        )
        self.assertEqual(a, b)

    def test_equivalent_open_frontier_reuses_same_child(self):
        first = claim_frontier(
            self.conn,
            parent_task_id="ROOT",
            predicate_text="UNRESOLVED: recover exact Global xref",
            origin_kind="AI_ROUTE",
            origin_id=10,
        )
        self.assertTrue(first.create_allowed)

        seed_task(
            self.conn,
            task_id="CHILD",
            work_type="research",
            status="READY",
        )
        mark_generated(
            self.conn,
            "CHILD",
            note="Autoflow research child from AI evidence routing.",
        )
        register_child(
            self.conn,
            first,
            child_task_id="CHILD",
            origin_kind="AI_ROUTE",
            origin_id=10,
        )

        second = claim_frontier(
            self.conn,
            parent_task_id="ROOT",
            predicate_text="UNRESOLVED: recover exact Global xref",
            origin_kind="AI_ROUTE",
            origin_id=11,
        )

        self.assertFalse(second.create_allowed)
        self.assertEqual("OPEN", second.state)
        self.assertEqual("CHILD", second.child_task_id)
        self.assertIn("already open", second.reason)

    def test_blocked_child_saturates_frontier_after_single_attempt(self):
        first = claim_frontier(
            self.conn,
            parent_task_id="ROOT",
            predicate_text="recover missing historical packet",
            origin_kind="AI_ROUTE",
            origin_id=20,
        )
        seed_task(
            self.conn,
            task_id="CHILD",
            work_type="research",
            status="BLOCKED_EVIDENCE",
        )
        mark_generated(
            self.conn,
            "CHILD",
            note="Autoflow research child from AI evidence routing.",
        )
        register_child(
            self.conn,
            first,
            child_task_id="CHILD",
            origin_kind="AI_ROUTE",
            origin_id=20,
        )

        again = claim_frontier(
            self.conn,
            parent_task_id="ROOT",
            predicate_text="recover missing historical packet",
            origin_kind="AI_ROUTE",
            origin_id=21,
        )

        self.assertFalse(again.create_allowed)
        self.assertEqual("SATURATED", again.state)
        self.assertEqual("CHILD", again.child_task_id)

    def test_generated_child_cannot_spawn_generated_descendant(self):
        first = claim_frontier(
            self.conn,
            parent_task_id="ROOT",
            predicate_text="first escalation",
            origin_kind="AI_ROUTE",
            origin_id=30,
        )
        seed_task(
            self.conn,
            task_id="CHILD",
            work_type="research",
            status="READY",
        )
        mark_generated(
            self.conn,
            "CHILD",
            note="Autoflow research child from AI evidence routing.",
        )
        register_child(
            self.conn,
            first,
            child_task_id="CHILD",
            origin_kind="AI_ROUTE",
            origin_id=30,
        )

        nested = claim_frontier(
            self.conn,
            parent_task_id="CHILD",
            predicate_text="second escalation must not exist",
            origin_kind="BRAIN_BLOCKER",
            origin_id=31,
        )

        self.assertFalse(nested.create_allowed)
        self.assertEqual("SATURATED", nested.state)
        self.assertEqual(MAX_GENERATED_DEPTH, nested.parent_depth)
        self.assertIn("depth ceiling", nested.reason)

    def test_reconcile_backfills_and_supersedes_recursive_legacy_descendant(self):
        seed_task(
            self.conn,
            task_id="CHILD1",
            work_type="research",
            status="BLOCKED_EVIDENCE",
        )
        mark_generated(
            self.conn,
            "CHILD1",
            note="Autoflow research child from AI evidence routing.",
        )
        self.conn.execute(
            """insert into task_dependencies(task_id,depends_on,kind,rationale)
               values('CHILD1','ROOT','evidence','Autoflow child')"""
        )

        seed_task(
            self.conn,
            task_id="CHILD2",
            work_type="research",
            status="BLOCKED_EVIDENCE",
        )
        mark_generated(
            self.conn,
            "CHILD2",
            note="Auto-routed from Brain event 99.",
            milestone="autoflow",
        )
        self.conn.execute(
            """insert into task_dependencies(task_id,depends_on,kind,rationale)
               values('CHILD1','CHILD2','hard',
                      'Auto-routed blocker event 99: still unresolved')"""
        )
        self.conn.commit()

        line = lineage_for_task(
            self.conn,
            "CHILD2",
            backfill=True,
        )
        self.assertIsNotNone(line)
        self.assertEqual("ROOT", line.root_task_id)
        self.assertEqual(2, line.depth)

        report = reconcile(self.conn, apply=True)

        self.assertIn("CHILD2", report["superseded_task_ids"])
        row = self.conn.execute(
            "select status,note from tasks where id='CHILD2'"
        ).fetchone()
        self.assertEqual("SUPERSEDED", row["status"])
        self.assertIn("evidence artifacts remain preserved", row["note"])

    def test_terminal_root_resolves_leftover_saturated_frontier(self):
        claim = claim_frontier(
            self.conn,
            parent_task_id="ROOT",
            predicate_text="recover bounded missing evidence",
            origin_kind="AI_ROUTE",
            origin_id=60,
        )
        seed_task(
            self.conn,
            task_id="CHILD_TERM",
            work_type="research",
            status="BLOCKED_EVIDENCE",
        )
        mark_generated(
            self.conn,
            "CHILD_TERM",
            note="Autoflow research child from AI evidence routing.",
        )
        register_child(
            self.conn,
            claim,
            child_task_id="CHILD_TERM",
            origin_kind="AI_ROUTE",
            origin_id=60,
        )
        self.conn.execute("update tasks set status='DONE' where id='ROOT'")
        self.conn.commit()

        report = reconcile(self.conn, apply=True)

        row = self.conn.execute(
            "select state from research_frontier where root_task_id='ROOT'"
        ).fetchone()
        self.assertEqual("RESOLVED", row["state"])
        self.assertEqual(1, report["stats"]["terminal_root_resolved"])

    def test_blocked_evidence_root_keeps_saturated_frontier(self):
        claim = claim_frontier(
            self.conn,
            parent_task_id="ROOT",
            predicate_text="still requires genuinely new primary evidence",
            origin_kind="AI_ROUTE",
            origin_id=61,
        )
        seed_task(
            self.conn,
            task_id="CHILD_BLOCKED",
            work_type="research",
            status="BLOCKED_EVIDENCE",
        )
        mark_generated(
            self.conn,
            "CHILD_BLOCKED",
            note="Autoflow research child from AI evidence routing.",
        )
        register_child(
            self.conn,
            claim,
            child_task_id="CHILD_BLOCKED",
            origin_kind="AI_ROUTE",
            origin_id=61,
        )
        self.conn.execute(
            "update tasks set status='BLOCKED_EVIDENCE' where id='ROOT'"
        )
        self.conn.commit()

        report = reconcile(self.conn, apply=True)

        row = self.conn.execute(
            "select state from research_frontier where root_task_id='ROOT'"
        ).fetchone()
        self.assertEqual("SATURATED", row["state"])
        self.assertEqual(0, report["stats"]["terminal_root_resolved"])

    def test_terminal_root_frontier_reconcile_is_idempotent(self):
        claim = claim_frontier(
            self.conn,
            parent_task_id="ROOT",
            predicate_text="historical search already satisfied elsewhere",
            origin_kind="AI_ROUTE",
            origin_id=62,
        )
        seed_task(
            self.conn,
            task_id="CHILD_IDEMP",
            work_type="research",
            status="BLOCKED_EVIDENCE",
        )
        mark_generated(
            self.conn,
            "CHILD_IDEMP",
            note="Autoflow research child from AI evidence routing.",
        )
        register_child(
            self.conn,
            claim,
            child_task_id="CHILD_IDEMP",
            origin_kind="AI_ROUTE",
            origin_id=62,
        )
        self.conn.execute("update tasks set status='SUPERSEDED' where id='ROOT'")
        self.conn.commit()

        first = reconcile(self.conn, apply=True)
        second = reconcile(self.conn, apply=True)

        self.assertEqual(1, first["stats"]["terminal_root_resolved"])
        self.assertEqual(0, second["stats"]["terminal_root_resolved"])
        row = self.conn.execute(
            "select state from research_frontier where root_task_id='ROOT'"
        ).fetchone()
        self.assertEqual("RESOLVED", row["state"])

    def test_saturated_auto_blocker_turns_root_into_evidence_ceiling(self):
        seed_task(
            self.conn,
            task_id="BLOCKER_CHILD",
            work_type="research",
            status="BLOCKED_EVIDENCE",
        )
        mark_generated(
            self.conn,
            "BLOCKER_CHILD",
            note="Auto-routed from Brain event 50.",
        )
        self.conn.execute(
            """insert into task_dependencies(task_id,depends_on,kind,rationale)
               values('ROOT','BLOCKER_CHILD','hard',
                      'Auto-routed blocker event 50: missing proof')"""
        )
        self.conn.execute(
            "update tasks set status='BLOCKED_DEP' where id='ROOT'"
        )
        self.conn.commit()

        report = reconcile(self.conn, apply=True)

        self.assertTrue(report["apply"])
        root = self.conn.execute(
            "select status,note from tasks where id='ROOT'"
        ).fetchone()
        self.assertEqual("BLOCKED_EVIDENCE", root["status"])
        self.assertIn("Evidence ceiling reached", root["note"])
        dep = self.conn.execute(
            """select kind,rationale from task_dependencies
                where task_id='ROOT' and depends_on='BLOCKER_CHILD'"""
        ).fetchone()
        self.assertEqual("evidence", dep["kind"])
        self.assertIn("frontier saturated", dep["rationale"])


if __name__ == "__main__":
    unittest.main()
