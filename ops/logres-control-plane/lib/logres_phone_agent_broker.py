from __future__ import annotations
import hashlib,hmac,json,sqlite3,time,uuid
from pathlib import Path
SCHEMA='''CREATE TABLE IF NOT EXISTS phone_agent_jobs(id TEXT PRIMARY KEY,phone_id TEXT NOT NULL,operation TEXT NOT NULL,args_json TEXT NOT NULL,state TEXT NOT NULL,created_at INTEGER NOT NULL,claimed_at INTEGER,result_json TEXT);'''
class Broker:
 def __init__(self,path): self.path=Path(path); self._init()
 def _db(self): c=sqlite3.connect(self.path); c.row_factory=sqlite3.Row; return c
 def _init(self):
  with self._db() as c: c.execute(SCHEMA)
 def enqueue(self,phone_id,operation,args=None):
  if operation not in {'status','shell_read','screenshot','logcat'}: raise ValueError('operation not allowlisted')
  jid=str(uuid.uuid4());
  with self._db() as c: c.execute('INSERT INTO phone_agent_jobs VALUES(?,?,?,?,?,?,NULL,NULL)',(jid,phone_id,operation,json.dumps(args or {}),'QUEUED',int(time.time())))
  return jid
 def poll(self,phone_id):
  with self._db() as c:
   r=c.execute("SELECT * FROM phone_agent_jobs WHERE phone_id=? AND state='QUEUED' ORDER BY created_at,id LIMIT 1",(phone_id,)).fetchone()
   if not r:return None
   c.execute("UPDATE phone_agent_jobs SET state='CLAIMED',claimed_at=? WHERE id=? AND state='QUEUED'",(int(time.time()),r['id']))
   return {'id':r['id'],'operation':r['operation'],'args':json.loads(r['args_json'])}
 def complete(self,phone_id,jid,result):
  with self._db() as c:
   n=c.execute("UPDATE phone_agent_jobs SET state='DONE',result_json=? WHERE id=? AND phone_id=? AND state='CLAIMED'",(json.dumps(result),jid,phone_id)).rowcount
  return n==1
 def get(self,jid):
  with self._db() as c:
   r=c.execute('SELECT * FROM phone_agent_jobs WHERE id=?',(jid,)).fetchone(); return dict(r) if r else None
def valid_signature(secret,body,sig): return hmac.compare_digest(hmac.new(secret.encode(),body,hashlib.sha256).hexdigest(),sig or '')
