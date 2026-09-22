#!/usr/bin/env python3
"""Find exact current-client references to recovered live Logres map package IDs."""
from __future__ import annotations
import argparse, hashlib, json, re, struct, sys, tempfile
from collections import Counter, defaultdict
from pathlib import Path

from hydrate_private_assets import _make_synthetic_mbn, parse_mbn

CACHE_NAME="jp-live-patch-cache"
MAP_RE=re.compile(rb"(?<![0-9])([0-9]{3}_[0-9]{3}_[0-9]{5})(?![0-9])")
MAP_NAME_RE=re.compile(r"^[0-9]{3}_[0-9]{3}_[0-9]{5}(?:__ans)?$")
SOURCE_SUFFIXES={".json",".lua",".luac",".txt",".xml",".bin"}
SCAN_TOPS={"(root)","gui","system","skitevent","battle"}
MAX_MBN=128*1024*1024
MAX_MANIFEST=16*1024*1024
MAX_REFS_PER_SOURCE=400
KEYWORDS=(
    b"tutorial",b"characreate",b"char_create",b"chara_create",b"character",
    b"spawn",b"warp",b"initial",b"start",b"entry",b"quest",b"field",b"map",
    b"encounter",b"battle",b"position",b"coordinate",b"posx",b"posy",
)
KEYWORD_WINDOW=4096

def read_manifest(path:Path):
    with path.open("rb") as f:
        head=f.read(8)
        if len(head)!=8: raise ValueError("short-header")
        reserved,size=struct.unpack("<II",head)
        if reserved!=0 or size>MAX_MANIFEST: raise ValueError("bad-header")
        raw=f.read(size)
        if len(raw)!=size: raise ValueError("short-manifest")
    value=json.loads(raw.decode("utf-8"))
    if not isinstance(value,list): raise ValueError("non-array")
    return value

def map_ids(root:Path):
    result=set()
    map_root=root/"map"
    if not map_root.is_dir(): return result
    for p in map_root.rglob("*.mbn"):
        stem=p.stem
        if not MAP_NAME_RE.fullmatch(stem): continue
        if stem.endswith("__ans"): stem=stem[:-5]
        result.add(stem)
    return result

def top_category(rel:str)->str:
    return rel.split("/",1)[0] if "/" in rel else "(root)"

def nearest_keyword(data:bytes,offset:int):
    lo=max(0,offset-KEYWORD_WINDOW); hi=min(len(data),offset+KEYWORD_WINDOW)
    chunk=data[lo:hi].lower()
    best=None
    for kw in KEYWORDS:
        start=0
        while True:
            pos=chunk.find(kw,start)
            if pos<0: break
            absolute=lo+pos
            distance=abs(absolute-offset)
            if best is None or distance<best[2]:
                best=(kw.decode("ascii"),absolute,distance)
            start=pos+1
    if best is None:return None
    return {"keyword":best[0],"keyword_offset":best[1],"distance":best[2]}

def name_context(container:str,entry:str):
    low=(container+" "+entry).lower()
    out=[]
    for label,terms in (
        ("tutorial",("tutorial",)),
        ("character_create",("characreate","char_create","chara_create")),
        ("character",("character",)),
        ("spawn",("spawn",)),
        ("start",("start","initial","entry")),
        ("quest",("quest",)),
        ("field",("field",)),
        ("battle",("battle",)),
        ("map",("map",)),
    ):
        if any(t in low for t in terms):out.append(label)
    return out

