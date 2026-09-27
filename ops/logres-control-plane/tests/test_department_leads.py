import json
import sqlite3
import sys
import unittest
from pathlib import Path

CONTROL_ROOT = Path(__file__).resolve().parents[1]
LIB = CONTROL_ROOT / "lib"
sys.path.insert(0, str(LIB))

import logres_studio_org as studio
import logres_department_leads as leads


class DepartmentLeadTests(unittest.TestCase):
    def setUp(self):
        self.policy = studio.load_policy(CONTROL_ROOT / "config" / "studio_departments.json")
        self.profiles = leads.load_profiles(
            CONTROL_ROOT / "config" / "department_lead_profiles.json", self.policy
        )

    def connection(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
        create table tasks(id text primary key, priority integer, lane text, title text,
          status text, branch text, owner text, note text, updated_at text);
        create table task_metadata(task_id text primary key, milestone text, work_type text,
          concurrency_key text, expected_minutes integer, evidence_policy text,
          created_at text, updated_at text);
        create table task_scopes(task_id text, path_prefix text);
        create table task_acceptance(task_id text, ordinal integer, criterion text);
        create table task_dependencies(task_id text, depends_on text, kind text, rationale text);
        create table verification(ref text, sha text, mode text, status text,
          duration_sec real, ran_at text, details text);
        create table regressions(id integer primary key, task_id text, kind text,
          summary text, status text, created_at text);
        create table swarm_jobs(id integer primary key, task_id text, worker_id text,
          engine text, state text, started_at text, updated_at text, finished_at text);
        create table brain_events(id integer primary key autoincrement, ts_epoch real, ts text,
          sender text, recipient text, event_type text, priority integer, task_id text,
          subject text, body text, artifact_path text, artifact_sha256 text,
          dedupe_key text, meta_json text);
        """)
        studio.ensure_schema(conn)
        leads.ensure_schema(conn)
        return conn

    def test_every_department_gets_complete_logical_lead_profile(self):
        self.assertEqual(set(studio.REQUIRED_DEPARTMENTS), set(self.profiles))
        required = {
            "department", "charter", "queue_view", "metrics", "decomposition_policy",
            "review_responsibilities", "escalation_rules", "allowed_scope_prefixes",
        }
        for department, profile in self.profiles.items():
            self.assertTrue(required <= set(profile), department)
            self.assertEqual(department, profile["department"])
            self.assertEqual(self.policy["departments"][department]["charter"], profile["charter"])
            self.assertTrue(profile["metrics"])

    def test_missing_department_profile_fails_closed(self):
        bad = {"schema": 1, "profiles": dict(json.loads(
            (CONTROL_ROOT / "config" / "department_lead_profiles.json").read_text()
        )["profiles"])}
        bad["profiles"].pop("qa_test")
        with self.assertRaisesRegex(ValueError, "missing department"):
            leads.validate_profiles(bad, self.policy)

    def test_department_queue_view_uses_brain_tasks_not_chat_memory(self):
        conn = self.connection()
        conn.execute("insert into tasks values('G',0,'game','Battle reward','READY',null,null,'','now')")
        conn.execute("insert into tasks values('Q',1,'qa','Exact SHA device verify','READY',null,null,'','now')")
        conn.commit()
        game = leads.department_snapshot(conn, "gameplay_engineering", self.policy, self.profiles)
        qa = leads.department_snapshot(conn, "qa_test", self.policy, self.profiles)
        self.assertEqual(['G'], [x['id'] for x in game['queue']])
        self.assertEqual(['Q'], [x['id'] for x in qa['queue']])
        self.assertEqual('brain', game['source'])

    def test_bounded_task_command_stays_inside_department_charter_and_scope(self):
        proposal = {
            "id": "DEPT-GAME-1", "priority": 1, "lane": "game",
            "title": "Implement battle reward", "work_type": "implementation",
            "expected_minutes": 45, "scopes": ["src/game/battle"],
            "acceptance": ["focused tests pass"], "provenance": {"source": "Brain"},
        }
        argv = leads.build_task_command(
            proposal, "gameplay_engineering", self.policy, self.profiles,
            coordinator_bin="/home/ubuntu/logres/bin/logres-coordinator",
        )
        self.assertEqual("add-task", argv[1])
        evidence = json.loads(argv[argv.index("--evidence-policy") + 1])
        self.assertEqual("gameplay_engineering", evidence["department"])
        self.assertFalse(evidence["direct_merge_deploy_authority"])
        bad = dict(proposal, id="DEPT-GAME-2", scopes=["ops/logres-control-plane/bin/root-tool"])
        with self.assertRaisesRegex(ValueError, "outside department scope"):
            leads.build_task_command(bad, "gameplay_engineering", self.policy, self.profiles)

    def test_cross_department_task_requires_explicit_work_order(self):
        conn = self.connection()
        proposal = {
            "id": "DEPT-ART-1", "priority": 1, "lane": "presentation",
            "title": "Visual UI presentation", "work_type": "art",
            "expected_minutes": 30, "scopes": ["src/game/ui"],
            "acceptance": ["visual review"], "provenance": {"source": "Brain"},
        }
        with self.assertRaisesRegex(ValueError, "work order"):
            leads.build_task_command(
                proposal, "gameplay_engineering", self.policy, self.profiles,
                requested_department="art_ui_ux",
            )
        work_id = studio.create_work_order(
            conn, source_department="gameplay_engineering", target_department="art_ui_ux",
            subject="Battle UI handoff", acceptance=["stable behavior contract"],
            provenance={"task_id": "G"}, policy=self.policy,
        )
        argv = leads.build_task_command(
            proposal, "gameplay_engineering", self.policy, self.profiles,
            requested_department="art_ui_ux", work_order_id=work_id, conn=conn,
        )
        evidence = json.loads(argv[argv.index("--evidence-policy") + 1])
        self.assertEqual(work_id, evidence["work_order_id"])

    def test_elastic_team_spawns_only_for_useful_queue_and_releases_when_drained(self):
        plan = leads.elastic_worker_plan(queue_depth=4, active_workers=1, desired_workers=3)
        self.assertEqual(2, plan["spawn"])
        self.assertEqual(0, plan["release"])
        empty = leads.elastic_worker_plan(queue_depth=0, active_workers=2, desired_workers=0)
        self.assertEqual(0, empty["spawn"])
        self.assertEqual(2, empty["release"])
        self.assertEqual(0, empty["target_workers"])

    def test_worker_cycle_delegates_elastic_changes_through_governed_capacity(self):
        report = {
            "departments": {
                "gameplay_engineering": {"metrics": {"queue_depth": 2, "active_workers": 0}},
                "art_ui_ux": {"metrics": {"queue_depth": 0, "active_workers": 0}},
            },
            "allocation": {
                "gameplay_engineering": {"desired_workers": 2},
                "art_ui_ux": {"desired_workers": 0},
            },
        }
        seen = []
        class Result:
            returncode = 0; stdout = "ok"; stderr = ""
        out = leads.run_worker_cycle(
            Path("/home/ubuntu/logres"), report, execute=True,
            runner=lambda argv, **kwargs: (seen.append(list(argv)) or Result()),
        )
        self.assertEqual(2, out["spawn"])
        self.assertEqual(0, out["release"])
        self.assertEqual(1, len(seen))
        self.assertEqual(["tick", "--execute"], seen[0][-2:])
        idle = leads.run_worker_cycle(
            Path("/home/ubuntu/logres"),
            {"departments": report["departments"], "allocation": {
                "gameplay_engineering": {"desired_workers": 0},
                "art_ui_ux": {"desired_workers": 0},
            }},
            execute=True, runner=lambda *a, **k: (_ for _ in ()).throw(AssertionError("unexpected dispatch")),
        )
        self.assertEqual(0, idle["spawn"] + idle["release"])

    def test_executive_allocation_honors_verifier_capacity_and_critical_path(self):
        tasks = [
            {"id":"G","priority":0,"lane":"game","title":"Battle critical path","status":"READY"},
            {"id":"A","priority":3,"lane":"presentation","title":"Visual polish","status":"READY"},
            {"id":"D","priority":3,"lane":"control-plane","title":"Build dashboard","status":"READY"},
        ]
        health = {name: {"verification_pass_rate": 1.0, "rework_rate": 0.0} for name in self.profiles}
        plan = leads.executive_allocate(
            tasks, self.policy, self.profiles, verifier_capacity=2,
            resource_pressure="normal", health=health,
        )
        self.assertLessEqual(sum(x["desired_workers"] for x in plan.values()), 2)
        self.assertGreaterEqual(plan["gameplay_engineering"]["desired_workers"], 1)

    def test_sensitive_work_requires_independent_downstream_review(self):
        cases = [
            ({"lane":"design","title":"Design battle rules"}, "qa_test"),
            ({"lane":"security","title":"Sandbox isolation"}, "security_integrity"),
            ({"lane":"release","title":"Release APK"}, "qa_test"),
            ({"lane":"research","title":"Historical Global fidelity"}, "qa_test"),
        ]
        for task, expected in cases:
            route = leads.independent_review_route(task, self.policy)
            self.assertTrue(route["required"], task)
            self.assertIn(expected, route["review_departments"])

    def test_standup_synthesizes_brain_progress_blockers_risks_and_actions(self):
        conn = self.connection()
        conn.execute("insert into tasks values('G',0,'game','Battle reward','READY',null,null,'','now')")
        conn.execute("insert into tasks values('Q',1,'qa','Verify battle','BLOCKED_DEP',null,null,'waiting on G','now')")
        conn.execute("insert into regressions values(1,'G','test','battle regression','OPEN','now')")
        conn.execute("insert into verification values('worker/g','abc','fast','PASS',4,'now','ok')")
        conn.commit()
        out = leads.studio_standup(
            conn, self.policy, self.profiles, verifier_capacity=2, resource_pressure="normal"
        )
        self.assertEqual("brain", out["source"])
        self.assertIn("gameplay_engineering", out["departments"])
        self.assertTrue(out["blockers"])
        self.assertTrue(out["risks"])
        self.assertTrue(out["next_actions"])
        self.assertNotIn("chat_memory", json.dumps(out))


if __name__ == "__main__":
    unittest.main()
