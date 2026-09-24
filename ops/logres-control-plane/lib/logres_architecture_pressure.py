from __future__ import annotations
import json,sqlite3
from datetime import datetime,timezone

def ensure_schema(conn):
    conn.executescript("""
    create table if not exists architecture_pressure_observations(
      id integer primary key autoincrement,
      created_at text not null,
      payload_json text not null
    );
    """);conn.commit()

def clamp(v): return max(0.0,min(1.0,float(v)))

def evaluate(metrics):
    m=dict(metrics)
    dimensions={
      "workspace_entropy":clamp(max(m.get("worktrees",0)/120.0,m.get("local_branches",0)/160.0,m.get("remote_branches",0)/260.0)),
      "queue_pressure":clamp(m.get("integration_backlog",0)/12.0),
      "blocked_pressure":clamp((m.get("blocked_evidence",0)+m.get("blocked_dep",0))/max(1,m.get("incomplete_tasks",0))),
      "state_consistency":clamp(m.get("stale_engine_records",0)/5.0),
      "schema_complexity":clamp(m.get("control_tables",0)/60.0),
      "utilization_imbalance":clamp(abs(m.get("worker_utilization",0.0)-0.75)/0.75),
      "decision_memory_gap":clamp(1.0-(m.get("decision_records",0)/max(1,m.get("significant_events",0))*10.0)),
    }
    weights={"workspace_entropy":.20,"queue_pressure":.15,"blocked_pressure":.20,"state_consistency":.15,
             "schema_complexity":.10,"utilization_imbalance":.10,"decision_memory_gap":.10}
    score=sum(dimensions[k]*weights[k] for k in weights)
    rec=[]
    if dimensions["workspace_entropy"]>=.65: rec.append({"kind":"WORKSPACE_LIFECYCLE","reason":"worktree/branch population is high","action":"Archive only clean integrated terminal workspaces using lifecycle plan."})
    if dimensions["blocked_pressure"]>=.45: rec.append({"kind":"MISSION_GAP_PLANNING","reason":"large blocked share","action":"Separate evidence ceilings from implementable gaps and feed explicit contracts."})
    if dimensions["state_consistency"]>0: rec.append({"kind":"ENGINE_RECONCILE","reason":"stale engine state detected","action":"Run bounded engine-state reconciliation."})
    if dimensions["queue_pressure"]>=.5: rec.append({"kind":"INTEGRATION_THROUGHPUT","reason":"integration backlog elevated","action":"Measure verification/preflight bottleneck before increasing worker count."})
    if dimensions["decision_memory_gap"]>=.6: rec.append({"kind":"DECISION_JOURNAL","reason":"few structured decisions relative to significant events","action":"Capture why/alternatives/evidence for architecture-level decisions."})
    level="LOW" if score<.30 else "MODERATE" if score<.55 else "HIGH" if score<.75 else "CRITICAL"
    return {"score":round(score,4),"level":level,"dimensions":{k:round(v,4) for k,v in dimensions.items()},"metrics":m,"recommendations":rec}

def persist(conn,payload):
    ensure_schema(conn)
    cur=conn.execute("insert into architecture_pressure_observations(created_at,payload_json) values(?,?)",
      (datetime.now(timezone.utc).isoformat(timespec="seconds"),json.dumps(payload,sort_keys=True)));conn.commit()
    return int(cur.lastrowid)
