import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

CONTROL_ROOT = Path(__file__).resolve().parents[1]
LIB = CONTROL_ROOT / "lib" / "logres_devin_lead.py"
SPEC = importlib.util.spec_from_file_location("logres_devin_lead", LIB)
lead = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lead)


class DevinLeadLifecycleTests(unittest.TestCase):
    def connection(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        return conn

    def test_single_leader_election(self):
        conn = self.connection()
        self.assertTrue(lead.acquire_leader(conn, instance_id="lead-a", now=100.0, ttl_seconds=30))
        self.assertFalse(lead.acquire_leader(conn, instance_id="lead-b", now=110.0, ttl_seconds=30))
        self.assertTrue(lead.renew_leader(conn, instance_id="lead-a", now=115.0, ttl_seconds=30))

    def test_stale_leader_can_be_reclaimed(self):
        conn = self.connection()
        self.assertTrue(lead.acquire_leader(conn, instance_id="lead-a", now=100.0, ttl_seconds=10))
        self.assertTrue(lead.acquire_leader(conn, instance_id="lead-b", now=111.0, ttl_seconds=20))
        row = conn.execute("select instance_id from devin_lead_runtime where singleton=1").fetchone()
        self.assertEqual("lead-b", row["instance_id"])

    def test_pause_blocks_actions_but_keeps_heartbeat(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "control").mkdir(parents=True)
            (root / "control" / "devin-lead.pause").write_text("operator pause\n")
            pause = lead.read_pause(root)
            self.assertTrue(pause["paused"])
            self.assertIn("operator pause", pause["reason"])
            lead.write_heartbeat(root, {"instance_id": "lead-a", "paused": True})
            heartbeat = json.loads((root / "control" / "devin-lead-heartbeat.json").read_text())
            self.assertEqual("lead-a", heartbeat["instance_id"])
            self.assertTrue(heartbeat["paused"])

    def test_policy_rejects_paid_default(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "devin_lead.json"
            path.write_text(json.dumps({"models": {"allow_paid_default": True}}))
            with self.assertRaisesRegex(ValueError, "paid"):
                lead.load_lead_policy(path)

    def planning_connection(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
        create table tasks(id text primary key, priority integer, lane text, title text, status text, branch text, owner text, note text, updated_at text);
        create table task_dependencies(task_id text, depends_on text, kind text, rationale text);
        create table brain_task_leases(task_id text primary key, chat_id text, branch text, lease_until_epoch real, acquired_at text, renewed_at text, progress integer, note text);
        create table task_metadata(task_id text primary key, milestone text, work_type text, concurrency_key text, expected_minutes integer, evidence_policy text, created_at text, updated_at text);
        create table integration_queue(task_id text, status text, candidate_sha text);
        create table regressions(task_id text, state text, candidate_sha text);
        """)
        return conn

    def test_snapshot_refreshes_tasks_dependencies_leases_and_verification(self):
        conn = self.planning_connection()
        conn.execute("insert into tasks values('GAME-1',0,'game','Finish battle','READY',null,null,'','now')")
        conn.execute("insert into task_dependencies values('GAME-1','BASE-1','hard','needs base')")
        conn.execute("insert into integration_queue values('CAND-1','READY_FOR_PREFLIGHT','abc')")
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'control').mkdir()
            (root/'control'/'capacity-state.json').write_text(json.dumps({'plan':{'pressure':'normal','logical_workers':12},'signals':{'verifier':{'backlog':1}}}))
            snap=lead.collect_planning_snapshot(conn, root, lead.default_policy())
        self.assertEqual('GAME-1', snap['tasks'][0]['id'])
        self.assertEqual('BASE-1', snap['dependencies'][0]['depends_on'])
        self.assertEqual('CAND-1', snap['integration_queue'][0]['task_id'])
        self.assertEqual('normal', snap['capacity']['plan']['pressure'])

    def test_game_critical_path_beats_noncritical_infrastructure(self):
        policy=lead.default_policy()
        snap={'capacity':{'plan':{'pressure':'normal'},'signals':{'verifier':{'backlog':0}}}}
        game={'id':'GAME-1','priority':1,'lane':'game','title':'Playable battle victory','status':'READY','note':'critical path'}
        infra={'id':'INFRA-1','priority':0,'lane':'control-plane','title':'Improve internal dashboard','status':'READY','note':''}
        self.assertLess(lead.score_ready_task(game,snap,policy), lead.score_ready_task(infra,snap,policy))

    def test_blocked_terminal_or_owned_tasks_are_excluded(self):
        snap={'tasks':[
            {'id':'A','priority':0,'lane':'game','title':'A','status':'READY','owner':None},
            {'id':'B','priority':0,'lane':'game','title':'B','status':'ACTIVE','owner':'worker'},
            {'id':'C','priority':0,'lane':'game','title':'C','status':'BLOCKED_DEP','owner':None},
            {'id':'D','priority':0,'lane':'game','title':'D','status':'DONE','owner':None}],
            'capacity':{'plan':{'pressure':'normal','logical_workers':12},'signals':{'verifier':{'backlog':0}}}}
        self.assertEqual(['A'], [x['id'] for x in lead.select_frontier(snap, lead.default_policy())])

    def test_resource_pressure_reduces_frontier_size(self):
        tasks=[{'id':f'G{i}','priority':0,'lane':'game','title':f'Game {i}','status':'READY','owner':None} for i in range(8)]
        normal={'tasks':tasks,'capacity':{'plan':{'pressure':'normal','logical_workers':12},'signals':{'verifier':{'backlog':0}}}}
        high={'tasks':tasks,'capacity':{'plan':{'pressure':'high','logical_workers':4},'signals':{'verifier':{'backlog':10}}}}
        self.assertGreater(len(lead.select_frontier(normal,lead.default_policy())), len(lead.select_frontier(high,lead.default_policy())))


if __name__ == "__main__":
    unittest.main()
