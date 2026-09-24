import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
LIB_DIR = CONTROL_ROOT / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_mission_coverage import scan, stable_ids_sha256

MANIFEST_PATH = CONTROL_ROOT / "config" / "completion_manifest.json"


class CoverageTests(unittest.TestCase):
    def db(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            create table mission_objectives(
              id text primary key,parent_id text,title text,
              definition_of_done text,sort_order integer
            );
            create table mission_links(
              objective_id text,milestone_id text,task_id text,gate_type text
            );
            create table tasks(
              id text primary key,status text,title text,note text
            );
            create table milestones(
              id text primary key,status text,title text,
              definition_of_done text
            );
            """
        )
        return conn

    def test_uncovered_is_implementation_gap(self):
        conn = self.db()
        conn.execute(
            "insert into mission_objectives values('A',null,'A','done',1)"
        )
        result = scan(conn)
        self.assertEqual(
            "IMPLEMENTATION_GAP",
            result["gaps"][0]["gap_kind"],
        )

    def test_evidence_ceiling_is_distinct(self):
        conn = self.db()
        conn.execute(
            "insert into mission_objectives values('A',null,'A','done',1)"
        )
        conn.execute(
            "insert into tasks values('T','BLOCKED_EVIDENCE','T','need archive')"
        )
        conn.execute(
            "insert into mission_links values('A',null,'T','required')"
        )
        result = scan(conn)
        self.assertEqual(
            "EVIDENCE_CEILING",
            result["gaps"][0]["gap_kind"],
        )

    def test_complete_leaf_removed_from_gaps(self):
        conn = self.db()
        conn.execute(
            "insert into mission_objectives values('A',null,'A','done',1)"
        )
        conn.execute("insert into tasks values('T','DONE','T','')")
        conn.execute(
            "insert into mission_links values('A',null,'T','required')"
        )
        result = scan(conn)
        self.assertEqual(0, result["gap_count"])
        self.assertEqual(1, result["counts"]["COMPLETE"])

    def test_stable_inventory_hash_is_order_independent(self):
        self.assertEqual(
            stable_ids_sha256(["b", "a"]),
            stable_ids_sha256(["a", "b"]),
        )

    def test_done_content_objective_remains_gap_when_source_inventory_is_missing(self):
        conn = self.db()
        conn.execute(
            """insert into mission_objectives
               values('MAP_CONTENT',null,'Maps','done',1)"""
        )
        conn.execute(
            "insert into tasks values('T','DONE','Maps','')"
        )
        conn.execute(
            """insert into mission_links
               values('MAP_CONTENT',null,'T','required')"""
        )

        with tempfile.TemporaryDirectory() as td:
            result = scan(
                conn,
                root=Path(td),
                manifest_path=MANIFEST_PATH,
            )

        self.assertEqual(1, result["gap_count"])
        self.assertEqual(
            "CONTENT_CORPUS_GAP",
            result["gaps"][0]["gap_kind"],
        )
        self.assertFalse(
            result["gaps"][0]["content_completion"]["complete"]
        )
        self.assertFalse(
            result["project_completion_scope"]["declared_scope_complete"]
        )


if __name__ == "__main__":
    unittest.main()
