import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
REPO_ROOT = TEST_DIR.parents[2]
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from fixtures import make_test_db
from logres_temporal import TemporalQueryError, query_temporal_lattice


def add_discovery_table(conn):
    conn.execute(
        """create table brain_discoveries(
             id integer primary key,
             ts text not null,
             author text not null,
             task_id text,
             confidence text not null,
             subject text not null,
             summary text not null,
             artifact_path text,
             artifact_sha256 text,
             status text not null default 'OPEN'
           )"""
    )
    conn.commit()


class TemporalQueryTests(unittest.TestCase):
    def test_query_filters_by_entity_version_change_and_grade(self):
        conn = make_test_db()
        add_discovery_table(conn)
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            a1 = base / "a1.json"
            a2 = base / "a2.json"
            a1.write_text(
                json.dumps(
                    {
                        "entity": "skill-tree",
                        "version": "global-2017",
                        "change_class": "changed",
                        "evidence_grade": "CONFIRMED ORIGINAL",
                        "fact": "Skill cooldown value changed",
                        "historical_predicate": True,
                    }
                )
            )
            a2.write_text(
                json.dumps(
                    {
                        "entity": "skill-tree",
                        "version": "current_jp",
                        "change_class": "persisted",
                        "evidence_grade": "CONFIRMED",
                        "fact": "Current JP still has cooldown",
                    }
                )
            )
            conn.execute(
                """insert into brain_discoveries(
                     id,ts,author,task_id,confidence,subject,summary,artifact_path,artifact_sha256,status
                   ) values(1,'now','finder','T1','CONFIRMED ORIGINAL','skill-tree','summary',?,?,'OPEN')""",
                (str(a1), "a" * 64),
            )
            conn.execute(
                """insert into brain_discoveries(
                     id,ts,author,task_id,confidence,subject,summary,artifact_path,artifact_sha256,status
                   ) values(2,'now','finder','T1','CONFIRMED','skill-tree','summary',?,?,'OPEN')""",
                (str(a2), "b" * 64),
            )
            conn.commit()

            out = query_temporal_lattice(
                conn,
                entity="skill-tree",
                version="global-2017",
                change_class="changed",
                evidence_grade="CONFIRMED ORIGINAL",
            )

        self.assertEqual(1, len(out["facts"]))
        self.assertEqual("Skill cooldown value changed", out["facts"][0]["fact"])
        self.assertEqual("a" * 64, out["facts"][0]["source_hashes"][0])

    def test_query_reports_interval_uncertainty(self):
        conn = make_test_db()
        add_discovery_table(conn)
        with tempfile.TemporaryDirectory() as td:
            artifact = Path(td) / "uncertain.json"
            artifact.write_text(
                json.dumps(
                    {
                        "entity": "market-tax",
                        "version": "global-2017",
                        "change_class": "unknowable",
                        "evidence_grade": "UNRESOLVED",
                        "interval_start": "2017-05",
                        "interval_end": "2018-01",
                        "interval_uncertain": True,
                        "unknown_interval_reason": "missing patch notes",
                        "historical_predicate": True,
                    }
                )
            )
            conn.execute(
                """insert into brain_discoveries(
                     id,ts,author,task_id,confidence,subject,summary,artifact_path,artifact_sha256,status
                   ) values(1,'now','finder','T1','UNRESOLVED','market-tax','summary',?,?,'OPEN')""",
                (str(artifact), "c" * 64),
            )
            conn.commit()

            out = query_temporal_lattice(conn, entity="market-tax", version="global-2017")

        self.assertEqual(1, len(out["interval_uncertainty"]))
        self.assertEqual("missing patch notes", out["interval_uncertainty"][0]["unknown_reason"])

    def test_query_rejects_current_jp_backfill_of_historical_interval(self):
        conn = make_test_db()
        add_discovery_table(conn)
        with tempfile.TemporaryDirectory() as td:
            artifact = Path(td) / "jp-only.json"
            artifact.write_text(
                json.dumps(
                    {
                        "entity": "login-flow",
                        "version": "current_jp",
                        "change_class": "changed",
                        "provenance": "CURRENT_JP_REFERENCE",
                        "fact": "Observed in current JP",
                    }
                )
            )
            conn.execute(
                """insert into brain_discoveries(
                     id,ts,author,task_id,confidence,subject,summary,artifact_path,artifact_sha256,status
                   ) values(1,'now','finder','T1','CONFIRMED','login-flow','summary',?,?,'OPEN')""",
                (str(artifact), "d" * 64),
            )
            conn.commit()

            with self.assertRaises(TemporalQueryError) as cm:
                query_temporal_lattice(conn, entity="login-flow", version="global-2017")

        self.assertIn("BLOCKED_EVIDENCE", str(cm.exception))

    def test_cli_outputs_json_error_for_blocked_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db_path = root / "control.sqlite"
            conn = make_test_db(str(db_path))
            add_discovery_table(conn)
            artifact = root / "jp-only.json"
            artifact.write_text(
                json.dumps(
                    {
                        "entity": "quest-state",
                        "version": "current_jp",
                        "change_class": "changed",
                        "provenance": "CURRENT_JP_REFERENCE",
                    }
                )
            )
            conn.execute(
                """insert into brain_discoveries(
                     id,ts,author,task_id,confidence,subject,summary,artifact_path,artifact_sha256,status
                   ) values(1,'now','finder','T1','CONFIRMED','quest-state','summary',?,?,'OPEN')""",
                (str(artifact), "e" * 64),
            )
            conn.commit()
            conn.close()

            script = REPO_ROOT / "ops" / "logres-control-plane" / "bin" / "logres-temporal"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "quest-state",
                    "--version",
                    "global-2017",
                    "--db",
                    str(db_path),
                ],
                capture_output=True,
                text=True,
            )

        self.assertEqual(2, completed.returncode)
        payload = json.loads(completed.stdout)
        self.assertIn("BLOCKED_EVIDENCE", payload["error"])


if __name__ == "__main__":
    unittest.main()
