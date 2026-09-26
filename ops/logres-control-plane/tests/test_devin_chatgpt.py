from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from logres_devin_chatgpt import (
    FIXED_COMMAND_KEY,
    FIXED_DELEGATION_MESSAGE,
    ensure_schema,
    eligible_workers,
    dispatch_once,
    reconcile_assignments,
    ConfiguredChatWakeBridge,
)


def make_db() -> sqlite3.Connection:
    c = sqlite3.connect(':memory:')
    c.row_factory = sqlite3.Row
    c.executescript("""
    create table tasks(id text primary key, priority integer, lane text, title text, status text, branch text, owner text, note text, updated_at text);
    create table task_metadata(task_id text primary key, work_type text);
    create table brain_members(chat_id text primary key, status text, last_seen_epoch real, capabilities_json text, metadata_json text);
    create table brain_task_leases(task_id text primary key, chat_id text, branch text, lease_until_epoch real, acquired_at text, renewed_at text, progress integer, note text);
    create table brain_events(id integer primary key autoincrement, ts_epoch real, ts text, sender text, recipient text, event_type text, priority integer, task_id text, subject text, body text, artifact_path text, artifact_sha256 text, dedupe_key text, meta_json text);
    create table brain_agent_sessions(session_key text primary key, member_id text, provider text, external_session_id text, session_kind text, state text, cost_class text, capabilities_json text, wake_method text, wake_target text, last_seen_epoch real, last_synced_at text, metadata_json text);
    create table verification(ref text, sha text, mode text, status text, duration_sec real, ran_at text, details text);
    """)
    ensure_schema(c)
    return c


class FakeContracts:
    def __init__(self, states): self.states = states
    def get(self, chat_id):
        state = self.states.get(chat_id)
        return None if state is None else {'state': state}
    def set_state(self, chat_id, state, **kwargs):
        self.states[chat_id] = state
        return {'chat_id': chat_id, 'state': state}


class FakeBridge:
    def __init__(self, before_send=None, result='SENT'):
        self.before_send = before_send
        self.result = result
        self.calls = []
    def send(self, key, command_id):
        self.calls.append((key, command_id))
        if self.before_send: self.before_send()
        return {'result': self.result}


class DevinChatGPTDelegationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root/'control/android-device/chat-watchdog-targets').mkdir(parents=True)
        (self.root/'control/capacity-state.json').write_text(json.dumps({'plan': {'lane_caps': {'chatgpt': 1}}, 'signals': {'verifier': {'backlog': 0}}}))
        self.target = self.root/'control/android-device/chat-watchdog-targets/worker-a.json'
        self.target.write_text(json.dumps({'enabled': True, 'target_name': 'Worker A', 'target_url': 'https://chatgpt.com/c/abcdef123456', 'target_semantic_labels': [], 'min_interval_seconds': 0}))
        self.policy = {'enabled': True, 'lease_minutes': 120, 'ack_timeout_seconds': 0, 'poll_interval_seconds': 0, 'max_active_brain_workers': 6, 'max_verifier_backlog': 6, 'workers': [{'member_id': 'worker-a', 'session_key': 'chatgpt:worker-a', 'enabled': True, 'target_config_path': str(self.target)}]}
        self.c = make_db()
        self.c.execute("insert into brain_members values('worker-a','IDLE',0,'{}','{}')")
        self.c.execute("insert into brain_agent_sessions values('chatgpt:worker-a','worker-a','chatgpt',null,'agent','AVAILABLE','subscription','[]','phone_exact_chat','exact',0,'now','{}')")
        self.c.execute("insert into tasks values('TASK-1',0,'game','Do bounded work','READY',null,null,'','now')")
        self.c.execute("insert into task_metadata values('TASK-1','implementation')")
        self.c.commit()

    def tearDown(self): self.tmp.cleanup()

    def test_eligible_worker_requires_registry_exact_target_capacity_and_idle_contract(self):
        workers = eligible_workers(self.c, self.root, self.policy, FakeContracts({'worker-a': 'DONE'}), now=100)
        self.assertEqual([w['member_id'] for w in workers], ['worker-a'])
        self.c.execute("update brain_agent_sessions set wake_method='brain_event' where session_key='chatgpt:worker-a'")
        self.c.commit()
        self.assertEqual(eligible_workers(self.c, self.root, self.policy, FakeContracts({'worker-a': 'DONE'}), now=100), [])

    def test_dispatch_assigns_before_send_and_ack_requires_post_wake_renewal(self):
        bridge = FakeBridge()
        def runner(argv, **kwargs):
            self.assertIn('acquire', argv)
            self.c.execute("insert into brain_task_leases values('TASK-1','worker-a','worker/worker-a-task-1',9999,'a','r1',0,'atomic')")
            self.c.execute("update tasks set status='ACTIVE',owner='worker-a',branch='worker/worker-a-task-1' where id='TASK-1'")
            self.c.commit()
            return SimpleNamespace(returncode=0, stdout='ACQUIRED', stderr='')
        def before_send():
            row = self.c.execute("select chat_id from brain_task_leases where task_id='TASK-1'").fetchone()
            self.assertEqual(row['chat_id'], 'worker-a')
            self.c.execute("update brain_task_leases set renewed_at='r2' where task_id='TASK-1'")
            self.c.commit()
        bridge.before_send = before_send
        result = dispatch_once(self.c, self.root, self.policy, contracts=FakeContracts({'worker-a':'DONE'}), runner=runner, bridge_factory=lambda *_: bridge, task_id='TASK-1', clock=lambda: 100.0, sleeper=lambda _: None)
        self.assertEqual(result['status'], 'ACKED')
        self.assertEqual(bridge.calls[0][0], FIXED_COMMAND_KEY)
        self.assertNotIn('TASK-1', FIXED_DELEGATION_MESSAGE)
        row = self.c.execute("select status,command_id from devin_chatgpt_assignments where task_id='TASK-1'").fetchone()
        self.assertEqual(row['status'], 'ACKED')

    def test_no_ack_leaves_assignment_recoverable_and_lease_intact(self):
        bridge = FakeBridge()
        def runner(argv, **kwargs):
            self.c.execute("insert into brain_task_leases values('TASK-1','worker-a','worker/worker-a-task-1',9999,'a','r1',0,'atomic')")
            self.c.execute("update tasks set status='ACTIVE',owner='worker-a',branch='worker/worker-a-task-1' where id='TASK-1'")
            self.c.commit()
            return SimpleNamespace(returncode=0, stdout='ACQUIRED', stderr='')
        result = dispatch_once(self.c, self.root, self.policy, contracts=FakeContracts({'worker-a':'DONE'}), runner=runner, bridge_factory=lambda *_: bridge, task_id='TASK-1', clock=lambda: 100.0, sleeper=lambda _: None)
        self.assertEqual(result['status'], 'SENT_UNACKNOWLEDGED')
        self.assertIsNotNone(self.c.execute("select 1 from brain_task_leases where task_id='TASK-1'").fetchone())

    def test_capacity_and_contract_backpressure_fail_closed(self):
        (self.root/'control/capacity-state.json').write_text(json.dumps({'plan': {'lane_caps': {'chatgpt': 0}}, 'signals': {'verifier': {'backlog': 0}}}))
        self.assertEqual(eligible_workers(self.c, self.root, self.policy, FakeContracts({'worker-a':'DONE'}), now=100), [])
        (self.root/'control/capacity-state.json').write_text(json.dumps({'plan': {'lane_caps': {'chatgpt': 1}}, 'signals': {'verifier': {'backlog': 0}}}))
        self.assertEqual(eligible_workers(self.c, self.root, self.policy, FakeContracts({'worker-a':'RUNNING'}), now=100), [])

    def test_engine_race_rejection_never_reaches_phone(self):
        bridge = FakeBridge()
        def runner(argv, **kwargs):
            return SimpleNamespace(returncode=1, stdout='', stderr='TASK_BUSY')
        result = dispatch_once(self.c, self.root, self.policy, contracts=FakeContracts({'worker-a':'DONE'}), runner=runner, bridge_factory=lambda *_: bridge, task_id='TASK-1', clock=lambda: 100.0, sleeper=lambda _: None)
        self.assertEqual(result['status'], 'ASSIGNMENT_REJECTED')
        self.assertEqual(bridge.calls, [])
        self.assertEqual(self.c.execute('select count(*) from devin_chatgpt_assignments').fetchone()[0], 0)

    def test_configured_bridge_replaces_target_messages_with_fixed_allowlist(self):
        target = json.loads(self.target.read_text())
        target['approved_messages'] = {'evil': 'Arbitrary free text'}
        bridge = ConfiguredChatWakeBridge(self.root, target)
        cfg = bridge.load_config()
        self.assertEqual(cfg['approved_messages'], {FIXED_COMMAND_KEY: FIXED_DELEGATION_MESSAGE})

    def test_reconcile_records_completion_and_verification_without_conversation_content(self):
        self.c.execute("insert into devin_chatgpt_assignments(assignment_id,task_id,member_id,branch,command_id,status,assigned_at,metadata_json) values('a1','TASK-1','worker-a','worker/worker-a-task-1','cmd1','ACKED','now','{}')")
        self.c.execute("update tasks set status='DONE',branch='worker/worker-a-task-1' where id='TASK-1'")
        self.c.execute("insert into verification values('worker/worker-a-task-1','abc','full-e2e','PASS',1,'now','ok')")
        self.c.commit()
        out = reconcile_assignments(self.c, now_epoch=200)
        self.assertEqual(out[0]['status'], 'COMPLETE')
        row = self.c.execute("select status,verification_status,metadata_json from devin_chatgpt_assignments where assignment_id='a1'").fetchone()
        self.assertEqual((row['status'], row['verification_status']), ('COMPLETE','PASS'))
        self.assertNotIn('conversation', row['metadata_json'].lower())


if __name__ == '__main__': unittest.main()
