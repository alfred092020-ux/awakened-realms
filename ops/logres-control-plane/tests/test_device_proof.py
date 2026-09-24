import importlib.machinery
import sqlite3
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
SCRIPT = TEST_DIR.parent / "bin" / "logres-device-proof"
loader = importlib.machinery.SourceFileLoader("logres_device_proof", str(SCRIPT))
proof = types.ModuleType(loader.name)
loader.exec_module(proof)


class DeviceProofPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "control.sqlite"
        self.sha = "a" * 40
        self.apk_sha = "b" * 64

    def tearDown(self):
        self.tmp.cleanup()

    def seed_schema(self):
        row_id, inserted = proof.persist_record(
            sha="0" * 40,
            apk_sha256=None,
            checkpoint="schema",
            status="PARTIAL",
            artifact_path=None,
            note="schema seed",
            db_path=self.db,
        )
        self.assertTrue(inserted)
        self.assertGreater(row_id, 0)

    def test_locked_writer_retries_until_proof_is_persisted(self):
        self.seed_schema()
        blocker = sqlite3.connect(
            self.db,
            timeout=0,
            check_same_thread=False,
        )
        blocker.execute("begin immediate")

        released = threading.Event()

        def unlock():
            time.sleep(0.12)
            blocker.commit()
            blocker.close()
            released.set()

        thread = threading.Thread(target=unlock)
        thread.start()
        try:
            row_id, inserted = proof.persist_record(
                sha=self.sha,
                apk_sha256=self.apk_sha,
                checkpoint="demo-0.2",
                status="PASS",
                artifact_path="/tmp/device-proof.json",
                note="contention test",
                db_path=self.db,
                busy_timeout_ms=15,
                retries=12,
                retry_delay_sec=0.02,
            )
        finally:
            thread.join(timeout=2)

        self.assertTrue(released.is_set())
        self.assertTrue(inserted)
        self.assertGreater(row_id, 0)
        conn = sqlite3.connect(self.db)
        count = conn.execute(
            "select count(*) from device_proofs where sha=?",
            (self.sha,),
        ).fetchone()[0]
        conn.close()
        self.assertEqual(1, count)

    def test_locked_writer_exhaustion_is_explicit_and_does_not_drop_fake_row(self):
        self.seed_schema()
        blocker = sqlite3.connect(self.db, timeout=0)
        blocker.execute("begin immediate")
        try:
            with self.assertRaisesRegex(
                proof.DeviceProofPersistenceError,
                "exhausted bounded SQLITE_BUSY retries",
            ):
                proof.persist_record(
                    sha=self.sha,
                    apk_sha256=self.apk_sha,
                    checkpoint="demo-0.2",
                    status="PASS",
                    artifact_path="/tmp/device-proof.json",
                    note="must fail explicitly",
                    db_path=self.db,
                    busy_timeout_ms=5,
                    retries=2,
                    retry_delay_sec=0.001,
                )
        finally:
            blocker.rollback()
            blocker.close()

        conn = sqlite3.connect(self.db)
        count = conn.execute(
            "select count(*) from device_proofs where sha=?",
            (self.sha,),
        ).fetchone()[0]
        conn.close()
        self.assertEqual(0, count)

    def test_reconcile_existing_json_is_idempotent_and_preserves_audit_fields(self):
        artifact = Path(self.tmp.name) / "device-proof.json"
        artifact.write_text(
            """{
  "schema_version": 2,
  "canonical_sha": "cccccccccccccccccccccccccccccccccccccccc",
  "status": "PASS",
  "apk": {
    "path": "/tmp/exact.apk",
    "sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
  }
}
"""
        )
        original_db = proof.DB
        proof.DB = self.db
        try:
            self.assertEqual(
                0,
                proof.main([
                    "reconcile",
                    str(artifact),
                    "--checkpoint",
                    "demo-0.2",
                ]),
            )
            self.assertEqual(
                0,
                proof.main([
                    "reconcile",
                    str(artifact),
                    "--checkpoint",
                    "demo-0.2",
                ]),
            )
        finally:
            proof.DB = original_db

        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "select * from device_proofs where sha=?",
            ("c" * 40,),
        ).fetchall()
        conn.close()
        self.assertEqual(1, len(rows))
        row = rows[0]
        self.assertEqual("d" * 64, row["apk_sha256"])
        self.assertEqual("demo-0.2", row["checkpoint"])
        self.assertEqual("PASS", row["status"])
        self.assertEqual(str(artifact.resolve()), row["artifact_path"])

    def test_same_logical_proof_record_is_idempotent(self):
        kwargs = dict(
            sha=self.sha,
            apk_sha256=self.apk_sha,
            checkpoint="demo-0.2",
            status="FAIL",
            artifact_path="/tmp/device-proof.json",
            note="first",
            db_path=self.db,
        )
        first_id, first_inserted = proof.persist_record(**kwargs)
        second_id, second_inserted = proof.persist_record(
            **{**kwargs, "note": "retry should not duplicate"}
        )
        self.assertTrue(first_inserted)
        self.assertFalse(second_inserted)
        self.assertEqual(first_id, second_id)


if __name__ == "__main__":
    unittest.main()
