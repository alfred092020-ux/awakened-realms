import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_goal_executor import (
    apply_one,
    coordinator_argv,
    plan_one,
    record_generation,
)


def make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        create table tasks(
          id text primary key,
          priority integer,
          lane text,
          title text,
          status text,
          branch text default '',
          owner text,
          note text default '',
          updated_at text default ''
        );
        create table task_metadata(
          task_id text primary key,
          milestone text,
          work_type text,
          concurrency_key text,
          expected_minutes integer,
          evidence_policy text,
          created_at text default '',
          updated_at text default ''
        );
        create table task_dependencies(
          task_id text,
          depends_on text,
          kind text,
          rationale text default '',
          primary key(task_id,depends_on)
        );
        create table task_acceptance(
          task_id text,
          ordinal integer,
          criterion text,
          primary key(task_id,ordinal)
        );
        create table task_scopes(
          task_id text,
          path_prefix text,
          primary key(task_id,path_prefix)
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


def template(**updates):
    value = {
        "title": "Implement bounded feature",
        "lane": "control-plane",
        "work_type": "implementation",
        "priority": 1,
        "expected_minutes": 30,
        "concurrency_key": "bounded-feature",
        "evidence_policy": "Use only explicit contract evidence.",
        "scopes": ["src/feature.ts"],
        "acceptance": ["Focused test passes."],
        "dependencies": {"hard": [], "integration": []},
    }
    value.update(updates)
    return value


def contract(*criteria, title="Test milestone"):
    return {
        "schema": "logres-milestone-contract-v1",
        "milestones": {
            "M1": {
                "title": title,
                "definition_of_done": "All explicit criteria pass.",
                "criteria": list(criteria),
            }
        },
    }


def criterion(
    criterion_id="missing-task",
    *,
    check=None,
    task_template=None,
    weight=1,
):
    value = {
        "id": criterion_id,
        "weight": weight,
        "description": criterion_id,
        "check": check or {
            "type": "task_state",
            "task_id": "MISSING",
            "pass_statuses": ["DONE", "RESOLVED"],
        },
    }
    if task_template is not None:
        value["task_template"] = task_template
    return value


def seed_equivalent(conn, task_id, task_template):
    conn.execute(
        """insert into tasks(
             id,priority,lane,title,status,branch,owner,note,updated_at
           ) values(?,?,?,?,?,'',null,'','')""",
        (
            task_id,
            task_template["priority"],
            task_template["lane"],
            task_template["title"],
            "READY",
        ),
    )
    conn.execute(
        """insert into task_metadata(
             task_id,milestone,work_type,concurrency_key,expected_minutes,
             evidence_policy,created_at,updated_at
           ) values(?,?,?,?,?,?,'','')""",
        (
            task_id,
            "M1",
            task_template["work_type"],
            task_template["concurrency_key"],
            task_template["expected_minutes"],
            task_template["evidence_policy"],
        ),
    )
    for ordinal, item in enumerate(task_template["acceptance"], 1):
        conn.execute(
            "insert into task_acceptance values(?,?,?)",
            (task_id, ordinal, item),
        )
    for scope in task_template["scopes"]:
        conn.execute(
            "insert into task_scopes values(?,?)",
            (task_id, scope),
        )
    for dep in task_template["dependencies"]["hard"]:
        conn.execute(
            "insert into task_dependencies values(?,?,?,'')",
            (task_id, dep, "hard"),
        )
    for dep in task_template["dependencies"]["integration"]:
        conn.execute(
            "insert into task_dependencies values(?,?,?,'')",
            (task_id, dep, "integration"),
        )
    conn.commit()


class GoalExecutorTests(unittest.TestCase):
    def setUp(self):
        self.conn = make_db()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def plan(self, payload):
        return plan_one(
            self.conn,
            payload,
            "M1",
            integration_sha="a" * 40,
            root=self.root,
        )

    def test_no_template_means_no_generation(self):
        result = self.plan(contract(criterion()))
        self.assertIsNone(result["candidate"])

    def test_missing_task_with_explicit_template_is_candidate(self):
        result = self.plan(contract(criterion(task_template=template())))
        self.assertIsNotNone(result["candidate"])
        self.assertEqual("missing-task", result["candidate"]["criterion_id"])
        self.assertTrue(result["candidate"]["task_id"].startswith("GOAL-M1-"))

    def test_evidence_dependency_and_external_checks_never_generate(self):
        for check_type in ("evidence_state", "dependency_state", "external_manual"):
            with self.subTest(check_type=check_type):
                conn = make_db()
                try:
                    conn.execute(
                        """insert into tasks(
                             id,priority,lane,title,status
                           ) values('BLOCK',1,'research','blocked','BLOCKED_EVIDENCE')"""
                    )
                    payload = contract(
                        criterion(
                            check={
                                "type": check_type,
                                "task_id": "BLOCK",
                                "pass_statuses": ["DONE"],
                            },
                            task_template=template(),
                        )
                    )
                    result = plan_one(
                        conn,
                        payload,
                        "M1",
                        integration_sha="a" * 40,
                        root=self.root,
                    )
                    self.assertIsNone(result["candidate"])
                finally:
                    conn.close()

    def test_existing_blocked_task_state_does_not_generate_replacement(self):
        self.conn.execute(
            """insert into tasks(
                 id,priority,lane,title,status
               ) values('MISSING',1,'research','blocked','BLOCKED_EVIDENCE')"""
        )
        result = self.plan(contract(criterion(task_template=template())))
        self.assertIsNone(result["candidate"])
        self.assertIn("BLOCKED_EVIDENCE", result["skipped"][0]["reason"])

    def test_incomplete_operational_template_is_skipped_fail_closed(self):
        incomplete = {
            "title": "x",
            "work_type": "implementation",
            "priority": 1,
            "scopes": ["src/x"],
            "acceptance": ["x"],
        }
        result = self.plan(
            contract(criterion(task_template=incomplete))
        )
        self.assertIsNone(result["candidate"])
        self.assertIn("not execution-ready", result["skipped"][0]["reason"])

    def test_semantically_equivalent_existing_task_suppresses_generation(self):
        task_template = template()
        seed_equivalent(self.conn, "EXISTING", task_template)
        result = self.plan(
            contract(criterion(task_template=task_template))
        )
        self.assertIsNone(result["candidate"])
        self.assertIn("equivalent task", result["skipped"][0]["reason"])

    def test_generation_record_is_idempotent_for_contract_fingerprint(self):
        result = self.plan(contract(criterion(task_template=template())))
        record_generation(self.conn, result["candidate"])
        again = self.plan(contract(criterion(task_template=template())))
        self.assertIsNone(again["candidate"])
        self.assertIn("already generated", again["skipped"][0]["reason"])

    def test_changed_contract_still_dedupes_equivalent_existing_work(self):
        task_template = template()
        first = self.plan(
            contract(criterion(task_template=task_template), title="First")
        )
        seed_equivalent(
            self.conn,
            first["candidate"]["task_id"],
            task_template,
        )
        second = self.plan(
            contract(criterion(task_template=task_template), title="Second")
        )
        self.assertIsNone(second["candidate"])
        self.assertIn("equivalent task", second["skipped"][0]["reason"])

    def test_coordinator_args_preserve_operational_template(self):
        task_template = template(
            dependencies={
                "hard": ["HARD-1"],
                "integration": ["API-1"],
            },
            scopes=["src/a.ts", "src/b.ts"],
            acceptance=["a", "b"],
        )
        candidate = self.plan(
            contract(criterion(task_template=task_template))
        )["candidate"]
        argv = coordinator_argv(candidate, "/bin/coordinator")
        self.assertIn("--depends", argv)
        self.assertIn("HARD-1", argv)
        self.assertIn("--depends-integrated", argv)
        self.assertIn("API-1", argv)
        self.assertEqual(2, argv.count("--scope"))
        self.assertEqual(2, argv.count("--accept"))
        self.assertIn("--minutes", argv)
        self.assertIn("30", argv)

    def test_autopilot_calls_executor_without_duplicate_outer_lock(self):
        text = (
            TEST_DIR.parent / "bin" / "logres-autopilot-watch"
        ).read_text()
        self.assertIn('"/home/ubuntu/logres/bin/logres-goal-executor"', text)
        self.assertNotIn(
            'run_locked_helper("logres-goal-executor"',
            text,
        )

    def test_executor_has_no_integration_authority(self):
        sources = "\n".join(
            [
                (TEST_DIR.parent / "bin" / "logres-goal-executor").read_text(),
                (LIB_DIR / "logres_goal_executor.py").read_text(),
            ]
        )
        for forbidden in (
            "logres-merge-train",
            "logres-merge-preflight",
            "apply-preflight",
            "READY_FOR_INTEGRATION",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, sources)

    def test_apply_creates_at_most_one_candidate_per_cycle(self):
        first_template = template(title="One")
        payload = contract(
            criterion("one", task_template=first_template),
            criterion(
                "two",
                check={
                    "type": "task_state",
                    "task_id": "MISSING-TWO",
                    "pass_statuses": ["DONE"],
                },
                task_template=template(title="Two", scopes=["src/two.ts"]),
            ),
        )
        calls = []

        def runner(argv, **kwargs):
            calls.append(argv)
            seed_equivalent(self.conn, argv[2], first_template)
            return subprocess.CompletedProcess(argv, 0, "CREATED", "")

        result = apply_one(
            self.conn,
            payload,
            "M1",
            integration_sha="a" * 40,
            root=self.root,
            coordinator="/bin/coordinator",
            runner=runner,
        )
        self.assertTrue(result["created"])
        self.assertEqual(1, len(calls))
        self.assertEqual("one", result["candidate"]["criterion_id"])


if __name__ == "__main__":
    unittest.main()
