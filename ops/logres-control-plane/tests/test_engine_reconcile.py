import sqlite3,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lib"))
from logres_engine_reconcile import apply,plan
class ReconcileTests(unittest.TestCase):
 def db(self):
  c=sqlite3.connect(":memory:");c.row_factory=sqlite3.Row
  c.executescript("""create table tasks(id text primary key,status text);
  create table copilot_jobs(id integer primary key,task_id text,state text,branch text,candidate_sha text,updated_at text);
  create table route_jobs(id integer primary key,task_id text,state text,external_ref text,last_error text,updated_at text);
  create table swarm_jobs(id integer primary key,task_id text,state text,pid integer,artifact_path text,last_error text,updated_at text,finished_at text);
  create table brain_task_leases(task_id text primary key,chat_id text,branch text,lease_until_epoch real);""")
  return c
 def test_terminal_task_supersedes_engine_but_not_task(self):
  c=self.db();c.execute("insert into tasks values('T','DONE')");c.execute("insert into copilot_jobs values(1,'T','ACTIVE','b','sha','now')")
  a=apply(c);self.assertEqual("SUPERSEDED",c.execute("select state from copilot_jobs").fetchone()[0]);self.assertEqual("DONE",c.execute("select status from tasks").fetchone()[0]);self.assertEqual(1,len(a))
 def test_terminal_owner_supersedes_live_copilot_states(self):
  statuses=("DONE","SUPERSEDED","CANCELLED","BLOCKED_EVIDENCE")
  states=("ASSIGNING","ACTIVE","PR_READY","VERIFYING","QUEUED")
  for i,status in enumerate(statuses,1):
   for j,state in enumerate(states,1):
    c=self.db();c.execute("insert into tasks values('T',?)",(status,));c.execute("insert into copilot_jobs values(1,'T',?,'b','sha','now')",(state,))
    a=apply(c)
    self.assertEqual("SUPERSEDED",c.execute("select state from copilot_jobs where id=1").fetchone()[0])
    self.assertEqual(status,c.execute("select status from tasks where id='T'").fetchone()[0])
    self.assertEqual(1,len([x for x in a if x["engine"]=="copilot"]),f"status={status} state={state} i={i} j={j}")
 def test_terminal_owner_supersedes_live_route_states(self):
  statuses=("DONE","SUPERSEDED","CANCELLED","BLOCKED_EVIDENCE")
  states=("ASSIGNING","ROUTED","ACTIVE","PR_READY","VERIFYING","QUEUED")
  for i,status in enumerate(statuses,1):
   for j,state in enumerate(states,1):
    c=self.db();c.execute("insert into tasks values('T',?)",(status,));c.execute("insert into route_jobs values(1,'T',?,null,null,'now')",(state,))
    a=apply(c)
    self.assertEqual("SUPERSEDED",c.execute("select state from route_jobs where id=1").fetchone()[0])
    self.assertEqual(status,c.execute("select status from tasks where id='T'").fetchone()[0])
    self.assertEqual(1,len([x for x in a if x["engine"]=="route"]),f"status={status} state={state} i={i} j={j}")
 def test_active_task_is_untouched(self):
  c=self.db();c.execute("insert into tasks values('T','ACTIVE')");c.execute("insert into route_jobs values(1,'T','ACTIVE',null,null,'now')");c.execute("insert into copilot_jobs values(1,'T','PR_READY','b','sha','now')")
  self.assertEqual([],plan(c))
 def test_terminal_lease_released(self):
  c=self.db();c.execute("insert into tasks values('T','SUPERSEDED')");c.execute("insert into brain_task_leases values('T','w','b',999)")
  apply(c);self.assertEqual(0,c.execute("select count(*) from brain_task_leases").fetchone()[0])
if __name__=="__main__":unittest.main()
