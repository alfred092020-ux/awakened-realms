import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

import logres_visual_truth as vt
from logres_visual_truth import (
    durable_record,
    ensure_schema,
    flush_spool,
    history,
    latest,
    record,
    regressions,
)

S = "a" * 40


class VisualTruthTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(":memory:")
        self.c.row_factory = sqlite3.Row
        ensure_schema(self.c)

    def test_pass_requires_reference_and_metrics(self):
        with self.assertRaises(ValueError):
            record(
                self.c,
                sha=S,
                checkpoint="title",
                observed_artifact="o.png",
                verdict="PASS",
            )

    def test_latest_is_append_only(self):
        record(
            self.c,
            sha=S,
            checkpoint="title",
            observed_artifact="o1",
            verdict="REVIEW",
        )
        record(
            self.c,
            sha=S,
            checkpoint="title",
            observed_artifact="o2",
            verdict="FAIL",
        )
        self.assertEqual("o2", latest(self.c, "title")["observed_artifact"])

    def test_regression_requires_prior_pass_then_fail(self):
        record(
            self.c,
            sha=S,
            checkpoint="title",
            observed_artifact="o1",
            verdict="PASS",
            reference_artifact="r",
            metrics={"ssim": 1},
        )
        record(
            self.c,
            sha=S,
            checkpoint="title",
            observed_artifact="o2",
            verdict="FAIL",
            reference_artifact="r",
            metrics={"ssim": 0.5},
        )
        self.assertEqual(1, len(regressions(self.c)))

    def test_established_schema_record_and_reads_execute_no_ddl(self):
        statements = []
        self.c.set_trace_callback(statements.append)
        record(
            self.c,
            sha=S,
            checkpoint="field",
            observed_artifact="field.png",
            verdict="REVIEW",
            metrics={"width": 720, "height": 1280},
        )
        latest(self.c, "field")
        history(self.c, "field")
        self.c.set_trace_callback(None)

        ddl = [
            sql
            for sql in statements
            if sql.lstrip().upper().startswith(("CREATE ", "DROP ", "ALTER "))
        ]
        self.assertEqual([], ddl)

    def test_uninitialized_schema_fails_closed_without_creating_it(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        with self.assertRaises(sqlite3.OperationalError):
            record(
                conn,
                sha=S,
                checkpoint="title",
                observed_artifact="o.png",
                verdict="REVIEW",
            )
        table = conn.execute(
            "select 1 from sqlite_master "
            "where type='table' and name='visual_truth_checks'"
        ).fetchone()
        self.assertIsNone(table)

    def test_direct_durable_record_commits_without_spool(self):
        with tempfile.TemporaryDirectory() as td:
            result = durable_record(
                self.c,
                Path(td),
                sha=S,
                checkpoint="title",
                observed_artifact="title.png",
                verdict="REVIEW",
                metrics={"width": 720},
                created_at="2026-09-24T19:20:00+00:00",
            )
            self.assertFalse(result["spooled"])
            self.assertIsInstance(result["id"], int)
            self.assertEqual([], list(Path(td).glob("*.json")))
            self.assertEqual("title.png", latest(self.c, "title")["observed_artifact"])

    def test_locked_db_spools_then_flushes_exactly_once(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "truth.sqlite"
            spool = root / "spool"

            setup = sqlite3.connect(db)
            setup.row_factory = sqlite3.Row
            ensure_schema(setup)
            setup.close()

            locker = sqlite3.connect(db, timeout=0.01)
            locker.execute("begin immediate")
            locker.execute(
                "insert into visual_truth_checks("
                "sha,checkpoint,observed_artifact,viewport_json,device_json,"
                "metrics_json,verdict,created_at,created_epoch"
                ") values(?,?,?,?,?,?,?,?,?)",
                (
                    "b" * 40,
                    "lock-holder",
                    "lock.png",
                    "{}",
                    "{}",
                    "{}",
                    "REVIEW",
                    "2026-09-24T19:20:00+00:00",
                    1790277600.0,
                ),
            )

            writer = sqlite3.connect(db, timeout=0.01)
            writer.row_factory = sqlite3.Row
            writer.execute("pragma busy_timeout=10")
            result = durable_record(
                writer,
                spool,
                sha=S,
                checkpoint="battle",
                observed_artifact="battle.png",
                verdict="PASS",
                reference_artifact="battle-ref",
                metrics={"dark_ratio": 0.1},
                created_at="2026-09-24T19:20:01+00:00",
            )
            self.assertTrue(result["spooled"])
            self.assertIsNone(result["id"])
            files = list(spool.glob("*.json"))
            self.assertEqual(1, len(files))
            envelope = json.loads(files[0].read_text())
            self.assertEqual(result["fingerprint"], envelope["fingerprint"])
            self.assertEqual("battle", envelope["record"]["checkpoint"])

            locker.rollback()
            locker.close()

            flushed = flush_spool(writer, spool, busy_timeout_ms=500)
            self.assertEqual(
                {
                    "flushed": 1,
                    "deduped": 0,
                    "remaining": 0,
                    "blocked": False,
                },
                flushed,
            )
            self.assertEqual(1, len(history(writer, "battle")))

            duplicate = vt._spool_payload(spool, envelope["record"])
            self.assertTrue(duplicate.exists())
            second = flush_spool(writer, spool, busy_timeout_ms=500)
            self.assertEqual(0, second["flushed"])
            self.assertEqual(1, second["deduped"])
            self.assertEqual(1, len(history(writer, "battle")))
            writer.close()

    def test_spool_write_failure_remains_fatal(self):
        class LockedConnection:
            def execute(self, *_args, **_kwargs):
                raise sqlite3.OperationalError("database is locked")

            def rollback(self):
                return None

        with tempfile.TemporaryDirectory() as td, mock.patch.object(
            vt,
            "_spool_payload",
            side_effect=OSError("disk unavailable"),
        ):
            with self.assertRaisesRegex(OSError, "disk unavailable"):
                durable_record(
                    LockedConnection(),
                    Path(td),
                    sha=S,
                    checkpoint="title",
                    observed_artifact="title.png",
                    verdict="REVIEW",
                    created_at="2026-09-24T19:20:02+00:00",
                )

    def test_non_lock_db_error_does_not_spool(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(sqlite3.OperationalError):
                durable_record(
                    conn,
                    Path(td),
                    sha=S,
                    checkpoint="title",
                    observed_artifact="title.png",
                    verdict="REVIEW",
                    created_at="2026-09-24T19:20:03+00:00",
                )
            self.assertEqual([], list(Path(td).glob("*.json")))

    def test_malformed_spool_is_quarantined_and_fails(self):
        with tempfile.TemporaryDirectory() as td:
            spool = Path(td)
            bad = spool / "bad.json"
            bad.write_text('{"schema": 1, "fingerprint": "wrong"}\n')
            with self.assertRaisesRegex(
                RuntimeError,
                "quarantined malformed visual-truth spool",
            ):
                flush_spool(self.c, spool)
            self.assertFalse(bad.exists())
            self.assertTrue((spool / "quarantine" / "bad.json").exists())

    def test_tampered_spool_epoch_is_quarantined(self):
        with tempfile.TemporaryDirectory() as td:
            spool = Path(td)
            payload = vt._payload(
                sha=S,
                checkpoint="title",
                observed_artifact="title.png",
                verdict="REVIEW",
                created_at="2026-09-24T19:20:05+00:00",
            )
            path = vt._spool_payload(spool, payload)
            envelope = json.loads(path.read_text())
            envelope["record"]["created_epoch"] += 1
            envelope["fingerprint"] = vt._fingerprint(envelope["record"])
            path.write_text(json.dumps(envelope))

            with self.assertRaisesRegex(
                RuntimeError,
                "quarantined malformed visual-truth spool",
            ):
                flush_spool(self.c, spool)
            self.assertTrue((spool / "quarantine" / path.name).exists())

    def test_locked_flush_is_bounded_and_preserves_spool(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "truth.sqlite"
            spool = root / "spool"

            setup = sqlite3.connect(db)
            setup.row_factory = sqlite3.Row
            ensure_schema(setup)
            payload = vt._payload(
                sha=S,
                checkpoint="field",
                observed_artifact="field.png",
                verdict="REVIEW",
                created_at="2026-09-24T19:20:04+00:00",
            )
            vt._spool_payload(spool, payload)
            setup.close()

            locker = sqlite3.connect(db, timeout=0.01)
            locker.execute("begin immediate")
            locker.execute(
                "insert into visual_truth_checks("
                "sha,checkpoint,observed_artifact,viewport_json,device_json,"
                "metrics_json,verdict,created_at,created_epoch"
                ") values(?,?,?,?,?,?,?,?,?)",
                (
                    "b" * 40,
                    "lock-holder",
                    "lock.png",
                    "{}",
                    "{}",
                    "{}",
                    "REVIEW",
                    "2026-09-24T19:20:00+00:00",
                    1790277600.0,
                ),
            )

            reader = sqlite3.connect(db, timeout=0.01)
            reader.row_factory = sqlite3.Row
            result = flush_spool(reader, spool, busy_timeout_ms=5)
            self.assertTrue(result["blocked"])
            self.assertEqual(1, result["remaining"])
            self.assertEqual(1, len(list(spool.glob("*.json"))))
            reader.close()
            locker.rollback()
            locker.close()


if __name__ == "__main__":
    unittest.main()
