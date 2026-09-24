from __future__ import annotations
import hashlib,json,sqlite3,time
from datetime import datetime,timezone

FIELDS=("source_sha","lock_hash","config_hash","evidence_version","env_hash","mode")

def ensure_schema(conn):
    conn.executescript("""
    create table if not exists verification_cache(
      id integer primary key autoincrement,
      cache_key text not null unique,
      dimensions_json text not null,
      status text not null,
      provenance_json text not null default '{}',
      created_at text not null,
      created_epoch real not null
    );
    """);conn.commit()

def key(dimensions):
    missing=[f for f in FIELDS if not dimensions.get(f)]
    if missing: raise ValueError("missing cache dimensions: "+",".join(missing))
    if len(str(dimensions["source_sha"]))!=40: raise ValueError("exact source SHA required")
    canon={f:str(dimensions[f]) for f in FIELDS}
    raw=json.dumps(canon,sort_keys=True,separators=(",",":"))
    return hashlib.sha256(raw.encode()).hexdigest(),canon

def put_pass(conn,dimensions,provenance=None,created_at=None):
    ensure_schema(conn);k,canon=key(dimensions)
    stamp=created_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    epoch=datetime.fromisoformat(stamp.replace("Z","+00:00")).timestamp()
    conn.execute("""insert or ignore into verification_cache(
      cache_key,dimensions_json,status,provenance_json,created_at,created_epoch
      ) values(?,?,'PASS',?,?,?)""",(k,json.dumps(canon,sort_keys=True),json.dumps(provenance or {},sort_keys=True),stamp,epoch))
    conn.commit();return lookup(conn,dimensions)

def lookup(conn,dimensions,now_epoch=None):
    ensure_schema(conn);k,canon=key(dimensions)
    r=conn.execute("""select id,dimensions_json,status,provenance_json,created_at,created_epoch
      from verification_cache where cache_key=? and status='PASS'""",(k,)).fetchone()
    if not r:return {"hit":False,"cache_key":k}
    age=max(0.0,(time.time() if now_epoch is None else float(now_epoch))-float(r[5]))
    return {"hit":True,"id":r[0],"cache_key":k,"dimensions":json.loads(r[1]),"status":r[2],
            "provenance":json.loads(r[3]),"created_at":r[4],"age_seconds":round(age,3)}

def list_entries(conn,limit=50):
    ensure_schema(conn)
    out=[]
    for r in conn.execute("""select id,cache_key,dimensions_json,status,provenance_json,created_at,created_epoch
      from verification_cache order by id desc limit ?""",(limit,)):
        out.append({"id":r[0],"cache_key":r[1],"dimensions":json.loads(r[2]),"status":r[3],
                    "provenance":json.loads(r[4]),"created_at":r[5],"created_epoch":r[6]})
    return out
