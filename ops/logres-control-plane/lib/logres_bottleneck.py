from __future__ import annotations
import json,sqlite3,time
from datetime import datetime,timezone

def ensure_schema(conn):
    conn.executescript("""
    create table if not exists bottleneck_observations(
      id integer primary key autoincrement,
      created_at text not null,
      payload_json text not null
    );
    """);conn.commit()

def _count(conn,sql,args=()):
    r=conn.execute(sql,args).fetchone(); return int(r[0] or 0) if r else 0

def analyze(conn,now_epoch=None,persist=False):
    ensure_schema(conn);now_epoch=time.time() if now_epoch is None else float(now_epoch)
    incomplete=_count(conn,"select count(*) from tasks where status not in ('DONE','SUPERSEDED','CANCELLED')")
    ready=_count(conn,"select count(*) from tasks where status='READY'")
    active=_count(conn,"select count(*) from tasks where status='ACTIVE'")
    evidence=_count(conn,"select count(*) from tasks where status='BLOCKED_EVIDENCE'")
    blocked_dep=_count(conn,"select count(*) from tasks where status='BLOCKED_DEP'")
    queue=_count(conn,"select count(*) from integration_queue where status not in ('INTEGRATED','SUPERSEDED')")
    regressions=_count(conn,"select count(*) from regressions where status='OPEN'")
    verify_fail=_count(conn,"select count(*) from verification where status='FAIL' and ran_at>=datetime('now','-2 hours')")
    overload=0
    try:
        r=conn.execute("""select max(ts_epoch) from brain_events where event_type='MACHINE_OVERLOADED'""").fetchone()
        overload=1 if r and r[0] and now_epoch-float(r[0])<600 else 0
    except sqlite3.OperationalError: pass
    denomin=max(1,incomplete)
    candidates=[
      {"kind":"RUNNABLE_SHORTAGE","severity":1.0 if incomplete and ready==0 and active==0 else (0.5 if incomplete and ready==0 else 0.0),"metrics":{"incomplete":incomplete,"ready":ready,"active":active}},
      {"kind":"EVIDENCE","severity":min(1.0,evidence/denomin*2.0),"metrics":{"blocked_evidence":evidence,"incomplete":incomplete}},
      {"kind":"DEPENDENCY","severity":min(1.0,blocked_dep/denomin*2.0),"metrics":{"blocked_dep":blocked_dep,"incomplete":incomplete}},
      {"kind":"VERIFICATION","severity":min(1.0,(verify_fail*0.5)+(queue*0.08)),"metrics":{"recent_failures":verify_fail,"integration_backlog":queue}},
      {"kind":"INTEGRATION","severity":min(1.0,queue/8.0),"metrics":{"integration_backlog":queue}},
      {"kind":"REGRESSION","severity":min(1.0,regressions/3.0),"metrics":{"open_regressions":regressions}},
      {"kind":"RESOURCE","severity":1.0 if overload else 0.0,"metrics":{"recent_overload":bool(overload)}},
      {"kind":"IMPLEMENTATION","severity":min(1.0,active/4.0),"metrics":{"active_tasks":active}},
    ]
    order={"RUNNABLE_SHORTAGE":0,"REGRESSION":1,"VERIFICATION":2,"INTEGRATION":3,"EVIDENCE":4,"DEPENDENCY":5,"RESOURCE":6,"IMPLEMENTATION":7}
    ranked=sorted(candidates,key=lambda x:(-x["severity"],order.get(x["kind"],99),x["kind"]))
    payload={"ranked":[x for x in ranked if x["severity"]>0],"metrics":{"incomplete":incomplete,"ready":ready,"active":active,"evidence":evidence,"blocked_dep":blocked_dep,"integration_backlog":queue,"open_regressions":regressions}}
    if persist:
        cur=conn.execute("insert into bottleneck_observations(created_at,payload_json) values(?,?)",(datetime.now(timezone.utc).isoformat(timespec="seconds"),json.dumps(payload,sort_keys=True)));conn.commit();payload["observation_id"]=int(cur.lastrowid)
    return payload
