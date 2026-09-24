from __future__ import annotations
import hashlib,json,re,sqlite3

STOP={"the","a","an","and","to","of","for","with","that","this","from","into","on","in","by","or"}

def norm_text(value):
    words=re.findall(r"[a-z0-9_./:-]+",str(value).lower())
    return " ".join(w for w in words if w not in STOP)

def _list(conn,sql,args=()):
    return [str(r[0]) for r in conn.execute(sql,args)]

def canonical(conn,task_id):
    t=conn.execute("""select t.id,t.lane,t.title,t.note,
      coalesce(m.work_type,''),coalesce(m.evidence_policy,'')
      from tasks t left join task_metadata m on m.task_id=t.id where t.id=?""",(task_id,)).fetchone()
    if not t: raise ValueError("unknown task")
    acceptance=sorted(norm_text(x) for x in _list(conn,"select criterion from task_acceptance where task_id=?",(task_id,)))
    scopes=sorted(norm_text(x) for x in _list(conn,"select path_prefix from task_scopes where task_id=?",(task_id,)))
    deps=sorted(norm_text(x) for x in _list(conn,"select depends_on from task_dependencies where task_id=?",(task_id,)))
    evidence=norm_text(t[5])
    failure=""
    note=norm_text(t[3] or "")
    m=re.search(r"(?:error|failure|regression|conflict)[: ]+(.+)",note)
    if m: failure=norm_text(m.group(1))
    semantic={"lane":norm_text(t[1]),"work_type":norm_text(t[4]),"title":norm_text(t[2]),
              "acceptance":acceptance,"scopes":scopes,"dependencies":deps,
              "failure_signature":failure,"evidence_predicate":evidence}
    exact={"lane":str(t[1] or ""),"work_type":str(t[4] or ""),"title":str(t[2] or ""),
           "acceptance":sorted(_list(conn,"select criterion from task_acceptance where task_id=?",(task_id,))),
           "scopes":sorted(_list(conn,"select path_prefix from task_scopes where task_id=?",(task_id,))),
           "dependencies":sorted(_list(conn,"select depends_on from task_dependencies where task_id=?",(task_id,))),
           "note":str(t[3] or ""),"evidence_policy":str(t[5] or "")}
    def h(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return {"task_id":task_id,"exact_sha":h(exact),"semantic_sha":h(semantic),"semantic":semantic}

def duplicates(conn,statuses=None):
    q="select id from tasks"
    args=[]
    if statuses:
        q+=" where status in (%s)"%(",".join("?" for _ in statuses));args=list(statuses)
    fps=[canonical(conn,r[0]) for r in conn.execute(q,args)]
    groups={}
    for f in fps: groups.setdefault(f["semantic_sha"],[]).append(f)
    return [{"semantic_sha":sha,"tasks":[x["task_id"] for x in items],
             "exact_match":len({x["exact_sha"] for x in items})==1}
            for sha,items in sorted(groups.items()) if len(items)>1]
