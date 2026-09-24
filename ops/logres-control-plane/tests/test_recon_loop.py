from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[3]
LIB = REPO / "ops/logres-control-plane/lib/logres_recon_loop.py"

spec = importlib.util.spec_from_file_location("logres_recon_loop_test", LIB)
loop = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = loop
spec.loader.exec_module(loop)


class Process:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def write_json(path: Path, value: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return loop.sha256_file(path)


class ReconLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.db_path = self.root / "control.sqlite"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """
            create table tasks(
              id text primary key,
              priority integer,
              lane text,
              title text,
              status text,
              branch text,
              owner text,
              note text,
              updated_at text
            )
            """
        )
        self.conn.commit()

        self.scope = (
            "src/game/logres/encounter/ReconstructedLogresEncounterAuthority.ts"
        )
        self.test_path = "tests/ReconstructedLogresEncounterAuthority.test.ts"
        scope_file = self.repo / self.scope
        scope_file.parent.mkdir(parents=True)
        scope_file.write_text("export const accepted = true\n")
        test_file = self.repo / self.test_path
        test_file.parent.mkdir(parents=True)
        test_file.write_text("export const testSentinel = true\n")

        self.certified = self.root / "certified.json"
        self.current = self.root / "current.json"
        self.truth = self.root / "truth.json"
        self.consistency = self.root / "consistency.json"
        self.trace = self.root / "trace.json"
        self.synthesis = self.root / "synthesis.json"

        write_json(
            self.certified,
            {
                "divergences": [
                    {
                        "id": "gap",
                        "classification": "IMPLEMENTATION_BUG",
                    }
                ],
                "implementation_packets": [
                    {"id": "PACKET-1"}
                ],
            },
        )
        write_json(
            self.current,
            {
                "divergences": [],
                "implementation_packets": [],
            },
        )
        write_json(
            self.truth,
            {
                "read_only": True,
                "stats": {"status": "RESOLVED"},
                "contradictions": [],
            },
        )
        write_json(
            self.consistency,
            {
                "status": "PASS",
                "invariant_counts": {"failed": 0},
            },
        )
        write_json(
            self.trace,
            {
                "offline_only": True,
                "certificate_id": "trace-1",
            },
        )
        self.write_synthesis("BOUNDED_PATCH_REQUIRED")

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def write_synthesis(
        self,
        status: str,
        *,
        files=None,
        active=True,
        tie=False,
    ):
        if files is None:
            files = [self.scope]
        payload = {
            "status": status,
            "packet": {
                "id": "PACKET-1",
                "classification": "IMPLEMENTATION_BUG",
                "scope": [self.scope],
                "acceptance": [
                    "Preserve exact accepted response behavior.",
                    "Preserve exact retry behavior.",
                ],
            },
            "delta": {
                "files_to_modify": files,
            },
            "predicates": {
                "active_gap_exists": active,
                "same_authority_contradiction_tie": tie,
            },
            "evidence": {
                "certified_differential": {
                    "path": str(self.certified),
                    "sha256": loop.sha256_file(self.certified),
                },
                "current_differential": {
                    "path": str(self.current),
                    "sha256": loop.sha256_file(self.current),
                },
                "truth_kernel": {
                    "path": str(self.truth),
                    "sha256": loop.sha256_file(self.truth),
                },
                "consistency_certificate": {
                    "path": str(self.consistency),
                    "sha256": loop.sha256_file(self.consistency),
                },
                "trace_certificate": {
                    "path": str(self.trace),
                    "sha256": loop.sha256_file(self.trace),
                },
                "current_scope_source_hashes": {
                    self.scope: loop.sha256_file(self.repo / self.scope),
                },
                "targeted_tests": [
                    {
                        "path": self.test_path,
                        "sha256": loop.sha256_file(
                            self.repo / self.test_path
                        ),
                    }
                ],
            },
            "rollback_predicate": {
                "invalidate_synthesis_if_any": [
                    "current gap returns",
                    "source hash changes",
                ]
            },
            "historical_authority_policy": {
                "retired_server_semantics_may_be_invented": False,
                "unknown_server_semantics_remain_unknown": True,
            },
        }
        write_json(self.synthesis, payload)

    def create_runner(self, calls):
        def runner(argv, **kwargs):
            calls.append(list(argv))
            task_id = argv[2]
            lane = argv[4]
            self.conn.execute(
                """
                insert into tasks(
                  id,priority,lane,title,status,updated_at
                ) values(?,?,?,?,?,?)
                """,
                (
                    task_id,
                    int(argv[3]),
                    lane,
                    argv[5],
                    "READY",
                    loop.utc_now(),
                ),
            )
            self.conn.commit()
            return Process(0, "created", "")
        return runner

    def test_plan_is_read_only_and_does_not_create_history_schema(self):
        repair = loop.plan(
            self.conn,
            synthesis_path=self.synthesis,
            repo=self.repo,
        )
        self.assertEqual("REPAIR_READY", repair.status)
        table = self.conn.execute(
            """
            select name from sqlite_master
             where type='table' and name='recon_loop_repairs'
            """
        ).fetchone()
        self.assertIsNone(table)

    def test_zero_delta_does_not_issue_repair(self):
        self.write_synthesis(
            "ZERO_DELTA_ALREADY_SATISFIED",
            files=[],
            active=False,
        )
        repair = loop.plan(
            self.conn,
            synthesis_path=self.synthesis,
            repo=self.repo,
        )
        self.assertEqual("NO_REPAIR_REQUIRED", repair.status)
        self.assertIsNone(repair.repair_task_id)
        self.assertEqual((), repair.scopes)

    def test_evidence_hash_drift_fails_closed(self):
        (self.repo / self.scope).write_text("changed\n")
        repair = loop.plan(
            self.conn,
            synthesis_path=self.synthesis,
            repo=self.repo,
        )
        self.assertEqual("STOP_EVIDENCE_HASH_DRIFT", repair.status)
        self.assertIn("source hash drift", repair.reason)

    def test_current_differential_artifact_hash_drift_fails_closed_before_first_issue(self):
        write_json(
            self.current,
            {
                "divergences": [
                    {
                        "id": "mutated-after-synthesis",
                        "classification": "IMPLEMENTATION_BUG",
                    }
                ],
                "implementation_packets": [
                    {"id": "PACKET-1"},
                ],
            },
        )
        with self.assertRaises(loop.ReconLoopError) as ctx:
            loop.plan(
                self.conn,
                synthesis_path=self.synthesis,
                repo=self.repo,
            )
        self.assertIn(
            "evidence hash drift for current_differential",
            str(ctx.exception),
        )

    def test_scope_expansion_fails_closed(self):
        self.write_synthesis(
            "BOUNDED_PATCH_REQUIRED",
            files=["src/game/logres/other.ts"],
        )
        repair = loop.plan(
            self.conn,
            synthesis_path=self.synthesis,
            repo=self.repo,
        )
        self.assertEqual("STOP_SCOPE_VIOLATION", repair.status)

    def test_same_authority_tie_stops_repair(self):
        self.write_synthesis(
            "BOUNDED_PATCH_REQUIRED",
            tie=True,
        )
        repair = loop.plan(
            self.conn,
            synthesis_path=self.synthesis,
            repo=self.repo,
        )
        self.assertEqual(
            "STOP_SAME_AUTHORITY_CONTRADICTION_TIE",
            repair.status,
        )

    def test_external_evidence_ceiling_never_becomes_implementation_work(self):
        self.write_synthesis(
            "BLOCKED_EXTERNAL_CEILING",
            files=[],
            active=False,
        )
        repair = loop.plan(
            self.conn,
            synthesis_path=self.synthesis,
            repo=self.repo,
        )
        self.assertEqual("STOP_EXTERNAL_EVIDENCE_CEILING", repair.status)

    def test_issue_creates_one_bounded_implementation_task(self):
        calls = []
        result = loop.issue(
            self.conn,
            synthesis_path=self.synthesis,
            repo=self.repo,
            coordinator="/fake/coordinator",
            runner=self.create_runner(calls),
        )
        self.assertTrue(result["created"])
        task_id = result["task_id"]
        self.assertTrue(task_id.startswith("RECON-REPAIR-"))
        self.assertFalse(task_id.startswith(("AUTO-RE", "UNBLOCK")))

        row = self.conn.execute(
            "select status,lane from tasks where id=?",
            (task_id,),
        ).fetchone()
        self.assertEqual("READY", row["status"])
        self.assertEqual("reconstruction-repair", row["lane"])

        argv = calls[0]
        self.assertIn("--work-type", argv)
        self.assertEqual("implementation", argv[argv.index("--work-type") + 1])
        self.assertIn("--scope", argv)
        self.assertIn(self.scope, argv)
        self.assertNotIn("merge", argv)
        self.assertNotIn("deploy", argv)

        history = loop.history(self.conn)
        self.assertEqual(1, len(history))
        self.assertEqual("ISSUED", history[0]["status"])

    def test_same_fingerprint_is_never_issued_twice(self):
        calls = []
        first = loop.issue(
            self.conn,
            synthesis_path=self.synthesis,
            repo=self.repo,
            coordinator="/fake/coordinator",
            runner=self.create_runner(calls),
        )
        second = loop.issue(
            self.conn,
            synthesis_path=self.synthesis,
            repo=self.repo,
            coordinator="/fake/coordinator",
            runner=self.create_runner(calls),
        )
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual("ALREADY_ISSUED", second["plan"]["status"])
        self.assertEqual(1, len(calls))

    def test_reconcile_requires_terminal_task_and_both_fresh_artifacts(self):
        calls = []
        issued = loop.issue(
            self.conn,
            synthesis_path=self.synthesis,
            repo=self.repo,
            coordinator="/fake/coordinator",
            runner=self.create_runner(calls),
        )
        fp = issued["plan"]["fingerprint"]

        active = loop.reconcile_one(
            self.conn,
            fp,
            current_differential=self.current,
            trace_certificate=self.trace,
        )
        self.assertEqual("REPAIR_IN_PROGRESS", active["status"])

        self.conn.execute(
            "update tasks set status='DONE' where id=?",
            (issued["task_id"],),
        )
        self.conn.commit()

        stale = loop.reconcile_one(
            self.conn,
            fp,
            current_differential=self.current,
            trace_certificate=self.trace,
        )
        self.assertEqual("AWAITING_FRESH_VERIFICATION", stale["status"])
        self.assertFalse(stale["differential_fresh"])
        self.assertFalse(stale["trace_fresh"])

    def test_fresh_clean_differential_and_trace_close_repair(self):
        calls = []
        issued = loop.issue(
            self.conn,
            synthesis_path=self.synthesis,
            repo=self.repo,
            coordinator="/fake/coordinator",
            runner=self.create_runner(calls),
        )
        fp = issued["plan"]["fingerprint"]
        self.conn.execute(
            "update tasks set status='DONE' where id=?",
            (issued["task_id"],),
        )
        self.conn.commit()

        write_json(
            self.current,
            {
                "divergences": [],
                "implementation_packets": [],
                "fresh": True,
            },
        )
        write_json(
            self.trace,
            {
                "offline_only": True,
                "certificate_id": "trace-2",
            },
        )
        result = loop.reconcile_one(
            self.conn,
            fp,
            current_differential=self.current,
            trace_certificate=self.trace,
        )
        self.assertEqual("VERIFIED_CLOSED", result["status"])
        self.assertFalse(result["automatic_repair_reissued"])
        self.assertFalse(result["automatic_merge"])
        self.assertFalse(result["automatic_deploy"])

    def test_surviving_divergence_exhausts_same_fingerprint_without_retry(self):
        calls = []
        issued = loop.issue(
            self.conn,
            synthesis_path=self.synthesis,
            repo=self.repo,
            coordinator="/fake/coordinator",
            runner=self.create_runner(calls),
        )
        fp = issued["plan"]["fingerprint"]
        self.conn.execute(
            "update tasks set status='DONE' where id=?",
            (issued["task_id"],),
        )
        self.conn.commit()

        write_json(
            self.current,
            {
                "divergences": [
                    {
                        "id": "still-broken",
                        "classification": "IMPLEMENTATION_BUG",
                    }
                ],
                "implementation_packets": [{"id": "PACKET-1"}],
                "fresh": True,
            },
        )
        write_json(
            self.trace,
            {
                "offline_only": True,
                "certificate_id": "trace-2",
            },
        )
        result = loop.reconcile_one(
            self.conn,
            fp,
            current_differential=self.current,
            trace_certificate=self.trace,
        )
        self.assertEqual(
            "REPAIR_EXHAUSTED_SAME_FINGERPRINT",
            result["status"],
        )
        self.assertFalse(result["automatic_repair_reissued"])

        again = loop.plan(
            self.conn,
            synthesis_path=self.synthesis,
            repo=self.repo,
        )
        self.assertEqual("ALREADY_ISSUED", again.status)
        self.assertEqual(1, len(calls))


if __name__ == "__main__":
    unittest.main()
