#!/usr/bin/env python3
import argparse, hashlib, hmac, json, os, re, sqlite3, subprocess, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE=Path(__file__).resolve().parent
ROOT=Path(os.environ.get("LOGRES_ROOT","/home/ubuntu/logres"))
DB=Path(os.environ.get("NEXUS_NATIVE_API_DB",ROOT/"control/nexus-native-command-api.sqlite"))
REPO=Path(os.environ.get("NEXUS_NATIVE_API_REPO",ROOT/"src/awakened-realms"))
BRAIN=Path(os.environ.get("NEXUS_NATIVE_API_BRAIN",ROOT/"bin/logres-brain"))
CONTROL=Path(os.environ.get("NEXUS_NATIVE_API_CONTROL",ROOT/"bin/logres-control"))
TOKEN=os.environ.get("NEXUS_NATIVE_API_TOKEN","")
ACTOR=os.environ.get("NEXUS_NATIVE_API_ACTOR","nexus-native-command-api")
POLL=max(1.0,float(os.environ.get("NEXUS_NATIVE_API_POLL","2")))
CACHE={"snapshot":None,"ts":0.0}; LOCK=threading.Lock()

def run(cmd,timeout=5):
    try:
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout,check=False)
        return p.returncode,p.stdout.strip(),p.stderr.strip()
    except Exception as e:
        return 127,"",f"{type(e).__name__}: {e}"

def parse_who(text):
    out=[]; pat=re.compile(r"^(\S+)\s+(ACTIVE|IDLE|STALE)\s+seen=\s*(\S+)\s+unread=(\d+)\s+work=(.*)$")
    for line in text.splitlines():
        m=pat.match(line.strip())
        if not m: continue
        work=m.group(5).strip(); task=progress=None
        if work!="-" and ":" in work:
            task,pct=work.rsplit(":",1); progress=pct if pct.endswith("%") else None
        out.append({"name":m.group(1),"state":m.group(2),"seen":m.group(3),"unread":int(m.group(4)),"work":work,"task":task,"progress":progress})
    return out

def parse_history(text):
    out=[]; cur=None
    pat=re.compile(r"^\[(\d+)\]\s+\[([^]]+)\]\s+([^\s]+)\s+([^→]+)→([^\s]+)(?:\s+task=([^:]+))?:\s+(.*)$")
    for line in text.splitlines():
        m=pat.match(line)
        if m:
            if cur: out.append(cur)
            cur={"id":int(m.group(1)),"priority":m.group(2),"type":m.group(3),"sender":m.group(4).strip(),"target":m.group(5).strip(),"task":(m.group(6) or "").strip() or None,"message":m.group(7).strip(),"detail":""}
        elif cur and line.startswith("  "):
            cur["detail"]+=("\n" if cur["detail"] else "")+line.strip()
    if cur: out.append(cur)
    return out

def parse_health(text):
    checks=[]; summary={"fails":None,"checks":None}
    for line in text.splitlines():
        if line.startswith(("PASS ","FAIL ","WARN ")):
            p=line.split(None,2); checks.append({"state":p[0],"name":p[1],"detail":p[2] if len(p)>2 else ""})
        if line.startswith("SUMMARY "):
            for k,v in re.findall(r"(fails|checks)=(\d+)",line): summary[k]=int(v)
    return {"checks":checks,"summary":summary}

def parse_dashboard(text):
    result={"active":[],"ready":[],"blocked":[]}; sec=None
    for line in text.splitlines():
        if line=="=== ACTIVE TASK LEASES ===": sec="active"; continue
        if line=="=== READY WORK PACKAGES ===": sec="ready"; continue
        if line.startswith("=== "): sec=None; continue
        if sec=="active":
            m=re.match(r"P(\d+)\s+(\S+)\s+owner=(\S+)\s+progress=(\S+)\s+branch=(\S+)\s+until=(\S+)",line)
            if m: result["active"].append({"priority":int(m.group(1)),"task":m.group(2),"owner":m.group(3),"progress":m.group(4),"branch":m.group(5),"until":m.group(6)})
        elif sec=="ready":
            m=re.match(r"P(\d+)\s+(\S+)\s+\[([^]]+)\]\s+~([^:]+)\s+::\s+(.*)",line)
            if m: result["ready"].append({"priority":int(m.group(1)),"task":m.group(2),"kind":m.group(3),"eta":m.group(4).strip(),"title":m.group(5).strip()})
        if line.startswith("P") and "[BLOCKED" in line:
            m=re.match(r"P(\d+)\s+(\S+)\s+\[([^]]+)\]\s+(\S+)\s+(.*)",line)
            if m: result["blocked"].append({"priority":int(m.group(1)),"task":m.group(2),"status":m.group(3),"lane":m.group(4),"title":m.group(5).split(" :: ")[0].strip()})
    return result

