import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db, seed_task
from logres_knowledge import (
    confidence_score,
    graph_stats,
    query_nodes,
    refresh_graph,
    task_knowledge,
)


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


class KnowledgeGraphTests(unittest.TestCase):
    def test_confidence_lattice_preserves_evidence_ceiling(self):
        self.assertEqual(1.0, confidence_score("CONFIRMED"))
        self.assertEqual(0.72, confidence_score("INFERENCE"))
        self.assertLess(
            confidence_score("VERSION_SENSITIVE"),
            confidence_score("INFERENCE"),
        )
        self.assertLess(
            confidence_score("UNRESOLVED"),
            confidence_score("LOW"),
        )

    def test_refresh_builds_task_claim_artifact_source_and_commit_edges(self):
        conn = make_test_db()
        add_discovery_table(conn)
        seed_task(conn, task_id="T1", work_type="research")
        with tempfile.TemporaryDirectory() as td:
            artifact = Path(td) / "proof.json"
            artifact.write_text(
                json.dumps(
                    {
                        "result": {
                            "sources": [
                                "https://example.test/global-proof"
                            ]
                        }
                    }
                )
            )
            conn.execute(
                """insert into brain_discoveries(
                     id,ts,author,task_id,confidence,subject,summary,
                     artifact_path,artifact_sha256,status
                   ) values(1,'now','finder','T1','CONFIRMED',
                            'Global proof','proof summary',?,?, 'OPEN')""",
                (str(artifact), "a" * 64),
            )
            conn.execute(
                """insert into integration_queue(
                     task_id,sha,branch,status,verification_mode,
                     queued_at,updated_at,note,integrated_at
                   ) values('T1',?,'worker/t1','INTEGRATED','full-e2e',
                            'now','now','done','now')""",
                ("b" * 40,),
            )
            conn.commit()

            counts = refresh_graph(conn)
            stats = graph_stats(conn)
            knowledge = task_knowledge(conn, "T1")

        self.assertEqual(1, counts["discoveries"])
        self.assertGreaterEqual(stats["nodes"], 5)
        self.assertEqual(1, stats["claims"])
        self.assertEqual(1, stats["sources"])
        self.assertEqual(1.0, knowledge.support_score)
        self.assertEqual(1, knowledge.confirmed_count)
        self.assertEqual(1, knowledge.artifact_count)
        self.assertEqual(1, knowledge.source_count)
        self.assertTrue(query_nodes(conn, "Global proof"))

    def test_current_jp_confirmation_is_clamped_for_global_required_task(self):
        conn = make_test_db()
        add_discovery_table(conn)
        seed_task(
            conn,
            task_id="T1",
            work_type="research",
            evidence_policy="CONFIRMED ORIGINAL Global evidence required",
        )
        with tempfile.TemporaryDirectory() as td:
            artifact = Path(td) / "current-jp-proof.json"
            artifact.write_text(
                json.dumps(
                    {
                        "provenance": "CURRENT_JP_REFERENCE",
                        "finding": "confirmed in current JP only",
                    }
                )
            )
            conn.execute(
                """insert into brain_discoveries(
                     id,ts,author,task_id,confidence,subject,summary,
                     artifact_path,artifact_sha256,status
                   ) values(1,'now','ai','T1','CONFIRMED',
                            'JP-only proof','current JP only',?,?, 'OPEN')""",
                (str(artifact), "c" * 64),
            )
            conn.commit()

            refresh_graph(conn)
            knowledge = task_knowledge(conn, "T1")

        self.assertLess(knowledge.support_score, 0.90)
        self.assertEqual(0, knowledge.confirmed_count)

    def test_many_inferences_do_not_become_confirmed_original(self):
        conn = make_test_db()
        add_discovery_table(conn)
        seed_task(conn, task_id="T1", work_type="research")
        for i in range(1, 8):
            conn.execute(
                """insert into brain_discoveries(
                     id,ts,author,task_id,confidence,subject,summary,status
                   ) values(?,?,?,?,?,?,?,'OPEN')""",
                (
                    i,
                    "now",
                    "ai",
                    "T1",
                    "INFERENCE",
                    f"inference {i}",
                    "current-JP corroboration only",
                ),
            )
        conn.commit()

        refresh_graph(conn)
        knowledge = task_knowledge(conn, "T1")

        self.assertLess(knowledge.support_score, 0.90)
        self.assertEqual(0, knowledge.confirmed_count)
        self.assertEqual(7, knowledge.discovery_count)


if __name__ == "__main__":
    unittest.main()
