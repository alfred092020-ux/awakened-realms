from __future__ import annotations
import json,sqlite3
from logres_executive import shadow_decide

def replay(conn:sqlite3.Connection,cases:list[dict]):
 results=[]
 for case in cases:
  before=conn.total_changes
  d=shadow_decide(conn,case['objective_id'],case['world'],case.get('gaps',[]))
  results.append({'case_id':case['case_id'],'decision':d,'expected_kind':case.get('expected_kind'),'matched':d['action']['kind']==case.get('expected_kind') if case.get('expected_kind') else None})
  # Only the advisory decision ledger may change in shadow replay.
  changed=conn.total_changes-before
  if changed!=1: raise RuntimeError(f'shadow replay unexpected mutations: {changed}')
 return results