def snapshot(full=False):
    now=time.time()
    with LOCK:
        if not full and CACHE["snapshot"] and now-CACHE["ts"]<1: return CACHE["snapshot"]
    _,sha,_=run(["git","-C",str(REPO),"rev-parse","HEAD"])
    _,branch,_=run(["git","-C",str(REPO),"rev-parse","--abbrev-ref","HEAD"])
    _,who,_=run([str(BRAIN),"who"],4)
    _,hist,_=run([str(BRAIN),"history","--limit","30"],4)
    hrc,health,herr=run([str(BRAIN),"health"],4)
    workers=parse_who(who)
    data={"now":int(now*1000),"integration":{"branch":branch or "feat/logres-reconstruction","sha":sha,"short":sha[:12] if sha else "unknown"},"workers":workers,"events":parse_history(hist),"health":parse_health(health),"health_error":herr if hrc else None,"counts":{"active_workers":sum(w["state"]=="ACTIVE" for w in workers),"stale_workers":sum(w["state"]=="STALE" for w in workers),"working":sum(bool(w.get("task")) for w in workers)},"approvals":approval_rows("PENDING")}
    if full:
        rc,dash,err=run([str(CONTROL),"dashboard"],15)
        if dash: data["tasks"]=parse_dashboard(dash)
        data["dashboard_error"]=err if rc else None
    elif CACHE["snapshot"] and CACHE["snapshot"].get("tasks"):
        data["tasks"]=CACHE["snapshot"]["tasks"]
    with LOCK: CACHE.update(snapshot=data,ts=now)
    return data

def init_db():
    DB.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(DB) as c: c.execute("create table if not exists approvals(id text primary key,sha text not null,reason text not null,evidence_summary text not null,status text not null,created_at real not null,decided_at real)")
def approval_rows(status=None):
    init_db(); q="select id,sha,reason,evidence_summary,status,created_at,decided_at from approvals"; a=[]
    if status: q+=" where status=?"; a=[status]
    q+=" order by created_at desc"
    with sqlite3.connect(DB) as c: rows=c.execute(q,a).fetchall()
    return [dict(zip(("id","sha","reason","evidence_summary","status","created_at","decided_at"),r)) for r in rows]
def register_approval(p):
    for k in ("id","sha","reason","evidence_summary"):
        if not p.get(k): return 400,{"ok":False,"error":"missing_"+k}
    if not re.fullmatch(r"[0-9a-fA-F]{40}",str(p["sha"])): return 400,{"ok":False,"error":"invalid_sha"}
    init_db(); now=time.time()
    try:
        with sqlite3.connect(DB) as c: c.execute("insert into approvals values(?,?,?,?,?,?,NULL)",(p["id"],p["sha"],p["reason"],p["evidence_summary"],"PENDING",now))
    except sqlite3.IntegrityError: return 409,{"ok":False,"error":"approval_exists"}
    return 201,[x for x in approval_rows() if x["id"]==p["id"]][0]
def decide_approval(p):
    if p.get("action") not in ("approve-gate","reject-gate"): return None
    init_db(); aid=p.get("approval_id")
    with sqlite3.connect(DB) as c:
        row=c.execute("select sha,status from approvals where id=?",(aid,)).fetchone()
        if not row:return 404,{"ok":False,"error":"approval_not_found"}
        if row[1]!="PENDING":return 409,{"ok":False,"error":"approval_already_decided"}
        if p.get("sha")!=row[0]:return 409,{"ok":False,"error":"sha_mismatch"}
        st="APPROVED" if p["action"]=="approve-gate" else "REJECTED"; c.execute("update approvals set status=?,decided_at=? where id=?",(st,time.time(),aid))
    run([str(BRAIN),"post",ACTOR,"lead","APPROVAL_DECISION",f"{st} approval={aid} exact_sha={row[0]}"],5)
    return 200,{"ok":True,"approval":[x for x in approval_rows() if x["id"]==aid][0]}

