from __future__ import annotations
import sqlite3

def _table(c,n): return c.execute("select 1 from sqlite_master where type='table' and name=?",(n,)).fetchone() is not None
def fact(subject,predicate,value,belief='KNOWN',confidence=1.0,provenance=()): return {'subject':subject,'predicate':predicate,'value':value,'belief':belief,'confidence':confidence,'provenance':list(provenance)}
def derive_world_model(c:sqlite3.Connection,*,git_head=None,origin_head=None,runtime_sha=None):
 facts=[]; conflicts=[]
 if git_head:
  b='KNOWN' if not origin_head or git_head==origin_head else 'CONFLICTED'; facts.append(fact('project','canonical_sha',git_head,b,1.0,('git:canonical',)))
  if origin_head and git_head!=origin_head: conflicts.append({'code':'GIT_ORIGIN_DIVERGED','expected':origin_head,'observed':git_head})
 if runtime_sha and git_head:
  b='KNOWN' if runtime_sha==git_head else 'CONFLICTED'; facts.append(fact('runtime','deployed_sha',runtime_sha,b,1.0,('runtime:observed','git:canonical')))
  if runtime_sha!=git_head: conflicts.append({'code':'RUNTIME_SHA_MISMATCH','expected':git_head,'observed':runtime_sha})
 if _table(c,'tasks'): facts.append(fact('brain','task_counts',{r[0]:r[1] for r in c.execute('select status,count(*) from tasks group by status')},provenance=('brain:tasks',)))
 if _table(c,'integration_queue'):
  n=c.execute("select count(*) from integration_queue where status in ('READY_FOR_PREFLIGHT','VERIFIED','PREFLIGHT_VERIFIED','PENDING','QUEUED')").fetchone()[0]; facts.append(fact('integration','actionable_candidates',n,provenance=('brain:integration_queue',)))
 return {'facts':facts,'contradictions':conflicts,'healthy':not conflicts}
