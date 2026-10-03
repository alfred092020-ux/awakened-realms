#!/usr/bin/env python3
"""Nexus Native Command API.

Authoritative realtime read surface plus governed control bridge for the
Nexus Command Center native Android application.

Sources of truth (read-only unless noted):
  - Brain CLI (logres-brain who|history|health|digest)   -> workers/events/health
  - logres-control dashboard                            -> active/ready/blocked queue
  - control/LEAD_SNAPSHOT.json                          -> tasks/leases/claims/deps/
                                                         recovery/verification/milestones
  - git                                                 -> exact integration/candidate SHA
  - /proc                                               -> runtime system metrics
  - control/evidence + control/integration-review       -> certification artifacts
  - local sqlite                                        -> approval inbox + decisions

Control requests never act on the system directly: they are recorded to the
audit log and posted to the Brain as CONTROL_REQUEST messages for Lead
governance. The API (and therefore the app) is an owner control surface,
never root authority.
"""
import argparse, hashlib, hmac, json, os, re, secrets, sqlite3, subprocess, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("LOGRES_ROOT", "/home/ubuntu/logres"))
DB = Path(os.environ.get("NEXUS_NATIVE_API_DB", ROOT / "control/nexus-native-command-api.sqlite"))
AUDIT_DIR = Path(os.environ.get("NEXUS_NATIVE_API_AUDIT_DIR", ROOT / "control/nexus-native-command-api"))
AUDIT_LOG = AUDIT_DIR / "audit.jsonl"
REPO = Path(os.environ.get("NEXUS_NATIVE_API_REPO", ROOT / "src/awakened-realms"))
BRAIN = Path(os.environ.get("NEXUS_NATIVE_API_BRAIN", ROOT / "bin/logres-brain"))
CONTROL = Path(os.environ.get("NEXUS_NATIVE_API_CONTROL", ROOT / "bin/logres-control"))
LEAD_SNAPSHOT = Path(os.environ.get("NEXUS_NATIVE_API_LEAD_SNAPSHOT", ROOT / "control/LEAD_SNAPSHOT.json"))
SUPERVISOR_STATE = Path(os.environ.get("NEXUS_NATIVE_API_SUPERVISOR_STATE", ROOT / "control/supervisor-heartbeat.json"))
EVIDENCE_DIRS = [Path(p) for p in os.environ.get(
    "NEXUS_NATIVE_API_EVIDENCE_DIRS",
    str(ROOT / "control/evidence") + ":" + str(ROOT / "control/integration-review")).split(":") if p]
MAINTENANCE_STATE = os.environ.get("NEXUS_NATIVE_API_MAINTENANCE_STATE", "")
GOOGLE_CLIENT_ID = os.environ.get("NEXUS_NATIVE_API_GOOGLE_CLIENT_ID", "")
GOOGLE_AUTH_ALLOWED = os.environ.get("NEXUS_NATIVE_API_ALLOW_GOOGLE_AUTH", "") == "1"
GOOGLE_SESSIONS = {}
GOOGLE_SESSION_TTL = 8 * 3600
TOKEN = os.environ.get("NEXUS_NATIVE_API_TOKEN", "")
ACTOR = os.environ.get("NEXUS_NATIVE_API_ACTOR", "nexus-native-command-api")
POLL = max(1.0, float(os.environ.get("NEXUS_NATIVE_API_POLL", "2")))
FULL_EVERY = max(5.0, float(os.environ.get("NEXUS_NATIVE_API_FULL_EVERY", "30")))
BRAIN_TIMEOUT = max(1.0, float(os.environ.get("NEXUS_NATIVE_API_BRAIN_TIMEOUT", "8")))
CONTROL_TIMEOUT = max(5.0, float(os.environ.get("NEXUS_NATIVE_API_CONTROL_TIMEOUT", "15")))
TASK_LIMIT = int(os.environ.get("NEXUS_NATIVE_API_TASK_LIMIT", "40"))
EVENT_LIMIT = int(os.environ.get("NEXUS_NATIVE_API_EVENT_LIMIT", "40"))
APPROVAL_VISIBLE_STATES = ("ACTIVE", "VERIFYING", "APPROVAL_REQUIRED")
CACHE = {"snapshot": None, "ts": 0.0}
LEAD_CACHE = {"mtime": None, "data": None}
LOCK = threading.Lock()

# ---------------------------------------------------------------- util

def run(cmd, timeout=5):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except Exception as e:
        return 127, "", f"{type(e).__name__}: {e}"

def source_record(name, status, checked_at, max_age_ms, provenance, error=None, cached=False):
    return {"name": name, "status": status, "checked_at": int(checked_at * 1000),
            "max_age_ms": int(max_age_ms), "provenance": provenance,
            "error": error or None, "cached": bool(cached)}

def carry_source(previous, key, error, max_age_ms, provenance):
    prev = ((previous or {}).get("sources") or {}).get(key) or {}
    checked = prev.get("checked_at")
    return {"name": key, "status": "STALE" if checked else "ERROR",
            "checked_at": checked, "max_age_ms": int(max_age_ms),
            "provenance": provenance, "error": error or "source unavailable",
            "cached": bool(checked)}

def audit(action, state, detail="", task=None):
    try:
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "actor": ACTOR,
               "action": action, "state": state, "task": task, "detail": str(detail)[:1000]}
        with AUDIT_LOG.open("a") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    except Exception:
        pass

def audit_tail(limit=50):
    rows = []
    try:
        if AUDIT_LOG.exists():
            lines = AUDIT_LOG.read_text().splitlines()[-limit:]
            for line in lines:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        pass
    rows.reverse()
    return rows

# ------------------------------------------------------------- parsers

