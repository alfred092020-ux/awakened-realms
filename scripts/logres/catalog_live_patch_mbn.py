#!/usr/bin/env python3
"""Catalog the persistent live Japanese Logres patch mirror using MBN manifests only."""
from __future__ import annotations
import argparse, json, os, struct, sys, tempfile
from collections import Counter, defaultdict
from pathlib import Path

CACHE_NAME="jp-live-patch-cache"
MAX_MANIFEST=16*1024*1024
MAX_SAMPLES=120
KEYWORDS=("tutorial","beginner","start","starter","field","map","quest","battle","title",
          "world","character","create","village","town","npc","enemy","monster","spawn","camera")
INNER_EXTS=(".json",".lua",".luac",".dds",".png",".astc",".lfla",".ogg",".wav",".plist",".bss",".rcb")

def safe_rel(root:Path,p:Path)->str:
    return p.relative_to(root).as_posix()

def read_manifest(path:Path):
    with path.open("rb") as f:
        head=f.read(8)
        if len(head)!=8: raise ValueError("short-header")
        reserved,size=struct.unpack("<II",head)
        if reserved!=0 or size<0 or size>MAX_MANIFEST: raise ValueError("bad-header")
        raw=f.read(size)
        if len(raw)!=size: raise ValueError("short-manifest")
    value=json.loads(raw.decode("utf-8"))
    if not isinstance(value,list): raise ValueError("non-array")
    names=[]
    for item in value:
        if isinstance(item,dict) and isinstance(item.get("name"),str):
            names.append(item["name"])
    return names

def inspect(anchor:Path):
    root=anchor.resolve().parent/CACHE_NAME
    if not root.is_dir(): raise ValueError("live patch cache not found")
    files=[]
    category=Counter(); category_bytes=Counter(); root_ext=Counter()
    for base,dirs,names in os.walk(root):
        dirs.sort(); names.sort()
        for name in names:
            p=Path(base)/name
            if p.is_symlink(): continue
            rel=safe_rel(root,p)
            if rel.startswith("_meta/"): continue
            try:size=p.stat().st_size
            except OSError: continue
            files.append((rel,p,size))
            top=rel.split("/",1)[0] if "/" in rel else "(root)"
            category[top]+=1; category_bytes[top]+=size
            root_ext[p.suffix.lower() or "(none)"]+=1

    mbn_ok=0; mbn_bad=0; inner_total=0
    inner_ext=Counter(); inner_top=Counter(); category_inner=Counter()
    keyword_packages=defaultdict(list); keyword_entries=defaultdict(list)
    category_samples=defaultdict(list)
    map_samples=[]
    manifest_entry_counts=[]

    for rel,p,size in files:
        top=rel.split("/",1)[0] if "/" in rel else "(root)"
        if len(category_samples[top])<12: category_samples[top].append(rel)
        lowrel=rel.lower()
        for key in KEYWORDS:
            if key in lowrel and len(keyword_packages[key])<MAX_SAMPLES:
                keyword_packages[key].append(rel)
        if p.suffix.lower()!=".mbn": continue
        try:names=read_manifest(p)
        except (OSError,ValueError,UnicodeDecodeError,json.JSONDecodeError):
            mbn_bad+=1; continue
        mbn_ok+=1; inner_total+=len(names); manifest_entry_counts.append(len(names))
        category_inner[top]+=len(names)
        local_ext=Counter()
        for name in names:
            nlow=name.lower()
            suffix=Path(name).suffix.lower() or "(none)"
            inner_ext[suffix]+=1; local_ext[suffix]+=1
            first=name.replace("\\","/").split("/",1)[0]
            inner_top[first]+=1
            for key in KEYWORDS:
                if key in nlow and len(keyword_entries[key])<MAX_SAMPLES:
                    keyword_entries[key].append({"package":rel,"entry":name[:300]})
        if top=="map" and len(map_samples)<250:
            map_samples.append({
                "package":rel,
                "entry_count":len(names),
                "extensions":dict(local_ext.most_common(12)),
                "sample_entries":names[:12],
            })

    counts=Counter(manifest_entry_counts)
    return {
      "provenance":"PUBLIC_LIVE_JP_PATCH_MBN_MANIFEST_CATALOG",
      "policy":"Manifest metadata only; no MBN payload bytes are exported.",
      "cache":{"file_count":len(files),"bytes":sum(x[2] for x in files)},
      "root_categories":[
        {"category":k,"files":category[k],"bytes":category_bytes[k],"inner_entries":category_inner[k]}
        for k,_ in category.most_common()
      ],
      "root_extensions":dict(root_ext.most_common()),
      "mbn":{"parsed":mbn_ok,"failed":mbn_bad,"inner_entry_count":inner_total,
             "entry_count_distribution":dict(counts.most_common(30))},
      "inner_extensions":dict(inner_ext.most_common(80)),
      "inner_top_components":dict(inner_top.most_common(100)),
      "category_samples":dict(category_samples),
      "keyword_package_matches":dict(keyword_packages),
      "keyword_entry_matches":dict(keyword_entries),
      "map_samples":map_samples,
    }

def self_test():
    manifest=json.dumps([{"name":"field_settings.json"},{"name":"map/test.dds"}]).encode()
    with tempfile.TemporaryDirectory() as d:
        root=Path(d); anchor=root/"private.zip";anchor.write_bytes(b"x")
        cache=root/CACHE_NAME; (cache/"map").mkdir(parents=True)
        mbn=cache/"map"/"tutorial_map.mbn"
        mbn.write_bytes(struct.pack("<II",0,len(manifest))+manifest+b"payload")
        out=inspect(anchor)
        assert out["mbn"]["parsed"]==1
        assert out["inner_extensions"][".json"]==1 and out["inner_extensions"][".dds"]==1
        assert out["keyword_package_matches"]["tutorial"][0]=="map/tutorial_map.mbn"
    print("Logres live patch MBN catalog self-test: PASS")

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--anchor",type=Path);ap.add_argument("--output",type=Path);ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test:self_test();return 0
    if not a.anchor:print("--anchor required",file=sys.stderr);return 2
    try:out=inspect(a.anchor)
    except Exception as e:print(f"catalog failed: {type(e).__name__}: {e}",file=sys.stderr);return 1
    text=json.dumps(out,indent=2,sort_keys=True,allow_nan=False)+"\n"
    if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(text,encoding="utf-8")
    else:sys.stdout.write(text)
    return 0
if __name__=="__main__":raise SystemExit(main())
