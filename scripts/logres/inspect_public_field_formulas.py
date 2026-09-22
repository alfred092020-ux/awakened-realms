#!/usr/bin/env python3
"""Recover bounded native instruction metadata for critical Logres field formulas.

Downloads the established public current Japanese XAPK temporarily, extracts
arm64 libgame.so, resolves exact demangled target functions, and emits bounded
instruction metadata (mnemonic/operands/addresses only) for a small allowlist.
No binary bytes or whole-library disassembly are exported.
"""
from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from zipfile import ZipFile

MAX_DOWNLOAD=180*1024*1024
MAX_FUNCTION_BYTES=8192
MAX_INSTRUCTIONS=1200

TARGET_PATTERNS=(
    ("tile_contains", re.compile(r"^lfs::field::FieldTerrain::tileContains\(cocos2d::Vec2 const&\) const$")),
    ("tile_at_vec3", re.compile(r"^lfs::field::FieldTerrain::tileAt\(lfs::Vector3 const&\) const$")),
    ("adjust_actor", re.compile(r"^lfs::field::FieldTerrain::adjustActorToTerrain\(")),
    ("link_cost", re.compile(r"^lfs::field::FieldTile::calculateLinkNodeCost\(")),
    ("player_depth", re.compile(r"^lfs::field::FieldPlayer::getDepthOrder\(\) const$")),
    ("copy_vertex", re.compile(r"^lfs::field::DataParser::copyVertex\(")),
    ("flip_uv_frame", re.compile(r"^lfs::field::FieldTerrainNode::flipAnimationFrame\(")),
    ("anim_update", re.compile(r"^lfs::field::FieldAnimator::updateFieldAnimations\(\)$")),
    ("anim_add", re.compile(r"^lfs::field::FieldAnimator::addAnimationData\(")),
    ("terrain_layer", re.compile(r"^lfs::field::Field::addNodeToTerrainLayer\(")),
)

NM_RE=re.compile(r"^\s*([0-9a-fA-F]+)\s+([A-Za-z])\s+(.+)$")
OBJDUMP_RE=re.compile(r"^\s*([0-9a-fA-F]+):\s+[0-9a-fA-F]{8}\s+([A-Za-z.][A-Za-z0-9.]*)\s*(.*)$")
LLVM_RE=re.compile(r"^\s*([0-9a-fA-F]+):\s+(?:[0-9a-fA-F]{2}\s+){4}([A-Za-z.][A-Za-z0-9.]*)\s*(.*)$")
KEEP_MNEMONIC=re.compile(
    r"^(?:b|bl|br|blr|cbz|cbnz|tbz|tbnz|ret|"
    r"add|adds|sub|subs|mul|madd|msub|sdiv|udiv|lsl|lsr|asr|and|orr|eor|"
    r"fadd|fsub|fmul|fdiv|fmadd|fmsub|fneg|fabs|fcmp|fcmpe|fcvt|fcvtzs|scvtf|ucvtf|"
    r"mov|movz|movk|fmov|adr|adrp|"
    r"ldr|ldur|ldp|str|stur|stp|"
    r"csel|csinc|cset|cmp|cmn|tst)$",
    re.I,
)


def download(url:str,out:Path)->dict[str,object]:
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"*/*"})
    total=0; digest=hashlib.sha256()
    with urllib.request.urlopen(req,timeout=120) as response, out.open("wb") as target:
        declared=response.headers.get("Content-Length")
        if declared and int(declared)>MAX_DOWNLOAD:
            raise ValueError("download too large")
        while True:
            chunk=response.read(1024*1024)
            if not chunk: break
            total+=len(chunk)
            if total>MAX_DOWNLOAD: raise ValueError("download exceeded limit")
            digest.update(chunk); target.write(chunk)
    return {"size":total,"sha256":digest.hexdigest()}


def find_libgame(xapk:Path)->tuple[str,bytes]:
    found=[]
    with ZipFile(xapk) as outer:
        for info in outer.infolist():
            if not info.filename.lower().endswith(".apk"): continue
            payload=outer.read(info)
            try:
                with ZipFile(BytesIO(payload)) as apk:
                    for member in apk.infolist():
                        if member.filename=="lib/arm64-v8a/libgame.so":
                            found.append((info.filename,apk.read(member)))
            except Exception:
                continue
    if not found: raise ValueError("arm64 libgame.so not found")
    found.sort(key=lambda x:len(x[1]),reverse=True)
    return found[0]


def run(args:list[str],timeout=120)->str:
    exe=shutil.which(args[0])
    if not exe: raise FileNotFoundError(args[0])
    p=subprocess.run([exe,*args[1:]],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=timeout,check=False)
    return p.stdout


def choose_objdump()->str:
    for candidate in ("llvm-objdump","aarch64-linux-gnu-objdump","objdump"):
        if shutil.which(candidate):
            return candidate
    raise ValueError("no objdump available")


def all_symbols(so:Path)->list[dict[str,object]]:
    text=run(["nm","-D","-C","--defined-only",str(so)])
    rows=[]
    for line in text.splitlines():
        m=NM_RE.match(line)
        if not m: continue
        typ=m.group(2)
        if typ.upper() not in {"T","W"}: continue
        rows.append({"address":int(m.group(1),16),"type":typ,"name":m.group(3)})
    rows.sort(key=lambda x:(int(x["address"]),str(x["name"])))
    return rows