def parse_who(text):
    out = []
    pat = re.compile(r"^(\S+)\s+(ACTIVE|IDLE|STALE)\s+seen=\s*(\S+)\s+unread=(\d+)\s+work=(.*)$")
    for line in text.splitlines():
        m = pat.match(line.strip())
        if not m:
            continue
        work = m.group(5).strip()
        task = progress = None
        if work != "-" and ":" in work:
            task, pct = work.rsplit(":", 1)
            progress = pct if pct.endswith("%") else None
        out.append({"name": m.group(1), "state": m.group(2), "seen": m.group(3),
                    "unread": int(m.group(4)), "work": work, "task": task, "progress": progress})
    return out

def parse_history(text):
    out, cur = [], None
    pat = re.compile(r"^\[(\d+)\]\s+\[([^]]+)\]\s+([^\s]+)\s+([^→]+)→([^\s]+)(?:\s+task=([^:]+))?:\s+(.*)$")
    for line in text.splitlines():
        m = pat.match(line)
        if m:
            if cur:
                out.append(cur)
            cur = {"id": int(m.group(1)), "priority": m.group(2), "type": m.group(3),
                   "sender": m.group(4).strip(), "target": m.group(5).strip(),
                   "task": (m.group(6) or "").strip() or None, "message": m.group(7).strip(), "detail": ""}
        elif cur and line.startswith("  "):
            cur["detail"] += ("\n" if cur["detail"] else "") + line.strip()
    if cur:
        out.append(cur)
    return out

def parse_health(text):
    checks, summary = [], {"fails": None, "checks": None}
    for line in text.splitlines():
        if line.startswith(("PASS ", "FAIL ", "WARN ")):
            p = line.split(None, 2)
            checks.append({"state": p[0], "name": p[1], "detail": p[2] if len(p) > 2 else ""})
        if line.startswith("SUMMARY "):
            for k, v in re.findall(r"(fails|checks)=(\d+)", line):
                summary[k] = int(v)
    return {"checks": checks, "summary": summary}

def parse_dashboard(text):
    result = {"active": [], "ready": [], "blocked": []}
    sec = None
    for line in text.splitlines():
        if line == "=== ACTIVE TASK LEASES ===":
            sec = "active"; continue
        if line == "=== READY WORK PACKAGES ===":
            sec = "ready"; continue
        if line.startswith("=== "):
            sec = None; continue
        if sec == "active":
            m = re.match(r"P(\d+)\s+(\S+)\s+owner=(\S+)\s+progress=(\S+)\s+branch=(\S+)\s+until=(\S+)", line)
            if m:
                result["active"].append({"priority": int(m.group(1)), "task": m.group(2),
                                         "owner": m.group(3), "progress": m.group(4),
                                         "branch": m.group(5), "until": m.group(6)})
        elif sec == "ready":
            m = re.match(r"P(\d+)\s+(\S+)\s+\[([^]]+)\]\s+~([^:]+)\s+::\s+(.*)", line)
            if m:
                result["ready"].append({"priority": int(m.group(1)), "task": m.group(2),
                                        "kind": m.group(3), "eta": m.group(4).strip(),
                                        "title": m.group(5).strip()})
        if line.startswith("P") and "[BLOCKED" in line:
            m = re.match(r"P(\d+)\s+(\S+)\s+\[([^]]+)\]\s+(\S+)\s+(.*)", line)
            if m:
                result["blocked"].append({"priority": int(m.group(1)), "task": m.group(2),
                                          "status": m.group(3), "lane": m.group(4),
                                          "title": m.group(5).split(" :: ")[0].strip()})
    return result

def system_metrics():
    try:
        parts = Path("/proc/loadavg").read_text().split()
        load1, load5, load15 = [float(x) for x in parts[:3]]
    except Exception:
        load1 = load5 = load15 = None
    mem_total = mem_avail = None
    try:
        vals = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":", 1)
            vals[k] = int(v.strip().split()[0])
        mem_total, mem_avail = vals.get("MemTotal"), vals.get("MemAvailable")
    except Exception:
        pass
    psi = None
    try:
        m = re.search(r"avg10=([0-9.]+)", Path("/proc/pressure/cpu").read_text().splitlines()[0])
        psi = float(m.group(1)) if m else None
    except Exception:
        pass
    cores = os.cpu_count() or 1
    return {"load1": load1, "load5": load5, "load15": load15, "cores": cores,
            "load_per_cpu": round(load1 / cores, 3) if load1 is not None else None,
            "cpu_psi_avg10": psi, "mem_total_kb": mem_total, "mem_available_kb": mem_avail,
            "mem_used_pct": round((1 - (mem_avail / mem_total)) * 100, 1) if mem_total and mem_avail else None}

def runtime_operations():
    def active(pattern):
        rc, out, _ = run(["pgrep", "-f", pattern], 1)
        return rc == 0 and bool(out.strip())
    return {"preflight_active": active("logres-merge-preflight run"),
            "verify_active": active("logres-verify-farm")}

def supervisor_summary():
    try:
        if not SUPERVISOR_STATE.exists():
            return None
        data = json.loads(SUPERVISOR_STATE.read_text())
        runs = data.get("last_runs") or {}
        out = {"baton": data.get("baton_heartbeat"), "last_runs": {}}
        for name, r in runs.items():
            out["last_runs"][name] = {"running": r.get("running"), "rc": r.get("rc"),
                                      "error": r.get("error"), "finished_at": r.get("finished_at"),
                                      "duration_seconds": r.get("duration_seconds")}
        return out
    except Exception:
        return None

# ------------------------------------------------------ lead snapshot

def load_lead_snapshot():
    """Read the authoritative Lead snapshot (read-only). Returns (data, error)."""
    try:
        if not LEAD_SNAPSHOT.exists():
            return None, "LEAD_SNAPSHOT.json not found"
        mtime = LEAD_SNAPSHOT.stat().st_mtime
        if LEAD_CACHE["data"] is not None and LEAD_CACHE["mtime"] == mtime:
            return LEAD_CACHE["data"], None
        data = json.loads(LEAD_SNAPSHOT.read_text())
        LEAD_CACHE.update(mtime=mtime, data=data)
        return data, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"

