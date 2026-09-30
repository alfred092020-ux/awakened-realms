from __future__ import annotations
import hashlib,json,sqlite3
from datetime import datetime,timezone
AUTHORITY='EXECUTIVE_SHADOW_NO_DISPATCH_NO_MERGE_NO_DEPLOY_NO_POLICY_OVERRIDE'
def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def ensure_schema(c):
 c.executescript("""create table if not exists executive_decisions(id integer primary key autoincrement,objective_id text not null,world_fingerprint text not null,authority text not null,reasoning_depth text not null,decision_json text not null,actual_outcome_json text,status text not null default 'SHADOW',created_at text not null,resolved_at text); create index if not exists executive_decisions_objective_idx on executive_decisions(objective_id,status,id);"""); c.commit()
def reasoning_depth(w): return 'DEEP' if w.get('contradictions') else ('FAST' if len(w.get('facts',[]))<=2 else 'NORMAL')
def shadow_decide(c,objective_id,world,gaps):
 ensure_schema(c); depth=reasoning_depth(world)
 if world.get('contradictions'): action={'kind':'RECONCILE','reason':'world model contains contradictions','gaps':gaps}
 elif gaps: action={'kind':'INVESTIGATE_OR_EXECUTE','reason':'verified objective gaps remain','gaps':gaps}
 else: action={'kind':'NOOP','reason':'no verified objective gap supplied','gaps':[]}
 fp=hashlib.sha256(json.dumps(world,sort_keys=True,separators=(',',':')).encode()).hexdigest(); guard={'dispatch':False,'merge':False,'deploy':False,'policy_override':False}; payload={'authority':AUTHORITY,'objective_id':objective_id,'reasoning_depth':depth,'action':action,'guardrails':guard}
 cur=c.execute('insert into executive_decisions(objective_id,world_fingerprint,authority,reasoning_depth,decision_json,created_at) values(?,?,?,?,?,?)',(objective_id,fp,AUTHORITY,depth,json.dumps(payload,sort_keys=True),now())); c.commit(); return {'decision_id':cur.lastrowid,**payload}
def record_outcome(c,decision_id,actual):
 ensure_schema(c); c.execute("update executive_decisions set actual_outcome_json=?,status='OBSERVED',resolved_at=? where id=?",(json.dumps(actual,sort_keys=True),now(),decision_id)); c.commit()
