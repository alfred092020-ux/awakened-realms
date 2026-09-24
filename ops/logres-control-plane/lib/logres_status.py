from __future__ import annotations
import sqlite3

def _exists(conn,name):
    return conn.execute("select 1 from sqlite_master where type='table' and name=?",(name,)).fetchone() is not None

def _one(conn,sql,args=(),default=0):
    r=conn.execute(sql,args).fetchone(); return default if r is None else r[0]

def build_status(conn):
    unavailable=[]
    out={}
    if _exists(conn,"mission_objectives"):
        from logres_mission import mission_status
        m=mission_status(conn)
        roots=m.get("missions",[])
        out["mission"]={
          "roots":roots,
          "uncovered_count":len(m.get("uncovered",[])),
          "leaf_counts":m.get("leaf_counts",{}),
          "progress_percent":roots[0]["progress_percent"] if roots else 0.0,
          "state":roots[0]["state"] if roots else "EMPTY",
        }
    else: out["mission"]=None;unavailable.append("mission")
    if _exists(conn,"brain_task_leases"):
        out["active_workers"]=[dict(r) for r in conn.execute("""select task_id,chat_id,branch,progress,lease_until_epoch from brain_task_leases order by renewed_at desc""")]
    else: out["active_workers"]=[];unavailable.append("leases")
    if _exists(conn,"integration_queue"):
        out["integration_backlog"]=[dict(r) for r in conn.execute("""select task_id,sha,branch,status,updated_at from integration_queue where status not in ('INTEGRATED','SUPERSEDED') order by updated_at desc""")]
    else: out["integration_backlog"]=[];unavailable.append("integration_queue")
    if _exists(conn,"regressions"):
        out["open_regressions"]=[dict(r) for r in conn.execute("select * from regressions where status='OPEN' order by rowid desc")]
    else: out["open_regressions"]=[];unavailable.append("regressions")
    if _exists(conn,"tasks"):
        out["evidence_ceilings"]=[dict(r) for r in conn.execute("""select id,title,note,updated_at from tasks where status='BLOCKED_EVIDENCE' order by updated_at desc""")]
    else: out["evidence_ceilings"]=[];unavailable.append("tasks")
    if _exists(conn,"verification"):
        r=conn.execute("""select ref,sha,mode,status,duration_sec,ran_at,details from verification order by ran_at desc limit 1""").fetchone()
        out["latest_verification"]=dict(r) if r else None
    else: out["latest_verification"]=None;unavailable.append("verification")
    if _exists(conn,"visual_truth_checks"):
        out["visual_failures"]=[dict(r) for r in conn.execute("""select v.checkpoint,v.sha,v.verdict,v.created_at from visual_truth_checks v join (select checkpoint,max(id) id from visual_truth_checks group by checkpoint)x on x.id=v.id where v.verdict='FAIL' order by v.checkpoint""")]
    else: out["visual_failures"]=[];unavailable.append("visual_truth")
    if _exists(conn,"behavior_trace_checks"):
        out["behavior_failures"]=[dict(r) for r in conn.execute("""select b.checkpoint,b.sha,b.verdict,b.created_at from behavior_trace_checks b join (select checkpoint,max(id) id from behavior_trace_checks group by checkpoint)x on x.id=b.id where b.verdict='FAIL' order by b.checkpoint""")]
    else: out["behavior_failures"]=[];unavailable.append("behavior_trace")
    out["unavailable"]=unavailable
    out["summary"]={
      "active_workers":len(out["active_workers"]),
      "integration_backlog":len(out["integration_backlog"]),
      "open_regressions":len(out["open_regressions"]),
      "evidence_ceilings":len(out["evidence_ceilings"]),
      "visual_failures":len(out["visual_failures"]),
      "behavior_failures":len(out["behavior_failures"]),
    }
    return out

def render_text(status):
    m=status.get("mission") or {}
    s=status["summary"]
    lines=[
      f"Mission: {m.get('state','UNAVAILABLE')} {m.get('progress_percent',0):.2f}%",
      f"Uncovered objectives: {m.get('uncovered_count','?')}",
      f"Active workers: {s['active_workers']}",
      f"Integration backlog: {s['integration_backlog']}",
      f"Open regressions: {s['open_regressions']}",
      f"Evidence ceilings: {s['evidence_ceilings']}",
      f"Visual failures: {s['visual_failures']}",
      f"Behavior failures: {s['behavior_failures']}",
    ]
    if status.get("latest_verification"):
        v=status["latest_verification"];lines.append(f"Latest verification: {v['status']} {v['mode']} {str(v['sha'] or '')[:12]}")
    if status["unavailable"]:lines.append("Unavailable: "+", ".join(status["unavailable"]))
    return "\n".join(lines)
