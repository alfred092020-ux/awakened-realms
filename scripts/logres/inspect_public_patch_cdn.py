#!/usr/bin/env python3
"""Probe the public Logres patch CDN for recovered file-list names."""
from __future__ import annotations
import argparse, hashlib, json, re, sys, urllib.error, urllib.request, zlib
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

DEFAULT_PATHS=(
    "filelist.bin",
    "filelistbin.hash",
    "extra_filelist.bin",
    "extra_filelistbin.hash",
    "binfilelist.bin",
    "patch/binfilelist.bin",
    "download_filelist.txt",
    "download_binfilelist.txt",
)
MAX_FILE=24*1024*1024
MAX_DECOMPRESSED=64*1024*1024
SAFE_TEXT=re.compile(rb"^[\x09\x0a\x0d\x20-\x7e]*$")

def safe_url(value):
    p=urlsplit(value)
    if p.scheme.lower() not in {"http","https"} or not p.hostname:
        raise ValueError("invalid base URL")
    netloc=p.hostname.lower()
    if p.port: netloc+=f":{p.port}"
    return urlunsplit((p.scheme.lower(),netloc,p.path,"",""))

def join(base,path):
    if path.startswith("/") or ".." in Path(path).parts:
        raise ValueError("unsafe path")
    return urljoin(base.rstrip("/")+"/",quote(path,safe="/._-"))

def summarize_text(data):
    if len(data)>4096 or not SAFE_TEXT.fullmatch(data):
        return None
    text=data.decode("ascii","replace").strip()
    return text[:1000]

def summarize_zlib(data):
    if len(data)<2 or data[0] != 0x78:
        return None
    try:
        raw=zlib.decompress(data)
    except zlib.error:
        return None
    if len(raw)>MAX_DECOMPRESSED:
        return {"decompressed_size":len(raw),"too_large":True}
    out={
        "decompressed_size":len(raw),
        "decompressed_sha256":hashlib.sha256(raw).hexdigest(),
        "line_count":raw.count(b"\n")+(0 if raw.endswith(b"\n") or not raw else 1),
        "mbn_ascii_count":raw.lower().count(b".mbn"),
    }
    if SAFE_TEXT.fullmatch(raw):
        lines=[line.decode("utf-8","replace") for line in raw.splitlines()[:5]]
        out["first_lines"]=[line[:500] for line in lines]
    return out

def fetch(base,path):
    url=join(base,path)
    req=urllib.request.Request(url,headers={"User-Agent":"Logres-Reconstruction-Evidence/1.0","Accept":"*/*"})
    result={"path":path,"url":safe_url(url)}
    try:
        with urllib.request.urlopen(req,timeout=45) as r:
            declared=r.headers.get("Content-Length")
            if declared and int(declared)>MAX_FILE:
                result.update({"status":r.status,"content_length":int(declared),"skipped":"too-large"})
                return result
            body=r.read(MAX_FILE+1)
            if len(body)>MAX_FILE:
                result.update({"status":r.status,"skipped":"too-large"})
                return result
            result.update({
                "status":r.status,
                "final_url":safe_url(r.geturl()),
                "content_type":r.headers.get("Content-Type"),
                "size":len(body),
                "sha1":hashlib.sha1(body).hexdigest(),
                "sha256":hashlib.sha256(body).hexdigest(),
                "header_hex":body[:16].hex(),
            })
    except urllib.error.HTTPError as e:
        body=e.read(4096)
        result.update({
            "status":e.code,
            "final_url":safe_url(e.geturl()),
            "content_type":e.headers.get("Content-Type"),
            "error_body_size":len(body),
        })
        return result
    except Exception as e:
        result["error"]=f"{type(e).__name__}: {e}"
        return result
    preview=summarize_text(body)
    if preview is not None:
        result["text_preview"]=preview
    z=summarize_zlib(body)
    if z is not None:
        result["zlib"]=z
    return result

def inspect(base,paths):
    clean=safe_url(base.rstrip("/")+"/")
    return {
        "provenance":"PUBLIC_LOGRES_PATCH_CDN_PROBE",
        "base":clean,
        "results":[fetch(clean,path) for path in paths],
    }

def self_test():
    payload=b"a"*40+b" 10 ./gui/title.mbn 123\n"
    compressed=zlib.compress(payload)
    z=summarize_zlib(compressed)
    assert z and z["mbn_ascii_count"]==1 and z["line_count"]==1
    assert join("https://cdn.example.invalid/patch/","filelist.bin")=="https://cdn.example.invalid/patch/filelist.bin"
    print("Logres public patch CDN inspector self-test: PASS")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--base")
    ap.add_argument("--path",action="append")
    ap.add_argument("--output",type=Path)
    ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test:
        self_test();return 0
    if not a.base:
        print("--base required",file=sys.stderr);return 2
    try:
        result=inspect(a.base,tuple(a.path) if a.path else DEFAULT_PATHS)
    except Exception as e:
        print(f"probe failed: {type(e).__name__}: {e}",file=sys.stderr);return 1
    encoded=json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n"
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(encoded,encoding="utf-8")
    else:
        sys.stdout.write(encoded)
    return 0
if __name__=="__main__":raise SystemExit(main())
