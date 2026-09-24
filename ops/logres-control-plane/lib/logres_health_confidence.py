from __future__ import annotations
import json,math,sqlite3,time
from datetime import datetime,timezone

def ensure_schema(conn):
    conn.executescript("""
    create table if not exists health_confidence_observations(
      id integer primary key autoincrement,
      subsystem text not null,
      source text not null,
      observed_status text not null,
      base_confidence real not null,
      observed_epoch real not null,
      observed_at text not null,
      metadata_json text not null default '{}'
    );
    create index if not exists health_confidence_subsystem_idx on health_confidence_observations(subsystem,observed_epoch);
    """);conn.commit()

def record(conn,subsystem,source,status,confidence=1.0,observed_epoch=None,metadata=None):
    ensure_schema(conn);status=status.upper()
    if status not in {"PASS","WARN","FAIL","UNKNOWN"}:raise ValueError("invalid status")
    confidence=max(0.0,min(1.0,float(confidence)));epoch=time.time() if observed_epoch is None else float(observed_epoch)
    stamp=datetime.fromtimestamp(epoch,timezone.utc).isoformat(timespec="seconds")
    cur=conn.execute("""insert into health_confidence_observations(
      subsystem,source,observed_status,base_confidence,observed_epoch,observed_at,metadata_json
      ) values(?,?,?,?,?,?,?)""",(subsystem,source,status,confidence,epoch,stamp,json.dumps(metadata or {},sort_keys=True)))
    conn.commit();return int(cur.lastrowid)

def decayed(base,age_seconds,half_life_seconds):
    if half_life_seconds<=0:return 0.0
    return max(0.0,min(1.0,float(base)*(0.5**(max(0.0,age_seconds)/float(half_life_seconds)))))

def subsystem(conn,subsystem,now_epoch=None,half_life_seconds=900):
    ensure_schema(conn);now_epoch=time.time() if now_epoch is None else float(now_epoch)
    rows=list(conn.execute("""select source,observed_status,base_confidence,observed_epoch,observed_at,metadata_json
      from health_confidence_observations where subsystem=? order by observed_epoch desc""",(subsystem,)))
    if not rows:return {"subsystem":subsystem,"status":"UNKNOWN","confidence":0.0,"observations":[]}
    obs=[]
    for r in rows:
        conf=decayed(r[2],now_epoch-float(r[3]),half_life_seconds)
        obs.append({"source":r[0],"status":r[1],"confidence":round(conf,6),"observed_at":r[4],"metadata":json.loads(r[5])})
    credible=[x for x in obs if x["confidence"]>=0.25]
    if not credible:status="UNKNOWN"
    elif any(x["status"]=="FAIL" and x["confidence"]>=0.5 for x in credible):status="FAIL"
    elif any(x["status"]=="WARN" and x["confidence"]>=0.5 for x in credible):status="WARN"
    elif any(x["status"]=="PASS" for x in credible):status="PASS"
    else:status="UNKNOWN"
    confidence=max((x["confidence"] for x in credible),default=0.0)
    return {"subsystem":subsystem,"status":status,"confidence":round(confidence,6),"observations":obs}

def summary(conn,now_epoch=None,half_life_seconds=900):
    ensure_schema(conn)
    names=[r[0] for r in conn.execute("select distinct subsystem from health_confidence_observations order by subsystem")]
    return [subsystem(conn,n,now_epoch,half_life_seconds) for n in names]