def inspect(anchor:Path):
    root=anchor.resolve().parent/CACHE_NAME
    if not root.is_dir(): raise ValueError("live patch cache not found")
    ids=map_ids(root)
    refs=[]; errors=[]; scanned_sources=0; scanned_mbn=0
    per_map=defaultdict(lambda:{"sources":set(),"contexts":Counter(),"refs":0})
    for p in sorted(root.rglob("*.mbn")):
        rel=p.relative_to(root).as_posix()
        if top_category(rel) not in SCAN_TOPS: continue
        try:size=p.stat().st_size
        except OSError:continue
        if size>MAX_MBN:continue
        try:manifest=read_manifest(p)
        except Exception as e:
            errors.append({"package":rel,"reason":type(e).__name__});continue
        candidate_names=[
            item.get("name") for item in manifest
            if isinstance(item,dict) and isinstance(item.get("name"),str)
            and Path(item["name"]).suffix.lower() in SOURCE_SUFFIXES
        ]
        if not candidate_names:continue
        scanned_mbn+=1
        try:entries=parse_mbn(p.read_bytes())
        except Exception as e:
            errors.append({"package":rel,"reason":"parse-"+type(e).__name__});continue
        for entry in candidate_names:
            data=entries.get(entry)
            if data is None:continue
            scanned_sources+=1
            source_refs=0
            seen=set()
            for match in MAP_RE.finditer(data):
                mid=match.group(1).decode("ascii")
                if mid not in ids:continue
                key=(mid,match.start())
                if key in seen:continue
                seen.add(key)
                item={
                    "map_id":mid,
                    "container":rel,
                    "entry":entry,
                    "format":Path(entry).suffix.lower().lstrip("."),
                    "offset":match.start(),
                    "source_sha256":hashlib.sha256(data).hexdigest(),
                    "name_contexts":name_context(rel,entry),
                }
                near=nearest_keyword(data,match.start())
                if near:item["nearest_keyword"]=near
                refs.append(item)
                per_map[mid]["sources"].add((rel,entry))
                per_map[mid]["refs"]+=1
                per_map[mid]["contexts"].update(item["name_contexts"])
                if near and near["distance"]<=KEYWORD_WINDOW:
                    per_map[mid]["contexts"].update([near["keyword"]])
                source_refs+=1
                if source_refs>=MAX_REFS_PER_SOURCE:break
    ranked=[]
    for mid,item in per_map.items():
        ranked.append({
            "map_id":mid,
            "reference_count":item["refs"],
            "source_count":len(item["sources"]),
            "contexts":[{"name":k,"count":v} for k,v in item["contexts"].most_common()],
        })
    ranked.sort(key=lambda x:(-sum(c["count"] for c in x["contexts"] if c["name"] in {"tutorial","character_create","spawn","start","quest"}),-x["source_count"],-x["reference_count"],x["map_id"]))
    return {
        "provenance":"PUBLIC_LIVE_JP_CONFIRMED_MAP_REFERENCE_METADATA",
        "policy":"Exact recovered map IDs only. No source text, dialogue, geometry or textures are exported. Context proximity does not by itself prove tutorial selection.",
        "confirmed_map_id_count":len(ids),
        "scanned_mbn_count":scanned_mbn,
        "scanned_source_count":scanned_sources,
        "reference_count":len(refs),
        "ranked_summary":ranked[:500],
        "references":refs[:5000],
        "errors":errors[:200],
    }

def self_test():
    secret="SECRET_DIALOGUE_DO_NOT_EXPORT"
    mid="001_000_00001"
    other="999_999_99999"
    with tempfile.TemporaryDirectory() as d:
        root=Path(d);anchor=root/"private.zip";anchor.write_bytes(b"x")
        cache=root/CACHE_NAME;(cache/"map").mkdir(parents=True);(cache/"gui").mkdir()
        m=_make_synthetic_mbn(mid+".map",b"x")
        (cache/"map"/(mid+".mbn")).write_bytes(m)
        payload=(secret+" tutorial spawn "+mid+" "+other).encode()
        (cache/"gui"/"tutorial.mbn").write_bytes(_make_synthetic_mbn("tutorial.lua",payload))
        out=inspect(anchor);enc=json.dumps(out)
        assert secret not in enc and other not in enc
        assert out["reference_count"]==1
        assert out["references"][0]["map_id"]==mid
        assert out["references"][0]["nearest_keyword"]["keyword"] in {"tutorial","spawn"}
    print("Logres live confirmed map reference inspector self-test: PASS")

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--anchor",type=Path);ap.add_argument("--output",type=Path);ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test:self_test();return 0
    if not a.anchor:print("--anchor required",file=sys.stderr);return 2
    try:out=inspect(a.anchor)
    except Exception as e:print(f"scan failed: {type(e).__name__}: {e}",file=sys.stderr);return 1
    text=json.dumps(out,indent=2,sort_keys=True,allow_nan=False)+"\n"
    if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(text,encoding="utf-8")
    else:sys.stdout.write(text)
    return 0
if __name__=="__main__":raise SystemExit(main())
