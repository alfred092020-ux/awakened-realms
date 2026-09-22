#!/usr/bin/env python3
"""Inspect public current Japanese Logres native HostEntry evidence."""
from __future__ import annotations
import argparse, hashlib, json, re, shutil, subprocess, sys, tempfile, urllib.request
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

MAX_DOWNLOAD=170*1024*1024
MAX_ITEMS=300
ASCII_RE=re.compile(rb"[ -~]{4,400}")
UTF16_RE=re.compile(rb"(?:[ -~]\\x00){4,240}")
STRING_TERMS=(
    "servicehost","hostentry","release-and","\${platform}","\${version}",
    "url_patch","url_debugresourcepatch","platform","version","filelist.bin",
    "download_filelist","cache/patch","mmo-logres",
)
SYMBOL_RE=re.compile(r"(HostEntry|ServiceHost|getPlatform|getVersion|AppVersion|URL_Patch|DebugResourcePatch)",re.I)

def download(url,out):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"*/*"})
    total=0; h=hashlib.sha256()
    with urllib.request.urlopen(req,timeout=120) as r, out.open("wb") as w:
        while True:
            chunk=r.read(1024*1024)
            if not chunk: break
            total+=len(chunk)
            if total>MAX_DOWNLOAD: raise ValueError("download limit exceeded")
            h.update(chunk); w.write(chunk)
    return {"size":total,"sha256":h.hexdigest()}

def find_libgame(xapk):
    with ZipFile(xapk) as outer:
        candidates=[]
        for info in outer.infolist():
            if not info.filename.lower().endswith(".apk"): continue
            payload=outer.read(info)
            try:
                with ZipFile(BytesIO(payload)) as apk:
                    for member in apk.infolist():
                        if member.filename=="lib/arm64-v8a/libgame.so":
                            data=apk.read(member)
                            candidates.append((info.filename,data))
            except Exception:
                pass
    if not candidates: raise ValueError("arm64 libgame.so not found")
    candidates.sort(key=lambda item:len(item[1]),reverse=True)
    return candidates[0]

def string_hits(data):
    out=[]; seen=set()
    def consume(offset,text,encoding):
        low=text.lower()
        matched=[t for t in STRING_TERMS if t.lower() in low]
        if not matched:return
        clean=text.strip()
        if len(clean)>360:clean=clean[:360]+"..."
        key=(encoding,clean)
        if key in seen:return
        seen.add(key)
        out.append({"offset":offset,"encoding":encoding,"terms":matched,"string":clean})
    for m in ASCII_RE.finditer(data):
        consume(m.start(),m.group(0).decode("ascii","ignore"),"ascii")
        if len(out)>=MAX_ITEMS:return out
    for m in UTF16_RE.finditer(data):
        consume(m.start(),m.group(0)[::2].decode("ascii","ignore"),"utf16le")
        if len(out)>=MAX_ITEMS:return out
    return out

def tool_output(command):
    exe=shutil.which(command[0])
    if not exe:return {"available":False,"rows":[]}
    try:
        p=subprocess.run([exe,*command[1:]],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=90,check=False)
    except Exception as e:
        return {"available":True,"error":f"{type(e).__name__}: {e}","rows":[]}
    rows=[]
    for line in p.stdout.splitlines():
        if SYMBOL_RE.search(line):
            rows.append(line[:700])
            if len(rows)>=MAX_ITEMS:break
    return {"available":True,"exit_code":p.returncode,"rows":rows}

def inspect(url):
    with tempfile.TemporaryDirectory() as raw:
        root=Path(raw); xapk=root/"logres.xapk"
        meta=download(url,xapk)
        apk_name,data=find_libgame(xapk)
        so=root/"libgame.so"; so.write_bytes(data)
        return {
            "provenance":"PUBLIC_CURRENT_JP_HOSTENTRY_NATIVE_METADATA",
            "download":meta,
            "apk":apk_name,
            "libgame":{"size":len(data),"sha256":hashlib.sha256(data).hexdigest()},
            "string_hits":string_hits(data),
            "nm":tool_output(["nm","-D","-C",str(so)]),
            "readelf":tool_output(["readelf","-Ws","--wide",str(so)]),
        }

def self_test():
    fake=(b"xx servicehost.json xx release-and xx ${platform} xx ${version} xx "
          b"_ZN3lfs9HostEntry12getURL_PatchEv xx")
    hits=string_hits(fake)
    enc=json.dumps(hits)
    assert "release-and" in enc and "${platform}" in enc and "URL_Patch" in enc
    print("Logres public HostEntry native inspector self-test: PASS")

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--url");ap.add_argument("--output",type=Path);ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test:self_test();return 0
    if not a.url:print("--url required",file=sys.stderr);return 2
    try:result=inspect(a.url)
    except Exception as e:print(f"inspection failed: {type(e).__name__}: {e}",file=sys.stderr);return 1
    text=json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n"
    if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(text,encoding="utf-8")
    else:sys.stdout.write(text)
    return 0
if __name__=="__main__":raise SystemExit(main())
