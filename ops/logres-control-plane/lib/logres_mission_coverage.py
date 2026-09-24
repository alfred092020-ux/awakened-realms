from __future__ import annotations
import json, sqlite3
from pathlib import Path

_CONTENT_OBJECTIVES=frozenset({"MAP_CONTENT","ACTOR_CONTENT","COMBAT_CONTENT","ITEM_CONTENT","QUEST_CONTENT"})
_MANIFEST_PATH=Path(__file__).resolve().parents[1]/"config"/"completion_manifest.json"


def ensure_schema(conn):
    conn.executescript("""
    create table if not exists mission_gap_scans(
      id integer primary key autoincrement,
      created_at text not null default (datetime('now')),
      payload_json text not null
    );
    """); conn.commit()


def _rows(conn,sql,args=()):
    return [dict(r) for r in conn.execute(sql,args)]


def _leaf_objectives(conn):
    return _rows(conn,"""select o.id,o.title,o.definition_of_done
      from mission_objectives o
      where not exists(select 1 from mission_objectives c where c.parent_id=o.id)
      order by o.sort_order,o.id""")


def _links(conn,obj):
    return _rows(conn,"select milestone_id,task_id,gate_type from mission_links where objective_id=? order by gate_type,milestone_id,task_id",(obj,))


def _task_refs(conn,links):
    out=[]
    for link in links:
        tid=link.get("task_id")
        if tid:
            row=conn.execute("select id,status,title,note from tasks where id=?",(tid,)).fetchone()
            if row: out.append({"type":"task","id":row["id"],"status":row["status"],"title":row["title"],"note":row["note"]})
        mid=link.get("milestone_id")
        if mid:
            row=conn.execute("select id,status,title,definition_of_done from milestones where id=?",(mid,)).fetchone()
            if row: out.append({"type":"milestone","id":row["id"],"status":row["status"],"title":row["title"],"definition_of_done":row["definition_of_done"]})
    return out


def _classify(refs):
    if not refs: return "UNCOVERED","IMPLEMENTATION_GAP"
    statuses={str(r["status"]) for r in refs}
    if statuses and all(s in {"DONE","COMPLETE","RESOLVED"} for s in statuses):
        return "COMPLETE","NONE"
    if statuses & {"ACTIVE","READY","IN_PROGRESS"}:
        return "IN_PROGRESS","RUNNABLE_OR_ACTIVE"
    if statuses and all(s in {"BLOCKED_EVIDENCE","WAITING_EXTERNAL"} for s in statuses):
        return "WAITING_EXTERNAL","EVIDENCE_CEILING"
    if statuses & {"BLOCKED_DEP","BLOCKED"}:
        return "BLOCKED","DEPENDENCY_BLOCKED"
    return "UNCOVERED","IMPLEMENTATION_GAP"


def load_completion_manifest(path=_MANIFEST_PATH):
    data=json.loads(Path(path).read_text())
    if data.get("schema")!="logres-project-completion-manifest-v1":
        raise ValueError("completion manifest schema must be logres-project-completion-manifest-v1")
    cats=data.get("categories")
    if not isinstance(cats,dict) or not cats:
        raise ValueError("completion manifest categories must be a non-empty object")
    normalized={}; objectives={}
    for cid,raw in cats.items():
        if not isinstance(raw,dict):
            raise ValueError(f"completion manifest category {cid} must be an object")
        objective_id=str(raw.get("objective_id") or "").strip()
        targets=raw.get("targets")
        if not objective_id or not isinstance(targets,list) or not targets:
            raise ValueError(f"completion manifest category {cid} must declare objective_id and non-empty targets")
        required_ids=[]; bounded_ids=[]; target_map={}
        for item in targets:
            if not isinstance(item,dict):
                raise ValueError(f"completion manifest target in {cid} must be an object")
            stable_id=str(item.get("stable_id") or "").strip()
            disposition=str(item.get("disposition") or "").strip()
            if not stable_id or stable_id in target_map:
                raise ValueError(f"completion manifest category {cid} has invalid or duplicate stable_id")
            if disposition=="required":
                if not str(item.get("provenance_class") or "").strip():
                    raise ValueError(f"completion manifest required target {stable_id} must declare provenance_class")
                required_ids.append(stable_id)
            elif disposition in {"ceiling","excluded"}:
                detail=str(item.get("evidence_ceiling") or item.get("exclusion_reason") or "").strip()
                if not detail:
                    raise ValueError(f"completion manifest bounded target {stable_id} must declare ceiling/exclusion detail")
                bounded_ids.append(stable_id)
            else:
                raise ValueError(f"completion manifest target {stable_id} has unsupported disposition {disposition!r}")
            target_map[stable_id]=item
        category={
          "category_id":cid,
          "objective_id":objective_id,
          "criterion_id":raw.get("criterion_id"),
          "title":raw.get("title") or cid,
          "targets":target_map,
          "required_ids":tuple(required_ids),
          "bounded_ids":tuple(bounded_ids),
        }
        normalized[cid]=category; objectives[objective_id]=category
    missing=sorted(_CONTENT_OBJECTIVES-set(objectives))
    if missing:
        raise ValueError(f"completion manifest missing content objectives: {', '.join(missing)}")
    return {
      "schema":data["schema"],
      "version":data.get("version"),
      "base_integration_sha":data.get("base_integration_sha"),
      "evidence_policy":data.get("evidence_policy"),
      "categories":normalized,
      "objectives":objectives,
    }


def _json_object(raw):
    if not isinstance(raw,str) or not raw.strip(): return None
    try:
        data=json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data,dict) else None