def resolve_targets(symbols:list[dict[str,object]])->list[dict[str,object]]:
    selected=[]
    for label,pattern in TARGET_PATTERNS:
        matches=[s for s in symbols if pattern.search(str(s["name"]))]
        # Ignore non-virtual thunks unless nothing else exists.
        normal=[s for s in matches if not str(s["name"]).startswith("non-virtual thunk")]
        if normal: matches=normal
        for s in matches[:4]:
            selected.append({"label":label,**s})
    return selected


def function_end(symbols:list[dict[str,object]],start:int)->int:
    higher=sorted({int(s["address"]) for s in symbols if int(s["address"])>start})
    if not higher: return start+MAX_FUNCTION_BYTES
    return min(start+MAX_FUNCTION_BYTES,higher[0])


def disassemble(tool:str,so:Path,start:int,stop:int)->str:
    if tool=="llvm-objdump":
        return run([tool,"-d","--demangle",f"--start-address=0x{start:x}",f"--stop-address=0x{stop:x}",str(so)])
    return run([tool,"-d","-C",f"--start-address=0x{start:x}",f"--stop-address=0x{stop:x}",str(so)])


def parse_instructions(text:str)->list[dict[str,object]]:
    out=[]
    for line in text.splitlines():
        m=OBJDUMP_RE.match(line) or LLVM_RE.match(line)
        if not m: continue
        mnemonic=m.group(2).lower()
        if not KEEP_MNEMONIC.match(mnemonic): continue
        operands=m.group(3).strip()
        # Bound operand text; symbol names and immediates are useful, instruction bytes are omitted.
        if len(operands)>500: operands=operands[:500]
        out.append({"address":"0x"+m.group(1).lower(),"mnemonic":mnemonic,"operands":operands})
        if len(out)>=MAX_INSTRUCTIONS: break
    return out


def summarize_instructions(instructions:list[dict[str,object]])->dict[str,object]:
    counts={}
    immediates=[]
    calls=[]
    for row in instructions:
        mnemonic=str(row["mnemonic"])
        counts[mnemonic]=counts.get(mnemonic,0)+1
        operands=str(row["operands"])
        if mnemonic in {"bl","blr"}:
            calls.append({"address":row["address"],"mnemonic":mnemonic,"operands":operands})
        for token in re.findall(r"#(?:-?0x[0-9a-fA-F]+|-?\d+)",operands):
            if token not in immediates and len(immediates)<120:
                immediates.append(token)
    return {"mnemonic_counts":counts,"immediates":immediates,"calls":calls[:120]}


def inspect(url:str)->dict[str,object]:
    with tempfile.TemporaryDirectory() as raw:
        root=Path(raw); xapk=root/"logres.xapk"
        dl=download(url,xapk)
        apk_name,data=find_libgame(xapk)
        so=root/"libgame.so"; so.write_bytes(data)
        symbols=all_symbols(so)
        targets=resolve_targets(symbols)
        tool=choose_objdump()
        results=[]
        for target in targets:
            start=int(target["address"]); stop=function_end(symbols,start)
            text=disassemble(tool,so,start,stop)
            instructions=parse_instructions(text)
            results.append({
                "label":target["label"],
                "name":target["name"],
                "address":f"0x{start:x}",
                "bounded_stop":f"0x{stop:x}",
                "bounded_bytes":stop-start,
                "instruction_count":len(instructions),
                "summary":summarize_instructions(instructions),
                "instructions":instructions,
            })
        return {
            "provenance":"PUBLIC_CURRENT_JP_FIELD_FORMULA_INSTRUCTION_METADATA",
            "policy":(
                "Public current libgame instruction metadata for an explicit small allowlist only. "
                "Machine-code bytes and whole-library disassembly are omitted. Instruction sequences "
                "are reverse-engineering evidence; semantic formulas require coordinator review."
            ),
            "download":dl,
            "apk":apk_name,
            "libgame":{"size":len(data),"sha256":hashlib.sha256(data).hexdigest()},
            "disassembler":tool,
            "target_count":len(results),
            "targets":results,
        }


def self_test()->None:
    symbols=[
        {"address":0x1000,"type":"T","name":"lfs::field::FieldTerrain::tileContains(cocos2d::Vec2 const&) const"},
        {"address":0x1100,"type":"T","name":"lfs::field::FieldPlayer::getDepthOrder() const"},
        {"address":0x1200,"type":"T","name":"other()"},
    ]
    targets=resolve_targets(symbols)
    assert {t["label"] for t in targets}=={"tile_contains","player_depth"}
    sample="  1000: 1e202820 fadd s0, s1, s0\n  1004: 94000001 bl 2000 <helper()>\n  1008: d65f03c0 ret\n"
    parsed=parse_instructions(sample)
    assert [p["mnemonic"] for p in parsed]==["fadd","bl","ret"]
    assert summarize_instructions(parsed)["calls"][0]["operands"].endswith("<helper()>")
    print("Logres public field formula inspector self-test: PASS")


def main()->int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url")
    ap.add_argument("--output",type=Path)
    ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test:
        self_test(); return 0
    if not a.url:
        print("--url required",file=sys.stderr); return 2
    try: result=inspect(a.url)
    except Exception as exc:
        print(f"inspection failed: {type(exc).__name__}: {exc}",file=sys.stderr); return 1
    encoded=json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n"
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(encoded,encoding="utf-8")
    else:
        sys.stdout.write(encoded)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
