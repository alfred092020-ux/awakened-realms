from __future__ import annotations
import json,sqlite3
from datetime import datetime,timezone

def ensure_schema(conn):
    conn.executescript("""
    create table if not exists zero_human_runs(
      id integer primary key autoincrement,
      created_at text not null,
      can_continue integer not null,
      payload_json text not null
    );
    """);conn.commit()

def _exists(conn,name):
    return conn.execute("select 1 from sqlite_master where type='table' and name=?",(name,)).fetchone() is not None
def _count(conn,sql,args=()):
    r=conn.execute(sql,args).fetchone();return int(r[0] or 0) if r else 0

def analyze(conn,persist=False):
    ensure_schema(conn)
    ready=_count(conn,"select count(*) from tasks where status='READY'") if _exists(conn,"tasks") else 0
    active=_count(conn,"select count(*) from tasks where status='ACTIVE'") if _exists(conn,"tasks") else 0
    blocked_ev=_count(conn,"select count(*) from tasks where status='BLOCKED_EVIDENCE'") if _exists(conn,"tasks") else 0
    blocked_dep=_count(conn,"select count(*) from tasks where status='BLOCKED_DEP'") if _exists(conn,"tasks") else 0
    queue=_count(conn,"select count(*) from integration_queue where status not in ('INTEGRATED','SUPERSEDED')") if _exists(conn,"integration_queue") else 0
    regressions=_count(conn,"select count(*) from regressions where status='OPEN'") if _exists(conn,"regressions") else 0
    visual_fail=0
    if _exists(conn,"visual_truth_checks"):
        visual_fail=_count(conn,"""select count(*) from visual_truth_checks v join
          (select checkpoint,max(id) id from visual_truth_checks group by checkpoint)x on x.id=v.id where v.verdict='FAIL'""")
    state_inconsistency=0
    if _exists(conn,"copilot_jobs") and _exists(conn,"tasks"):
        state_inconsistency+=_count(conn,"""select count(*) from copilot_jobs c join tasks t on t.id=c.task_id
          where c.state in ('ACTIVE','VERIFYING','QUEUED') and t.status in ('DONE','SUPERSEDED','CANCELLED','BLOCKED_EVIDENCE')""")
    reasons=[]
    proposals=[]
    can_continue=bool(ready or active or queue)
    if not can_continue and blocked_ev:
        reasons.append({"code":"EXTERNAL_EVIDENCE","count":blocked_ev})
        proposals.append({"kind":"EVIDENCE_ACQUISITION","action":"Seek genuinely new evidence or explicitly accept a bounded reconstruction ceiling."})
    if not can_continue and blocked_dep:
        reasons.append({"code":"NO_RUNNABLE_WORK","count":blocked_dep})
        proposals.append({"kind":"DEPENDENCY_REVIEW","action":"Reconcile blocked dependencies and create work only for explicit unmet criteria."})
    if state_inconsistency:
        reasons.append({"code":"STATE_INCONSISTENCY","count":state_inconsistency})
        proposals.append({"kind":"ENGINE_RECONCILE","action":"Run bounded engine-state reconciliation before scheduling more work."})
    if visual_fail:
        reasons.append({"code":"VISUAL_GATE","count":visual_fail})
        proposals.append({"kind":"VISUAL_REPAIR","action":"Create bounded repair work tied to the failed visual checkpoint and exact SHA."})
    if regressions:
        reasons.append({"code":"OPEN_REGRESSION","count":regressions})
        proposals.append({"kind":"REGRESSION_REPAIR","action":"Prioritize isolated regression repair before release certification."})
    if not can_continue and not reasons:
        reasons.append({"code":"MISSING_SCOPE_OR_COMPLETE","count":1})
        proposals.append({"kind":"MISSION_REVIEW","action":"Compare mission coverage against completion certificates; uncovered objectives require explicit scope or completion proof."})
    payload={"can_continue_without_human":can_continue and not state_inconsistency,
             "metrics":{"ready":ready,"active":active,"integration_backlog":queue,"blocked_evidence":blocked_ev,"blocked_dep":blocked_dep,"open_regressions":regressions,"visual_failures":visual_fail,"state_inconsistencies":state_inconsistency},
             "stop_reasons":reasons,"improvement_proposals":proposals,
             "authority":"ANALYSIS_ONLY_NO_TASK_CREATION_NO_AUTHORITY_CHANGE"}
    if persist:
        cur=conn.execute("insert into zero_human_runs(created_at,can_continue,payload_json) values(?,?,?)",
          (datetime.now(timezone.utc).isoformat(timespec="seconds"),1 if payload["can_continue_without_human"] else 0,json.dumps(payload,sort_keys=True)));conn.commit();payload["run_id"]=int(cur.lastrowid)
    return payload
