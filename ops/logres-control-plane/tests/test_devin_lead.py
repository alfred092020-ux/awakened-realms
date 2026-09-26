import importlib.util
import json
import os
import sqlite3
import subprocess
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

    def proposal_connection(self):
        conn=self.planning_connection()
        conn.executescript("""
        create table brain_events(id integer primary key autoincrement, ts_epoch real, ts text, sender text, recipient text, event_type text, priority integer, task_id text, subject text, body text, artifact_path text, artifact_sha256 text, dedupe_key text unique, meta_json text);
        create table task_scopes(task_id text, path_prefix text, primary key(task_id,path_prefix));
        create table task_acceptance(task_id text, ordinal integer, criterion text, primary key(task_id,ordinal));
        """)
        return conn

    def proposal(self, **overrides):
        base={'id':'GEN-GAME-1','priority':0,'lane':'game','title':'Implement victory reward','work_type':'implementation','concurrency_key':'game:victory','expected_minutes':45,'evidence_policy':'evidence-first','acceptance':['reward visible'],'dependencies':[],'scopes':['src/game/victory']}
        base.update(overrides); return base

    def test_duplicate_fingerprint_is_suppressed(self):
        conn=self.proposal_connection(); snap={'tasks':[]}
        first=self.proposal()
        self.assertEqual('GEN-GAME-1', lead.create_bounded_task(conn, first))
        duplicate=dict(first); duplicate['id']='GEN-GAME-2'
        ok,reason=lead.validate_proposal(conn, duplicate, snap, lead.default_policy())
        self.assertFalse(ok); self.assertIn('duplicate',reason)

    def test_dependency_cycle_is_rejected(self):
        conn=self.proposal_connection(); conn.execute("insert into tasks values('A',0,'game','A','READY',null,null,'','now')")
        conn.execute("insert into task_dependencies values('A','B','hard','')")
        proposal=self.proposal(id='B',dependencies=['A'])
        ok,reason=lead.validate_proposal(conn,proposal,{'tasks':[]},lead.default_policy())
        self.assertFalse(ok); self.assertIn('cycle',reason)

    def test_generation_cap_and_cooldown_hold(self):
        conn=self.proposal_connection(); policy=lead.default_policy(); policy['task_generation_cap_per_cycle']=1; policy['predicate_cooldown_seconds']=9999
        self.assertEqual('GEN-GAME-1',lead.create_bounded_task(conn,self.proposal(),policy=policy,now=100.0,cycle_id='c1'))
        self.assertIsNone(lead.create_bounded_task(conn,self.proposal(id='GEN-GAME-2',concurrency_key='game:other'),policy=policy,now=101.0,cycle_id='c1'))
        ok,reason=lead.validate_proposal(conn,self.proposal(id='GEN-GAME-3'),{'tasks':[]},policy,now=102.0)
        self.assertFalse(ok); self.assertIn('cooldown',reason)

    def test_infrastructure_budget_preserves_game_slots(self):
        policy=lead.default_policy(); policy['assignment_cap_per_cycle']=4; policy['infrastructure_work_ratio_max']=0.25
        snap={'active_assignments':[],'capacity':{'plan':{'pressure':'normal'}}}
        infra={'id':'I','priority':0,'lane':'control-plane','title':'Internal tooling','status':'READY'}
        game={'id':'G','priority':0,'lane':'game','title':'Battle field','status':'READY'}
        self.assertEqual('defer',lead.route_task(infra,snap,policy)['action'])
        self.assertEqual('dispatch',lead.route_task(game,snap,policy)['action'])

    def test_free_devin_is_preferred_for_safe_implementation(self):
        task={'id':'G','priority':0,'lane':'game','title':'Battle flow','status':'READY','work_type':'implementation'}
        route=lead.route_task(task,{'capacity':{'plan':{'lane_caps':{'devin_cloud':2}}}},lead.default_policy())
        self.assertEqual('devin',route['engine']); self.assertEqual('swe-2-max',route['model']); self.assertFalse(route['paid'])

    def test_paid_route_is_never_enabled_by_lead(self):
        policy=lead.default_policy(); policy['models']['allow_paid_default']=True
        task={'id':'G','priority':0,'lane':'game','title':'Battle flow','status':'READY','work_type':'implementation'}
        route=lead.route_task(task,{'capacity':{'plan':{'lane_caps':{'devin_cloud':1}}}},policy)
        self.assertFalse(route['paid'])

    def test_stale_worker_recovery_preserves_evidence(self):
        policy=lead.default_policy(); policy['stale_worker_seconds']=60
        observations=[{'task_id':'T1','state':'stale','age_seconds':120,'branch':'worker/t1','recovery_path':'/tmp/recovery/T1.json'}]
        plans=lead.plan_recoveries(self.proposal_connection(),observations,policy)
        self.assertEqual('recover',plans[0]['action'])
        self.assertEqual('/tmp/recovery/T1.json',plans[0]['recovery_path'])
        self.assertTrue(plans[0]['preserve_evidence'])

    def test_failed_verification_creates_bounded_repair_not_auto_approval(self):
        observations=[{'task_id':'T2','state':'verification_failed','candidate_sha':'deadbeef','failure_class':'test'}]
        plans=lead.plan_recoveries(self.proposal_connection(),observations,lead.default_policy())
        self.assertEqual('repair',plans[0]['action'])
        self.assertNotIn('approve',plans[0])
        self.assertEqual('deadbeef',plans[0]['failed_candidate_sha'])

    def test_every_assignment_recovery_and_escalation_records_brain_event(self):
        conn=self.proposal_connection()
        for kind in ('ASSIGNMENT','TASK_RECLAIMED','BLOCKER'):
            event_id=lead.record_lead_event(conn,event_type=kind,subject=kind,body='evidence',task_id='T1',dedupe_key='lead:'+kind)
            self.assertGreater(event_id,0)
        rows=conn.execute("select event_type,task_id from brain_events order by id").fetchall()
        self.assertEqual(['ASSIGNMENT','TASK_RECLAIMED','BLOCKER'],[r['event_type'] for r in rows])
        self.assertTrue(all(r['task_id']=='T1' for r in rows))

    def test_metrics_report_latency_rework_queue_pass_rate_utilization_and_contention(self):
        conn=self.proposal_connection()
        snap={'metrics_input':{'completed_latencies_seconds':[30,90,60],'rework_count':2,'completed_count':8,'ready_queue_age_seconds':600,'verification_passed':9,'verification_failed':1,'active_workers':6,'logical_capacity':12,'resource_contention':0.25}}
        metrics=lead.compute_lead_metrics(conn,snap)
        self.assertEqual(60.0,metrics['median_task_latency_seconds'])
        self.assertEqual(0.2,metrics['rework_rate'])
        self.assertEqual(600.0,metrics['queue_age_seconds'])
        self.assertEqual(0.9,metrics['verification_pass_rate'])
        self.assertEqual(0.5,metrics['worker_utilization'])
        self.assertEqual(0.25,metrics['resource_contention'])

    def runtime_root(self, td):
        root=Path(td); (root/'control').mkdir(parents=True); (root/'config').mkdir(); (root/'bin').mkdir()
        conn=sqlite3.connect(root/'control'/'control.sqlite')
        conn.executescript("""
        create table tasks(id text primary key, priority integer, lane text, title text, status text, branch text, owner text, note text, updated_at text);
        create table task_dependencies(task_id text, depends_on text, kind text, rationale text);
        create table task_scopes(task_id text, path_prefix text);
        create table brain_task_leases(task_id text primary key, chat_id text, branch text, lease_until_epoch real, acquired_at text, renewed_at text, progress integer, note text);
        create table task_metadata(task_id text primary key, milestone text, work_type text, concurrency_key text, expected_minutes integer, evidence_policy text, created_at text, updated_at text);
        create table integration_queue(task_id text, status text, candidate_sha text);
        create table regressions(task_id text, state text, candidate_sha text);
        create table brain_events(id integer primary key autoincrement, ts_epoch real, ts text, sender text, recipient text, event_type text, priority integer, task_id text, subject text, body text, artifact_path text, artifact_sha256 text, dedupe_key text unique, meta_json text);
        """); conn.commit(); conn.close()
        (root/'config'/'devin_lead.json').write_text(json.dumps(lead.default_policy()))
        (root/'control'/'capacity-state.json').write_text(json.dumps({'plan':{'pressure':'normal','logical_workers':4,'lane_caps':{'devin_cloud':1}},'signals':{'verifier':{'backlog':0}}}))
        return root

    def test_tick_dry_run_has_no_side_effects(self):
        with tempfile.TemporaryDirectory() as td:
            root=self.runtime_root(td)
            conn=sqlite3.connect(root/'control'/'control.sqlite'); conn.execute("insert into tasks values('G',0,'game','Battle victory','READY',null,null,'','now')"); conn.commit(); conn.close()
            result=lead.lead_tick(root,execute=False,instance_id='dry-run')
            self.assertFalse(result['executed'])
            conn=sqlite3.connect(root/'control'/'control.sqlite')
            self.assertEqual(1,conn.execute("select count(*) from tasks").fetchone()[0])
            self.assertEqual(0,conn.execute("select count(*) from brain_events").fetchone()[0])

    def test_run_refuses_second_leader(self):
        with tempfile.TemporaryDirectory() as td:
            root=self.runtime_root(td); conn=sqlite3.connect(root/'control'/'control.sqlite')
            self.assertTrue(lead.acquire_leader(conn,instance_id='other',now=100.0,ttl_seconds=1000)); conn.close()
            self.assertEqual(2,lead.run_forever(root,interval_seconds=0,instance_id='second',max_cycles=1,now_fn=lambda:101.0))

    def test_pause_resume_cli(self):
        with tempfile.TemporaryDirectory() as td:
            root=self.runtime_root(td); cli=CONTROL_ROOT/'bin'/'logres-devin-lead'; env={**os.environ,'LOGRES_ROOT':str(root)}
            paused=subprocess.run([str(cli),'pause','--reason','operator test'],env=env,text=True,capture_output=True)
            self.assertEqual(0,paused.returncode); self.assertTrue((root/'control'/'devin-lead.pause').is_file())
            resumed=subprocess.run([str(cli),'resume'],env=env,text=True,capture_output=True)
            self.assertEqual(0,resumed.returncode); self.assertFalse((root/'control'/'devin-lead.pause').exists())

    def test_status_reports_heartbeat_frontier_metrics_and_last_decision(self):
        with tempfile.TemporaryDirectory() as td:
            root=self.runtime_root(td)
            lead.write_heartbeat(root,{'instance_id':'lead-a','frontier':[{'id':'G'}],'metrics':{'worker_utilization':0.5},'last_decision':'game-first'})
            status=lead.status_payload(root)
            self.assertEqual('lead-a',status['heartbeat']['instance_id']); self.assertEqual('G',status['heartbeat']['frontier'][0]['id']); self.assertEqual(0.5,status['heartbeat']['metrics']['worker_utilization']); self.assertEqual('game-first',status['heartbeat']['last_decision'])

    def test_service_restarts_and_runs_unprivileged(self):
        text=(CONTROL_ROOT/'systemd'/'logres-devin-lead.service').read_text()
        self.assertIn('Restart=always',text); self.assertIn('User=ubuntu',text); self.assertIn('/home/ubuntu/logres/bin/logres-devin-lead run',text); self.assertNotIn('User=root',text)

    def test_paused_run_loop_does_not_dispatch(self):
        with tempfile.TemporaryDirectory() as td:
            root=self.runtime_root(td); (root/'control'/'devin-lead.pause').write_text('hold')
            original=lead.dispatch_plan
            lead.dispatch_plan=lambda *a,**k: (_ for _ in ()).throw(AssertionError('dispatch while paused'))
            try:
                result=lead.lead_tick(root,execute=True,instance_id='paused')
            finally:
                lead.dispatch_plan=original
            self.assertTrue(result['paused']); self.assertFalse(result['executed']); self.assertTrue((root/'control'/'devin-lead-heartbeat.json').is_file())

    def test_unmet_milestone_decomposition_uses_goal_executor_and_generation_cap(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'bin').mkdir(parents=True)
            (root/'bin'/'logres-goal-executor').write_text('placeholder')
            snapshot={'milestones':[
                {'id':'M1','status':'ACTIVE','title':'One'},
                {'id':'M2','status':'ACTIVE','title':'Two'},
                {'id':'M3','status':'ACTIVE','title':'Three'},
                {'id':'DONE','status':'DONE','title':'Done'}]}
            policy=lead.default_policy(); policy['task_generation_cap_per_cycle']=2
            seen=[]
            class Result:
                returncode=0; stdout='{"status":"CREATED","task_id":"X"}'; stderr=''
            def runner(argv,**kwargs):
                seen.append(list(argv)); return Result()
            out=lead.decompose_unmet_milestones(root,snapshot,policy,execute=True,runner=runner)
            self.assertEqual(2,len(out)); self.assertEqual(2,len(seen))
            self.assertTrue(all('--apply' in argv and '--json' in argv for argv in seen))
            self.assertEqual(['M1','M2'],[item['milestone_id'] for item in out])

    def test_dry_run_decomposition_has_no_subprocess_side_effects(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            snapshot={'milestones':[{'id':'M1','status':'ACTIVE','title':'One'}]}
            called=[]
            out=lead.decompose_unmet_milestones(root,snapshot,lead.default_policy(),execute=False,runner=lambda *a,**k: called.append(a))
            self.assertEqual([],called); self.assertEqual('planned',out[0]['status'])

    def test_service_allows_governed_swarm_git_metadata_and_scratch(self):
        text=(CONTROL_ROOT/'systemd'/'logres-devin-lead.service').read_text()
        self.assertIn('/home/ubuntu/logres/src/awakened-realms',text)
        self.assertIn('/home/ubuntu/logres/scratch',text)

    def test_lead_tick_reports_milestone_decomposition_before_dispatch(self):
        with tempfile.TemporaryDirectory() as td:
            root=self.runtime_root(td)
            conn=sqlite3.connect(root/'control'/'control.sqlite')
            conn.execute("create table milestones(id text primary key,title text,sort_order integer,status text,definition_of_done text,created_at text,updated_at text)")
            conn.execute("insert into milestones values('M1','Game milestone',1,'ACTIVE','done','now','now')")
            conn.commit(); conn.close()
            original_decompose=lead.decompose_unmet_milestones
            original_dispatch=lead.dispatch_plan
            lead.decompose_unmet_milestones=lambda *a,**k:[{'milestone_id':'M1','status':'created','task_id':'NEW'}]
            lead.dispatch_plan=lambda *a,**k:{'executed':True,'dispatchable':0,'returncode':0}
            try:
                result=lead.lead_tick(root,execute=True,instance_id='lead-one')
            finally:
                lead.decompose_unmet_milestones=original_decompose; lead.dispatch_plan=original_dispatch
            self.assertEqual('M1',result['decomposition'][0]['milestone_id'])

    def test_existing_active_concurrency_key_suppresses_proposal(self):
        conn=self.proposal_connection()
        conn.execute("insert into tasks values('EXISTING',0,'game','Existing victory','ACTIVE','worker/existing','worker','','now')")
        conn.execute("insert into task_metadata values('EXISTING','DEMO','implementation','game:victory',30,'evidence-first','now','now')")
        ok,reason=lead.validate_proposal(conn,self.proposal(id='NEW'),{'tasks':[]},lead.default_policy())
        self.assertFalse(ok); self.assertIn('existing',reason)

    def test_create_bounded_task_persists_acceptance_scopes_and_dependencies(self):
        conn=self.proposal_connection()
        conn.execute("insert into tasks values('BASE',0,'game','Base','DONE',null,null,'','now')")
        proposal=self.proposal(dependencies=['BASE'],acceptance=['first','second'],scopes=['src/game/a','src/game/b'])
        self.assertEqual('GEN-GAME-1',lead.create_bounded_task(conn,proposal))
        self.assertEqual(['BASE'],[r[0] for r in conn.execute("select depends_on from task_dependencies where task_id='GEN-GAME-1'")])
        self.assertEqual(['first','second'],[r[0] for r in conn.execute("select criterion from task_acceptance where task_id='GEN-GAME-1' order by ordinal")])
        self.assertEqual(['src/game/a','src/game/b'],[r[0] for r in conn.execute("select path_prefix from task_scopes where task_id='GEN-GAME-1' order by path_prefix")])

    def test_policy_rejects_nonfree_preferred_model(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'devin_lead.json'
            path.write_text(json.dumps({'models':{'preferred':'paid-model','allow_paid_default':False}}))
            with self.assertRaisesRegex(ValueError,'free SWE-2'):
                lead.load_lead_policy(path)

    def test_frontier_enforces_infrastructure_budget_when_game_work_exists(self):
        policy=lead.default_policy(); policy['assignment_cap_per_cycle']=4; policy['infrastructure_work_ratio_max']=0.25
        tasks=[
            {'id':'G1','priority':0,'lane':'game','title':'Battle one','status':'READY','owner':None},
            {'id':'G2','priority':0,'lane':'game','title':'Field two','status':'READY','owner':None},
            {'id':'G3','priority':1,'lane':'game','title':'Quest three','status':'READY','owner':None},
            {'id':'I1','priority':0,'lane':'control-plane','title':'Unblock build','status':'READY','owner':None,'note':'critical blocker'},
            {'id':'I2','priority':0,'lane':'control-plane','title':'Unblock metrics','status':'READY','owner':None,'note':'critical blocker'}]
        snap={'tasks':tasks,'capacity':{'plan':{'pressure':'normal','logical_workers':12},'signals':{'verifier':{'backlog':0}}}}
        front=lead.select_frontier(snap,policy)
        infra=[x for x in front if x['lane']=='control-plane']
        games=[x for x in front if x['lane']=='game']
        self.assertLessEqual(len(infra),1); self.assertGreaterEqual(len(games),3)

    def test_live_metrics_input_reads_history_verification_and_swarm(self):
        conn=self.proposal_connection()
        conn.executescript("""
        create table task_state_history(id integer primary key autoincrement,task_id text,ts_epoch real,ts text,status text,owner text,branch text,source text,note text);
        create table verification(ref text primary key,sha text,mode text,status text,duration_sec real,ran_at text,details text);
        create table swarm_jobs(id integer primary key,task_id text,worker_id text,engine text,state text,pid integer,artifact_path text,last_error text,started_at text,updated_at text,finished_at text,branch text,model text,session_id text,verification text);
        """)
        conn.execute("insert into task_state_history(task_id,ts_epoch,ts,status,source,note) values('T',100,'x','ACTIVE','t','')")
        conn.execute("insert into task_state_history(task_id,ts_epoch,ts,status,source,note) values('T',160,'x','DONE','t','')")
        conn.execute("insert into verification values('a','a','full-e2e','PASS',1,'x','')")
        conn.execute("insert into verification values('b','b','full-e2e','FAIL',1,'x','')")
        conn.execute("insert into swarm_jobs(id,task_id,worker_id,engine,state,started_at,updated_at) values(1,'A','w1','devin','RUNNING','x','x')")
        conn.execute("insert into swarm_jobs(id,task_id,worker_id,engine,state,started_at,updated_at) values(2,'B','w2','research','RUNNING','x','x')")
        snap={'tasks':[],'regressions':[{'status':'OPEN'}],'capacity':{'plan':{'logical_workers':4},'signals':{'queue':{'oldest_ready_age_seconds':300},'host':{'cpu_psi_avg10':0.2,'memory_psi_avg10':0.1,'io_psi_avg10':0.0}}}}
        src=lead._metrics_input(conn,snap)
        self.assertEqual([60.0],src['completed_latencies_seconds']); self.assertEqual(1,src['completed_count'])
        self.assertEqual(1,src['verification_passed']); self.assertEqual(1,src['verification_failed']); self.assertEqual(2,src['active_workers'])

    def test_paused_cycle_blocks_decomposition_and_dispatch_but_keeps_heartbeat(self):
        with tempfile.TemporaryDirectory() as td:
            root=self.runtime_root(td); (root/'control'/'devin-lead.pause').write_text('stop')
            original_decompose=lead.decompose_unmet_milestones; original_dispatch=lead.dispatch_plan
            lead.decompose_unmet_milestones=lambda *a,**k: (_ for _ in ()).throw(AssertionError('decompose while paused'))
            lead.dispatch_plan=lambda *a,**k: (_ for _ in ()).throw(AssertionError('dispatch while paused'))
            try:
                result=lead.lead_tick(root,execute=True,instance_id='paused-two')
            finally:
                lead.decompose_unmet_milestones=original_decompose; lead.dispatch_plan=original_dispatch
            self.assertTrue(result['paused']); self.assertTrue((root/'control'/'devin-lead-heartbeat.json').is_file())

    def test_pause_resume_cli_records_brain_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            root=self.runtime_root(td); cli=CONTROL_ROOT/'bin'/'logres-devin-lead'; env={**os.environ,'LOGRES_ROOT':str(root)}
            self.assertEqual(0,subprocess.run([str(cli),'pause','--reason','audit'],env=env,capture_output=True,text=True).returncode)
            self.assertEqual(0,subprocess.run([str(cli),'resume'],env=env,capture_output=True,text=True).returncode)
            conn=sqlite3.connect(root/'control'/'control.sqlite')
            rows=conn.execute("select subject from brain_events order by id").fetchall()
            self.assertEqual([('Devin Lead paused',),('Devin Lead resumed',)],rows)

    def test_dispatch_failure_is_fail_closed_and_audited(self):
        with tempfile.TemporaryDirectory() as td:
            root=self.runtime_root(td); conn=sqlite3.connect(root/'control'/'control.sqlite')
            conn.execute("insert into tasks values('G',0,'game','Battle','READY',null,null,'','now')"); conn.commit(); conn.close()
            od=lead.decompose_unmet_milestones; op=lead.dispatch_plan
            lead.decompose_unmet_milestones=lambda *a,**k:[]
            lead.dispatch_plan=lambda *a,**k:{'executed':True,'dispatchable':1,'returncode':7,'stderr':'boom'}
            try:
                result=lead.lead_tick(root,execute=True,instance_id='lead-fail')
            finally:
                lead.decompose_unmet_milestones=od; lead.dispatch_plan=op
            self.assertTrue(result['dispatch_failed']); self.assertIn('dispatch failed',result['error'])
            heartbeat=json.loads((root/'control'/'devin-lead-heartbeat.json').read_text()); self.assertIn('error',heartbeat)
            conn=sqlite3.connect(root/'control'/'control.sqlite'); self.assertEqual(1,conn.execute("select count(*) from brain_events where event_type='BLOCKER'").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
