import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
ROUTER = CONTROL_ROOT / "bin" / "logres-blocker-router"


def make_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        create table meta(key text primary key,value text);
        create table tasks(
          id text primary key,priority integer,lane text,title text,status text,
          branch text,owner text,note text,updated_at text
        );
        create table task_metadata(
          task_id text primary key,milestone text,work_type text,
          concurrency_key text,expected_minutes integer,evidence_policy text,
          created_at text,updated_at text
        );
        create table task_acceptance(
          task_id text,ordinal integer,criterion text
        );
        create table task_dependencies(
          task_id text,depends_on text,kind text,rationale text,
          primary key(task_id,depends_on)
        );
        create table brain_events(
          id integer primary key,ts_epoch real,ts text,sender text,recipient text,
          event_type text,priority integer,task_id text,subject text,body text,
          artifact_path text,artifact_sha256 text,dedupe_key text,meta_json text
        );
        """
    )
    conn.execute(
        "insert into meta(key,value) values('blocker_router_last_id','0')"
    )
    conn.commit()
    return conn


def seed_parent(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    status: str = "READY",
    note: str = "",
    work_type: str = "implementation",
    milestone: str = "DEMO-0.2",
) -> None:
    stamp = "2026-09-24T09:00:00+00:00"
    conn.execute(
        "insert into tasks values(?,?,?,?,?,?,?,?,?)",
        (task_id, 0, "research", task_id, status, "", None, note, stamp),
    )
    conn.execute(
        "insert into task_metadata values(?,?,?,?,?,?,?,?)",
        (
            task_id,
            milestone,
            work_type,
            f"key:{task_id}",
            45,
            "Evidence-first.",
            stamp,
            stamp,
        ),
    )
    conn.commit()


def seed_event(
    conn: sqlite3.Connection,
    event_id: int,
    task_id: str,
    *,
    event_type: str = "BLOCKER",
    subject: str = "Need focused evidence",
    body: str = "Recover the exact missing evidence.",
) -> None:
    conn.execute(
        "insert into brain_events values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            event_id,
            1.0,
            "2026-09-24T09:00:00+00:00",
            "worker",
            "ALL",
            event_type,
            1,
            task_id,
            subject,
            body,
            None,
            None,
            None,
            "{}",
        ),
    )
    conn.commit()


class BlockerRouterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db_path = self.root / "control.sqlite"
        self.conn = make_db(self.db_path)

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def run_router(self):
        env = os.environ.copy()
        env["LOGRES_CONTROL_DB"] = str(self.db_path)
        env["LOGRES_BRAIN"] = "/bin/true"
        return subprocess.run(
            [sys.executable, str(ROUTER)],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_normal_first_level_blocker_creates_one_unblock_task(self):
        seed_parent(self.conn, "PARENT")
        seed_event(self.conn, 1, "PARENT")
        result = self.run_router()
        self.assertEqual(0, result.returncode, result.stderr)
        children = list(
            self.conn.execute(
                "select * from tasks where id like 'UNBLOCK-PARENT-%'"
            )
        )
        self.assertEqual(1, len(children))
        child_id = children[0]["id"]
        parent = self.conn.execute(
            "select status,note from tasks where id='PARENT'"
        ).fetchone()
        self.assertEqual("BLOCKED_DEP", parent["status"])
        self.assertIn(child_id, parent["note"])
        dep = self.conn.execute(
            "select kind from task_dependencies "
            "where task_id='PARENT' and depends_on=?",
            (child_id,),
        ).fetchone()
        self.assertEqual("hard", dep["kind"])

    def test_equivalent_blocker_events_share_one_frontier_child(self):
        seed_parent(self.conn, "PARENT")
        seed_event(
            self.conn,
            1,
            "PARENT",
            subject="Missing historical packet",
            body="Recover exact Global packet evidence.",
        )
        seed_event(
            self.conn,
            2,
            "PARENT",
            subject="Missing historical packet",
            body="Recover exact Global packet evidence.",
        )

        result = self.run_router()

        self.assertEqual(0, result.returncode, result.stderr)
        children = list(
            self.conn.execute(
                "select id from tasks where id like 'UNBLOCK-PARENT-%'"
            )
        )
        self.assertEqual(1, len(children))
        frontier = self.conn.execute(
            "select attempts,child_task_id,state from research_frontier"
        ).fetchone()
        self.assertEqual(1, frontier["attempts"])
        self.assertEqual(children[0]["id"], frontier["child_task_id"])
        self.assertEqual("OPEN", frontier["state"])

    def test_blocked_frontier_child_saturates_parent_without_new_sibling(self):
        seed_parent(self.conn, "PARENT")
        seed_event(
            self.conn,
            1,
            "PARENT",
            subject="Missing historical packet",
            body="Recover exact Global packet evidence.",
        )
        first = self.run_router()
        self.assertEqual(0, first.returncode, first.stderr)
        child = self.conn.execute(
            "select id from tasks where id like 'UNBLOCK-PARENT-%'"
        ).fetchone()["id"]
        self.conn.execute(
            "update tasks set status='BLOCKED_EVIDENCE' where id=?",
            (child,),
        )
        self.conn.commit()

        seed_event(
            self.conn,
            2,
            "PARENT",
            subject="Missing historical packet",
            body="Recover exact Global packet evidence.",
        )
        second = self.run_router()

        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual(
            1,
            self.conn.execute(
                "select count(*) from tasks where id like 'UNBLOCK-PARENT-%'"
            ).fetchone()[0],
        )
        parent = self.conn.execute(
            "select status,note from tasks where id='PARENT'"
        ).fetchone()
        self.assertEqual("BLOCKED_EVIDENCE", parent["status"])
        self.assertIn("Evidence ceiling reached", parent["note"])
        dep = self.conn.execute(
            "select kind from task_dependencies where task_id='PARENT' and depends_on=?",
            (child,),
        ).fetchone()
        self.assertEqual("evidence", dep["kind"])

    def test_autoflow_generated_parent_does_not_spawn_descendant(self):
        seed_parent(
            self.conn,
            "AUTO-RE-PARENT-123",
            status="BLOCKED_EVIDENCE",
            note="Autoflow research child from AI evidence routing.",
            work_type="research",
            milestone="autoflow",
        )
        seed_event(self.conn, 2, "AUTO-RE-PARENT-123")
        result = self.run_router()
        self.assertEqual(0, result.returncode, result.stderr)
        count = self.conn.execute(
            "select count(*) from tasks "
            "where id like 'UNBLOCK-AUTO-RE-PARENT-123-%'"
        ).fetchone()[0]
        self.assertEqual(0, count)
        cursor = self.conn.execute(
            "select value from meta where key='blocker_router_last_id'"
        ).fetchone()[0]
        self.assertEqual("2", cursor)

    def test_auto_routed_unblock_parent_does_not_spawn_descendant(self):
        seed_parent(
            self.conn,
            "UNBLOCK-AUTO-RE-PARENT-ABC",
            status="BLOCKED_EVIDENCE",
            note="Auto-routed from Brain event 99.",
            work_type="research",
        )
        seed_event(
            self.conn,
            3,
            "UNBLOCK-AUTO-RE-PARENT-ABC",
            event_type="EVIDENCE_CONFLICT",
        )
        result = self.run_router()
        self.assertEqual(0, result.returncode, result.stderr)
        count = self.conn.execute(
            "select count(*) from tasks "
            "where id like 'UNBLOCK-UNBLOCK-AUTO-RE-PARENT-ABC-%'"
        ).fetchone()[0]
        self.assertEqual(0, count)

    def test_hardware_blocker_remains_non_research(self):
        seed_parent(self.conn, "DEVICE-PARENT", status="BLOCKED_EVIDENCE")
        seed_event(
            self.conn,
            4,
            "DEVICE-PARENT",
            body="Awaiting real-device proof. No ADB device attached.",
        )
        result = self.run_router()
        self.assertEqual(0, result.returncode, result.stderr)
        count = self.conn.execute(
            "select count(*) from tasks "
            "where id like 'UNBLOCK-DEVICE-PARENT-%'"
        ).fetchone()[0]
        self.assertEqual(0, count)


if __name__ == "__main__":
    unittest.main()
