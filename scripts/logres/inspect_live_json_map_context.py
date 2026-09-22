#!/usr/bin/env python3
"""Inspect structural JSON context around exact live Logres map-ID references."""
from __future__ import annotations
import argparse, json, re, sys, tempfile
from pathlib import Path
from hydrate_private_assets import _make_synthetic_mbn, parse_mbn

CACHE_NAME="jp-live-patch-cache"
MAP_RE=re.compile(r"(?<![0-9])([0-9]{3}_[0-9]{3}_[0-9]{5})(?![0-9])")
CONTEXT_RE=re.compile(r"(tutorial|map|field|spawn|warp|start|initial|entry|quest|battle|character|create|position|coord|area|room)",re.I)

def segment(v):
    s=str(v)
    if len(s)>96:return "<long-key>"
    return s

def context_keys(stack):
    out=[]
    for key in stack[-12:]:
        if CONTEXT_RE.search(str(key)):
            out.append(segment(key))
    return out

def inspect_value(value,target,entry):
    refs=[]
    def walk(v,pointer,stack):
        if isinstance(v,dict):
            for raw_key,child in v.items():
                key=str(raw_key); esc=key.replace("~","~0").replace("/","~1")
                q=pointer+"/"+esc
                if key==target:
                    refs.append({"entry":entry,"map_id":target,"kind":"key","pointer":q,
                                 "ancestor_context_keys":context_keys(stack+[key]),
                                 "child_type":type_name(child)})
                elif target in key and MAP_RE.search(key):
                    refs.append({"entry":entry,"map_id":target,"kind":"embedded-key","pointer":q,
                                 "ancestor_context_keys":context_keys(stack+[key]),
                                 "child_type":type_name(child)})
                walk(child,q,stack+[key])
        elif isinstance(v,list):
            for i,child in enumerate(v):
                walk(child,pointer+"/"+str(i),stack)
        elif isinstance(v,str):
            if v==target:
                refs.append({"entry":entry,"map_id":target,"kind":"value","pointer":pointer,
                             "ancestor_context_keys":context_keys(stack),"value_length":len(v)})
            elif target in v:
                refs.append({"entry":entry,"map_id":target,"kind":"embedded-string","pointer":pointer,
                             "ancestor_context_keys":context_keys(stack),"value_length":len(v)})
    walk(value,"",[])
    return refs

def type_name(v):
    if isinstance(v,bool):return "bool"
    if v is None:return "null"
    if isinstance(v,dict):return "object"
    if isinstance(v,list):return "array"
    if isinstance(v,str):return "string"
    if isinstance(v,int):return "int"
    if isinstance(v,float):return "float"
    return type(v).__name__

def inspect(anchor,target,only_entry=None):
    root=anchor.resolve().parent/CACHE_NAME
    package=root/"json_resource.mbn"
    if not package.is_file():raise ValueError("json_resource.mbn not found")
    if not (root/"map"/(target+".mbn")).is_file() and not (root/"map"/(target+"__ans.mbn")).is_file():
        raise ValueError("target is not a recovered map package")
    entries=parse_mbn(package.read_bytes())
    refs=[]; parsed=0; errors=[]
    for name,data in sorted(entries.items()):
        if Path(name).suffix.lower()!=".json":continue
        if only_entry and name!=only_entry:continue
        try:value=json.loads(data)
        except (UnicodeDecodeError,json.JSONDecodeError):
            errors.append(name);continue
        parsed+=1
        refs.extend(inspect_value(value,target,name))
    return {
        "provenance":"PUBLIC_LIVE_JP_JSON_MAP_REFERENCE_STRUCTURE",
        "policy":"Structural metadata only. String values are never exported.",
        "target_map_id":target,
        "parsed_json_entries":parsed,
        "reference_count":len(refs),
        "references":refs,
        "parse_errors":errors,
    }

def self_test():
    secret="SECRET_TEXT_MUST_NOT_EXPORT"
    target="100_001_00002"
    payload={"tutorial":{"maps":{target:{"text":secret}},"next_map":target,
                         "embedded":"prefix "+target+" suffix"}}
    with tempfile.TemporaryDirectory() as d:
        root=Path(d);anchor=root/"private.zip";anchor.write_bytes(b"x")
        cache=root/CACHE_NAME;(cache/"map").mkdir(parents=True)
        (cache/"map"/(target+".mbn")).write_bytes(_make_synthetic_mbn(target+".map",b"x"))
        (cache/"json_resource.mbn").write_bytes(_make_synthetic_mbn("popUp_tutorial_texts.json",json.dumps(payload).encode()))
        out=inspect(anchor,target);enc=json.dumps(out)
        assert secret not in enc
        kinds={r["kind"] for r in out["references"]}
        assert {"key","value","embedded-string"}<=kinds
    print("Logres live JSON map context inspector self-test: PASS")

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--anchor",type=Path);ap.add_argument("--map-id");ap.add_argument("--entry");ap.add_argument("--output",type=Path);ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test:self_test();return 0
    if not a.anchor or not a.map_id:print("--anchor and --map-id required",file=sys.stderr);return 2
    try:out=inspect(a.anchor,a.map_id,a.entry)
    except Exception as e:print(f"inspect failed: {type(e).__name__}: {e}",file=sys.stderr);return 1
    text=json.dumps(out,indent=2,sort_keys=True,allow_nan=False)+"\n"
    if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(text,encoding="utf-8")
    else:sys.stdout.write(text)
    return 0
if __name__=="__main__":raise SystemExit(main())
