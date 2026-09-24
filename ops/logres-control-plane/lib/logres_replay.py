from __future__ import annotations
import hashlib, json, sqlite3
from datetime import datetime, timezone

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def ensure_schema(conn):
    conn.executescript("""
    create table if not exists project_snapshots(
      id integer primary key autoincrement,
      ts text not null,
      ts_epoch real not null,
      integration_sha text not null,
      brain_event_cursor integer not null default 0,
      task_history_cursor integer not null default 0,
      journal_cursor integer not null default 0,
      decision_cursor integer not null default 0,
      payload_json text not null,
      payload_sha256 text not null
    );
    create index if not exists project_snapshots_time_idx on project_snapshots(ts_epoch,id);
    """)
    conn.commit()

def _exists(conn,name):
    return conn.execute("select 1 from sqlite_master where type='table' and name=?",(name,)).fetchone() is not None

def _rows(conn,sql,args=()):
    return [dict(r) for r in conn.execute(sql,args)]

def _cursor(conn,table):
    if not _exists(conn,table): return 0
    row=conn.execute(f"select coalesce(max(id),0) from {table}").fetchone()
    return int(row[0] or 0)

def build_payload(conn,integration_sha):
    unavailable=[]
    payload={"integration_sha":integration_sha}
    if _exists(conn,"tasks"):
        payload["tasks"]=_rows(conn,"select id,priority,lane,title,status,branch,owner,note,updated_at from tasks order by id")
    else: payload["tasks"]=[]; unavailable.append("tasks")
    if _exists(conn,"brain_task_leases"):
        payload["leases"]=_rows(conn,"select task_id,chat_id,branch,lease_until_epoch,acquired_at,renewed_at,progress,note from brain_task_leases order by task_id")
    else: payload["leases"]=[]; unavailable.append("leases")
    if _exists(conn,"integration_queue"):
        payload["integration_queue"]=_rows(conn,"select task_id,sha,branch,status,verification_mode,queued_at,updated_at,ready_at,integrated_at from integration_queue order by queued_at,task_id,sha")
    else: payload["integration_queue"]=[]; unavailable.append("integration_queue")
    if _exists(conn,"verification"):
        payload["verification"]=_rows(conn,"select ref,sha,mode,status,duration_sec,ran_at,details from verification order by ran_at,ref")
    else: payload["verification"]=[]; unavailable.append("verification")
    if _exists(conn,"mission_objectives"):
        payload["mission_objectives"]=_rows(conn,"select id,parent_id,title,weight,definition_of_done,status_override,sort_order from mission_objectives order by sort_order,id")
        payload["mission_links"]=_rows(conn,"select objective_id,milestone_id,task_id,gate_type from mission_links order by objective_id,gate_type")
    else:
        payload["mission_objectives"]=[]; payload["mission_links"]=[]; unavailable.append("mission")
    if _exists(conn,"knowledge_nodes"):
        payload["knowledge_counts"]={
          "nodes":conn.execute("select count(*) from knowledge_nodes").fetchone()[0],
          "edges":conn.execute("select count(*) from knowledge_edges").fetchone()[0] if _exists(conn,"knowledge_edges") else 0
        }
    else: payload["knowledge_counts"]={}; unavailable.append("knowledge")
    payload["cursors"]={
      "brain_events":_cursor(conn,"brain_events"),
      "task_state_history":_cursor(conn,"task_state_history"),
      "project_journal":_cursor(conn,"project_journal"),
      "project_decisions":_cursor(conn,"project_decisions"),
    }
    payload["unavailable_historical_fields"]=unavailable
    return payload

def capture(conn,integration_sha,ts=None,ts_epoch=None):
    ensure_schema(conn)
    stamp=ts or now()
    if ts_epoch is None:
        ts_epoch=datetime.fromisoformat(stamp.replace("Z","+00:00")).timestamp()
    payload=build_payload(conn,integration_sha)
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"))
    digest=hashlib.sha256(raw.encode()).hexdigest()
    c=payload["cursors"]
    cur=conn.execute("""insert into project_snapshots(
      ts,ts_epoch,integration_sha,brain_event_cursor,task_history_cursor,journal_cursor,decision_cursor,payload_json,payload_sha256
      ) values(?,?,?,?,?,?,?,?,?)""",(stamp,float(ts_epoch),integration_sha,c["brain_events"],c["task_state_history"],c["project_journal"],c["project_decisions"],raw,digest))
    conn.commit()
    return {"id":int(cur.lastrowid),"ts":stamp,"integration_sha":integration_sha,"payload_sha256":digest}

def replay_at(conn,ts_epoch):
    ensure_schema(conn)
    row=conn.execute("""select id,ts,ts_epoch,integration_sha,payload_json,payload_sha256
      from project_snapshots where ts_epoch<=? order by ts_epoch desc,id desc limit 1""",(float(ts_epoch),)).fetchone()
    if row is None:
        return {"available":False,"reason":"NO_SNAPSHOT_AT_OR_BEFORE_TIMESTAMP","requested_epoch":float(ts_epoch)}
    return {"available":True,"snapshot_id":row[0],"snapshot_ts":row[1],"snapshot_epoch":row[2],
            "integration_sha":row[3],"payload":json.loads(row[4]),"payload_sha256":row[5],
            "replay_mode":"NEAREST_IMMUTABLE_SNAPSHOT"}

def list_snapshots(conn,limit=20):
    ensure_schema(conn)
    return _rows(conn,"select id,ts,ts_epoch,integration_sha,payload_sha256 from project_snapshots order by id desc limit ?",(limit,))
