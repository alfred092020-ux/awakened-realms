import json
import os
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
CAPTURE = CONTROL_ROOT / "bin" / "logres-regression-capture"


def init_db(path: Path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
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
          task_id text,ordinal integer,criterion text,
          primary key(task_id,ordinal)
        );
        create table task_scopes(
          task_id text,path_prefix text,
          primary key(task_id,path_prefix)
        );
        create table regressions(
          id integer primary key autoincrement,
          fingerprint text not null unique,
          task_id text,kind text not null,ref text,sha text,
          summary text not null,logs_json text not null,
          created_at text,created_epoch real,status text not null
        );
        """
    )
    conn.commit()
    conn.close()


class RegressionCaptureTests(unittest.TestCase):
    def run_capture(self, db: Path, log: Path, *, ref: str, sha: str):
        env = os.environ.copy()
        env["LOGRES_CONTROL_DB"] = str(db)
        env["LOGRES_BRAIN"] = "/bin/true"
        env["LOGRES_ROOT"] = str(db.parent)
        return subprocess.run(
            [
                str(CAPTURE),
                "--kind",
                "candidate-verify",
                "--ref",
                ref,
                "--sha",
                sha,
                "--summary",
                "verify-farm test_rc=0 e2e_rc=1",
                "--log",
                str(log),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=env,
            timeout=20,
        )

    def test_semantic_duplicate_does_not_create_second_task(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "control.sqlite"
            init_db(db)
            first = root / "first.log"
            second = root / "second.log"
            first.write_text(
                "Error: Visual checkpoint title failed\n"
                "sqlite3.OperationalError: database is locked\n"
            )
            second.write_text(
                "Error: Visual checkpoint field failed\n"
                "sqlite3.OperationalError: database is locked\n"
            )

            one = self.run_capture(
                db,
                first,
                ref="a" * 40,
                sha="a" * 40,
            )
            two = self.run_capture(
                db,
                second,
                ref="b" * 40,
                sha="b" * 40,
            )

            self.assertEqual(0, one.returncode, one.stderr)
            self.assertIn("CREATED", one.stdout)
            self.assertEqual(0, two.returncode, two.stderr)
            self.assertIn("DEDUPED_SEMANTIC", two.stdout)

            conn = sqlite3.connect(db)
            regressions = conn.execute(
                "select task_id,logs_json from regressions"
            ).fetchall()
            tasks = conn.execute(
                "select id from tasks where lane='regression'"
            ).fetchall()
            conn.close()
            self.assertEqual(1, len(regressions))
            self.assertEqual(1, len(tasks))
            logs = json.loads(regressions[0][1])
            self.assertEqual([str(first), str(second)], logs)

    def test_distinct_root_causes_create_distinct_regressions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "control.sqlite"
            init_db(db)
            first = root / "first.log"
            second = root / "second.log"
            first.write_text(
                "Error: LOGRES_BEHAVIOR_TRACE_OUT is required\n"
            )
            second.write_text(
                "sqlite3.OperationalError: database is locked\n"
            )

            one = self.run_capture(
                db,
                first,
                ref="a",
                sha="a" * 40,
            )
            two = self.run_capture(
                db,
                second,
                ref="b",
                sha="b" * 40,
            )

            self.assertEqual(0, one.returncode, one.stderr)
            self.assertEqual(0, two.returncode, two.stderr)
            conn = sqlite3.connect(db)
            self.assertEqual(
                2,
                conn.execute(
                    "select count(*) from regressions"
                ).fetchone()[0],
            )
            conn.close()

    def test_capture_is_runtime_path_configurable(self):
        source = CAPTURE.read_text()
        self.assertIn("LOGRES_CONTROL_DB", source)
        self.assertIn("LOGRES_BRAIN", source)
        self.assertIn("semantic_fingerprint", source)
        self.assertIn("find_semantic_duplicate", source)


if __name__ == "__main__":
    unittest.main()