TERMINAL = {"DONE", "SUPERSEDED", "RESOLVED", "CANCELLED"}

def task_progress(lead, task_id, workers):
    """Best authoritative progress for a task: latest lease RENEW, else worker work string."""
    best = None
    for lease in lead.get("lease_history") or []:
        if lease.get("task_id") == task_id and lease.get("action") in ("RENEW", "CLAIM", "START"):
            p = lease.get("progress")
            if isinstance(p, (int, float)):
                if best is None or lease.get("ts_epoch", 0) >= best[0]:
                    best = (lease.get("ts_epoch", 0), p)
    if best is not None:
        return best[1]
    for w in workers:
        if w.get("task") == task_id and w.get("progress"):
            try:
                return int(str(w["progress"]).rstrip("%"))
            except ValueError:
                return None
    return None

def task_started_epoch(lead, task_id):
    start = None
    for lease in lead.get("lease_history") or []:
        if lease.get("task_id") == task_id:
            ts = lease.get("ts_epoch")
            if ts and (start is None or ts < start):
                start = ts
    return start

def derive_task_state(task, pending_approval_task_ids, verify_active, verify_shas):
    status = (task.get("status") or "").upper()
    if task.get("id") in pending_approval_task_ids:
        return "APPROVAL_REQUIRED"
    if status.startswith("BLOCKED"):
        return "BLOCKED"
    if status == "FAILED":
        return "FAILED"
    if status in TERMINAL:
        return "DONE" if status in ("DONE", "RESOLVED") else status
    if status == "ACTIVE":
        branch = task.get("branch") or ""
        if verify_active and any(branch and branch in (s or "") for s in verify_shas):
            return "VERIFYING"
        return "AUTONOMOUS"
    if status == "READY":
        return "READY"
    return "UNKNOWN"

def plain_summary(task, state, deps):
    title = (task.get("title") or "").strip()
    tid = task.get("id") or "task"
    what = title if title else f"tracked work item {tid}"
    if state == "AUTONOMOUS":
        return f"An AI worker is building this autonomously: {what}."
    if state == "VERIFYING":
        return f"Finished work is under independent verification: {what}."
    if state == "APPROVAL_REQUIRED":
        return f"Waiting for your approval before it can proceed: {what}."
    if state == "BLOCKED":
        dep_names = ", ".join(deps[:3]) if deps else "an upstream prerequisite"
        return f"Blocked — waiting on {dep_names}: {what}."
    if state == "READY":
        return f"Queued and ready for an autonomous worker to claim: {what}."
    if state == "DONE":
        return f"Completed: {what}."
    if state == "FAILED":
        return f"Failed and needs recovery attention: {what}."
    if state == "SUPERSEDED":
        return f"Replaced by a newer candidate: {what}."
    return f"Status is being reconciled: {what}."

def build_task_view(lead, workers, pending_approval_task_ids, verify_active):
    verify_shas = [v.get("sha") for v in lead.get("verification") or []]
    verify_shas += [v.get("ref") for v in lead.get("verification") or []]
    tasks = lead.get("tasks") or []
    deps_by_task = {}
    for d in lead.get("task_dependencies") or []:
        deps_by_task.setdefault(d.get("task_id"), []).append(d.get("depends_on"))
    now = time.time()
    keep, recent_done = [], []
    for t in tasks:
        status = (t.get("status") or "").upper()
        updated = t.get("updated_at") or ""
        view = dict(t)
        view["state"] = derive_task_state(t, pending_approval_task_ids, verify_active, verify_shas)
        deps = [x for x in deps_by_task.get(t.get("id"), []) if x]
        view["depends_on"] = deps
        view["progress"] = task_progress(lead, t.get("id"), workers)
        started = task_started_epoch(lead, t.get("id"))
        if status == "ACTIVE" and started:
            view["elapsed_ms"] = max(0, int((now - started) * 1000))
            view["started_at"] = int(started * 1000)
        else:
            view["elapsed_ms"] = None
            view["started_at"] = None
        view["summary"] = plain_summary(t, view["state"], deps)
        view["updated_at"] = updated
        if status in TERMINAL or status == "SUPERSEDED":
            recent_done.append(view)
        else:
            keep.append(view)
    state_rank = {"APPROVAL_REQUIRED": 0, "FAILED": 1, "BLOCKED": 2, "VERIFYING": 3,
                  "AUTONOMOUS": 4, "READY": 5, "UNKNOWN": 6}
    keep.sort(key=lambda t: (state_rank.get(t["state"], 9), t.get("priority", 9), t.get("id") or ""))
    recent_done.sort(key=lambda t: t.get("updated_at") or "", reverse=True)
    out = {"open": keep[:TASK_LIMIT], "recent_done": recent_done[:10]}
    counts = {}
    for t in tasks:
        s = (t.get("status") or "UNKNOWN").upper()
        counts[s] = counts.get(s, 0) + 1
    out["status_counts"] = counts
    return out

def active_leases(lead):
    now = time.time()
    latest = {}
    for lease in lead.get("lease_history") or []:
        tid = lease.get("task_id")
        ts = lease.get("ts_epoch") or 0
        if tid and (tid not in latest or ts >= latest[tid].get("ts_epoch", 0)):
            latest[tid] = lease
    rows = []
    for tid, lease in latest.items():
        until = lease.get("lease_until_epoch")
        if until and until > now:
            rows.append({"task_id": tid, "owner": lease.get("chat_id"),
                         "branch": lease.get("branch"), "progress": lease.get("progress"),
                         "lease_until_epoch": until,
                         "lease_remaining_ms": int((until - now) * 1000)})
    rows.sort(key=lambda r: r.get("lease_until_epoch") or 0)
    return rows

