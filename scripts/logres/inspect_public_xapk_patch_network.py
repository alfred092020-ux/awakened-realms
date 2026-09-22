#!/usr/bin/env python3
"""Inspect a public Logres XAPK for patch/CDN network strings.

The package is downloaded to temporary storage only. Output is bounded metadata.
"""
from __future__ import annotations
import argparse, hashlib, json, re, sys, tempfile, urllib.request
from collections import Counter
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from zipfile import ZipFile, BadZipFile

MAX_DOWNLOAD=160*1024*1024
MAX_ENTRY=96*1024*1024
MAX_ITEMS=500
TERMS=("download_filelist","download_binfilelist","download_extra_filelist",
       "filelist.bin","binfilelist.bin","filelistbin.hash","cache/patch",
       ".mbn","patch","download","cdn","manifest","mmo-logres")
ASCII_RE=re.compile(rb"[ -~]{5,500}")
UTF16_RE=re.compile(rb"(?:[ -~]\x00){5,300}")
URL_RE=re.compile(r"https?://[^\s\x00\"'<>]{4,1024}",re.I)
DOMAIN_RE=re.compile(r"(?<![A-Za-z0-9.-])(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?::\d+)?(?![A-Za-z0-9.-])")

def safe_url(v):
    try: p=urlsplit(v.rstrip("\"'<>),]}"))
    except ValueError: return None
    if p.scheme.lower() not in {"http","https"} or not p.hostname: return None
    host=p.hostname.lower()
    try: port=p.port
    except ValueError: port=None
    netloc=host if port is None else f"{host}:{port}"
    return urlunsplit((p.scheme.lower(),netloc,p.path or "/","",""))

def scrub_urls(text):
    return URL_RE.sub(lambda m:safe_url(m.group(0)) or "<url>",text)

def download(url,out):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"*/*"})
    total=0; h=hashlib.sha256()
    with urllib.request.urlopen(req,timeout=120) as r, out.open("wb") as w:
        declared=r.headers.get("Content-Length")
        if declared and int(declared)>MAX_DOWNLOAD: raise ValueError("download too large")
        final=r.geturl()
        while True:
            chunk=r.read(1024*1024)
            if not chunk: break
            total+=len(chunk)
            if total>MAX_DOWNLOAD: raise ValueError("download exceeded limit")
            h.update(chunk); w.write(chunk)
    p=urlsplit(final)
    return {"size":total,"sha256":h.hexdigest(),"final_host":p.hostname,"final_path":p.path}

def scan_blob(data):
    urls=[]; domains=Counter(); hits=[]; seen_url=set(); seen_hit=set()
    def consume(offset,text,enc):
        for m in URL_RE.finditer(text):
            u=safe_url(m.group(0))
            if u and u not in seen_url and len(urls)<MAX_ITEMS:
                seen_url.add(u); urls.append({"offset":offset+m.start(),"encoding":enc,"url":u})
        for d in DOMAIN_RE.findall(text):
            domains[d.lower()]+=1
        low=text.lower()
        terms=[t for t in TERMS if t in low]
        if terms:
            clean=scrub_urls(text.strip())
            if len(clean)>420: clean=clean[:420]+"..."
            key=(enc,clean)
            if key not in seen_hit and len(hits)<MAX_ITEMS:
                seen_hit.add(key); hits.append({"offset":offset,"encoding":enc,"terms":terms,"string":clean})
    for m in ASCII_RE.finditer(data):
        consume(m.start(),m.group(0).decode("ascii","ignore"),"ascii")
    for m in UTF16_RE.finditer(data):
        consume(m.start(),m.group(0)[::2].decode("ascii","ignore"),"utf16le")
    return {"urls":urls,"domains":dict(domains.most_common(300)),"term_strings":hits}

def inspect_apk(name,payload):
    evidence=[]; libs=[]
    with ZipFile(BytesIO(payload)) as apk:
        for info in sorted(apk.infolist(),key=lambda x:x.filename):
            if info.is_dir(): continue
            low=info.filename.lower()
            if low.startswith("lib/") and low.endswith(".so"):
                libs.append({"path":info.filename,"size":info.file_size})
            scan=(low.startswith("lib/") or low.endswith(".dex") or low.startswith("assets/")
                  or low.startswith("res/raw/") or low.endswith((".json",".xml",".txt",".cfg",".ini",".plist")))
            if not scan or info.file_size>MAX_ENTRY: continue
            try: data=apk.read(info)
            except Exception: continue
            result=scan_blob(data)
            if result["urls"] or result["domains"] or result["term_strings"]:
                evidence.append({"path":info.filename,"size":len(data),
                                 "sha256":hashlib.sha256(data).hexdigest(),**result})
    return {"apk":name,"native_libraries":libs,"evidence":evidence}

def inspect_xapk(path):
    apks=[]; members=[]
    with ZipFile(path) as outer:
        for info in sorted(outer.infolist(),key=lambda x:x.filename):
            if info.is_dir(): continue
            members.append({"path":info.filename,"size":info.file_size})
            if not info.filename.lower().endswith(".apk") or info.file_size>MAX_DOWNLOAD: continue
            try: apks.append(inspect_apk(info.filename,outer.read(info)))
            except BadZipFile: apks.append({"apk":info.filename,"error":"bad-apk"})
    host_counts=Counter(); domain_counts=Counter(); term_counts=Counter()
    for apk in apks:
        for item in apk.get("evidence",[]):
            for u in item["urls"]:
                h=urlsplit(u["url"]).hostname
                if h: host_counts[h]+=1
            domain_counts.update(item["domains"])
            for hit in item["term_strings"]:
                term_counts.update(hit["terms"])
    return {"top_members":members,"apks":apks,
            "url_hosts":dict(host_counts.most_common(200)),
            "domains":dict(domain_counts.most_common(300)),
            "terms":dict(term_counts.most_common())}

def self_test():
    fake=(b"https://patch.example.invalid/a/filelist.bin?token=SECRET\x00"
          b"download_filelist.txt\x00cache/patch/gui/title.mbn\x00cdn.example.invalid\x00")
    with tempfile.TemporaryDirectory() as d:
        root=Path(d); apk=root/"base.apk"; xapk=root/"game.xapk"
        with ZipFile(apk,"w") as z:z.writestr("lib/arm64-v8a/libgame.so",fake)
        with ZipFile(xapk,"w") as z:z.write(apk,"base.apk")
        out=inspect_xapk(xapk); enc=json.dumps(out)
        assert "patch.example.invalid" in enc and "download_filelist" in enc
        assert "token=SECRET" not in enc
    print("Logres public XAPK patch network inspector self-test: PASS")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--url"); ap.add_argument("--output",type=Path); ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test: self_test(); return 0
    if not a.url: print("--url required",file=sys.stderr); return 2
    try:
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"logres.xapk"; meta=download(a.url,p); result={"provenance":"PUBLIC_XAPK_PATCH_NETWORK_METADATA","download":meta,**inspect_xapk(p)}
    except Exception as e:
        print(f"inspection failed: {type(e).__name__}: {e}",file=sys.stderr); return 1
    text=json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n"
    if a.output: a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(text,encoding="utf-8")
    else: sys.stdout.write(text)
    return 0
if __name__=="__main__": raise SystemExit(main())
