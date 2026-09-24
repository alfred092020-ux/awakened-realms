from __future__ import annotations
import json, sqlite3, time
from datetime import datetime, timezone

VALID={"PASS","FAIL","REVIEW"}
def ensure_schema(conn):
    conn.executescript("""
    create table if not exists visual_truth_checks(
      id integer primary key autoincrement,
      sha text not null,
      checkpoint text not null,
      objective_id text,
      reference_artifact text,
      observed_artifact text not null,
      viewport_json text not null default '{}',
      device_json text not null default '{}',
      metrics_json text not null default '{}',
      verdict text not null,
      created_at text not null,
      created_epoch real not null
    );
    create index if not exists visual_truth_checkpoint_idx on visual_truth_checks(checkpoint,id);
    """); conn.commit()

def record(conn,*,sha,checkpoint,observed_artifact,verdict,reference_artifact=None,
           objective_id=None,viewport=None,device=None,metrics=None,created_at=None):
    ensure_schema(conn)
    verdict=verdict.upper()
    if verdict not in VALID: raise ValueError("invalid verdict")
    if len(sha)!=40: raise ValueError("exact 40-character SHA required")
    if verdict=="PASS" and (not reference_artifact or not metrics):
        raise ValueError("PASS requires explicit reference artifact and measurement metrics")
    stamp=created_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    epoch=datetime.fromisoformat(stamp.replace("Z","+00:00")).timestamp()
    cur=conn.execute("""insert into visual_truth_checks(
      sha,checkpoint,objective_id,reference_artifact,observed_artifact,viewport_json,device_json,metrics_json,verdict,created_at,created_epoch
    ) values(?,?,?,?,?,?,?,?,?,?,?)""",(sha,checkpoint,objective_id,reference_artifact,observed_artifact,
      json.dumps(viewport or {},sort_keys=True),json.dumps(device or {},sort_keys=True),
      json.dumps(metrics or {},sort_keys=True),verdict,stamp,epoch))
    conn.commit(); return int(cur.lastrowid)

def _row(r):
    return {"id":r[0],"sha":r[1],"checkpoint":r[2],"objective_id":r[3],"reference_artifact":r[4],
      "observed_artifact":r[5],"viewport":json.loads(r[6]),"device":json.loads(r[7]),
      "metrics":json.loads(r[8]),"verdict":r[9],"created_at":r[10]}

def history(conn,checkpoint):
    ensure_schema(conn)
    return [_row(r) for r in conn.execute("""select id,sha,checkpoint,objective_id,reference_artifact,observed_artifact,
      viewport_json,device_json,metrics_json,verdict,created_at from visual_truth_checks where checkpoint=? order by id""",(checkpoint,))]

def latest(conn,checkpoint=None):
    ensure_schema(conn)
    if checkpoint:
        r=conn.execute("""select id,sha,checkpoint,objective_id,reference_artifact,observed_artifact,
          viewport_json,device_json,metrics_json,verdict,created_at from visual_truth_checks where checkpoint=? order by id desc limit 1""",(checkpoint,)).fetchone()
        return None if not r else _row(r)
    rows=conn.execute("""select v.id,v.sha,v.checkpoint,v.objective_id,v.reference_artifact,v.observed_artifact,
      v.viewport_json,v.device_json,v.metrics_json,v.verdict,v.created_at
      from visual_truth_checks v join (select checkpoint,max(id) id from visual_truth_checks group by checkpoint) x on x.id=v.id
      order by v.checkpoint""")
    return [_row(r) for r in rows]

def regressions(conn):
    ensure_schema(conn); out=[]
    for row in latest(conn):
        hist=history(conn,row["checkpoint"])
        prior_pass=any(x["verdict"]=="PASS" for x in hist[:-1])
        if prior_pass and row["verdict"]=="FAIL": out.append(row)
    return out