def build_graph(lead, workers, tasks_view, approvals_pending, operations):
    """Architecture/dependency/worker graph derived only from authoritative data."""
    nodes, edges = [], []
    nodes.append({"id": "brain", "type": "authority", "label": "Brain / Lead",
                  "state": "AUTONOMOUS", "lane": "authority"})
    nodes.append({"id": "owner", "type": "owner", "label": "Owner (you)",
                  "state": "IDLE", "lane": "authority"})
    edges.append({"from": "owner", "to": "brain", "kind": "governs"})
    seen_workers = set()
    stale_count = 0
    for w in workers:
        wid = w.get("name") or "worker"
        if wid in seen_workers:
            continue
        if w.get("state") == "STALE":
            stale_count += 1
            continue
        if len(seen_workers) >= 14:
            stale_count += 1
            continue
        seen_workers.add(wid)
        state = {"ACTIVE": "AUTONOMOUS", "IDLE": "IDLE"}.get(w.get("state"), "UNKNOWN")
        nodes.append({"id": f"worker:{wid}", "type": "worker", "label": wid,
                      "state": state, "lane": "workers",
                      "task": w.get("task"), "progress": w.get("progress")})
        edges.append({"from": "brain", "to": f"worker:{wid}", "kind": "leases"})
        if w.get("task"):
            nodes.append({"id": f"task:{w['task']}", "type": "task", "label": w["task"],
                          "state": "AUTONOMOUS", "lane": "tasks"})
            edges.append({"from": f"worker:{wid}", "to": f"task:{w['task']}", "kind": "works_on"})
    if stale_count:
        nodes.append({"id": "worker:_stale", "type": "worker", "label": f"{stale_count} inactive/stale workers",
                      "state": "BLOCKED", "lane": "workers"})
        edges.append({"from": "brain", "to": "worker:_stale", "kind": "leases"})
    for t in (tasks_view.get("open") or [])[:18]:
        tid = t.get("id")
        nid = f"task:{tid}"
        if not any(n["id"] == nid for n in nodes):
            nodes.append({"id": nid, "type": "task", "label": tid,
                          "state": t.get("state") or "UNKNOWN", "lane": "tasks"})
            edges.append({"from": "brain", "to": nid, "kind": "tracks"})
        for dep in (t.get("depends_on") or [])[:4]:
            did = f"task:{dep}"
            if not any(n["id"] == did for n in nodes):
                nodes.append({"id": did, "type": "task", "label": dep,
                              "state": "UNKNOWN", "lane": "tasks"})
            edges.append({"from": did, "to": nid, "kind": "blocks"})
    if operations.get("verify_active") or operations.get("preflight_active"):
        label = "Verify farm" if operations.get("verify_active") else "Merge preflight"
        nodes.append({"id": "verify", "type": "verify", "label": label,
                      "state": "VERIFYING", "lane": "verification"})
        edges.append({"from": "verify", "to": "brain", "kind": "attests"})
    for ap in approvals_pending[:6]:
        aid = f"approval:{ap['id']}"
        nodes.append({"id": aid, "type": "approval", "label": "Approval " + str(ap["id"]),
                      "state": "APPROVAL_REQUIRED", "lane": "approvals"})
        edges.append({"from": "brain", "to": aid, "kind": "awaits"})
        edges.append({"from": aid, "to": "owner", "kind": "decides"})
    lanes = [
        {"id": "authority", "title": "Authority", "nodes": [n["id"] for n in nodes if n["lane"] == "authority"]},
        {"id": "workers", "title": "AI Workers", "nodes": [n["id"] for n in nodes if n["lane"] == "workers"]},
        {"id": "tasks", "title": "Tasks", "nodes": [n["id"] for n in nodes if n["lane"] == "tasks"]},
        {"id": "verification", "title": "Verification", "nodes": [n["id"] for n in nodes if n["lane"] == "verification"]},
        {"id": "approvals", "title": "Approvals", "nodes": [n["id"] for n in nodes if n["lane"] == "approvals"]},
    ]
    return {"nodes": nodes, "edges": edges, "lanes": lanes}

