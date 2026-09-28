#!/usr/bin/env python3
import argparse, base64, hashlib, hmac, json, mimetypes, os, re, secrets, struct, subprocess, threading, time
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
ROOT = Path(os.environ.get("LOGRES_ROOT", "/home/ubuntu/logres"))
REPO = Path(os.environ.get("NEXUS_CONTROL_CENTER_REPO", ROOT / "src/awakened-realms"))
BRAIN = Path(os.environ.get("NEXUS_CONTROL_CENTER_BRAIN", ROOT / "bin/logres-brain"))
CONTROL = Path(os.environ.get("NEXUS_CONTROL_CENTER_CONTROL", ROOT / "bin/logres-control"))
TOKEN = os.environ.get("NEXUS_CONTROL_CENTER_TOKEN", "")
ACTOR = os.environ.get("NEXUS_CONTROL_CENTER_ACTOR", "nexus-control-center")
FAST_POLL = max(0.5, float(os.environ.get("NEXUS_CONTROL_CENTER_FAST_POLL", "1.0")))
FULL_POLL = max(10.0, float(os.environ.get("NEXUS_CONTROL_CENTER_FULL_POLL", "15")))
SESSION_TTL = int(os.environ.get("NEXUS_CONTROL_CENTER_SESSION_TTL", "28800"))
AUDIT_DIR = ROOT / "control/nexus-control-center"
AUDIT_LOG = AUDIT_DIR / "audit.jsonl"
SESSIONS = {}
SESSION_LOCK = threading.Lock()
STATE = {"snapshot": None, "revision": 0, "digest": None, "updated": 0.0}
STATE_CV = threading.Condition()
STOP = threading.Event()

def run(cmd, timeout=6):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except Exception as exc:
        return 127, "", f"{type(exc).__name__}: {exc}"

def spawn(cmd, env=None):
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        return True, f"started pid={p.pid}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"

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
        out.append({"name": m.group(1), "state": m.group(2), "seen": m.group(3), "unread": int(m.group(4)), "work": work, "task": task, "progress": progress})
    return out

def parse_history(text):
    out, cur = [], None
    pat = re.compile(r"^\[(\d+)\]\s+\[([^]]+)\]\s+([^\s]+)\s+([^→]+)→([^\s]+)(?:\s+task=([^:]+))?:\s+(.*)$")
    for line in text.splitlines():
        m = pat.match(line)
        if m:
            if cur:
                out.append(cur)
            cur = {"id": int(m.group(1)), "priority": m.group(2), "type": m.group(3), "sender": m.group(4).strip(), "target": m.group(5).strip(), "task": (m.group(6) or "").strip() or None, "message": m.group(7).strip(), "detail": ""}
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
                result["active"].append({"priority": int(m.group(1)), "task": m.group(2), "owner": m.group(3), "progress": m.group(4), "branch": m.group(5), "until": m.group(6)})
        elif sec == "ready":
            m = re.match(r"P(\d+)\s+(\S+)\s+\[([^]]+)\]\s+~([^:]+)\s+::\s+(.*)", line)
            if m:
                result["ready"].append({"priority": int(m.group(1)), "task": m.group(2), "kind": m.group(3), "eta": m.group(4).strip(), "title": m.group(5).strip()})
        if line.startswith("P") and "[BLOCKED" in line:
            m = re.match(r"P(\d+)\s+(\S+)\s+\[([^]]+)\]\s+(\S+)\s+(.*)", line)
            if m:
                result["blocked"].append({"priority": int(m.group(1)), "task": m.group(2), "status": m.group(3), "lane": m.group(4), "title": m.group(5).split(" :: ")[0].strip()})
    return result

def source_record(name,status,checked_at,max_age_ms,provenance,error=None,cached=False):
    return {"name":name,"status":status,"checked_at":int(checked_at*1000),"max_age_ms":int(max_age_ms),"provenance":provenance,"error":error or None,"cached":bool(cached)}

def previous_source(previous,key):
    return ((previous or {}).get("sources") or {}).get(key) or {}

def carry_source(previous,key,error,max_age_ms,provenance):
    prev=previous_source(previous,key)
    checked=prev.get("checked_at")
    return {"name":key,"status":"STALE" if checked else "ERROR","checked_at":checked,"max_age_ms":int(max_age_ms),"provenance":provenance,"error":error or "source unavailable","cached":bool(checked)}

