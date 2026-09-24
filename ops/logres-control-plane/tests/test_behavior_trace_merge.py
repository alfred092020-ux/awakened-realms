import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
REPO_ROOT = CONTROL_ROOT.parents[1]
LIB_DIR = CONTROL_ROOT / "lib"
MERGER = REPO_ROOT / "scripts" / "logres" / "merge_behavior_trace_records.py"
sys.path.insert(0, str(LIB_DIR))

from logres_behavior_trace import ensure_schema, record


def load_merger():
    spec = importlib.util.spec_from_file_location(
        "merge_behavior_trace_records_test",
        MERGER,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BehaviorTraceMergeTests(unittest.TestCase):
    def test_isolated_record_merges_idempotently(self):
        module = load_merger()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.sqlite"
            target = root / "target.sqlite"

            src = sqlite3.connect(source)
            tgt = sqlite3.connect(target)
            ensure_schema(src)
            ensure_schema(tgt)
            payload = {
                "events": ["FIELD_READY", "BATTLE_ACTIVE"],
                "final_state": {"mode": "battle"},
            }
            recorded = record(
                src,
                sha="a" * 40,
                checkpoint="checkpoint",
                expected=payload,
                observed=payload,
                objective_id="BEHAVIORAL_FIDELITY",
                provenance={"kind": "RECONSTRUCTED"},
            )
            self.assertEqual("PASS", recorded["verdict"])
            src.close()
            tgt.close()

            first = module.merge(
                source=source,
                target=target,
                busy_timeout_ms=1000,
            )
            second = module.merge(
                source=source,
                target=target,
                busy_timeout_ms=1000,
            )

            self.assertEqual(1, first["inserted_rows"])
            self.assertEqual(0, second["inserted_rows"])
            self.assertEqual(1, second["deduped_rows"])
            conn = sqlite3.connect(target)
            self.assertEqual(
                1,
                conn.execute(
                    "select count(*) from behavior_trace_checks"
                ).fetchone()[0],
            )
            conn.close()

    def test_missing_target_schema_fails_closed(self):
        module = load_merger()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.sqlite"
            target = root / "target.sqlite"
            src = sqlite3.connect(source)
            ensure_schema(src)
            src.close()
            sqlite3.connect(target).close()

            with self.assertRaisesRegex(
                module.MergeError,
                "missing columns",
            ):
                module.merge(
                    source=source,
                    target=target,
                    busy_timeout_ms=1000,
                )

    def test_source_and_target_must_differ(self):
        module = load_merger()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "same.sqlite"
            conn = sqlite3.connect(path)
            ensure_schema(conn)
            conn.close()

            with self.assertRaisesRegex(
                module.MergeError,
                "must differ",
            ):
                module.merge(
                    source=path,
                    target=path,
                    busy_timeout_ms=1000,
                )


if __name__ == "__main__":
    unittest.main()