def list_evidence(limit=30):
    rows = []
    for d in EVIDENCE_DIRS:
        try:
            if not d.exists():
                continue
            files = sorted(d.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
            for p in files[:limit]:
                if not p.is_file():
                    continue
                item = {"name": p.name, "dir": d.name, "size": p.stat().st_size,
                        "mtime": int(p.stat().st_mtime * 1000),
                        "kind": "certification" if p.suffix == ".json" else "report"}
                if p.suffix == ".json":
                    try:
                        doc = json.loads(p.read_text()[:200000])
                        for key in ("verdict", "status", "result", "conclusion"):
                            if isinstance(doc, dict) and doc.get(key):
                                item["verdict"] = str(doc[key])[:60]
                                break
                    except Exception:
                        pass
                rows.append(item)
        except Exception:
            continue
    rows.sort(key=lambda r: r["mtime"], reverse=True)
    return rows[:limit]

def verification_view(lead, limit=25):
    rows = []
    for v in (lead.get("verification") or [])[-limit:]:
        rows.append({"ref": v.get("ref"), "sha": v.get("sha"), "status": v.get("status"),
                     "mode": v.get("mode"), "duration_sec": v.get("duration_sec"),
                     "details": v.get("details"), "ran_at": v.get("ran_at")})
    rows.reverse()
    return rows

def maintenance_view():
    """External Maintenance status — only when an authoritative state file is configured."""
    if not MAINTENANCE_STATE:
        return {"available": False, "note": "No External Maintenance state source is configured on this backend."}
    p = Path(MAINTENANCE_STATE)
    try:
        if not p.exists():
            return {"available": False, "note": "Maintenance state source not found."}
        data = json.loads(p.read_text())
        return {"available": True, "state": data.get("state"), "note": data.get("note"),
                "updated_at": data.get("updated_at"), "source": str(p)}
    except Exception as e:
        return {"available": False, "note": f"Maintenance state unreadable: {type(e).__name__}"}

# ------------------------------------------------------------- snapshot

def snapshot(full=False, previous=None):
    now = time.time()
    with LOCK:
        if not full and CACHE["snapshot"] and now - CACHE["ts"] < 1:
            return CACHE["snapshot"]
    sources = {}
    prev = previous or {}
    # --- Brain presence (workers + events) ---
    rc, who, werr = run([str(BRAIN), "who"], BRAIN_TIMEOUT)
    if rc == 0:
        workers = parse_who(who)
        sources["brain_presence"] = source_record("brain_presence", "OK", now, 15000, "Brain: logres-brain who")
    else:
        workers = list(prev.get("workers") or [])
        sources["brain_presence"] = carry_source(prev, "brain_presence", werr, 15000, "Brain: logres-brain who")
    rc, hist, herr = run([str(BRAIN), "history", "--limit", str(EVENT_LIMIT)], BRAIN_TIMEOUT)
    if rc == 0:
        events = parse_history(hist)
        sources["brain_events"] = source_record("brain_events", "OK", now, 15000, "Brain: logres-brain history")
    else:
        events = list(prev.get("events") or [])
        sources["brain_events"] = carry_source(prev, "brain_events", herr, 15000, "Brain: logres-brain history")
    # --- Lead snapshot (tasks/deps/claims/recovery/verification/milestones) ---
    lead, lead_err = load_lead_snapshot()
    if lead is not None:
        sources["lead_snapshot"] = source_record("lead_snapshot", "OK", now, 30000,
                                                 "Lead: control/LEAD_SNAPSHOT.json")
    else:
        lead = {"tasks": [], "lease_history": [], "task_dependencies": [], "claims": [],
                "task_recovery": [], "verification": [], "milestones": [], "meta": {},
                "task_state_history": [], "regressions": [], "integration_queue": []}
        sources["lead_snapshot"] = carry_source(prev, "lead_snapshot", lead_err, 30000,
                                                "Lead: control/LEAD_SNAPSHOT.json")
    # --- git exact SHA ---
    gr, sha, ge = run(["git", "-C", str(REPO), "rev-parse", "feat/logres-reconstruction"], 5)
    orc, origin, oe = run(["git", "-C", str(REPO), "rev-parse", "origin/feat/logres-reconstruction"], 5)
    if gr == 0 and sha:
        integration = {"branch": "feat/logres-reconstruction", "sha": sha, "short": sha[:12],
                       "origin_sha": origin or None,
                       "in_sync": (sha == origin) if origin else None,
                       "candidate_sha": (lead.get("meta") or {}).get("integration_sha")}
        sources["git"] = source_record("git", "OK", now, 60000, "Git: canonical integration + origin")
    else:
        integration = dict(prev.get("integration") or {"branch": "feat/logres-reconstruction",
                                                       "sha": None, "short": None})
        integration["in_sync"] = None
        sources["git"] = carry_source(prev, "git", ge or oe, 60000, "Git: canonical integration + origin")
    # --- Brain health + dashboard (full refresh only) ---
    if full:
        hr, h, he = run([str(BRAIN), "health"], BRAIN_TIMEOUT)
        if hr == 0:
            health_data, health_error = parse_health(h), None
            sources["brain_health"] = source_record("brain_health", "OK", now, 60000, "Brain: logres-brain health")
        else:
            health_data = dict(prev.get("health") or {"checks": [], "summary": {"fails": None, "checks": None}})
            health_error = he or "Brain health unavailable"
            sources["brain_health"] = carry_source(prev, "brain_health", health_error, 60000, "Brain: logres-brain health")
        cr, dash, derr = run([str(CONTROL), "dashboard"], CONTROL_TIMEOUT)
        if cr == 0 and dash:
            dashboard = parse_dashboard(dash)
            sources["control_dashboard"] = source_record("control_dashboard", "OK", now, 60000,
                                                         "Control: logres-control dashboard")
        else:
            dashboard = dict(prev.get("dashboard") or {"active": [], "ready": [], "blocked": []})
            sources["control_dashboard"] = carry_source(prev, "control_dashboard", derr, 60000,
                                                        "Control: logres-control dashboard")
    else:
        health_data = dict(prev.get("health") or {"checks": [], "summary": {"fails": None, "checks": None}})
        health_error = prev.get("health_error", "initializing")
        dashboard = dict(prev.get("dashboard") or {"active": [], "ready": [], "blocked": []})
        for key in ("brain_health", "control_dashboard"):
            if (prev.get("sources") or {}).get(key):
                sources[key] = dict(prev["sources"][key])
    # --- approvals + derived views ---
    pending = approval_rows("PENDING")
    pending_task_ids = {a.get("task_id") for a in pending if a.get("task_id")}
    operations = runtime_operations()
    tasks_view = build_task_view(lead, workers, pending_task_ids,
                                 operations.get("verify_active") or operations.get("preflight_active"))
    leases = active_leases(lead)
    graph = build_graph(lead, workers, tasks_view, pending, operations)
    evidence = {"verification": verification_view(lead), "artifacts": list_evidence(20)}
    maintenance = maintenance_view()
    claims = [{"task_id": c.get("task_id"), "owner": c.get("owner"),
               "path_prefix": c.get("path_prefix"), "created_at": c.get("created_at")}
              for c in (lead.get("claims") or [])[-20:]]
    recovery = [{"task_id": r.get("task_id"), "branch": r.get("branch"),
                 "status": r.get("status"), "created_at": r.get("created_at"),
                 "manifest_path": r.get("manifest_path")}
                for r in (lead.get("task_recovery") or [])[-10:]]
    milestones = [{"id": m.get("id"), "title": m.get("title"), "status": m.get("status"),
                   "definition_of_done": m.get("definition_of_done")}
                  for m in (lead.get("milestones") or [])]
    regressions = [{"id": r.get("id"), "kind": r.get("kind"), "ref": r.get("ref"),
                    "sha": r.get("sha"), "created_at": r.get("created_at"),
                    "fingerprint": (r.get("fingerprint") or "")[:16]}
                   for r in (lead.get("regressions") or [])[-10:]]
    workers_total = len(workers)
    if sources["brain_presence"]["status"] == "OK":
        counts = {"active_workers": sum(w["state"] == "ACTIVE" for w in workers),
                  "idle_workers": sum(w["state"] == "IDLE" for w in workers),
                  "stale_workers": sum(w["state"] == "STALE" for w in workers),
                  "working": sum(w["state"] == "ACTIVE" and bool(w.get("task")) for w in workers)}
    else:
        counts = dict(prev.get("counts") or {"active_workers": None, "idle_workers": None,
                                             "stale_workers": None, "working": None})
    counts["pending_approvals"] = len(pending)
    counts["blocked_tasks"] = sum(1 for t in tasks_view["open"] if t["state"] == "BLOCKED")
    counts["failed_tasks"] = sum(1 for t in tasks_view["open"] if t["state"] == "FAILED")
    counts["autonomous_tasks"] = sum(1 for t in tasks_view["open"] if t["state"] == "AUTONOMOUS")
    # --- overall system state (honest precedence) ---
    if sources["brain_presence"]["status"] != "OK" and sources["lead_snapshot"]["status"] != "OK":
        system_state = {"state": "OFFLINE", "reasons": ["Authoritative sources unreachable"]}
    elif pending:
        system_state = {"state": "APPROVAL_REQUIRED",
                        "reasons": [f"{len(pending)} approval(s) waiting for owner decision"]}
    elif any(t["state"] == "FAILED" for t in tasks_view["open"]):
        system_state = {"state": "FAILED", "reasons": ["Open tasks are in a failed state"]}
    elif operations.get("verify_active") or operations.get("preflight_active"):
        system_state = {"state": "VERIFYING", "reasons": ["Independent verification is running"]}
    elif counts.get("blocked_tasks"):
        system_state = {"state": "BLOCKED", "reasons": [f"{counts['blocked_tasks']} task(s) blocked"]}
    elif counts.get("autonomous_tasks"):
        system_state = {"state": "AUTONOMOUS", "reasons": [f"{counts['autonomous_tasks']} task(s) under autonomous work"]}
    else:
        system_state = {"state": "IDLE", "reasons": ["No active autonomous work"]}
    capabilities = {"approvals": True, "audit": True, "evidence": bool(evidence["artifacts"] or evidence["verification"]),
                    "graph": True, "tasks": lead is not None or sources["lead_snapshot"]["status"] == "OK",
                    "elapsed_timers": True, "google_signin": bool(GOOGLE_CLIENT_ID),
                    "google_client_id": GOOGLE_CLIENT_ID or None,
                    "emergency_stop": True, "external_maintenance": bool(maintenance.get("available")),
                    "deployed_sha": bool(integration.get("sha")), "worker_graph": True,
                    "control_requests": sorted(GOVERNED_ACTIONS)}
    workers_view = [w for w in workers if w.get("state") != "STALE"][:60]
    data = {"now": int(now * 1000), "system_state": system_state, "integration": integration,
            "workers": workers_view, "workers_total": workers_total,
            "leases": leases, "claims": claims, "events": events,
            "tasks": tasks_view, "dashboard": dashboard, "approvals": {"pending": pending},
            "graph": graph, "audit": audit_tail(40), "evidence": evidence,
            "maintenance": maintenance, "milestones": milestones, "recovery": recovery,
            "regressions": regressions, "health": health_data, "health_error": health_error,
            "system": system_metrics(), "counts": counts, "operations": operations,
            "supervisor": supervisor_summary(), "sources": sources, "capabilities": capabilities,
            "truth_contract": {"operational": "Brain", "code": "Git",
                               "missing_data_policy": "UNKNOWN_OR_STALE_NEVER_ZERO"}}
    with LOCK:
        CACHE.update(snapshot=data, ts=now)
    return data

# ------------------------------------------------------------- approvals

APPROVAL_COLUMNS = ("id", "sha", "reason", "evidence_summary", "status", "created_at",
                    "decided_at", "action", "scope", "risk", "evidence_json", "rollback",
                    "decision_note", "task_id")

def init_db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB) as c:
        c.execute("""create table if not exists approvals(
            id text primary key, sha text not null, reason text not null,
            evidence_summary text not null, status text not null,
            created_at real not null, decided_at real)""")
        cols = {r[1] for r in c.execute("pragma table_info(approvals)")}
        for col in ("action", "scope", "risk", "evidence_json", "rollback", "decision_note", "task_id"):
            if col not in cols:
                c.execute(f"alter table approvals add column {col} text")

