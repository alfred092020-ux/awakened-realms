import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/logres/merge_visual_truth_records.py"
VISUAL_LIB = (
    REPO
    / "ops/logres-control-plane/lib/logres_visual_truth.py"
)

spec = importlib.util.spec_from_file_location(
    "logres_visual_truth_merge_test",
    SCRIPT,
)
merge_module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(merge_module)

visual_spec = importlib.util.spec_from_file_location(
    "logres_visual_truth_lib_test",
    VISUAL_LIB,
)
visual = importlib.util.module_from_spec(visual_spec)
assert visual_spec.loader is not None
visual_spec.loader.exec_module(visual)


SHA = "a" * 40


def make_db(
    path: Path,
) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    visual.ensure_schema(conn)
    return conn


def record_sample(
    conn: sqlite3.Connection,
    *,
    checkpoint: str = "title",
    observed: str = "observed.png",
    created_at: str = "2026-09-24T19:15:00+00:00",
) -> int:
    return visual.record(
        conn,
        sha=SHA,
        checkpoint=checkpoint,
        objective_id="DEMO-0.2",
        reference_artifact="reference.png",
        observed_artifact=observed,
        viewport={
            "width": 720,
            "height": 1280,
            "source": "playwright-canvas",
        },
        device={
            "runner": "canonical-playwright",
            "gate": "structural",
        },
        metrics={
            "width": 720,
            "height": 1280,
            "structural_provenance": {
                "assets": "RECOVERED_GLOBAL",
            },
        },
        verdict="REVIEW",
        created_at=created_at,
    )


class VisualTruthMergeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "isolated.sqlite"
        self.target = self.root / "canonical.sqlite"

    def tearDown(self):
        self.temp.cleanup()

    def test_merges_exact_row_preserving_sha_and_provenance_fields(self):
        source = make_db(self.source)
        target = make_db(self.target)
        try:
            record_sample(source)
        finally:
            source.close()
            target.close()

        result = merge_module.merge(
            source=self.source,
            target=self.target,
            busy_timeout_ms=500,
        )

        self.assertEqual("PASS", result["status"])
        self.assertEqual(1, result["inserted_rows"])
        self.assertEqual(0, result["deduped_rows"])

        conn = sqlite3.connect(self.target)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                """select sha,checkpoint,objective_id,reference_artifact,
                          observed_artifact,viewport_json,device_json,
                          metrics_json,verdict,created_at,created_epoch
                     from visual_truth_checks"""
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(SHA, row["sha"])
        self.assertEqual("title", row["checkpoint"])
        self.assertEqual("DEMO-0.2", row["objective_id"])
        self.assertEqual("reference.png", row["reference_artifact"])
        self.assertEqual("observed.png", row["observed_artifact"])
        self.assertEqual("REVIEW", row["verdict"])
        metrics = json.loads(row["metrics_json"])
        self.assertEqual(
            "RECOVERED_GLOBAL",
            metrics["structural_provenance"]["assets"],
        )

    def test_retry_is_idempotent_and_does_not_duplicate_rows(self):
        source = make_db(self.source)
        target = make_db(self.target)
        try:
            record_sample(source)
        finally:
            source.close()
            target.close()

        first = merge_module.merge(
            source=self.source,
            target=self.target,
            busy_timeout_ms=500,
        )
        second = merge_module.merge(
            source=self.source,
            target=self.target,
            busy_timeout_ms=500,
        )

        self.assertEqual(1, first["inserted_rows"])
        self.assertEqual(0, second["inserted_rows"])
        self.assertEqual(1, second["deduped_rows"])

        conn = sqlite3.connect(self.target)
        try:
            count = conn.execute(
                "select count(*) from visual_truth_checks"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(1, count)

    def test_distinct_source_truth_rows_are_preserved(self):
        source = make_db(self.source)
        target = make_db(self.target)
        try:
            record_sample(
                source,
                checkpoint="title",
                observed="title.png",
            )
            record_sample(
                source,
                checkpoint="battle",
                observed="battle.png",
                created_at="2026-09-24T19:15:01+00:00",
            )
        finally:
            source.close()
            target.close()

        result = merge_module.merge(
            source=self.source,
            target=self.target,
            busy_timeout_ms=500,
        )

        self.assertEqual(2, result["inserted_rows"])
        self.assertEqual(0, result["deduped_rows"])

    def test_transient_canonical_lock_retries_then_merges(self):
        source = make_db(self.source)
        initial_target = make_db(self.target)
        try:
            record_sample(source)
        finally:
            source.close()
            initial_target.close()

        target = sqlite3.connect(
            self.target,
            check_same_thread=False,
        )
        target.execute("begin exclusive")
        release = threading.Timer(
            0.08,
            target.rollback,
        )
        release.start()
        try:
            result = merge_module.merge(
                source=self.source,
                target=self.target,
                busy_timeout_ms=25,
            )
        finally:
            release.join(timeout=1)
            target.close()

        self.assertEqual("PASS", result["status"])
        self.assertGreaterEqual(result["lock_retry_count"], 1)
        self.assertLessEqual(
            result["lock_attempts"],
            merge_module.MAX_LOCK_ATTEMPTS,
        )
        conn = sqlite3.connect(self.target)
        try:
            count = conn.execute(
                "select count(*) from visual_truth_checks"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(1, count)

    def test_persistent_lock_durably_spools_then_flushes_exactly_once(self):
        source = make_db(self.source)
        initial_target = make_db(self.target)
        try:
            record_sample(source)
        finally:
            source.close()
            initial_target.close()

        spool = self.root / "visual-spool"
        holder = sqlite3.connect(self.target)
        holder.execute("begin immediate")
        try:
            result = merge_module.merge(
                source=self.source,
                target=self.target,
                busy_timeout_ms=10,
                spool_dir=spool,
            )
        finally:
            holder.rollback()
            holder.close()

        self.assertEqual("PASS", result["status"])
        self.assertEqual("DURABLE_SPOOL", result["persistence_mode"])
        self.assertEqual(1, result["source_rows"])
        self.assertEqual(0, result["canonical_direct_rows"])
        self.assertEqual(1, result["spooled_rows"])
        self.assertTrue(result["canonical_flush_required"])
        self.assertFalse(result["evidence_loss"])
        self.assertEqual(1, len(result["spool_paths"]))
        self.assertTrue(Path(result["spool_paths"][0]).is_file())

        writer = sqlite3.connect(self.target)
        writer.row_factory = sqlite3.Row
        try:
            flushed = visual.flush_spool(
                writer,
                spool,
                busy_timeout_ms=500,
            )
            self.assertEqual(1, flushed["flushed"])
            self.assertEqual(0, flushed["deduped"])
            self.assertEqual(0, flushed["remaining"])

            second = visual.flush_spool(
                writer,
                spool,
                busy_timeout_ms=500,
            )
            self.assertEqual(0, second["flushed"])
            self.assertEqual(0, second["remaining"])

            count = writer.execute(
                "select count(*) from visual_truth_checks"
            ).fetchone()[0]
            self.assertEqual(1, count)
        finally:
            writer.close()

    def test_spool_fallback_rejects_malformed_isolated_json(self):
        source = make_db(self.source)
        initial_target = make_db(self.target)
        try:
            record_sample(source)
            source.execute(
                "update visual_truth_checks set viewport_json='[]'"
            )
            source.commit()
        finally:
            source.close()
            initial_target.close()

        holder = sqlite3.connect(self.target)
        holder.execute("begin immediate")
        try:
            with self.assertRaisesRegex(
                merge_module.MergeError,
                "viewport_json must be a JSON object",
            ):
                merge_module.merge(
                    source=self.source,
                    target=self.target,
                    busy_timeout_ms=10,
                    spool_dir=self.root / "spool",
                )
        finally:
            holder.rollback()
            holder.close()

        self.assertEqual(
            [],
            list((self.root / "spool").glob("*.json")),
        )

    def test_cli_can_acknowledge_durable_spool_under_persistent_lock(self):
        source = make_db(self.source)
        initial_target = make_db(self.target)
        try:
            record_sample(source)
        finally:
            source.close()
            initial_target.close()

        spool = self.root / "cli-spool"
        holder = sqlite3.connect(self.target)
        holder.execute("begin immediate")
        try:
            run = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--source",
                    str(self.source),
                    "--target",
                    str(self.target),
                    "--busy-timeout-ms",
                    "10",
                    "--spool-dir",
                    str(spool),
                ],
                cwd=REPO,
                text=True,
                capture_output=True,
            )
        finally:
            holder.rollback()
            holder.close()

        self.assertEqual(0, run.returncode, run.stdout + run.stderr)
        payload = json.loads(run.stdout)
        self.assertEqual("PASS", payload["status"])
        self.assertEqual("DURABLE_SPOOL", payload["persistence_mode"])
        self.assertEqual(1, payload["spooled_rows"])
        self.assertEqual(1, len(list(spool.glob("*.json"))))

    def test_locked_canonical_database_fails_closed_with_bounded_timeout(self):
        source = make_db(self.source)
        target = make_db(self.target)
        try:
            record_sample(source)
            target.execute("begin exclusive")
            with self.assertRaises(merge_module.MergeError) as ctx:
                merge_module.merge(
                    source=self.source,
                    target=self.target,
                    busy_timeout_ms=50,
                )
            self.assertIn(
                "locked",
                str(ctx.exception).lower(),
            )
        finally:
            try:
                target.rollback()
            except sqlite3.Error:
                pass
            source.close()
            target.close()

    def test_cli_returns_nonzero_on_lock_failure(self):
        source = make_db(self.source)
        target = make_db(self.target)
        try:
            record_sample(source)
            target.execute("begin exclusive")
            run = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--source",
                    str(self.source),
                    "--target",
                    str(self.target),
                    "--busy-timeout-ms",
                    "50",
                ],
                cwd=REPO,
                text=True,
                capture_output=True,
            )
            self.assertEqual(2, run.returncode)
            payload = json.loads(run.stdout)
            self.assertEqual("FAIL", payload["status"])
            self.assertIn(
                "locked",
                payload["message"].lower(),
            )
        finally:
            try:
                target.rollback()
            except sqlite3.Error:
                pass
            source.close()
            target.close()

    def test_source_and_target_must_be_different_databases(self):
        conn = make_db(self.source)
        conn.close()
        with self.assertRaises(merge_module.MergeError):
            merge_module.merge(
                source=self.source,
                target=self.source,
                busy_timeout_ms=500,
            )

    def test_missing_canonical_schema_fails_closed_without_creating_it(self):
        source = make_db(self.source)
        source.close()
        sqlite3.connect(self.target).close()

        with self.assertRaises(merge_module.MergeError):
            merge_module.merge(
                source=self.source,
                target=self.target,
                busy_timeout_ms=500,
            )

        conn = sqlite3.connect(self.target)
        try:
            row = conn.execute(
                """select name from sqlite_master
                    where type='table'
                      and name='visual_truth_checks'"""
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNone(row)


if __name__ == "__main__":
    unittest.main()
