import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_goal_certify import (
    apply_milestone_completion,
    build_certificate,
    current_certificate_valid,
    write_certificate,
)


SHA = "a" * 40


def contracts(title="M"):
    return {
        "schema": "logres-milestone-contract-v1",
        "milestones": {
            "M": {
                "title": title,
                "definition_of_done": "all gates pass",
                "criteria": [
                    {
                        "id": "task",
                        "weight": 50,
                        "description": "task complete",
                        "check": {
                            "type": "task_state",
                            "task_id": "T",
                            "pass_statuses": ["DONE"],
                        },
                    },
                    {
                        "id": "verify",
                        "weight": 50,
                        "description": "exact sha verified",
                        "check": {
                            "type": "verification",
                            "mode": "full-e2e",
                            "status": "PASS",
                        },
                    },
                ],
            }
        },
    }


def make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        create table tasks(id text primary key,status text not null);
        create table task_dependencies(
          task_id text,depends_on text,kind text,rationale text
        );
        create table verification(
          ref text primary key,sha text,mode text,status text,
          duration_sec real,ran_at text,details text
        );
        create table regressions(
          id integer primary key,status text
        );
        create table milestones(
          id text primary key,status text,updated_at text
        );
        """
    )
    conn.execute("insert into tasks values('T','DONE')")
    conn.execute("insert into milestones values('M','ACTIVE','now')")
    conn.execute(
        "insert into verification values(?,?,?,?,?,?,?)",
        ("v", SHA, "full-e2e", "PASS", 1.0, "2026-09-24T00:00:00+00:00", "ok"),
    )
    conn.commit()
    return conn


class GoalCertifyTests(unittest.TestCase):
    def test_valid_exact_sha_certificate_can_complete_milestone(self):
        conn = make_db()
        with tempfile.TemporaryDirectory() as td:
            cert = build_certificate(
                conn,
                contracts(),
                "M",
                integration_sha=SHA,
                root=Path(td),
                timestamp="2026-09-24T00:00:00+00:00",
            )
            self.assertTrue(cert["valid"])
            self.assertEqual("PASS", cert["status"])
            self.assertEqual(1, len(cert["verification_rows"]))
            written = write_certificate(
                conn,
                cert,
                artifact_dir=Path(td) / "certs",
            )
            self.assertTrue(Path(written["artifact_path"]).is_file())
            self.assertTrue(apply_milestone_completion(conn, cert))
            status = conn.execute(
                "select status from milestones where id='M'"
            ).fetchone()[0]
            self.assertEqual("DONE", status)

    def test_open_regression_fails_closed(self):
        conn = make_db()
        conn.execute("insert into regressions values(1,'OPEN')")
        cert = build_certificate(
            conn,
            contracts(),
            "M",
            integration_sha=SHA,
            root=Path("."),
            timestamp="2026-09-24T00:00:00+00:00",
        )
        self.assertFalse(cert["valid"])
        self.assertEqual(1, cert["open_regression_count"])

    def test_contract_change_invalidates_old_certificate(self):
        conn = make_db()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old = build_certificate(
                conn,
                contracts("old"),
                "M",
                integration_sha=SHA,
                root=root,
                timestamp="2026-09-24T00:00:00+00:00",
            )
            write_certificate(conn, old, artifact_dir=root / "certs")
            self.assertFalse(
                current_certificate_valid(
                    conn,
                    contracts("new"),
                    "M",
                    integration_sha=SHA,
                    root=root,
                )
            )

    def test_evidence_state_change_invalidates_old_certificate(self):
        conn = make_db()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cert = build_certificate(
                conn,
                contracts(),
                "M",
                integration_sha=SHA,
                root=root,
                timestamp="2026-09-24T00:00:00+00:00",
            )
            write_certificate(conn, cert, artifact_dir=root / "certs")
            conn.execute("update tasks set status='BLOCKED_EVIDENCE' where id='T'")
            conn.commit()
            self.assertFalse(
                current_certificate_valid(
                    conn,
                    contracts(),
                    "M",
                    integration_sha=SHA,
                    root=root,
                )
            )

    def test_certificate_artifacts_are_append_only(self):
        conn = make_db()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cert = build_certificate(
                conn,
                contracts(),
                "M",
                integration_sha=SHA,
                root=root,
                timestamp="2026-09-24T00:00:00+00:00",
            )
            write_certificate(conn, cert, artifact_dir=root / "certs")
            with self.assertRaises(FileExistsError):
                write_certificate(conn, cert, artifact_dir=root / "certs")


if __name__ == "__main__":
    unittest.main()