def approval_rows(status=None):
    init_db()
    q = ("select " + ",".join(APPROVAL_COLUMNS) + " from approvals")
    args = []
    if status:
        q += " where status=?"
        args = [status]
    q += " order by created_at desc"
    with sqlite3.connect(DB) as c:
        rows = c.execute(q, args).fetchall()
    out = []
    for r in rows:
        row = dict(zip(APPROVAL_COLUMNS, r))
        try:
            row["evidence"] = json.loads(row.pop("evidence_json") or "null")
        except Exception:
            row["evidence"] = None
        row["elapsed_ms"] = int((time.time() - row["created_at"]) * 1000) if row["status"] == "PENDING" else None
        out.append(row)
    return out

def register_approval(p):
    for k in ("id", "sha", "reason"):
        if not p.get(k):
            return 400, {"ok": False, "error": "missing_" + k}
    if not re.fullmatch(r"[0-9a-fA-F]{40}", str(p["sha"])):
        return 400, {"ok": False, "error": "invalid_sha"}
    init_db()
    now = time.time()
    evidence = p.get("evidence")
    evidence_summary = p.get("evidence_summary") or (
        json.dumps(evidence)[:500] if evidence else "No evidence summary supplied")
    try:
        with sqlite3.connect(DB) as c:
            c.execute("""insert into approvals
                (id,sha,reason,evidence_summary,status,created_at,decided_at,
                 action,scope,risk,evidence_json,rollback,decision_note,task_id)
                values(?,?,?,?,?,?,NULL,?,?,?,?,?,NULL,?)""",
                (str(p["id"])[:128], str(p["sha"]), str(p["reason"])[:1000], str(evidence_summary)[:1000],
                 "PENDING", now, str(p.get("action") or "integrate-candidate")[:120],
                 str(p.get("scope") or "unspecified")[:300], str(p.get("risk") or "unspecified")[:500],
                 json.dumps(evidence)[:4000] if evidence else None,
                 str(p.get("rollback") or "")[:1000], str(p.get("task_id") or "")[:128]))
    except sqlite3.IntegrityError:
        return 409, {"ok": False, "error": "approval_exists"}
    audit("approval-register", "RECORDED", f"approval={p['id']} sha={p['sha'][:12]}", p.get("task_id"))
    return 201, [x for x in approval_rows() if x["id"] == p["id"]][0]

