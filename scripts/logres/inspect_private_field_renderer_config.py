#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, struct, sys, tempfile
from collections import Counter
from pathlib import Path
from zipfile import ZipFile
from hydrate_private_assets import _make_synthetic_mbn, parse_mbn

KEY_RE=re.compile(r"(camera|zoom|view.?scale|uv|anim(?:ation)?|frame|interval|fps|depth|layer|mask|terrain|projection|viewport|scroll|parallax|shader)",re.I)
MAX_MBN=128*1024*1024
MAX_HITS=300

def manifest(z,info):
    with z.open(info) as h:
        head=h.read(8)
        if len(head)!=8: raise ValueError("short")
        reserved,size=struct.unpack("<II",head)
        if reserved!=0 or size>8*1024*1024: raise ValueError("header")
        raw=h.read(size)
    value=json.loads(raw)
    if not isinstance(value,list): raise ValueError("manifest")
    return value

def kind(v):
    if isinstance(v,bool): return "bool"
    if isinstance(v,int): return "int"
    if isinstance(v,float): return "float"
    if isinstance(v,str): return "string"
    if isinstance(v,list): return "array"
    if isinstance(v,dict): return "object"
    if v is None: return "null"
    return type(v).__name__

def esc(s): return str(s).replace("~","~0").replace("/","~1")

def hits(value):
    out=[]
    def walk(v,p):
        if len(out)>=MAX_HITS: return
        if isinstance(v,dict):
            for k,child in sorted(v.items(),key=lambda x:str(x[0])):
                key=str(k); q=p+"/"+esc(key)
                if KEY_RE.search(key):
                    item={"pointer":q,"key":key,"value_type":kind(child)}
                    if isinstance(child,bool) or (isinstance(child,(int,float)) and not isinstance(child,bool)):
                        item["value"]=child
                    elif isinstance(child,(list,dict)):
                        item["size"]=len(child)
                    out.append(item)
                walk(child,q)
        elif isinstance(v,list):
            for i,child in enumerate(v): walk(child,p+"/"+str(i))
    walk(value,"")
    return out

def inspect(path):
    sources=[]; errors=[]
    with ZipFile(path) as z:
        for info in sorted(z.infolist(),key=lambda x:x.filename):
            if Path(info.filename).suffix.lower()!=".mbn": continue
            try: records=manifest(z,info)
            except (ValueError,json.JSONDecodeError,struct.error) as e:
                errors.append({"member":info.filename,"reason":type(e).__name__}); continue
            names=[r["name"] for r in records if isinstance(r,dict) and isinstance(r.get("name"),str) and Path(r["name"]).suffix.lower()==".json"]
            if not names: continue
            if info.file_size>MAX_MBN:
                errors.append({"member":info.filename,"reason":"scan-bound"}); continue
            try: entries=parse_mbn(z.read(info))
            except ValueError:
                errors.append({"member":info.filename,"reason":"parse-mbn"}); continue
            for name in names:
                data=entries.get(name)
                if data is None: continue
                try: parsed=json.loads(data)
                except (UnicodeDecodeError,json.JSONDecodeError): continue
                found=hits(parsed)
                if found:
                    sources.append({"container":info.filename,"entry":name,"size":len(data),"sha256":hashlib.sha256(data).hexdigest(),"hits":found})
    c=Counter(); n=Counter()
    for s in sources:
        for h in s["hits"]:
            c[h["key"]]+=1
            if "value" in h: n[h["key"]]+=1
    return {"provenance":"PRIVATE_CACHE_FIELD_RENDER_CONFIG_METADATA","semantic_policy":"Key names and numeric/bool values are evidence only. String values and source text are not exported.","source_count":len(sources),"sources":sources,"key_summary":[{"key":k,"occurrence_count":v,"numeric_or_bool_count":n[k]} for k,v in c.most_common(300)],"errors":errors}

def self_test():
    secret="PRIVATE_STRING_MUST_NOT_EXPORT"
    payload={"field":{"initial_view_scale":1.25,"animation_interval":0.2,"camera_mask":3,"shader_name":secret,"dialogue":secret}}
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/"x.zip"
        with ZipFile(p,"w") as z:
            z.writestr("files/cache/patch/json_resource.mbn",_make_synthetic_mbn("field_settings.json",json.dumps(payload).encode()))
        result=inspect(p); encoded=json.dumps(result)
        assert secret not in encoded
        vals={h["key"]:h.get("value") for s in result["sources"] for h in s["hits"]}
        assert vals["initial_view_scale"]==1.25 and vals["animation_interval"]==0.2 and vals["camera_mask"]==3
        shader=[h for s in result["sources"] for h in s["hits"] if h["key"]=="shader_name"][0]
        assert shader["value_type"]=="string" and "value" not in shader
    print("Logres private field renderer config inspector self-test: PASS")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("archive",nargs="?",type=Path); ap.add_argument("--output",type=Path); ap.add_argument("--self-test",action="store_true"); a=ap.parse_args()
    if a.self_test: self_test(); return 0
    if a.archive is None: print("archive required",file=sys.stderr); return 2
    try: result=inspect(a.archive)
    except (OSError,ValueError) as e: print(f"scan failed: {e}",file=sys.stderr); return 1
    text=json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n"
    if a.output: a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(text,encoding="utf-8")
    else: sys.stdout.write(text)
    return 0
if __name__=="__main__": raise SystemExit(main())
