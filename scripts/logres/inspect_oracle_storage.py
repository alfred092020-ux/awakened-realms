#!/usr/bin/env python3
"""Report persistent Oracle storage available for the public Logres patch mirror."""
from __future__ import annotations
import argparse, json, os, shutil, sys, tempfile
from pathlib import Path

CACHE_NAME="jp-live-patch-cache"

def tree_usage(root:Path):
    files=0; total=0
    if not root.exists():
        return {"exists":False,"file_count":0,"bytes":0}
    for base,dirs,names in os.walk(root):
        dirs.sort(); names.sort()
        for name in names:
            p=Path(base)/name
            try:
                if p.is_symlink(): continue
                total+=p.stat().st_size; files+=1
            except OSError:
                pass
    return {"exists":True,"file_count":files,"bytes":total}

def inspect(anchor:Path,required:int):
    parent=anchor.resolve().parent
    usage=shutil.disk_usage(parent)
    cache=parent/CACHE_NAME
    current=tree_usage(cache)
    remaining=max(0,required-current["bytes"])
    reserve=2*1024**3
    return {
        "provenance":"ORACLE_PRIVATE_STORAGE_METADATA",
        "filesystem_path_kind":"private-archive-parent",
        "disk":{"total_bytes":usage.total,"used_bytes":usage.used,"free_bytes":usage.free,
                "free_gib":round(usage.free/1024**3,3)},
        "patch_cache":current,
        "required_manifest_bytes":required,
        "remaining_manifest_bytes":remaining,
        "remaining_gib":round(remaining/1024**3,3),
        "safety_reserve_bytes":reserve,
        "enough_with_2gib_reserve":usage.free >= remaining+reserve,
    }

def self_test():
    with tempfile.TemporaryDirectory() as d:
        root=Path(d); anchor=root/"private.zip";anchor.write_bytes(b"x")
        cache=root/CACHE_NAME;cache.mkdir();(cache/"a").write_bytes(b"1234")
        out=inspect(anchor,10)
        assert out["patch_cache"]["bytes"]==4
        assert out["remaining_manifest_bytes"]==6
    print("Oracle Logres storage inspector self-test: PASS")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--anchor",type=Path)
    ap.add_argument("--required-bytes",type=int,required=False,default=0)
    ap.add_argument("--output",type=Path)
    ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test:self_test();return 0
    if not a.anchor:
        print("--anchor required unless --self-test",file=sys.stderr);return 2
    result=inspect(a.anchor,a.required_bytes)
    encoded=json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n"
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(encoded,encoding="utf-8")
    else:sys.stdout.write(encoded)
    return 0
if __name__=="__main__":raise SystemExit(main())
