import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
BIN_DIR = TEST_DIR.parent / "bin"
sys.path.insert(0, str(LIB_DIR))

from logres_temporal import (
    TemporalBackfillError,
    fact_at_date,
    lattice_stats,
    load_lattice,
    query_entities,
)


def make_lattice(path: Path):
    payload = {
        "provenance": "HYPERDIMENSION_VERSION_SCOPED_TEMPORAL_EVIDENCE_LATTICE",
        "lattice_id": "lattice-1",
        "sealed_evidence_merkle_root": "m" * 64,
        "snapshots": [
            {
                "id": "GLOBAL_3_0_24_2017_05_25",
                "date": "2017-05-25",
                "authority": "HISTORICAL_TARGET",
            },
            {
                "id": "CURRENT_JP_2026_09_24",
                "date": "2026-09-24",
                "authority": "LINEAGE_REFERENCE_ONLY",
            },
        ],
        "sources": {
            "protocol_schema": {
                "path": "/evidence/protocol.json",
                "sha256": "a" * 64,
            }
        },
        "counts": {"entities": 2},
        "temporal_policy": {
            "endpoint_identity": "endpoint only",
        },
        "entities": [
            {
                "entity_id": "protocol:LOGIN",
                "kind": "protocol_message",
                "name": "LOGIN",
                "relation": "ENDPOINTS_OPCODE_STABLE_SCHEMA_CHANGED",
                "source_lineage_grade": "JP_LINEAGE_OPCODE_STABLE_SCHEMA_CHANGED",
                "global": {
                    "snapshot": "GLOBAL_3_0_24_2017_05_25",
                    "present": True,
                    "opcode_hex": "0x01",
                    "normalized_args": ["string", "string"],
                },
                "current_jp": {
                    "snapshot": "CURRENT_JP_2026_09_24",
                    "present": True,
                    "opcode_hex": "0x01",
                    "normalized_args": ["ClientLoginInfo"],
                },
                "temporal_uncertainty": {
                    "continuous_history_proven": False,
                    "change_interval": {
                        "after": "2017-05-25",
                        "on_or_before": "2026-09-24",
                        "exact_change_time_known": False,
                    },
                },
            },
            {
                "entity_id": "resource:TITLE",
                "kind": "resource",
                "name": "gui/title.png",
                "relation": "ENDPOINTS_BYTES_IDENTICAL_SAME_PATH",
                "source_lineage_grade": "GLOBAL_JP_IDENTICAL",
                "global": {
                    "snapshot": "GLOBAL_3_0_24_2017_05_25",
                    "present": True,
                    "path": "gui/title.png",
                    "sha1": "x",
                },
                "current_jp": {
                    "snapshot": "CURRENT_JP_2026_09_24",
                    "present": True,
                    "paths": ["gui/title.png"],
                },
                "temporal_uncertainty": {
                    "continuous_history_proven": False,
                    "statement": "endpoint only",
                },
            },
        ],
    }
    path.write_text(json.dumps(payload))
    return payload


class TemporalQueryTests(unittest.TestCase):
    def test_query_by_entity_relation_grade_and_kind(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "lattice.json"
            lattice = make_lattice(path)
            loaded = load_lattice(path)
            out = query_entities(
                loaded,
                entity="login",
                relation="ENDPOINTS_OPCODE_STABLE_SCHEMA_CHANGED",
                evidence_grade="JP_LINEAGE_OPCODE_STABLE_SCHEMA_CHANGED",
                kind="protocol_message",
            )
        self.assertEqual(lattice["lattice_id"], out["lattice_id"])
        self.assertEqual(1, out["count"])
        self.assertEqual("protocol:LOGIN", out["results"][0]["entity_id"])

    def test_version_query_returns_scoped_fact_plus_uncertainty(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "lattice.json"
            make_lattice(path)
            loaded = load_lattice(path)
            out = query_entities(
                loaded,
                entity="LOGIN",
                version="global",
            )
        row = out["results"][0]
        self.assertEqual("GLOBAL_3_0_24_2017_05_25", row["snapshot"])
        self.assertEqual(["string", "string"], row["fact"]["normalized_args"])
        self.assertFalse(
            row["temporal_uncertainty"]["continuous_history_proven"]
        )
        self.assertEqual("a" * 64, out["sources"]["protocol_schema"]["sha256"])

    def test_current_jp_query_does_not_flatten_over_global(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "lattice.json"
            make_lattice(path)
            out = query_entities(
                load_lattice(path),
                entity="LOGIN",
                version="jp",
            )
        row = out["results"][0]
        self.assertEqual("CURRENT_JP_2026_09_24", row["snapshot"])
        self.assertEqual(["ClientLoginInfo"], row["fact"]["normalized_args"])
        self.assertNotIn("facts", row)

    def test_exact_snapshot_date_is_allowed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "lattice.json"
            make_lattice(path)
            out = fact_at_date(
                load_lattice(path),
                "protocol:LOGIN",
                "2017-05-25",
            )
        self.assertEqual("GLOBAL_3_0_24_2017_05_25", out["snapshot"]["id"])
        self.assertEqual("0x01", out["fact"]["opcode_hex"])

    def test_intermediate_date_is_rejected_instead_of_backfilled(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "lattice.json"
            make_lattice(path)
            with self.assertRaises(TemporalBackfillError) as ctx:
                fact_at_date(
                    load_lattice(path),
                    "protocol:LOGIN",
                    "2020-01-01",
                )
        self.assertIn("Refusing to backfill", str(ctx.exception))

    def test_stats_preserve_sources_and_snapshots(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "lattice.json"
            make_lattice(path)
            out = lattice_stats(load_lattice(path))
        self.assertEqual(2, out["counts"]["entities"])
        self.assertEqual(2, len(out["snapshots"]))
        self.assertEqual("m" * 64, out["sealed_evidence_merkle_root"])

    def test_cli_emits_json_and_backfill_error_code(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "lattice.json"
            make_lattice(path)
            cmd = [
                sys.executable,
                str(BIN_DIR / "logres-temporal"),
                "--lattice",
                str(path),
                "query",
                "--entity",
                "LOGIN",
                "--version",
                "global",
            ]
            ok = subprocess.run(cmd, text=True, capture_output=True)
            self.assertEqual(0, ok.returncode)
            payload = json.loads(ok.stdout)
            self.assertEqual(1, payload["count"])

            bad = subprocess.run(
                [
                    sys.executable,
                    str(BIN_DIR / "logres-temporal"),
                    "--lattice",
                    str(path),
                    "at",
                    "protocol:LOGIN",
                    "2020-01-01",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(2, bad.returncode)
            error = json.loads(bad.stdout)
            self.assertEqual("TEMPORAL_BACKFILL_REJECTED", error["error"])


if __name__ == "__main__":
    unittest.main()
