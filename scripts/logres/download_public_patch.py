#!/usr/bin/env python3
"""Plan or download the live public Japanese Logres patch set to persistent Oracle storage."""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, json, os, re, sys, tempfile, time, urllib.error, urllib.request, zlib
from collections import Counter, OrderedDict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

DEFAULT_BASE="https://prd-cdn.mmo-logres.com/patch/1789742711/android/"
MAX_META=24*1024*1024
SHA1_RE=re.compile(r"^[0-9a-f]{40}$")
MAX_FAILURES=100

@dataclass(frozen=True)
class Record:
    sha1:str
    size:int
    path:str
    timestamp:int
    fields:tuple[str,...]

def safe_base(value):
    p=urlsplit(value)
    if p.scheme.lower() not in {"http","https"} or not p.hostname:
        raise ValueError("invalid base URL")
    netloc=p.hostname.lower()
    if p.port:netloc+=f":{p.port}"
    path=p.path if p.path.endswith("/") else p.path+"/"
    return urlunsplit((p.scheme.lower(),netloc,path,"",""))

def safe_rel(value):
    raw=value.strip().replace("\\","/")
    while raw.startswith("./"):raw=raw[2:]
    p=Path(raw)
    if not raw or raw.startswith("/") or ".." in p.parts:
        raise ValueError(f"unsafe patch path: {value!r}")
    return p.as_posix()

def remote_url(base,path):
    return urljoin(base,quote(safe_rel(path),safe="/._-"))

