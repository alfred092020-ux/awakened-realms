from __future__ import annotations
import sqlite3
from datetime import datetime, timezone

TERMINAL_TASK={"DONE","SUPERSEDED","CANCELLED","BLOCKED_EVIDENCE"}
COPILOT_LIVE={"ASSIGNING","ACTIVE","PR_READY","VERIFYING","QUEUED"}
ROUTE_TERMINAL_PATH={
  "ASSIGNING":["ACTIVE","SUPERSEDED"],
  "ROUTED":["ASSIGNING","ACTIVE","SUPERSEDED"],
  "ACTIVE":["SUPERSEDED"],
  "PR_READY":["SUPERSEDED"],
  "VERIFYING":["QUEUED","SUPERSEDED"],
  "QUEUED":["SUPERSEDED"],
}
ROUTE_LIVE=set(ROUTE_TERMINAL_PATH)
SWARM_LIVE={"STARTING","RUNNING"}

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def in_states(states):
    return ",".join(f"'{s}'" for s in sorted(states))

def plan(conn):
    actions=[]
    for r in conn.execute(f"""select c.id,c.task_id,c.state,t.status,c.branch,c.candidate_sha
      from copilot_jobs c left join tasks t on t.id=c.task_id
      where c.state in ({in_states(COPILOT_LIVE)})"""):
        task_status=r[3] or "MISSING"
        if task_status in TERMINAL_TASK or task_status=="MISSING":
            actions.append({"engine":"copilot","id":r[0],"task_id":r[1],"from_state":r[2],
              "to_state":"SUPERSEDED","reason":f"task_{task_status.lower()}","branch":r[4],"candidate_sha":r[5]})
    for r in conn.execute(f"""select r.id,r.task_id,r.state,t.status,r.external_ref,r.last_error
      from route_jobs r left join tasks t on t.id=r.task_id
      where r.state in ({in_states(ROUTE_LIVE)})"""):
        task_status=r[3] or "MISSING"
        if task_status in TERMINAL_TASK or task_status=="MISSING":
            actions.append({"engine":"route","id":r[0],"task_id":r[1],"from_state":r[2],
              "to_state":"SUPERSEDED","reason":f"task_{task_status.lower()}","external_ref":r[4],"last_error":r[5]})
    for r in conn.execute("""select s.id,s.task_id,s.state,t.status,s.pid,s.artifact_path,s.last_error
      from swarm_jobs s left join tasks t on t.id=s.task_id
      where s.state in ('STARTING','RUNNING')"""):
        task_status=r[3] or "MISSING"
        if task_status in TERMINAL_TASK or task_status=="MISSING":
            actions.append({"engine":"swarm","id":r[0],"task_id":r[1],"from_state":r[2],
              "to_state":"SUPERSEDED","reason":f"task_{task_status.lower()}","pid":r[4],
              "artifact_path":r[5],"last_error":r[6]})
    for r in conn.execute("""select l.task_id,l.chat_id,l.branch,t.status,l.lease_until_epoch
      from brain_task_leases l left join tasks t on t.id=l.task_id"""):
        task_status=r[3] or "MISSING"
        if task_status in TERMINAL_TASK or task_status=="MISSING":
            actions.append({"engine":"lease","id":r[0],"task_id":r[0],"from_state":"LEASED",
              "to_state":"RELEASED","reason":f"task_{task_status.lower()}","chat_id":r[1],
              "branch":r[2],"lease_until_epoch":r[4]})
    return sorted(actions,key=lambda x:(x["engine"],str(x["id"])))

def apply(conn):
    actions=plan(conn); stamp=now()
    for a in actions:
        if a["engine"]=="copilot":
            conn.execute("update copilot_jobs set state='SUPERSEDED',updated_at=? where id=? and state=?",
                         (stamp,a["id"],a["from_state"]))
        elif a["engine"]=="route":
            state=a["from_state"]
            for nxt in ROUTE_TERMINAL_PATH.get(state,["SUPERSEDED"]):
                cur=conn.execute("update route_jobs set state=?,updated_at=? where id=? and state=?",
                                 (nxt,stamp,a["id"],state))
                if cur.rowcount!=1:
                    break
                state=nxt
        elif a["engine"]=="swarm":
            conn.execute("""update swarm_jobs set state='SUPERSEDED',updated_at=?,finished_at=coalesce(finished_at,?)
              where id=? and state=?""",(stamp,stamp,a["id"],a["from_state"]))
        else:
            conn.execute("delete from brain_task_leases where task_id=?",(a["task_id"],))
    conn.commit()
    return actions
