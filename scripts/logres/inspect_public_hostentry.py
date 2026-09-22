#!/usr/bin/env python3
"""Probe the public Logres host-entry bootstrap endpoint with bounded platform guesses."""
from __future__ import annotations
import argparse, hashlib, json, re, sys, urllib.error, urllib.request
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

DEFAULT_BASE="https://capi-sp.mmo-logres.com:8443/cusapi/hostentry"
PLATFORMS=("and","android","release-and","gp","googleplay")
SECRET_KEY=re.compile(r"(token|secret|password|passwd|auth|credential|session|cookie)",re.I)
HOST_RE=re.compile(r"^(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?::\d+)?$")
URL_RE=re.compile(r"^https?://",re.I)
INTERESTING=re.compile(r"(host|url|patch|asset|resource|download|filelist|api|web|socket|server|version|platform|name)",re.I)

def safe_url(v):
    try:p=urlsplit(v)
    except ValueError:return "<invalid-url>"
    if p.scheme.lower() not in {"http","https"} or not p.hostname:return "<invalid-url>"
    host=p.hostname.lower()
    try:port=p.port
    except ValueError:port=None
    netloc=host if port is None else f"{host}:{port}"
    return urlunsplit((p.scheme.lower(),netloc,p.path or "/","",""))

def safe_scalar(key,v):
    if SECRET_KEY.search(str(key)):return "<redacted>"
    if isinstance(v,bool) or v is None:return v
    if isinstance(v,(int,float)):return v
    if not isinstance(v,str):return f"<{type(v).__name__}>"
    s=v.strip()
    if URL_RE.match(s):return safe_url(s)
    if HOST_RE.fullmatch(s):return s.lower()
    if len(s)<=300 and (INTERESTING.search(str(key)) or "/" in s or "." in s):return s
    return "<text>"

def sanitize_json(value,key="",depth=0):
    if depth>10:return "<depth-limit>"
    if isinstance(value,dict):
        out={}
        for k,v in list(value.items())[:200]:
            if SECRET_KEY.search(str(k)):
                out[str(k)]="<redacted>"
            elif isinstance(v,(dict,list)):
                out[str(k)]=sanitize_json(v,str(k),depth+1)
            else:
                out[str(k)]=safe_scalar(str(k),v)
        return out
    if isinstance(value,list):
        return [sanitize_json(v,key,depth+1) if isinstance(v,(dict,list)) else safe_scalar(key,v) for v in value[:200]]
    return safe_scalar(key,value)

def probe(base,platform,version):
    url=f"{base.rstrip('/')}/{platform}/{version}"
    req=urllib.request.Request(url,headers={"User-Agent":"Logres-Reconstruction-Evidence/1.0","Accept":"application/json,*/*"})
    result={"platform":platform,"request_url":safe_url(url)}
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            body=r.read(2*1024*1024+1)
            if len(body)>2*1024*1024:raise ValueError("response too large")
            result.update({"status":r.status,"final_url":safe_url(r.geturl()),"content_type":r.headers.get("Content-Type"),
                           "size":len(body),"sha256":hashlib.sha256(body).hexdigest()})
    except urllib.error.HTTPError as e:
        body=e.read(256*1024)
        result.update({"status":e.code,"final_url":safe_url(e.geturl()),"content_type":e.headers.get("Content-Type"),
                       "size":len(body),"sha256":hashlib.sha256(body).hexdigest()})
    except Exception as e:
        result["error"]=f"{type(e).__name__}: {e}"
        return result
    try:
        result["json"]=sanitize_json(json.loads(body))
    except (json.JSONDecodeError,UnicodeDecodeError):
        text=body.decode("utf-8","ignore")
        hits=[]
        for line in text.splitlines():
            low=line.lower()
            if any(t in low for t in ("host","patch","asset","resource","download","filelist","mmo-logres","http")):
                clean=re.sub(r"https?://[^\s\"'<>]+",lambda m:safe_url(m.group(0)),line.strip(),flags=re.I)
                hits.append(clean[:500])
                if len(hits)>=80:break
        result["text_hits"]=hits
    return result

def self_test():
    sample={"name":"release-and","url":"https://example.invalid/a?token=SECRET","token":"SECRET","nested":{"host":"cdn.example.invalid","version":12101}}
    out=sanitize_json(sample); enc=json.dumps(out)
    assert "SECRET" not in enc
    assert out["url"]=="https://example.invalid/a"
    assert out["nested"]["host"]=="cdn.example.invalid"
    print("Logres public host-entry inspector self-test: PASS")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--version")
    ap.add_argument("--base",default=DEFAULT_BASE)
    ap.add_argument("--platform",action="append")
    ap.add_argument("--output",type=Path)
    ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test:
        self_test()
        return 0
    if not a.version:
        print("--version required unless --self-test is used",file=sys.stderr)
        return 2
    platforms=tuple(a.platform) if a.platform else PLATFORMS
    result={"provenance":"PUBLIC_LOGRES_HOSTENTRY_METADATA","base":safe_url(a.base),"version":a.version,
            "probes":[probe(a.base,p,a.version) for p in platforms]}
    encoded=json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n"
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(encoded,encoding="utf-8")
    else:
        sys.stdout.write(encoded)
    return 0
if __name__=="__main__":raise SystemExit(main())