def fetch_bytes(url,max_bytes=MAX_META,timeout=60):
    req=urllib.request.Request(url,headers={"User-Agent":"Logres-Reconstruction-PatchMirror/1.0","Accept":"*/*"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        declared=r.headers.get("Content-Length")
        if declared and int(declared)>max_bytes:raise ValueError("metadata file too large")
        data=r.read(max_bytes+1)
        if len(data)>max_bytes:raise ValueError("metadata file exceeded bound")
        return data

def load_meta(base,name,timeout=60):
    data=fetch_bytes(remote_url(base,name),timeout=timeout)
    return {"name":name,"size":len(data),"sha1":hashlib.sha1(data).hexdigest(),"sha256":hashlib.sha256(data).hexdigest()},data

def verify_sidecar(data,expected_sha1,name):
    text=data.decode("ascii","strict").strip().lower()
    if not SHA1_RE.fullmatch(text):raise ValueError(f"{name} is not a SHA-1 sidecar")
    if text!=expected_sha1:raise ValueError(f"{name} does not match compressed file")
    return text

def parse_filelist(compressed,source):
    raw=zlib.decompress(compressed)
    records=[]
    for number,line in enumerate(raw.decode("utf-8","strict").splitlines(),1):
        if not line.strip():continue
        fields=line.split()
        if len(fields)<4:raise ValueError(f"{source}:{number}: short record")
        sha1=fields[0].lower()
        if not SHA1_RE.fullmatch(sha1):raise ValueError(f"{source}:{number}: invalid SHA-1")
        try:size=int(fields[1]);timestamp=int(fields[3])
        except ValueError as exc:raise ValueError(f"{source}:{number}: invalid numeric field") from exc
        if size<0:raise ValueError(f"{source}:{number}: negative size")
        path=safe_rel(fields[2])
        records.append(Record(sha1,size,path,timestamp,tuple(fields[4:])))
    return raw,records

def build_plan(base,timeout=60):
    file_meta,file_bin=load_meta(base,"filelist.bin",timeout)
    hash_meta,file_hash=load_meta(base,"filelistbin.hash",timeout)
    extra_meta,extra_bin=load_meta(base,"extra_filelist.bin",timeout)
    extra_hash_meta,extra_hash=load_meta(base,"extra_filelistbin.hash",timeout)
    bin_meta,bin_bin=load_meta(base,"binfilelist.bin",timeout)
    verify_sidecar(file_hash,file_meta["sha1"],"filelistbin.hash")
    verify_sidecar(extra_hash,extra_meta["sha1"],"extra_filelistbin.hash")
    file_raw,main=parse_filelist(file_bin,"filelist.bin")
    extra_raw,extra=parse_filelist(extra_bin,"extra_filelist.bin")
    merged=OrderedDict((r.path,r) for r in main)
    for r in extra:merged[r.path]=r
    records=list(merged.values())
    categories=Counter((r.path.split("/",1)[0] if "/" in r.path else "(root)") for r in records)
    total=sum(r.size for r in records)
    return {
        "base":base,
        "records":records,
        "metadata":{
            "filelist":{**file_meta,"decompressed_size":len(file_raw),"decompressed_sha256":hashlib.sha256(file_raw).hexdigest(),"record_count":len(main)},
            "filelist_hash":hash_meta,
            "extra_filelist":{**extra_meta,"decompressed_size":len(extra_raw),"decompressed_sha256":hashlib.sha256(extra_raw).hexdigest(),"record_count":len(extra)},
            "extra_filelist_hash":extra_hash_meta,
            "binfilelist":{**bin_meta,"zlib":bin_bin[:1]==b"\x78"},
        },
        "record_count":len(records),
        "total_bytes":total,
        "categories":dict(categories.most_common()),
        "main_count":len(main),
        "extra_count":len(extra),
    },{"filelist.bin":file_bin,"filelistbin.hash":file_hash,"extra_filelist.bin":extra_bin,"extra_filelistbin.hash":extra_hash,"binfilelist.bin":bin_bin}

def file_sha1(path):
    h=hashlib.sha1()
    with path.open("rb") as f:
        while True:
            chunk=f.read(1024*1024)
            if not chunk:break
            h.update(chunk)
    return h.hexdigest()

def verify_existing(target,record):
    try:
        if target.stat().st_size!=record.size:return False
        return file_sha1(target)==record.sha1
    except OSError:return False

def download_one(base,root,record,timeout,retries):
    target=root/record.path
    target.parent.mkdir(parents=True,exist_ok=True)
    if verify_existing(target,record):
        return {"status":"verified","path":record.path,"size":record.size}
    url=remote_url(base,record.path)
    last=None
    for attempt in range(retries+1):
        part=target.with_name(target.name+".part")
        try:
            h=hashlib.sha1();total=0
            req=urllib.request.Request(url,headers={"User-Agent":"Logres-Reconstruction-PatchMirror/1.0","Accept":"*/*"})
            with urllib.request.urlopen(req,timeout=timeout) as r,part.open("wb") as w:
                while True:
                    chunk=r.read(1024*1024)
                    if not chunk:break
                    total+=len(chunk)
                    if total>record.size:raise ValueError("download larger than manifest size")
                    h.update(chunk);w.write(chunk)
            if total!=record.size:raise ValueError(f"size mismatch {total}!={record.size}")
            digest=h.hexdigest()
            if digest!=record.sha1:raise ValueError(f"SHA1 mismatch {digest}")
            os.replace(part,target)
            return {"status":"downloaded","path":record.path,"size":record.size}
        except Exception as exc:
            last=f"{type(exc).__name__}: {exc}"
            try:part.unlink()
            except OSError:pass
            if attempt<retries:time.sleep(min(4,2**attempt))
    return {"status":"failed","path":record.path,"size":record.size,"error":last}

def save_meta(root,meta_files):
    dest=root/"_meta";dest.mkdir(parents=True,exist_ok=True)
    for name,data in meta_files.items():
        (dest/name).write_bytes(data)

def execute(plan,meta_files,root,workers,timeout,retries,max_files):
    save_meta(root,meta_files)
    records=plan["records"][:max_files] if max_files else plan["records"]
    counts=Counter();bytes_downloaded=0;failures=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures=[pool.submit(download_one,plan["base"],root,r,timeout,retries) for r in records]
        for fut in concurrent.futures.as_completed(futures):
            item=fut.result();counts[item["status"]]+=1
            if item["status"]=="downloaded":bytes_downloaded+=item["size"]
            if item["status"]=="failed" and len(failures)<MAX_FAILURES:failures.append(item)
    return {"selected_records":len(records),"counts":dict(counts),"bytes_downloaded":bytes_downloaded,"failure_count":counts["failed"],"failures":failures}

def public_summary(plan):
    return {
        "provenance":"PUBLIC_LOGRES_PATCH_DOWNLOAD_PLAN",
        "base":plan["base"],
        "record_count":plan["record_count"],
        "main_count":plan["main_count"],
        "extra_count":plan["extra_count"],
        "total_bytes":plan["total_bytes"],
        "total_gib":round(plan["total_bytes"]/(1024**3),3),
        "categories":plan["categories"],
        "metadata":plan["metadata"],
    }

def self_test():
    line="0123456789abcdef0123456789abcdef01234567 10 ./gui/title.mbn 123\n"
    raw,records=parse_filelist(zlib.compress(line.encode()),"test")
    assert len(records)==1 and records[0].path=="gui/title.mbn" and records[0].size==10
    assert safe_rel("./a/b.mbn")=="a/b.mbn"
    try:safe_rel("../bad.mbn");raise AssertionError("unsafe path accepted")
    except ValueError:pass
    print("Logres public patch downloader self-test: PASS")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--base",default=DEFAULT_BASE)
    ap.add_argument("--anchor",type=Path)
    ap.add_argument("--download",action="store_true")
    ap.add_argument("--workers",type=int,default=8)
    ap.add_argument("--timeout",type=int,default=60)
    ap.add_argument("--retries",type=int,default=2)
    ap.add_argument("--max-files",type=int)
    ap.add_argument("--output",type=Path)
    ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test:self_test();return 0
    if not 1<=a.workers<=16:print("workers must be 1..16",file=sys.stderr);return 2
    base=safe_base(a.base)
    try:plan,meta_files=build_plan(base,a.timeout)
    except Exception as e:print(f"plan failed: {type(e).__name__}: {e}",file=sys.stderr);return 1
    result=public_summary(plan)
    if a.download:
        if not a.anchor:print("--anchor required for persistent download",file=sys.stderr);return 2
        root=a.anchor.resolve().parent/"jp-live-patch-cache"
        root.mkdir(parents=True,exist_ok=True)
        result["download"]=execute(plan,meta_files,root,a.workers,a.timeout,a.retries,a.max_files)
        result["storage"]="oracle-private-sibling/jp-live-patch-cache"
    encoded=json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n"
    if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(encoded,encoding="utf-8")
    else:sys.stdout.write(encoded)
    return 0
if __name__=="__main__":raise SystemExit(main())