def system_metrics():
    load1=load5=load15=None
    try:
        parts=Path("/proc/loadavg").read_text().split()
        load1,load5,load15=[float(x) for x in parts[:3]]
    except Exception:
        pass
    mem_total=mem_avail=None
    try:
        vals={}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k,v=line.split(":",1); vals[k]=int(v.strip().split()[0])
        mem_total,mem_avail=vals.get("MemTotal"),vals.get("MemAvailable")
    except Exception:
        pass
    psi=None
    try:
        m=re.search(r"avg10=([0-9.]+)",Path("/proc/pressure/cpu").read_text().splitlines()[0])
        psi=float(m.group(1)) if m else None
    except Exception:
        pass
    cores=os.cpu_count() or 1
    return {"load1":load1,"load5":load5,"load15":load15,"cores":cores,"load_per_cpu":round(load1/cores,3) if load1 is not None else None,"cpu_psi_avg10":psi,"mem_total_kb":mem_total,"mem_available_kb":mem_avail,"mem_used_pct":round((1-(mem_avail/mem_total))*100,1) if mem_total and mem_avail is not None else None}

def snapshot(full=False,previous=None):
    now=time.time(); sources={}
    who_rc,who,who_err=run([str(BRAIN),"who"],5)
    if who_rc==0:
        workers=parse_who(who)
        sources["brain_presence"]=source_record("brain_presence","OK",now,5000,"Brain: logres-brain who")
    else:
        workers=list((previous or {}).get("workers") or [])
        sources["brain_presence"]=carry_source(previous,"brain_presence",who_err,5000,"Brain: logres-brain who")

    hist_rc,hist,hist_err=run([str(BRAIN),"history","--limit","50"],5)
    if hist_rc==0:
        events=parse_history(hist)
        sources["brain_events"]=source_record("brain_events","OK",now,5000,"Brain: logres-brain history")
    else:
        events=list((previous or {}).get("events") or [])
        sources["brain_events"]=carry_source(previous,"brain_events",hist_err,5000,"Brain: logres-brain history")

    if full or not previous:
        git_rc,sha,git_err=run(["git","-C",str(REPO),"rev-parse","feat/logres-reconstruction"])
        origin_rc,origin_sha,origin_err=run(["git","-C",str(REPO),"rev-parse","origin/feat/logres-reconstruction"])
        if git_rc==0 and origin_rc==0 and sha and origin_sha:
            integration={"branch":"feat/logres-reconstruction","sha":sha,"short":sha[:12],"origin_sha":origin_sha,"in_sync":sha==origin_sha}
            sources["git"]=source_record("git","OK",now,60000,"Git: canonical integration + origin")
        else:
            integration=dict((previous or {}).get("integration") or {"branch":"feat/logres-reconstruction","sha":None,"short":None,"origin_sha":None,"in_sync":None})
            integration["in_sync"]=None
            sources["git"]=carry_source(previous,"git",git_err or origin_err,60000,"Git: canonical integration + origin")

        hrc,health,herr=run([str(BRAIN),"health"],5)
        if hrc==0:
            health_data=parse_health(health); health_error=None
            sources["brain_health"]=source_record("brain_health","OK",now,60000,"Brain: logres-brain health")
        else:
            health_data=dict((previous or {}).get("health") or {"checks":[],"summary":{"fails":None,"checks":None}})
            health_error=herr or "Brain health unavailable"
            sources["brain_health"]=carry_source(previous,"brain_health",health_error,60000,"Brain: logres-brain health")

        dash_rc,dash,dash_err=run([str(CONTROL),"dashboard"],30)
        if dash_rc==0:
            tasks=parse_dashboard(dash); dashboard_error=None
            sources["control_plane"]=source_record("control_plane","OK",now,60000,"Control plane: logres-control dashboard")
        else:
            tasks=dict((previous or {}).get("tasks") or {"active":[],"ready":[],"blocked":[]})
            dashboard_error=dash_err or "Control dashboard unavailable"
            sources["control_plane"]=carry_source(previous,"control_plane",dashboard_error,60000,"Control plane: logres-control dashboard")
    else:
        integration=dict(previous.get("integration") or {})
        health_data=dict(previous.get("health") or {})
        health_error=previous.get("health_error")
        tasks=dict(previous.get("tasks") or {"active":[],"ready":[],"blocked":[]})
        dashboard_error=previous.get("dashboard_error")
        for key in ("git","brain_health","control_plane"):
            if previous_source(previous,key): sources[key]=dict(previous_source(previous,key))

    metrics=system_metrics()
    system_ok=any(metrics.get(k) is not None for k in ("load_per_cpu","cpu_psi_avg10","mem_used_pct"))
    sources["system"]=source_record("system","OK" if system_ok else "ERROR",now,5000,"Linux kernel: /proc telemetry",None if system_ok else "kernel telemetry unavailable")

    if sources["brain_presence"]["status"]=="OK":
        counts={"active_workers":sum(w["state"]=="ACTIVE" for w in workers),"idle_workers":sum(w["state"]=="IDLE" for w in workers),"stale_workers":sum(w["state"]=="STALE" for w in workers),"working":sum(w["state"]=="ACTIVE" and bool(w.get("task")) for w in workers)}
    else:
        counts=dict((previous or {}).get("counts") or {"active_workers":None,"idle_workers":None,"stale_workers":None,"working":None})

    return {"now":int(now*1000),"integration":integration,"workers":workers,"events":events,"health":health_data,"health_error":health_error,"system":metrics,"counts":counts,"tasks":tasks,"dashboard_error":dashboard_error,"sources":sources,"truth_contract":{"operational":"Brain","code":"Git","missing_data_policy":"UNKNOWN_OR_STALE_NEVER_ZERO"}}

