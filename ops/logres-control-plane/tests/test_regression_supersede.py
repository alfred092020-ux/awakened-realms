import sqlite3
import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TEST_DIR.parent / "lib"))

from logres_regression_supersede import apply_supersede, plan_supersede


def make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        create table integration_preflights(
          id integer primary key,
          status text not null,
          tasks_json text not null,
          result_sha text,
          created_epoch real not null,
          verification_mode text
        );
        create table regressions(
          id integer primary key,
          task_id text,
          kind text,
          ref text,
          sha text,
          status text not null,
          created_epoch real not null
        );
        create table tasks(
          id text primary key,
          status text not null,
          owner text,
          branch text,
          note text,
          updated_at text
        );
        create table integration_queue(
          task_id text,
          status text,
          updated_at text,
          note text
        );
        create table task_dependencies(
          task_id text not null,
          depends_on text not null,
          kind text not null,
          rationale text not null default '',
          primary key(task_id,depends_on)
        );
        """
    )
    return conn


def preflight(
    conn,
    row_id,
    status,
    tasks,
    result,
    created,
    verification_mode=None,
):
    import json

    if verification_mode is None and status in {"VERIFIED", "APPLIED"}:
        verification_mode = "full-e2e"
    conn.execute(
        "insert into integration_preflights values(?,?,?,?,?,?)",
        (
            row_id,
            status,
            json.dumps(tasks),
            result,
            created,
            verification_mode,
        ),
    )


def regression(conn, row_id, task_id, kind, ref, created, status="OPEN"):
    conn.execute(
        "insert into regressions values(?,?,?,?,?,?,?)",
        (row_id, task_id, kind, ref, ref, status, created),
    )
    conn.execute(
        "insert or ignore into tasks(id,status) values(?,?)",
        (task_id, "READY"),
    )


class RegressionSupersedeTests(unittest.TestCase):
    def test_broader_success_supersedes_subset_failure_and_exact_ref_sibling(self):
        conn = make_db()
        preflight(conn, 10, "FAILED", ["VISUAL"], "v" * 40, 10)
        preflight(conn, 20, "APPLIED", ["VISUAL", "DEPLOY"], "s" * 40, 20)
        regression(conn, 1, "REG-MERGE", "merge-preflight", "v" * 40, 11)
        regression(conn, 2, "REG-CAND", "candidate-verify", "v" * 40, 10.5)
        regression(conn, 3, "OTHER", "candidate-verify", "x" * 40, 10.5)

        targets = plan_supersede(conn, 20)
        self.assertEqual([1, 2], [item.regression_id for item in targets])

    def test_explicit_integrated_carrier_supersedes_original_failed_task(self):
        conn = make_db()
        preflight(conn, 10, "FAILED", ["ORIGINAL"], "f" * 40, 10)
        preflight(conn, 20, "APPLIED", ["CARRIER"], "s" * 40, 20)
        regression(conn, 1, "REG-MERGE", "merge-preflight", "f" * 40, 11)
        conn.execute(
            "insert into task_dependencies values(?,?,?,?)",
            (
                "ORIGINAL",
                "CARRIER",
                "integration_carrier",
                "explicit fresh-base carrier",
            ),
        )
        conn.execute(
            "insert into integration_queue values(?,?,?,?)",
            ("CARRIER", "INTEGRATED", None, ""),
        )

        targets = plan_supersede(conn, 20)

        self.assertEqual([1], [item.regression_id for item in targets])
        self.assertEqual(
            "failed-task-carrier-subset",
            targets[0].proof,
        )
        self.assertEqual(("ORIGINAL",), targets[0].failed_tasks)

    def test_carrier_must_be_integrated(self):
        conn = make_db()
        preflight(conn, 10, "FAILED", ["ORIGINAL"], "f" * 40, 10)
        preflight(conn, 20, "APPLIED", ["CARRIER"], "s" * 40, 20)
        regression(conn, 1, "REG-MERGE", "merge-preflight", "f" * 40, 11)
        conn.execute(
            "insert into task_dependencies values(?,?,?,?)",
            ("ORIGINAL", "CARRIER", "integration_carrier", ""),
        )
        conn.execute(
            "insert into integration_queue values(?,?,?,?)",
            ("CARRIER", "READY_FOR_PREFLIGHT", None, ""),
        )

        self.assertEqual([], plan_supersede(conn, 20))

    def test_unrelated_dependency_kind_does_not_expand_success(self):
        conn = make_db()
        preflight(conn, 10, "FAILED", ["ORIGINAL"], "f" * 40, 10)
        preflight(conn, 20, "APPLIED", ["CARRIER"], "s" * 40, 20)
        regression(conn, 1, "REG-MERGE", "merge-preflight", "f" * 40, 11)
        conn.execute(
            "insert into task_dependencies values(?,?,?,?)",
            ("ORIGINAL", "CARRIER", "hard", ""),
        )
        conn.execute(
            "insert into integration_queue values(?,?,?,?)",
            ("CARRIER", "INTEGRATED", None, ""),
        )

        self.assertEqual([], plan_supersede(conn, 20))

    def test_integrated_carrier_not_in_successful_batch_does_not_expand(self):
        conn = make_db()
        preflight(conn, 10, "FAILED", ["ORIGINAL"], "f" * 40, 10)
        preflight(conn, 20, "APPLIED", ["OTHER"], "s" * 40, 20)
        regression(conn, 1, "REG-MERGE", "merge-preflight", "f" * 40, 11)
        conn.execute(
            "insert into task_dependencies values(?,?,?,?)",
            ("ORIGINAL", "CARRIER", "integration_carrier", ""),
        )
        conn.execute(
            "insert into integration_queue values(?,?,?,?)",
            ("CARRIER", "INTEGRATED", None, ""),
        )

        self.assertEqual([], plan_supersede(conn, 20))

    def test_carrier_expansion_is_one_hop_only(self):
        conn = make_db()
        preflight(conn, 10, "FAILED", ["ROOT"], "f" * 40, 10)
        preflight(conn, 20, "APPLIED", ["LEAF"], "s" * 40, 20)
        regression(conn, 1, "REG-MERGE", "merge-preflight", "f" * 40, 11)
        conn.execute(
            "insert into task_dependencies values(?,?,?,?)",
            ("MID", "LEAF", "integration_carrier", ""),
        )
        conn.execute(
            "insert into task_dependencies values(?,?,?,?)",
            ("ROOT", "MID", "integration_carrier", ""),
        )
        conn.execute(
            "insert into integration_queue values(?,?,?,?)",
            ("LEAF", "INTEGRATED", None, ""),
        )
        conn.execute(
            "insert into integration_queue values(?,?,?,?)",
            ("MID", "INTEGRATED", None, ""),
        )

        self.assertEqual([], plan_supersede(conn, 20))

    def test_mixed_failure_remains_open_when_success_does_not_cover_every_task(self):
        conn = make_db()
        preflight(
            conn,
            10,
            "FAILED",
            ["VISUAL", "BEHAVIOR"],
            "m" * 40,
            10,
        )
        preflight(conn, 20, "APPLIED", ["VISUAL", "DEPLOY"], "s" * 40, 20)
        regression(conn, 1, "REG-MERGE", "merge-preflight", "m" * 40, 11)
        regression(conn, 2, "REG-CAND", "candidate-verify", "m" * 40, 10.5)

        self.assertEqual([], plan_supersede(conn, 20))

    def test_candidate_siblings_require_exact_failed_result_ref(self):
        conn = make_db()
        preflight(conn, 10, "FAILED", ["VISUAL"], "v" * 40, 10)
        preflight(conn, 20, "VERIFIED", ["VISUAL"], "s" * 40, 20)
        regression(conn, 1, "REG-MERGE", "merge-preflight", "v" * 40, 11)
        regression(conn, 2, "REG-CAND-YES", "candidate-verify", "v" * 40, 10.5)
        regression(conn, 3, "REG-CAND-NO", "candidate-verify", "z" * 40, 10.5)

        targets = plan_supersede(conn, 20)
        self.assertEqual(
            {"REG-MERGE", "REG-CAND-YES"},
            {item.task_id for item in targets},
        )

    def test_exact_full_e2e_result_supersedes_pruned_failure_rows(self):
        conn = make_db()
        sha = "e" * 40
        preflight(conn, 20, "APPLIED", ["REPAIR"], sha, 20)
        regression(conn, 1, "REG-CAND", "candidate-verify", sha, 10)
        regression(conn, 2, "REG-MERGE", "merge-preflight", sha, 11)

        targets = plan_supersede(conn, 20)

        self.assertEqual([1, 2], [item.regression_id for item in targets])
        self.assertEqual(
            {"exact-result-sha"},
            {item.proof for item in targets},
        )
        self.assertTrue(
            all(item.failed_preflight_id is None for item in targets)
        )

    def test_exact_result_requires_full_e2e(self):
        conn = make_db()
        sha = "e" * 40
        preflight(
            conn,
            20,
            "APPLIED",
            ["REPAIR"],
            sha,
            20,
            verification_mode="fast",
        )
        regression(conn, 1, "REG-CAND", "candidate-verify", sha, 10)

        self.assertEqual([], plan_supersede(conn, 20))

    def test_exact_result_does_not_touch_different_sha(self):
        conn = make_db()
        sha = "e" * 40
        preflight(conn, 20, "VERIFIED", ["REPAIR"], sha, 20)
        regression(
            conn,
            1,
            "REG-CAND",
            "candidate-verify",
            "x" * 40,
            10,
        )

        self.assertEqual([], plan_supersede(conn, 20))

    def test_exact_result_preserves_active_repair_task(self):
        conn = make_db()
        sha = "e" * 40
        preflight(conn, 20, "APPLIED", ["REPAIR"], sha, 20)
        regression(conn, 1, "REG-CAND", "candidate-verify", sha, 10)
        conn.execute(
            "update tasks set status='ACTIVE' where id='REG-CAND'"
        )

        result = apply_supersede(
            conn,
            20,
            active_task_ids={"REG-CAND"},
        )

        self.assertEqual(
            ["REG-CAND"],
            result["preserved_active_tasks"],
        )
        self.assertEqual(
            "SUPERSEDED",
            conn.execute(
                "select status from regressions where id=1"
            ).fetchone()[0],
        )
        self.assertEqual(
            "ACTIVE",
            conn.execute(
                "select status from tasks where id='REG-CAND'"
            ).fetchone()[0],
        )
        self.assertEqual(
            "exact-result-sha",
            result["superseded"][0]["proof"],
        )

    def test_exact_result_apply_is_idempotent(self):
        conn = make_db()
        sha = "e" * 40
        preflight(conn, 20, "APPLIED", ["REPAIR"], sha, 20)
        regression(conn, 1, "REG-CAND", "candidate-verify", sha, 10)

        first = apply_supersede(conn, 20)
        second = apply_supersede(conn, 20)

        self.assertEqual(1, len(first["superseded"]))
        self.assertEqual([], second["superseded"])
        note = conn.execute(
            "select note from tasks where id='REG-CAND'"
        ).fetchone()[0]
        self.assertIn("exact result SHA", note)

    def test_apply_is_idempotent(self):
        conn = make_db()
        preflight(conn, 10, "FAILED", ["VISUAL"], "v" * 40, 10)
        preflight(conn, 20, "APPLIED", ["VISUAL"], "s" * 40, 20)
        regression(conn, 1, "REG-MERGE", "merge-preflight", "v" * 40, 11)
        regression(conn, 2, "REG-CAND", "candidate-verify", "v" * 40, 10.5)
        conn.execute(
            "insert into integration_queue values('REG-MERGE','READY',null,'')"
        )

        first = apply_supersede(conn, 20)
        second = apply_supersede(conn, 20)
        self.assertEqual(2, len(first["superseded"]))
        self.assertEqual([], second["superseded"])
        self.assertEqual(
            0,
            conn.execute(
                "select count(*) from regressions where status='OPEN'"
            ).fetchone()[0],
        )
        self.assertEqual(
            "SUPERSEDED",
            conn.execute(
                "select status from tasks where id='REG-MERGE'"
            ).fetchone()[0],
        )
        self.assertEqual(
            "SUPERSEDED",
            conn.execute(
                "select status from integration_queue where task_id='REG-MERGE'"
            ).fetchone()[0],
        )

    def test_active_repair_task_is_preserved_while_regression_is_superseded(self):
        conn = make_db()
        preflight(conn, 10, "FAILED", ["VISUAL"], "v" * 40, 10)
        preflight(conn, 20, "APPLIED", ["VISUAL"], "s" * 40, 20)
        regression(conn, 1, "REG-MERGE", "merge-preflight", "v" * 40, 11)
        conn.execute("update tasks set status='ACTIVE' where id='REG-MERGE'")

        result = apply_supersede(
            conn,
            20,
            active_task_ids={"REG-MERGE"},
        )
        self.assertEqual(["REG-MERGE"], result["preserved_active_tasks"])
        self.assertEqual(
            "SUPERSEDED",
            conn.execute(
                "select status from regressions where id=1"
            ).fetchone()[0],
        )
        self.assertEqual(
            "ACTIVE",
            conn.execute(
                "select status from tasks where id='REG-MERGE'"
            ).fetchone()[0],
        )


if __name__ == "__main__":
    unittest.main()
