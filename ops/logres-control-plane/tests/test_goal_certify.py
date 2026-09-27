import hashlib
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


def device_contracts():
    return {
        "schema": "logres-milestone-contract-v1",
        "milestones": {
            "M": {
                "title": "release",
                "definition_of_done": "exact release proof",
                "criteria": [
                    {
                        "id": "device",
                        "weight": 50,
                        "description": "exact device proof",
                        "check": {
                            "type": "device_proof",
                            "checkpoint": "demo-0.2",
                            "status": "PASS",
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


def add_device_proof(
    conn,
    root: Path,
    *,
    sha: str,
    embedded_sha: str | None = None,
    status: str = "PASS",
    checkpoint: str = "demo-0.2",
):
    artifact = root / f"device-proof-{sha[:12]}.json"
    artifact.write_text(
        json.dumps(
            {
                "canonical_sha": embedded_sha or sha,
                "checkpoint": checkpoint,
                "apk": {"sha256": "c" * 64},
            },
            sort_keys=True,
        )
        + "\n"
    )
    cur = conn.execute(
        """insert into device_proofs(
             sha,apk_sha256,checkpoint,status,artifact_path,note,
             created_at,created_epoch
           ) values(?,?,?,?,?,?,?,?)""",
        (
            sha,
            "c" * 64,
            checkpoint,
            status,
            str(artifact),
            "test proof",
            "2026-09-24T00:00:00+00:00",
            1.0,
        ),
    )
    conn.commit()
    return int(cur.lastrowid), artifact


def add_regression(
    conn,
    *,
    regression_id: int,
    sha: str | None,
    task_id: str = "REG-TEST",
    kind: str = "candidate-verify",
    ref: str | None = None,
    status: str = "OPEN",
):
    conn.execute(
        """insert into regressions(
             id,fingerprint,task_id,kind,ref,sha,summary,logs_json,
             created_at,created_epoch,status
           ) values(?,?,?,?,?,?,?,?,?,?,?)""",
        (
            regression_id,
            f"fp-{regression_id}",
            task_id,
            kind,
            ref,
            sha,
            f"regression {regression_id}",
            "[]",
            "2026-09-24T00:00:00+00:00",
            float(regression_id),
            status,
        ),
    )
    conn.commit()


def add_verification(conn, *, sha: str, status: str = "FAIL", ref: str | None = None):
    conn.execute(
        "insert into verification values(?,?,?,?,?,?,?)",
        (
            ref or f"verify-{sha[:12]}",
            sha,
            "full-e2e",
            status,
            1.0,
            "2026-09-24T00:00:00+00:00",
            "test evidence",
        ),
    )
    conn.commit()


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
          id integer primary key,
          fingerprint text not null,
          task_id text,
          kind text not null,
          ref text,
          sha text,
          summary text not null,
          logs_json text not null default '[]',
          created_at text not null,
          created_epoch real not null,
          status text not null default 'OPEN'
        );
        create table milestones(
          id text primary key,status text,updated_at text
        );
        create table device_proofs(
          id integer primary key autoincrement,
          sha text not null,
          apk_sha256 text,
          checkpoint text not null,
          status text not null,
          artifact_path text,
          note text not null default '',
          created_at text not null,
          created_epoch real not null
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

    def test_exact_device_proof_is_embedded_in_certificate_provenance(self):
        conn = make_db()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proof_id, artifact = add_device_proof(
                conn,
                root,
                sha=SHA,
            )
            artifact_digest = hashlib.sha256(
                artifact.read_bytes()
            ).hexdigest()
            cert = build_certificate(
                conn,
                device_contracts(),
                "M",
                integration_sha=SHA,
                root=root,
                timestamp="2026-09-24T00:00:00+00:00",
            )

        self.assertTrue(cert["valid"])
        self.assertEqual("PASS", cert["status"])
        self.assertEqual(1, len(cert["device_proof_rows"]))
        proof = cert["device_proof_rows"][0]
        self.assertEqual("device", proof["criterion_id"])
        self.assertEqual(proof_id, proof["id"])
        self.assertEqual(SHA, proof["sha"])
        self.assertEqual("demo-0.2", proof["checkpoint"])
        self.assertEqual("PASS", proof["status"])
        self.assertEqual(str(artifact), proof["artifact_path"])
        self.assertEqual(
            artifact_digest,
            proof["artifact_sha256"],
        )

    def test_stale_device_proof_cannot_certify_current_release_sha(self):
        conn = make_db()
        old = "b" * 40
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            add_device_proof(
                conn,
                root,
                sha=old,
            )
            cert = build_certificate(
                conn,
                device_contracts(),
                "M",
                integration_sha=SHA,
                root=root,
                timestamp="2026-09-24T00:00:00+00:00",
            )

        self.assertFalse(cert["valid"])
        self.assertEqual("FAIL", cert["status"])
        self.assertIn("device", cert["unmet_criterion_ids"])
        self.assertEqual([], cert["device_proof_rows"])

    def test_open_regression_fails_closed(self):
        conn = make_db()
        add_regression(conn, regression_id=1, sha=None)
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
        self.assertEqual(1, cert["blocking_regression_count"])
        self.assertEqual([], cert["nonblocking_regressions"])
        self.assertEqual("missing_sha", cert["blocking_regressions"][0]["blocking_reason"])

    def test_open_regression_on_current_integration_sha_blocks_certificate(self):
        conn = make_db()
        add_regression(conn, regression_id=1, sha=SHA, ref=SHA)
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
        self.assertEqual(1, cert["blocking_regression_count"])
        self.assertEqual("current_integration_sha", cert["blocking_regressions"][0]["blocking_reason"])
        self.assertEqual(SHA, cert["blocking_regressions"][0]["sha"])

    def test_attributed_noncanonical_regression_is_audit_only(self):
        conn = make_db()
        candidate = "b" * 40
        add_verification(conn, sha=candidate, status="FAIL", ref="candidate-fail")
        add_regression(conn, regression_id=1, sha=candidate, ref=candidate)
        before = [tuple(row) for row in conn.execute("select * from regressions order by id")]
        cert = build_certificate(
            conn,
            contracts(),
            "M",
            integration_sha=SHA,
            root=Path("."),
            timestamp="2026-09-24T00:00:00+00:00",
        )
        after = [tuple(row) for row in conn.execute("select * from regressions order by id")]
        self.assertTrue(cert["valid"])
        self.assertEqual("PASS", cert["status"])
        self.assertEqual(1, cert["open_regression_count"])
        self.assertEqual(0, cert["blocking_regression_count"])
        self.assertEqual([], cert["blocking_regressions"])
        self.assertEqual(1, len(cert["nonblocking_regressions"]))
        evidence = cert["nonblocking_regressions"][0]
        self.assertEqual(candidate, evidence["sha"])
        self.assertEqual("noncanonical_attributed_sha", evidence["nonblocking_reason"])
        self.assertIn("verification", evidence["attribution_sources"])
        self.assertEqual(before, after)

    def test_missing_malformed_and_unattributable_regressions_fail_closed(self):
        conn = make_db()
        add_regression(conn, regression_id=1, sha=None)
        add_regression(conn, regression_id=2, sha="not-a-sha")
        add_regression(conn, regression_id=3, sha="c" * 40)
        with tempfile.TemporaryDirectory() as td:
            cert = build_certificate(
                conn,
                contracts(),
                "M",
                integration_sha=SHA,
                root=Path(td),
                timestamp="2026-09-24T00:00:00+00:00",
            )
        self.assertFalse(cert["valid"])
        self.assertEqual(3, cert["open_regression_count"])
        self.assertEqual(3, cert["blocking_regression_count"])
        reasons = {row["blocking_reason"] for row in cert["blocking_regressions"]}
        self.assertEqual({"missing_sha", "malformed_sha", "unattributable_sha"}, reasons)

    def test_failed_memory_and_plugin_candidates_do_not_invalidate_verified_canonical_release(self):
        conn = make_db()
        memory_sha = "b" * 40
        plugin_sha = "c" * 40
        add_verification(conn, sha=memory_sha, status="FAIL", ref="memory-candidate")
        add_verification(conn, sha=plugin_sha, status="FAIL", ref="plugin-candidate")
        add_regression(
            conn,
            regression_id=1,
            sha=memory_sha,
            task_id="MEMORY-INTELLIGENCE-CANDIDATE",
            ref=memory_sha,
        )
        add_regression(
            conn,
            regression_id=2,
            sha=plugin_sha,
            task_id="BRAIN-PLUGIN-CANDIDATE",
            ref=plugin_sha,
        )
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            add_device_proof(conn, root, sha=SHA)
            before = [tuple(row) for row in conn.execute("select * from regressions order by id")]
            cert = build_certificate(
                conn,
                device_contracts(),
                "M",
                integration_sha=SHA,
                root=root,
                timestamp="2026-09-24T00:00:00+00:00",
            )
            after = [tuple(row) for row in conn.execute("select * from regressions order by id")]
        self.assertTrue(cert["valid"])
        self.assertEqual("PASS", cert["status"])
        self.assertEqual(2, cert["open_regression_count"])
        self.assertEqual(0, cert["blocking_regression_count"])
        self.assertEqual(2, len(cert["nonblocking_regressions"]))
        self.assertEqual({memory_sha, plugin_sha}, {row["sha"] for row in cert["nonblocking_regressions"]})
        self.assertEqual(before, after)

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