def commit_snapshot(data):
    stable=dict(data); stable.pop("now",None)
    digest=hashlib.sha256(json.dumps(stable,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    with STATE_CV:
        changed=digest!=STATE["digest"]
        STATE["snapshot"]=data
        STATE["updated"]=time.time()
        if changed:
            STATE["digest"]=digest
            STATE["revision"]+=1
            STATE_CV.notify_all()
    return changed

def initial_snapshot_seed():
    return {
        "integration":{"branch":"feat/logres-reconstruction","sha":None,"short":None,"origin_sha":None,"in_sync":None},
        "workers":[],"events":[],"health":{"checks":[],"summary":{"fails":None,"checks":None}},
        "health_error":"initializing","system":{},"counts":{"active_workers":None,"idle_workers":None,"stale_workers":None,"working":None},
        "tasks":{"active":[],"ready":[],"blocked":[]},"dashboard_error":"initializing",
        "sources":{
            "git":{"name":"git","status":"ERROR","checked_at":None,"max_age_ms":60000,"provenance":"Git: canonical integration + origin","error":"initializing","cached":False},
            "brain_health":{"name":"brain_health","status":"ERROR","checked_at":None,"max_age_ms":60000,"provenance":"Brain: logres-brain health","error":"initializing","cached":False},
            "control_plane":{"name":"control_plane","status":"ERROR","checked_at":None,"max_age_ms":60000,"provenance":"Control plane: logres-control dashboard","error":"initializing","cached":False},
        },
    }

def publisher():
    previous=initial_snapshot_seed()
    while not STOP.is_set():
        data=snapshot(full=False,previous=previous)
        commit_snapshot(data)
        previous=data
        STOP.wait(FAST_POLL)

def heavy_publisher():
    while not STOP.is_set():
        with STATE_CV:
            STATE_CV.wait_for(lambda: STATE["snapshot"] is not None,timeout=30)
            previous=STATE["snapshot"]
        if previous is not None:
            heavy=snapshot(full=True,previous=previous)
            with STATE_CV:
                latest=STATE["snapshot"] or previous
            for key in ("workers","events","counts","system","now"):
                if key in latest: heavy[key]=latest[key]
            heavy_sources=heavy.get("sources") or {}
            latest_sources=latest.get("sources") or {}
            for key in ("brain_presence","brain_events","system"):
                if key in latest_sources: heavy_sources[key]=latest_sources[key]
            heavy["sources"]=heavy_sources
            commit_snapshot(heavy)
        STOP.wait(FULL_POLL)

def cleanup_sessions():
    now = time.time()
    with SESSION_LOCK:
        for sid in [sid for sid, s in SESSIONS.items() if s["expires"] <= now]:
            SESSIONS.pop(sid, None)

def create_session(operator=False):
    cleanup_sessions()
    sid = secrets.token_urlsafe(32)
    with SESSION_LOCK:
        SESSIONS[sid] = {"expires": time.time() + SESSION_TTL, "operator": bool(operator)}
    return sid

def session_from_cookie(header):
    cleanup_sessions()
    jar = cookies.SimpleCookie()
    try:
        jar.load(header or "")
        sid = jar.get("nexus_session").value if jar.get("nexus_session") else None
    except Exception:
        sid = None
    if not sid:
        return None, None
    with SESSION_LOCK:
        sess = SESSIONS.get(sid)
        if sess:
            sess["expires"] = time.time() + SESSION_TTL
        return sid, dict(sess) if sess else None

def audit(action, state, detail="", task=None):
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "actor": ACTOR, "action": action, "state": state, "task": task, "detail": str(detail)[:1000]}
    with AUDIT_LOG.open("a") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")

def control_request(action, payload):
    task = (payload.get("task") or "").strip() or None
    confirm = str(payload.get("confirm") or "")
    if action == "wake-lead":
        msg = "Operator requested immediate Lead reassessment from Nexus Control Center."
        rc, out, err = run([str(BRAIN), "post", ACTOR, "lead", "INFO", "HIGH", "Control request: wake Lead", "--body", msg], 6)
        return rc == 0, "EXECUTED" if rc == 0 else "FAILED", out or err or "Lead notified"
    if action == "refresh":
        with STATE_CV:
            STATE["digest"] = None
        return True, "EXECUTED", "Live snapshot refresh forced"
    if action == "supervisor-tick":
        ok, msg = spawn([str(ROOT / "bin/logres-supervisor"), "tick"])
        return ok, "STARTED" if ok else "FAILED", msg
    if action == "autonomy-cycle":
        ok, msg = spawn([str(ROOT / "bin/logres-autonomy"), "cycle"])
        return ok, "STARTED" if ok else "FAILED", msg
    if action == "run-preflight":
        if confirm != "RUN PREFLIGHT":
            return False, "CONFIRM_REQUIRED", "Type RUN PREFLIGHT to authorize"
        p = subprocess.run(["pgrep", "-f", "logres-merge-preflight run"], capture_output=True, text=True)
        if p.returncode == 0 and p.stdout.strip():
            return False, "BUSY", "A merge preflight is already running"
        ok, msg = spawn([str(ROOT / "bin/logres-merge-preflight"), "run", "--max", "1", "--min-age", "0", "--min-count", "1"])
        return ok, "STARTED" if ok else "FAILED", msg
    if action == "verify-ref":
        ref = str(payload.get("ref") or "").strip()
        if not ref or not re.fullmatch(r"[A-Za-z0-9._/@+-]{3,256}", ref):
            return False, "REJECTED", "A valid Git ref is required"
        ok, msg = spawn([str(ROOT / "bin/logres-verify-ref"), ref])
        return ok, "STARTED" if ok else "FAILED", msg
    if action in ("pause-autonomy", "resume-autonomy", "retry-task", "release-stale-lease", "device-qa"):
        messages = {"pause-autonomy": "Request governed pause of autonomous dispatch after safe checkpoints.", "resume-autonomy": "Request governed autonomous dispatch resume.", "retry-task": f"Reassess and retry task {task or '(unspecified)'} if governance permits.", "release-stale-lease": f"Inspect and release confirmed stale lease for {task or '(unspecified)'} if safe.", "device-qa": "Request governed Samsung/device QA run after checking live device ownership."}
        cmd = [str(BRAIN), "post", ACTOR, "lead", "INFO", "HIGH", "Control request: " + action, "--body", messages[action]]
        if task:
            cmd = cmd[:-2] + ["--task", task] + cmd[-2:]
        rc, out, err = run(cmd, 6)
        return rc == 0, "REQUESTED" if rc == 0 else "FAILED", out or err or "Control request recorded"
    return False, "REJECTED", "Unsupported control action"

def ws_frame(payload):
    body = payload.encode("utf-8")
    head = bytearray([0x81]); n = len(body)
    if n < 126:
        head.append(n)
    elif n < 65536:
        head.append(126); head += struct.pack("!H", n)
    else:
        head.append(127); head += struct.pack("!Q", n)
    return bytes(head) + body

class Handler(BaseHTTPRequestHandler):
    server_version = "NexusControlCenter/1.0"
    protocol_version = "HTTP/1.1"
    def log_message(self, fmt, *args): pass
    def send_json(self, payload, status=200, headers=None):
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.send_header("X-Content-Type-Options", "nosniff"); self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (headers or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(body)
    def session(self): return session_from_cookie(self.headers.get("Cookie"))
    def require_session(self, operator=False):
        sid, sess = self.session()
        if not sess:
            self.send_json({"error": "unauthorized"}, 401); return None
        if operator and not sess.get("operator"):
            self.send_json({"error": "operator_locked"}, 403); return None
        return sid, sess
    def do_POST(self):
        path = urlparse(self.path).path
        try:
            n = min(int(self.headers.get("Content-Length", "0")), 16384); payload = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self.send_json({"error": "invalid_json"}, 400)
        if path == "/api/session":
            supplied = str(payload.get("token") or "")
            if not TOKEN or not supplied or not hmac.compare_digest(supplied, TOKEN):
                return self.send_json({"ok": False, "error": "invalid_credentials"}, 401)
            sid = create_session(operator=False)
            cookie = f"nexus_session={sid}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_TTL}"
            if self.headers.get("X-Forwarded-Proto") == "https": cookie += "; Secure"
            audit("login", "EXECUTED")
            return self.send_json({"ok": True, "operator": False}, headers={"Set-Cookie": cookie})
        if path == "/api/operator/unlock":
            auth = self.require_session()
            if not auth: return
            supplied = str(payload.get("token") or "")
            if not TOKEN or not hmac.compare_digest(supplied, TOKEN):
                audit("operator_unlock", "FAILED"); return self.send_json({"ok": False, "error": "invalid_credentials"}, 401)
            sid, _ = auth
            with SESSION_LOCK:
                if sid in SESSIONS: SESSIONS[sid]["operator"] = True
            audit("operator_unlock", "EXECUTED")
            return self.send_json({"ok": True, "operator": True})
        if path == "/api/control":
            auth = self.require_session(operator=True)
            if not auth: return
            action = str(payload.get("action") or "")
            ok, state, msg = control_request(action, payload); audit(action, state, msg, payload.get("task"))
            return self.send_json({"ok": ok, "state": state, "message": msg}, 202 if ok else 409)
        return self.send_json({"error": "not_found"}, 404)
    def do_DELETE(self):
        if urlparse(self.path).path != "/api/session": return self.send_json({"error": "not_found"}, 404)
        sid, _ = self.session()
        if sid:
            with SESSION_LOCK: SESSIONS.pop(sid, None)
        audit("logout", "EXECUTED")
        self.send_json({"ok": True}, headers={"Set-Cookie": "nexus_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"})
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/snapshot":
            if not self.require_session(): return
            with STATE_CV:
                STATE_CV.wait_for(lambda: STATE["snapshot"] is not None, timeout=3)
                data=STATE["snapshot"]
            if data is None:
                return self.send_json({"error":"initializing","message":"Live truth sources are still initializing."},503)
            return self.send_json(data)
        if path == "/api/session":
            auth = self.require_session()
            if not auth: return
            return self.send_json({"ok": True, "operator": bool(auth[1].get("operator"))})
        if path == "/api/ws" and self.headers.get("Upgrade", "").lower() == "websocket":
            if not self.require_session(): return
            return self.handle_ws()
        return self.serve_static(path)
    def handle_ws(self):
        key = self.headers.get("Sec-WebSocket-Key")
        if not key: return self.send_json({"error": "missing_ws_key"}, 400)
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        self.send_response(101, "Switching Protocols"); self.send_header("Upgrade", "websocket"); self.send_header("Connection", "Upgrade"); self.send_header("Sec-WebSocket-Accept", accept); self.end_headers()
        last_rev = -1
        try:
            while True:
                with STATE_CV:
                    STATE_CV.wait_for(lambda: STATE["revision"] != last_rev, timeout=15); rev = STATE["revision"]; data = STATE["snapshot"]
                if data is None: continue
                self.wfile.write(ws_frame(json.dumps({"type": "snapshot", "revision": rev, "data": data}, separators=(",", ":")))); self.wfile.flush(); last_rev = rev
        except (BrokenPipeError, ConnectionResetError, OSError):
            return
    def serve_static(self, path):
        rel = "index.html" if path in ("", "/") else path.lstrip("/"); target = (STATIC / rel).resolve()
        if not str(target).startswith(str(STATIC.resolve())) or not target.is_file(): target = STATIC / "index.html"
        body = target.read_bytes(); ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(200); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body))); self.send_header("X-Content-Type-Options", "nosniff"); self.send_header("Referrer-Policy", "no-referrer"); self.send_header("Cache-Control", "no-cache" if target.name in ("index.html", "sw.js", "app.js", "app.css") else "public,max-age=3600"); self.end_headers(); self.wfile.write(body)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--host", default=os.environ.get("NEXUS_CONTROL_CENTER_HOST", "127.0.0.1")); ap.add_argument("--port", type=int, default=int(os.environ.get("NEXUS_CONTROL_CENTER_PORT", "8787"))); args = ap.parse_args()
    if args.host not in ("127.0.0.1", "::1", "localhost") and not TOKEN: raise SystemExit("Refusing non-loopback bind without NEXUS_CONTROL_CENTER_TOKEN")
    threading.Thread(target=publisher, daemon=True, name="nexus-fast-publisher").start()
    threading.Thread(target=heavy_publisher, daemon=True, name="nexus-heavy-publisher").start()
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()

if __name__ == "__main__":
    main()
