from __future__ import annotations
import sqlite3

KNOWN = {
 "task":{"READY","ACTIVE","BLOCKED_DEP","BLOCKED_EVIDENCE","DONE","RESOLVED","SUPERSEDED","CANCELLED"},
 "integration":{"READY_FOR_PREFLIGHT","INTEGRATED","SUPERSEDED","QUARANTINED"},
 "preflight":{"PENDING","RUNNING","VERIFIED","FAILED","APPLIED","STALE"},
 "swarm":{"STARTING","RUNNING","DONE","BLOCKED","FAILED","SUPERSEDED"},
 "copilot":{"QUEUED","ACTIVE","VERIFYING","DONE","FAILED","SUPERSEDED","CANCELLED"},
 "frontier":{"OPEN","RESOLVED","SATURATED"},
}
TERMINAL = {
 "task":{"DONE","RESOLVED","SUPERSEDED","CANCELLED"},
 "integration":{"INTEGRATED","SUPERSEDED","QUARANTINED"},
 "preflight":{"FAILED","APPLIED","STALE"},
 "swarm":{"DONE","BLOCKED","FAILED","SUPERSEDED"},
 "copilot":{"DONE","FAILED","SUPERSEDED","CANCELLED"},
 "frontier":{"RESOLVED","SATURATED"},
}
TRANSITIONS = {
 "task":{
  None:{"READY","ACTIVE","BLOCKED_DEP","BLOCKED_EVIDENCE","DONE","RESOLVED","SUPERSEDED"},
  "READY":{"ACTIVE","BLOCKED_DEP","BLOCKED_EVIDENCE","DONE","SUPERSEDED","CANCELLED"},
  "ACTIVE":{"READY","BLOCKED_DEP","BLOCKED_EVIDENCE","DONE","RESOLVED","SUPERSEDED","CANCELLED"},
  "BLOCKED_DEP":{"READY","ACTIVE","BLOCKED_EVIDENCE","DONE","SUPERSEDED","CANCELLED"},
  "BLOCKED_EVIDENCE":{"READY","ACTIVE","DONE","RESOLVED","SUPERSEDED","CANCELLED"},
  "DONE":set(),"RESOLVED":set(),"SUPERSEDED":set(),"CANCELLED":set(),
 },
 "integration":{
  None:{"READY_FOR_PREFLIGHT","INTEGRATED","SUPERSEDED","QUARANTINED"},
  "READY_FOR_PREFLIGHT":{"INTEGRATED","SUPERSEDED","QUARANTINED"},
  "INTEGRATED":set(),"SUPERSEDED":set(),"QUARANTINED":set(),
 },
 "preflight":{
  None:{"PENDING","RUNNING","VERIFIED","FAILED","APPLIED","STALE"},
  "PENDING":{"RUNNING","STALE","FAILED"},
  "RUNNING":{"VERIFIED","FAILED","STALE"},
  "VERIFIED":{"APPLIED","STALE","FAILED"},
  "FAILED":{"STALE"},"APPLIED":set(),"STALE":set(),
 },
 "swarm":{
  None:{"STARTING","RUNNING","DONE","BLOCKED","FAILED","SUPERSEDED"},
  "STARTING":{"RUNNING","FAILED","SUPERSEDED"},
  "RUNNING":{"DONE","BLOCKED","FAILED","SUPERSEDED"},
  "DONE":set(),"BLOCKED":set(),"FAILED":set(),"SUPERSEDED":set(),
 },
 "copilot":{
  None:{"QUEUED","ACTIVE","VERIFYING","DONE","FAILED","SUPERSEDED","CANCELLED"},
  "QUEUED":{"ACTIVE","VERIFYING","FAILED","SUPERSEDED","CANCELLED"},
  "ACTIVE":{"VERIFYING","DONE","FAILED","SUPERSEDED","CANCELLED"},
  "VERIFYING":{"DONE","FAILED","SUPERSEDED","CANCELLED"},
  "DONE":set(),"FAILED":set(),"SUPERSEDED":set(),"CANCELLED":set(),
 },
 "frontier":{
  None:{"OPEN","RESOLVED","SATURATED"},
  "OPEN":{"RESOLVED","SATURATED"},
  "RESOLVED":set(),"SATURATED":set(),
 },
}

def validate_transition(entity,prior,next_state):
    if entity not in KNOWN:return {"valid":False,"reason":"UNKNOWN_ENTITY"}
    if next_state not in KNOWN[entity]:return {"valid":False,"reason":"UNKNOWN_NEXT_STATE"}
    if prior is not None and prior not in KNOWN[entity]:return {"valid":False,"reason":"UNKNOWN_PRIOR_STATE"}
    allowed=TRANSITIONS[entity].get(prior,set())
    return {"valid":next_state in allowed,"reason":"ALLOWED" if next_state in allowed else "ILLEGAL_TRANSITION",
            "entity":entity,"prior":prior,"next":next_state}

def audit_task_history(conn):
    rows=list(conn.execute("""select task_id,status,ts,id from task_state_history order by task_id,id"""))
    prior={}
    violations=[]
    for task_id,state,ts,row_id in rows:
        state=str(state) if state is not None else None
        if state is None:continue
        p=prior.get(str(task_id))
        if p==state:
            continue
        result=validate_transition("task",p,state)
        if not result["valid"]:
            violations.append({"entity":"task","entity_id":str(task_id),"history_id":row_id,"ts":ts,
                               "prior":p,"next":state,"reason":result["reason"]})
        prior[str(task_id)]=state
    return violations

def audit_current_states(conn):
    specs=[
      ("task","tasks","status","id"),("integration","integration_queue","status","task_id"),
      ("preflight","integration_preflights","status","id"),("swarm","swarm_jobs","state","id"),
      ("copilot","copilot_jobs","state","id"),("frontier","research_frontier","state","id"),
    ]
    out=[]
    for entity,table,col,idcol in specs:
        exists=conn.execute("select 1 from sqlite_master where type='table' and name=?",(table,)).fetchone()
        if not exists:continue
        for ident,state in conn.execute(f"select {idcol},{col} from {table}"):
            if str(state) not in KNOWN[entity]:
                out.append({"entity":entity,"entity_id":str(ident),"state":str(state),"reason":"UNKNOWN_CURRENT_STATE"})
    return out

def audit(conn):
    violations=audit_current_states(conn)
    if conn.execute("select 1 from sqlite_master where type='table' and name='task_state_history'").fetchone():
        violations.extend(audit_task_history(conn))
    return {"valid":not violations,"violation_count":len(violations),"violations":violations,
            "policy":"AUDIT_ONLY_NO_HISTORY_REWRITE"}