def _stable_ids(value):
    if not isinstance(value,list): return []
    out=[]; seen=set()
    for item in value:
        sid=str(item or "").strip()
        if sid and sid not in seen:
            seen.add(sid); out.append(sid)
    return out


def _coverage_bucket(payload,key):
    bucket=payload.get(key)
    if isinstance(bucket,dict): return bucket
    alias=payload.get("by_objective",{}).get(key)
    return alias if isinstance(alias,dict) else None


def _coverage_from_ref(ref,category):
    if ref.get("type")=="task": data=_json_object(ref.get("note"))
    else: data=_json_object(ref.get("definition_of_done"))
    if not data: return None
    payload=data.get("completion_coverage")
    if not isinstance(payload,dict): return None
    bucket=_coverage_bucket(payload,category["category_id"]) or _coverage_bucket(payload,category["objective_id"])
    if not isinstance(bucket,dict): return None
    return {
      "represented_ids":_stable_ids(bucket.get("represented_ids")),
      "ceiling_ids":_stable_ids(bucket.get("ceiling_ids")),
      "excluded_ids":_stable_ids(bucket.get("excluded_ids")),
    }


def _content_status(manifest,objective_id,refs,manifest_error=None):
    if manifest_error:
        return {"objective_id":objective_id,"error":manifest_error,"required_count":0,"represented_count":0,
                "ceiling_or_excluded_count":0,"missing_count":0,"undeclared_represented_count":0,
                "represented_ids":[],"ceiling_ids":[],"excluded_ids":[],"missing_ids":[],
                "undeclared_represented_ids":[],"complete":False}
    category=manifest["objectives"].get(objective_id)
    if not category:
        return {"objective_id":objective_id,"error":"content objective missing from completion manifest","required_count":0,
                "represented_count":0,"ceiling_or_excluded_count":0,"missing_count":0,
                "undeclared_represented_count":0,"represented_ids":[],"ceiling_ids":[],"excluded_ids":[],
                "missing_ids":[],"undeclared_represented_ids":[],"complete":False}
    represented=[]; ceiling=[]; excluded=[]
    for ref in refs:
        bucket=_coverage_from_ref(ref,category)
        if not bucket: continue
        for name,items in ((represented,bucket["represented_ids"]),(ceiling,bucket["ceiling_ids"]),(excluded,bucket["excluded_ids"])):
            for item in items:
                if item not in name: name.append(item)
    required_ids=set(category["required_ids"])
    bounded_ids=set(category["bounded_ids"])
    declared_ids=set(category["targets"])
    represented_ids=[item for item in represented if item in required_ids]
    ceiling_ids=[item for item in ceiling if item in bounded_ids]
    excluded_ids=[item for item in excluded if item in bounded_ids]
    missing_ids=sorted(required_ids-set(represented_ids))
    undeclared_represented_ids=sorted(set(represented)-declared_ids)
    undeclared_bounded_ids=sorted((set(ceiling)|set(excluded))-declared_ids)
    return {
      "category_id":category["category_id"],
      "objective_id":objective_id,
      "criterion_id":category.get("criterion_id"),
      "title":category["title"],
      "manifest_version":manifest.get("version"),
      "required_count":len(required_ids),
      "represented_count":len(represented_ids),
      "ceiling_or_excluded_count":len(bounded_ids),
      "missing_count":len(missing_ids),
      "undeclared_represented_count":len(undeclared_represented_ids)+len(undeclared_bounded_ids),
      "represented_ids":represented_ids,
      "ceiling_ids":ceiling_ids,
      "excluded_ids":excluded_ids,
      "missing_ids":missing_ids,
      "undeclared_represented_ids":undeclared_represented_ids+undeclared_bounded_ids,
      "complete":not missing_ids and not undeclared_represented_ids and not undeclared_bounded_ids,
    }


def scan(conn,persist=False,manifest_path=None):
    ensure_schema(conn)
    gaps=[]; counts={}; content_completion={}; manifest_error=None
    try:
        manifest=load_completion_manifest(manifest_path or _MANIFEST_PATH)
    except Exception as exc:
        manifest=None; manifest_error=str(exc)
    for obj in _leaf_objectives(conn):
        links=_links(conn,obj["id"]); refs=_task_refs(conn,links)
        state,kind=_classify(refs)
        completion=None
        if obj["id"] in _CONTENT_OBJECTIVES:
            completion=_content_status(manifest,obj["id"],refs,manifest_error)
            content_completion[completion.get("category_id") or obj["id"]]=completion
            if not completion["complete"]: kind="DECLARED_CONTENT_GAP"
        item={"objective_id":obj["id"],"title":obj["title"],"definition_of_done":obj["definition_of_done"],
              "state":state,"gap_kind":kind,"references":refs}
        if completion is not None: item["content_completion"]=completion
        counts[state]=counts.get(state,0)+1
        if state!="COMPLETE" or (completion is not None and not completion["complete"]): gaps.append(item)
    payload={"counts":counts,"gaps":gaps,"gap_count":len(gaps),"content_completion":content_completion}
    if manifest_error: payload["content_manifest_error"]=manifest_error
    if persist:
        cur=conn.execute("insert into mission_gap_scans(payload_json) values(?)",(json.dumps(payload,sort_keys=True),))
        conn.commit(); payload["scan_id"]=int(cur.lastrowid)
    return payload


def latest(conn):
    ensure_schema(conn)
    row=conn.execute("select id,created_at,payload_json from mission_gap_scans order by id desc limit 1").fetchone()
    if not row: return {"available":False}
    return {"available":True,"scan_id":row[0],"created_at":row[1],"payload":json.loads(row[2])}
