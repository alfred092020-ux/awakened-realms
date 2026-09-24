from __future__ import annotations
import json,sqlite3
from datetime import datetime,timezone

def ensure_schema(conn):
    conn.executescript("""
    create table if not exists shadow_scheduler_runs(
      id integer primary key autoincrement,
      created_at text not null,
      inputs_json text not null,
      authoritative_json text not null,
      shadow_json text not null
    );
    """);conn.commit()

def _avg(conn,sql,args=(),default=0.0):
    r=conn.execute(sql,args).fetchone(); return default if not r or r[0] is None else float(r[0])

def score_candidates(conn):
    rows=conn.execute("""select t.id,coalesce(t.priority,9),coalesce(m.work_type,'implementation'),
      coalesce(m.expected_minutes,60),coalesce(m.concurrency_key,''),coalesce(m.evidence_policy,'')
      from tasks t left join task_metadata m on m.task_id=t.id where t.status='READY' order by t.id""")
    out=[]
    for tid,priority,work_type,minutes,key,evidence in rows:
        avg_cost=_avg(conn,"""select avg(coalesce(estimated_cost_usd,0)) from optimizer_observations
          where work_type=?""",(work_type,))
        failures=_avg(conn,"""select avg(case when outcome in ('FAILED','INFRA_FAILURE') then 1.0 else 0.0 end)
          from optimizer_observations where work_type=?""",(work_type,))
        conflict=1.0 if key and conn.execute("""select 1 from tasks t join task_metadata m on m.task_id=t.id
          where t.status='ACTIVE' and m.concurrency_key=? limit 1""",(key,)).fetchone() else 0.0
        ev=0.0
        e=str(evidence).lower()
        if any(x in e for x in ("historical","external","unknown","inference")):ev=.7
        elif e:ev=.25
        progress=max(1.0,100.0-float(priority)*8.0)
        denom=1.0+float(minutes)/60.0+avg_cost*10.0+conflict*2.5+ev*1.5+failures*2.0
        score=progress/denom
        out.append({"task_id":tid,"score":round(score,6),"progress_value":round(progress,3),
          "duration_minutes":int(minutes),"cost_estimate":round(avg_cost,6),"conflict_risk":conflict,
          "evidence_uncertainty":ev,"rework_risk":round(failures,4),"work_type":work_type})
    return sorted(out,key=lambda x:(-x["score"],x["task_id"]))

def compare(conn,authoritative_ids,persist=False):
    ensure_schema(conn);shadow=score_candidates(conn);shadow_ids=[x["task_id"] for x in shadow]
    auth=list(authoritative_ids)
    overlap=len(set(auth[:5])&set(shadow_ids[:5]))
    payload={"authoritative":auth,"shadow":shadow,"top5_overlap":overlap,
             "authority":"SHADOW_ONLY_NO_DISPATCH"}
    if persist:
        cur=conn.execute("""insert into shadow_scheduler_runs(created_at,inputs_json,authoritative_json,shadow_json)
          values(?,?,?,?)""",(datetime.now(timezone.utc).isoformat(timespec="seconds"),json.dumps({"ready_count":len(shadow)}),
          json.dumps(auth),json.dumps(shadow,sort_keys=True)));conn.commit();payload["run_id"]=int(cur.lastrowid)
    return payload