def decide_approval(p):
    if p.get("action") not in ("approve-gate", "reject-gate"):
        return None
    init_db()
    aid = p.get("approval_id")
    with sqlite3.connect(DB) as c:
        row = c.execute("select sha,status from approvals where id=?", (aid,)).fetchone()
        if not row:
            return 404, {"ok": False, "error": "approval_not_found"}
        if row[1] != "PENDING":
            return 409, {"ok": False, "error": "approval_already_decided"}
        if p.get("sha") != row[0]:
            return 409, {"ok": False, "error": "sha_mismatch"}
        st = "APPROVED" if p["action"] == "approve-gate" else "DECLINED"
        note = str(p.get("note") or "")[:500]
        c.execute("update approvals set status=?,decided_at=?,decision_note=? where id=?",
                  (st, time.time(), note, aid))
    audit("approval-decision", st, f"approval={aid} sha={row[0][:12]} note={note}")
    run([str(BRAIN), "post", ACTOR, "lead", "APPROVAL_DECISION",
         f"{st} approval={aid} exact_sha={row[0]} note={note}"], 5)
    return 200, {"ok": True, "state": "DECIDED", "decision": st,
                 "approval": [x for x in approval_rows() if x["id"] == aid][0]}

# ------------------------------------------------------------- control

GOVERNED_ACTIONS = {
    "wake-lead": "Wake Lead and reassess the current primary mission.",
    "retry-task": "Reassess and retry a task if governance permits.",
    "run-preflight": "Run guarded canonical preflight for eligible verified candidates.",
    "pause-autonomy": "Request a governed pause of autonomous dispatch after safe checkpoints.",
    "resume-autonomy": "Request governed autonomous dispatch to resume.",
    "release-stale-lease": "Inspect and release a confirmed stale lease if safe.",
    "supervisor-tick": "Request one supervisor pass over live state.",
    "autonomy-cycle": "Request one governed autonomy evaluation cycle.",
    "verify-ref": "Request independent verification of a specific ref.",
}
EMERGENCY_ACTIONS = {
    "emergency-stop": "EMERGENCY: request governed stop of autonomous construction after the current safe checkpoint.",
    "revoke-lease": "EMERGENCY: request governed revocation of a specific task lease.",
}

def control_request(action, task=None, note="", confirm="", ref=None):
    audit("control-request", "SUBMITTED", f"action={action} task={task} note={note[:200]}", task)
    if action in EMERGENCY_ACTIONS:
        expected = "REVOKE" if action == "revoke-lease" else "EMERGENCY STOP"
        if confirm != expected:
            return False, f'Type {expected} to authorize this governed emergency request.'
        if action == "revoke-lease" and not task:
            return False, "revoke-lease requires a task id."
        msg = EMERGENCY_ACTIONS[action] + (f" Target task: {task}." if task else "") + \
              (f" Operator note: {note[:300]}" if note else "")
        cmd = [str(BRAIN), "post", ACTOR, "lead", "CONTROL_REQUEST", msg] + (["--task", task] if task else [])
        rc, out, err = run(cmd, 6)
        audit("control-request", "REQUESTED" if rc == 0 else "FAILED", f"action={action}", task)
        return rc == 0, out or err or "Emergency request delivered to Lead governance"
    if action not in GOVERNED_ACTIONS:
        return False, "unsupported action"
    if action == "run-preflight" and confirm != "RUN PREFLIGHT":
        return False, "Type RUN PREFLIGHT to authorize."
    if action == "retry-task" and not task:
        return False, "retry-task requires a task id."
    if action == "release-stale-lease" and not task:
        return False, "release-stale-lease requires a task id."
    if action == "verify-ref":
        if not ref or not re.fullmatch(r"[A-Za-z0-9._/@+-]{3,256}", str(ref)):
            return False, "verify-ref requires a valid git ref."
    msg = GOVERNED_ACTIONS[action] + (f" Target: {task or ref}." if (task or ref) else "") + \
          (f" Operator note: {note[:300]}" if note else "")
    cmd = [str(BRAIN), "post", ACTOR, "lead", "CONTROL_REQUEST", msg]
    if task:
        cmd += ["--task", task]
    rc, out, err = run(cmd, 6)
    audit("control-request", "REQUESTED" if rc == 0 else "FAILED", f"action={action}", task)
    return rc == 0, out or err or "Request delivered to Lead governance"

# ------------------------------------------------- google session auth

