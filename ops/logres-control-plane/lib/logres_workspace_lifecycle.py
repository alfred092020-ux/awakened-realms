from __future__ import annotations
import sqlite3

def classify(record):
    if record.get("protected"): return "LIVE"
    if record.get("active_lease") or record.get("task_status")=="ACTIVE": return "LIVE"
    if record.get("dirty"): return "KEEP_DIRTY"
    if record.get("unique_commits",0)>0 and not record.get("integrated"): return "WARM"
    if record.get("task_status") in {"DONE","SUPERSEDED","CANCELLED","BLOCKED_EVIDENCE"} and record.get("integrated"):
        return "ARCHIVE_CANDIDATE"
    return "WARM"

def task_for_branch(conn,branch):
    r=conn.execute("select id,status from tasks where branch=? order by updated_at desc limit 1",(branch,)).fetchone()
    return (r[0],r[1]) if r else (None,None)

def integrated_for_task(conn,task_id):
    if not task_id:return False
    r=conn.execute("""select 1 from integration_queue where task_id=? and status in ('INTEGRATED','SUPERSEDED') limit 1""",(task_id,)).fetchone()
    return bool(r)

def lease_for_task(conn,task_id):
    if not task_id:return False
    return bool(conn.execute("select 1 from brain_task_leases where task_id=?",(task_id,)).fetchone())
