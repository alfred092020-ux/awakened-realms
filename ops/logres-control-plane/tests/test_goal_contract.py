import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
LIB_DIR = CONTROL_ROOT / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_goal_contract import (
    evaluate_criterion,
    evaluate_milestone,
    load_contracts,
    validate_contracts,
)


def make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        create table tasks(
          id text primary key,
          status text not null
        );
        create table task_dependencies(
          task_id text not null,
          depends_on text not null,
          kind text not null,
          rationale text not null default ''
        );
        create table verification(
          ref text primary key,
          sha text,
          mode text,
          status text,
          duration_sec real,
          ran_at text,
          details text
        );
        """
    )
    return conn


def criterion(
    criterion_id,
    check,
    *,
    weight=1,
    task_template=None,
):
    item = {
        "id": criterion_id,
        "weight": weight,
        "description": criterion_id,
        "check": check,
    }
    if task_template is not None:
        item["task_template"] = task_template
    return item


class GoalContractTests(unittest.TestCase):
    def test_seed_demo_contract_is_valid_and_weights_sum_to_100(self):
        path = CONTROL_ROOT / "config" / "milestone_contracts.json"
        contracts = load_contracts(path)
        demo = contracts["milestones"]["DEMO-0.2"]
        self.assertEqual(100, sum(item["weight"] for item in demo["criteria"]))
        ids = [item["id"] for item in demo["criteria"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("millennium-tree-map-identity", ids)
        self.assertIn("android-real-device-visual-proof", ids)

    def test_task_template_schema_is_supported_but_not_required(self):
        payload = {
            "schema": "logres-milestone-contract-v1",
            "milestones": {
                "M": {
                    "criteria": [
                        criterion(
                            "c",
                            {"type": "artifact", "path": "proof.json"},
                            task_template={
                                "title": "Build proof",
                                "work_type": "control-plane",
                                "priority": 1,
                                "scopes": ["proof.json"],
                                "acceptance": ["proof exists"],
                            },
                        )
                    ]
                }
            },
        }
        validate_contracts(payload)

    def test_task_state_ready_is_executable_and_done_passes(self):
        conn = make_db()
        conn.execute("insert into tasks values('T','READY')")
        item = criterion(
            "task",
            {
                "type": "task_state",
                "task_id": "T",
                "pass_statuses": ["DONE"],
            },
        )
        with tempfile.TemporaryDirectory() as td:
            result = evaluate_criterion(
                conn,
                item,
                integration_sha="a" * 40,
                root=Path(td),
            )
            self.assertEqual("EXECUTABLE", result.status)
            conn.execute("update tasks set status='DONE' where id='T'")
            result = evaluate_criterion(
                conn,
                item,
                integration_sha="a" * 40,
                root=Path(td),
            )
            self.assertTrue(result.passed)

    def test_exact_sha_verification_does_not_accept_other_sha(self):
        conn = make_db()
        conn.execute(
            "insert into verification values(?,?,?,?,?,?,?)",
            (
                "old",
                "b" * 40,
                "full-e2e",
                "PASS",
                60,
                "2026-09-24T00:00:00+00:00",
                "old sha",
            ),
        )
        item = criterion(
            "verify",
            {"type": "verification", "mode": "full-e2e", "status": "PASS"},
        )
        with tempfile.TemporaryDirectory() as td:
            result = evaluate_criterion(
                conn,
                item,
                integration_sha="a" * 40,
                root=Path(td),
            )
            self.assertEqual("BLOCKED_DEP", result.status)
            conn.execute(
                "insert into verification values(?,?,?,?,?,?,?)",
                (
                    "current",
                    "a" * 40,
                    "full-e2e",
                    "PASS",
                    60,
                    "2026-09-24T01:00:00+00:00",
                    "current sha",
                ),
            )
            result = evaluate_criterion(
                conn,
                item,
                integration_sha="a" * 40,
                root=Path(td),
            )
            self.assertTrue(result.passed)

    def test_artifact_presence_and_hash_are_deterministic(self):
        conn = make_db()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proof = root / "proof.json"
            proof.write_text('{"ok":true}\n')
            digest = hashlib.sha256(proof.read_bytes()).hexdigest()
            item = criterion(
                "artifact",
                {
                    "type": "artifact",
                    "path": "proof.json",
                    "sha256": digest,
                },
            )
            result = evaluate_criterion(
                conn,
                item,
                integration_sha="a" * 40,
                root=root,
            )
            self.assertTrue(result.passed)
            proof.write_text("changed\n")
            result = evaluate_criterion(
                conn,
                item,
                integration_sha="a" * 40,
                root=root,
            )
            self.assertEqual("BLOCKED_DEP", result.status)

    def test_dependency_and_evidence_checks_preserve_evidence_ceiling(self):
        conn = make_db()
        conn.executemany(
            "insert into tasks values(?,?)",
            [
                ("ROOT", "BLOCKED_DEP"),
                ("DEP1", "DONE"),
                ("DEP2", "BLOCKED_EVIDENCE"),
                ("EVIDENCE", "BLOCKED_EVIDENCE"),
            ],
        )
        conn.executemany(
            "insert into task_dependencies values(?,?,?,?)",
            [
                ("ROOT", "DEP1", "hard", ""),
                ("ROOT", "DEP2", "evidence", ""),
            ],
        )
        with tempfile.TemporaryDirectory() as td:
            dependency_result = evaluate_criterion(
                conn,
                criterion(
                    "deps",
                    {"type": "dependency_state", "task_id": "ROOT"},
                ),
                integration_sha="a" * 40,
                root=Path(td),
            )
            evidence_result = evaluate_criterion(
                conn,
                criterion(
                    "evidence",
                    {
                        "type": "evidence_state",
                        "task_id": "EVIDENCE",
                        "pass_statuses": ["DONE"],
                    },
                ),
                integration_sha="a" * 40,
                root=Path(td),
            )
        self.assertEqual("BLOCKED_EVIDENCE", dependency_result.status)
        self.assertEqual("BLOCKED_EVIDENCE", evidence_result.status)

    def test_external_manual_gate_is_fail_closed(self):
        conn = make_db()
        conn.execute("insert into tasks values('DEVICE','BLOCKED_EVIDENCE')")
        item = criterion(
            "device",
            {
                "type": "external_manual",
                "task_id": "DEVICE",
                "pass_statuses": ["DONE"],
            },
        )
        with tempfile.TemporaryDirectory() as td:
            result = evaluate_criterion(
                conn,
                item,
                integration_sha="a" * 40,
                root=Path(td),
            )
            self.assertEqual("BLOCKED_EXTERNAL", result.status)
            conn.execute("update tasks set status='DONE' where id='DEVICE'")
            result = evaluate_criterion(
                conn,
                item,
                integration_sha="a" * 40,
                root=Path(td),
            )
            self.assertTrue(result.passed)

    def test_demo_contract_reports_80_percent_and_real_blockers_only(self):
        contracts = load_contracts(
            CONTROL_ROOT / "config" / "milestone_contracts.json"
        )
        conn = make_db()
        referenced_tasks = {
            item["check"].get("task_id")
            for item in contracts["milestones"]["DEMO-0.2"]["criteria"]
            if item["check"].get("task_id")
        }
        for task_id in sorted(referenced_tasks):
            status = "DONE"
            if task_id in {"G17-TUT-001", "ANDROID-VISUAL-QA-001"}:
                status = "BLOCKED_EVIDENCE"
            conn.execute(
                "insert into tasks values(?,?)",
                (task_id, status),
            )
        current = "c" * 40
        conn.execute(
            "insert into verification values(?,?,?,?,?,?,?)",
            (
                "current",
                current,
                "full-e2e",
                "PASS",
                60,
                "2026-09-24T02:00:00+00:00",
                "authoritative",
            ),
        )
        before = conn.execute("select count(*) from tasks").fetchone()[0]
        with tempfile.TemporaryDirectory() as td:
            result = evaluate_milestone(
                conn,
                contracts,
                "DEMO-0.2",
                integration_sha=current,
                root=Path(td),
            )
        after = conn.execute("select count(*) from tasks").fetchone()[0]

        self.assertEqual(80.0, result.progress_percent)
        self.assertEqual("BLOCKED_EXTERNAL", result.state)
        self.assertEqual(before, after)
        by_id = {item.criterion_id: item for item in result.criteria}
        self.assertEqual(
            "BLOCKED_DEP",
            by_id["millennium-tree-map-identity"].status,
        )
        self.assertIn(
            "artifact missing",
            by_id["millennium-tree-map-identity"].reason,
        )
        self.assertEqual(
            "BLOCKED_EXTERNAL",
            by_id["android-real-device-visual-proof"].status,
        )
        self.assertTrue(
            all(
                item.passed
                for key, item in by_id.items()
                if key
                not in {
                    "millennium-tree-map-identity",
                    "android-real-device-visual-proof",
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