def google_session_exchange(id_token):
    """Verify a Google ID token against Google's tokeninfo and issue a session.
    Real verification only — no local fake identity."""
    if not GOOGLE_CLIENT_ID:
        return 503, {"ok": False, "error": "google_signin_not_configured"}
    if not id_token or len(id_token) > 8192 or not re.fullmatch(r"[A-Za-z0-9_\-.=]+", id_token):
        return 400, {"ok": False, "error": "invalid_id_token"}
    try:
        with urlopen("https://oauth2.googleapis.com/tokeninfo?id_token=" + id_token, timeout=6) as r:
            info = json.loads(r.read().decode())
    except Exception as e:
        return 401, {"ok": False, "error": f"google_verify_failed: {type(e).__name__}"}
    if info.get("aud") != GOOGLE_CLIENT_ID:
        return 401, {"ok": False, "error": "audience_mismatch"}
    try:
        if int(info.get("exp", "0")) <= int(time.time()):
            return 401, {"ok": False, "error": "token_expired"}
    except ValueError:
        return 401, {"ok": False, "error": "token_expired"}
    sid = secrets.token_urlsafe(32)
    GOOGLE_SESSIONS[sid] = {"email": info.get("email", ""), "name": info.get("name", ""),
                            "exp": time.time() + GOOGLE_SESSION_TTL}
    audit("google-signin", "VERIFIED", f"email={info.get('email','')}")
    return 200, {"ok": True, "session": sid, "email": info.get("email", ""),
                 "name": info.get("name", ""), "post_allowed": GOOGLE_AUTH_ALLOWED}

def valid_google_session(sid):
    sess = GOOGLE_SESSIONS.get(sid)
    if not sess:
        return False
    if sess["exp"] <= time.time():
        GOOGLE_SESSIONS.pop(sid, None)
        return False
    return True

# ------------------------------------------------------------- http

class Handler(BaseHTTPRequestHandler):
    server_version = "NexusNativeCommandAPI/0.2"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def authorized(self, write=False):
        if not TOKEN:
            return self.client_address[0] in ("127.0.0.1", "::1")
        supplied = self.headers.get("Authorization", "")
        supplied = supplied[7:] if supplied.startswith("Bearer ") else self.headers.get("X-Nexus-Token", "")
        if supplied and hmac.compare_digest(supplied, TOKEN):
            return True
        # Google sessions read telemetry; writes additionally require operator opt-in.
        if supplied and valid_google_session(supplied):
            return GOOGLE_AUTH_ALLOWED or not write
        return False

    def send_json(self, payload, status=200):
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _deny(self):
        return self.send_json({"error": "unauthorized"}, 401)

    def do_GET(self):
        p = urlparse(self.path)
        path = p.path
        qs = parse_qs(p.query)
        if not self.authorized():
            return self._deny()
        if path == "/api/health":
            return self.send_json({"ok": True, "now": int(time.time() * 1000),
                                   "google_signin": bool(GOOGLE_CLIENT_ID)})
        if path == "/api/snapshot":
            return self.send_json(snapshot(full=qs.get("full", ["0"])[0] in ("1", "true")))
        if path == "/api/approvals":
            status = qs.get("status", [None])[0]
            return self.send_json({"approvals": approval_rows(status if status != "ALL" else None)})
        if path == "/api/audit":
            try:
                limit = min(int(qs.get("limit", ["50"])[0]), 200)
            except ValueError:
                limit = 50
            return self.send_json({"audit": audit_tail(limit)})
        if path == "/api/evidence":
            lead, _ = load_lead_snapshot()
            return self.send_json({"verification": verification_view(lead or {}, 50),
                                   "artifacts": list_evidence(50)})
        if path == "/api/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            last = None
            # First push is the fast path so the client renders quickly; the
            # heavier sources (health/dashboard) join on the next cycle.
            full_at = time.time() + min(4.0, FULL_EVERY)
            previous = None
            try:
                while True:
                    now = time.time()
                    full = now >= full_at
                    if full:
                        full_at = now + FULL_EVERY
                    data = snapshot(full=full, previous=previous)
                    previous = data
                    digest = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
                    if digest != last:
                        self.wfile.write(b"event: snapshot\n")
                        self.wfile.write(b"data: " + json.dumps(data, separators=(",", ":"), default=str).encode() + b"\n\n")
                        self.wfile.flush()
                        last = digest
                    else:
                        self.wfile.write(b": heartbeat\n\n")
                        self.wfile.flush()
                    time.sleep(POLL)
            except (BrokenPipeError, ConnectionResetError):
                return
            except Exception:
                return
        return self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        p = urlparse(self.path).path
        try:
            n = min(int(self.headers.get("Content-Length", "0")), 65536)
            payload = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self.send_json({"error": "invalid json"}, 400)
        if p == "/api/session/google":
            code, obj = google_session_exchange(str(payload.get("id_token") or ""))
            return self.send_json(obj, code)
        if not self.authorized(write=True):
            return self._deny()
        if p == "/api/approvals/register":
            code, obj = register_approval(payload)
            return self.send_json(obj, code)
        if p != "/api/control":
            return self.send_json({"error": "not found"}, 404)
        decision = decide_approval(payload)
        if decision:
            code, obj = decision
            return self.send_json(obj, code)
        ok, msg = control_request(str(payload.get("action", "")), payload.get("task"),
                                  str(payload.get("note", "")), str(payload.get("confirm", "")),
                                  payload.get("ref"))
        return self.send_json({"ok": ok, "state": "REQUESTED" if ok else "REJECTED", "message": msg},
                              202 if ok else 400)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=os.environ.get("NEXUS_NATIVE_API_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("NEXUS_NATIVE_API_PORT", "8787")))
    args = ap.parse_args()
    if args.host not in ("127.0.0.1", "::1", "localhost") and not TOKEN:
        raise SystemExit("Refusing non-loopback bind without NEXUS_NATIVE_API_TOKEN")
    init_db()
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()

if __name__ == "__main__":
    main()