def control_request(action,task=None,note=""):
    allowed={"wake-lead":"Wake Lead and reassess the current primary mission.","retry-task":f"Reassess and retry task {task or '(unspecified)'} if governance permits.","run-preflight":"Run guarded canonical preflight for eligible verified candidates.","pause-autonomy":"Request a governed pause of autonomous dispatch after safe checkpoints.","resume-autonomy":"Request governed autonomous dispatch to resume."}
    if action not in allowed: return False,"unsupported action"
    msg=allowed[action]+(f" Operator note: {note[:300]}" if note else "")
    cmd=[str(BRAIN),"post",ACTOR,"lead","CONTROL_REQUEST",msg]+(["--task",task] if task else [])
    rc,out,err=run(cmd,5); return rc==0,out or err or "request recorded"

class Handler(BaseHTTPRequestHandler):
    server_version="NexusControlCenter/0.1"
    def log_message(self,fmt,*args): pass
    def authorized(self):
        if not TOKEN: return self.client_address[0] in ("127.0.0.1","::1")
        supplied=self.headers.get("Authorization","")
        supplied=supplied[7:] if supplied.startswith("Bearer ") else self.headers.get("X-Nexus-Token","")
        return bool(supplied) and hmac.compare_digest(supplied,TOKEN)
    def send_json(self,payload,status=200):
        body=json.dumps(payload,separators=(",",":")).encode(); self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Cache-Control","no-store"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        p=urlparse(self.path).path
        if p=="/api/snapshot":
            if not self.authorized(): return self.send_json({"error":"unauthorized"},401)
            return self.send_json(snapshot(full=True))
        if p=="/api/events":
            if not self.authorized(): return self.send_json({"error":"unauthorized"},401)
            self.send_response(200); self.send_header("Content-Type","text/event-stream"); self.send_header("Cache-Control","no-store"); self.send_header("Connection","keep-alive"); self.end_headers()
            last=None; full_at=0.0
            try:
                while True:
                    now=time.time(); full=now>=full_at; data=snapshot(full=full)
                    if full: full_at=now+30
                    digest=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
                    if digest!=last:
                        self.wfile.write(b"event: snapshot\n"); self.wfile.write(b"data: "+json.dumps(data,separators=(",",":")).encode()+b"\n\n"); self.wfile.flush(); last=digest
                    else: self.wfile.write(b": heartbeat\n\n"); self.wfile.flush()
                    time.sleep(POLL)
            except (BrokenPipeError,ConnectionResetError): return
        return self.send_json({"error":"not found"},404)
    def do_POST(self):
        p=urlparse(self.path).path
        if not self.authorized(): return self.send_json({"error":"unauthorized"},401)
        try:
            n=min(int(self.headers.get("Content-Length","0")),16384); payload=json.loads(self.rfile.read(n) or b"{}")
        except Exception: return self.send_json({"error":"invalid json"},400)
        if p=="/api/approvals/register":
            code,obj=register_approval(payload); return self.send_json(obj,code)
        if p!="/api/control": return self.send_json({"error":"not found"},404)
        decision=decide_approval(payload)
        if decision:
            code,obj=decision; return self.send_json(obj,code)
        ok,msg=control_request(str(payload.get("action","")),payload.get("task"),str(payload.get("note","")))
        return self.send_json({"ok":ok,"state":"REQUESTED" if ok else "REJECTED","message":msg},202 if ok else 400)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--host",default=os.environ.get("NEXUS_NATIVE_API_HOST","127.0.0.1")); ap.add_argument("--port",type=int,default=int(os.environ.get("NEXUS_NATIVE_API_PORT","8787"))); args=ap.parse_args()
    if args.host not in ("127.0.0.1","::1","localhost") and not TOKEN: raise SystemExit("Refusing non-loopback bind without NEXUS_NATIVE_API_TOKEN")
    ThreadingHTTPServer((args.host,args.port),Handler).serve_forever()
if __name__=="__main__": main()
