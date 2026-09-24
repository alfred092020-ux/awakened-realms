import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
import sys

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_mission import ensure_schema, load_config, mission_status, objective_status


def make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        create table tasks(id text primary key,status text);
        create table milestones(id text primary key,status text);
        """
    )
    ensure_schema(conn)
    return conn
def write_config(path: Path):
    path.write_text(json.dumps({
        "mission_id": "ROOT",
        "title": "Root",
        "objectives": [
            {"id": "A", "parent_id": "ROOT", "title": "A", "weight": 1, "definition_of_done": "A done"},
            {"id": "B", "parent_id": "ROOT", "title": "B", "weight": 1, "definition_of_done": "B done"},
        ],
        "links": [
            {"objective_id": "A", "task_id": "TA", "gate_type": "required"}
        ],
    }))


class MissionTests(unittest.TestCase):
    def test_uncovered_leaf_never_silently_completes(self):
        conn = make_db()
        conn.execute("insert into tasks values(\'TA\',\'ACTIVE\')")
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "mission.json"
            write_config(cfg)
            load_config(conn, cfg)
            status = mission_status(conn)
        self.assertEqual("UNCOVERED", objective_status(conn, "B").state)
        self.assertEqual(["B"], [item["id"] for item in status["uncovered"]])
    def test_task_link_drives_leaf_and_parent_progress(self):
        conn = make_db()
        conn.execute("insert into tasks values('TA','DONE')")
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "mission.json"
            write_config(cfg)
            load_config(conn, cfg)
        leaf = objective_status(conn, "A")
        root = objective_status(conn, "ROOT")
        self.assertEqual("COMPLETE", leaf.state)
        self.assertEqual(100.0, leaf.progress_percent)
        self.assertEqual("IN_PROGRESS", root.state)
        self.assertEqual(50.0, root.progress_percent)

    def test_active_milestone_is_progress_not_complete(self):
        conn = make_db()
        conn.execute("insert into milestones values('M1','ACTIVE')")
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "mission.json"
            cfg.write_text(json.dumps({
                "mission_id": "ROOT",
                "title": "Root",
                "objectives": [
                    {"id": "A", "parent_id": "ROOT", "title": "A", "weight": 1}
                ],
                "links": [{"objective_id": "A", "milestone_id": "M1"}],
            }))
            load_config(conn, cfg)
        self.assertEqual("IN_PROGRESS", objective_status(conn, "A").state)
    def test_config_reload_is_idempotent(self):
        conn = make_db()
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "mission.json"
            write_config(cfg)
            first = load_config(conn, cfg)
            second = load_config(conn, cfg)
        self.assertEqual(first, second)
        self.assertEqual(3, conn.execute("select count(*) from mission_objectives").fetchone()[0])
        self.assertEqual(1, conn.execute("select count(*) from mission_links").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
