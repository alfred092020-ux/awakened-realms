from __future__ import annotations
import json, sqlite3

def ensure_schema(conn):
    conn.executescript("""
    create table if not exists mission_gap_scans(
      id integer primary key autoincrement,
      created_at text not null default (datetime('now')),
      payload_json text not null
    );
    """); conn.commit()

def _rows(conn,sql,args=()):
    return [dict(r) for r in conn.execute(sql,args)]

def _leaf_objectives(conn):
    return _rows(conn,"""select o.id,o.title,o.definition_of_done
      from mission_objectives o
      where not exists(select 1 from mission_objectives c where c.parent_id=o.id)
      order by o.sort_order,o.id""")

def _links(conn,obj):
    return _rows(conn,"select milestone_id,task_id,gate_type from mission_links where objective_id=? order by gate_type,milestone_id,task_id",(obj,))

def _task_refs(conn,links):
    out=[]
    for link in links:
        tid=link.get("task_id")
        if tid:
            row=conn.execute("select id,status,title,note from tasks where id=?",(tid,)).fetchone()
            if row: out.append({"type":"task","id":row["id"],"status":row["status"],"title":row["title"],"note":row["note"]})
        mid=link.get("milestone_id")
        if mid:
            row=conn.execute("select id,status,title,definition_of_done from milestones where id=?",(mid,)).fetchone()
            if row: out.append({"type":"milestone","id":row["id"],"status":row["status"],"title":row["title"],"definition_of_done":row["definition_of_done"]})
    return out

def _classify(refs):
    if not refs: return "UNCOVERED","IMPLEMENTATION_GAP"
    statuses={str(r["status"]) for r in refs}
    if statuses and all(s in {"DONE","COMPLETE","RESOLVED"} for s in statuses):
        return "COMPLETE","NONE"
    if statuses & {"ACTIVE","READY","IN_PROGRESS"}:
        return "IN_PROGRESS","RUNNABLE_OR_ACTIVE"
    if statuses and all(s in {"BLOCKED_EVIDENCE","WAITING_EXTERNAL"} for s in statuses):
        return "WAITING_EXTERNAL","EVIDENCE_CEILING"
    if statuses & {"BLOCKED_DEP","BLOCKED"}:
        return "BLOCKED","DEPENDENCY_BLOCKED"
    return "UNCOVERED","IMPLEMENTATION_GAP"

def scan(conn,persist=False):
    ensure_schema(conn)
    gaps=[]; counts={}
    for obj in _leaf_objectives(conn):
        links=_links(conn,obj["id"]); refs=_task_refs(conn,links)
        state,kind=_classify(refs)
        item={"objective_id":obj["id"],"title":obj["title"],"definition_of_done":obj["definition_of_done"],
              "state":state,"gap_kind":kind,"references":refs}
        counts[state]=counts.get(state,0)+1
        if state!="COMPLETE": gaps.append(item)
    payload={"counts":counts,"gaps":gaps,"gap_count":len(gaps)}
    if persist:
        cur=conn.execute("insert into mission_gap_scans(payload_json) values(?)",(json.dumps(payload,sort_keys=True),))
        conn.commit(); payload["scan_id"]=int(cur.lastrowid)
    return payload

def latest(conn):
    ensure_schema(conn)
    row=conn.execute("select id,created_at,payload_json from mission_gap_scans order by id desc limit 1").fetchone()
    if not row: return {"available":False}
    return {"available":True,"scan_id":row[0],"created_at":row[1],"payload":json.loads(row[2])}
