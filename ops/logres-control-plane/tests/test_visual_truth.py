import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from logres_visual_truth import ensure_schema, history, latest, record, regressions

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
            "select 1 from sqlite_master where type='table' and name='visual_truth_checks'"
        ).fetchone()
        self.assertIsNone(table)


if __name__ == "__main__":
    unittest.main()
