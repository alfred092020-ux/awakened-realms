from __future__ import annotations
import json, sqlite3
from datetime import datetime, timezone

def ensure_schema(conn):
    conn.executescript("""
    create table if not exists behavior_trace_checks(
      id integer primary key autoincrement,
      sha text not null,
      objective_id text,
      checkpoint text not null,
      expected_json text not null,
      observed_json text not null,
      divergence_json text not null,
      provenance_json text not null default '{}',
      verdict text not null,
      created_at text not null
    );
    create index if not exists behavior_trace_checkpoint_idx on behavior_trace_checks(checkpoint,id);
    """); conn.commit()

def compare(expected,observed):
    exp_events=list(expected.get("events",[])); obs_events=list(observed.get("events",[]))
    mismatches=[]
    n=max(len(exp_events),len(obs_events))
    for i in range(n):
        e=exp_events[i] if i<len(exp_events) else None
        o=obs_events[i] if i<len(obs_events) else None
        if e!=o: mismatches.append({"index":i,"expected":e,"observed":o})
    exp_final=expected.get("final_state"); obs_final=observed.get("final_state")
    final_match=exp_final==obs_final
    return {"event_count_expected":len(exp_events),"event_count_observed":len(obs_events),
            "event_mismatches":mismatches,"final_state_match":final_match,
            "expected_final_state":exp_final,"observed_final_state":obs_final}

def record(conn,*,sha,checkpoint,expected,observed,objective_id=None,provenance=None):
    ensure_schema(conn)
    if len(sha)!=40: raise ValueError("exact 40-character SHA required")
    if not expected or ("events" not in expected and "final_state" not in expected):
        raise ValueError("expected trace is required; missing truth cannot pass")
    div=compare(expected,observed)
    verdict="PASS" if not div["event_mismatches"] and div["final_state_match"] else "FAIL"
    cur=conn.execute("""insert into behavior_trace_checks(
      sha,objective_id,checkpoint,expected_json,observed_json,divergence_json,provenance_json,verdict,created_at
      ) values(?,?,?,?,?,?,?,?,?)""",(sha,objective_id,checkpoint,json.dumps(expected,sort_keys=True),
      json.dumps(observed,sort_keys=True),json.dumps(div,sort_keys=True),json.dumps(provenance or {},sort_keys=True),
      verdict,datetime.now(timezone.utc).isoformat(timespec="seconds")))
    conn.commit()
    return {"id":int(cur.lastrowid),"verdict":verdict,"divergence":div}

def _row(r):
    return {"id":r[0],"sha":r[1],"objective_id":r[2],"checkpoint":r[3],"expected":json.loads(r[4]),
            "observed":json.loads(r[5]),"divergence":json.loads(r[6]),"provenance":json.loads(r[7]),
            "verdict":r[8],"created_at":r[9]}

def latest(conn,checkpoint=None):
    ensure_schema(conn)
    if checkpoint:
        r=conn.execute("""select id,sha,objective_id,checkpoint,expected_json,observed_json,divergence_json,
          provenance_json,verdict,created_at from behavior_trace_checks where checkpoint=? order by id desc limit 1""",(checkpoint,)).fetchone()
        return None if not r else _row(r)
    rows=conn.execute("""select b.id,b.sha,b.objective_id,b.checkpoint,b.expected_json,b.observed_json,b.divergence_json,
      b.provenance_json,b.verdict,b.created_at from behavior_trace_checks b
      join (select checkpoint,max(id) id from behavior_trace_checks group by checkpoint) x on x.id=b.id order by b.checkpoint""")
    return [_row(r) for r in rows]

def failures(conn):
    return [x for x in latest(conn) if x["verdict"]=="FAIL"]
