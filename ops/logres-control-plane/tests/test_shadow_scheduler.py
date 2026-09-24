import sqlite3,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lib"))
from logres_shadow_scheduler import compare,score_candidates
class ShadowTests(unittest.TestCase):
 def db(self):
  c=sqlite3.connect(":memory:");c.row_factory=sqlite3.Row
  c.executescript("""create table tasks(id text primary key,priority integer,status text);
  create table task_metadata(task_id text primary key,work_type text,expected_minutes integer,concurrency_key text,evidence_policy text);
  create table optimizer_observations(id integer primary key,work_type text,outcome text,estimated_cost_usd real);""");return c
 def add(self,c,i,p,m):c.execute("insert into tasks values(?,?,?)",(i,p,'READY'));c.execute("insert into task_metadata values(?,?,?,?,?)",(i,'implementation',m,i,''))
 def test_short_high_value_ranks_first(self):
  c=self.db();self.add(c,'A',1,20);self.add(c,'B',4,120);r=score_candidates(c);self.assertEqual('A',r[0]['task_id'])
 def test_shadow_never_mutates_tasks(self):
  c=self.db();self.add(c,'A',1,20);before=c.execute("select * from tasks").fetchall();compare(c,['A'],True);after=c.execute("select * from tasks").fetchall();self.assertEqual(before,after)
 def test_conflict_penalty(self):
  c=self.db();self.add(c,'A',1,20);c.execute("update task_metadata set concurrency_key='x' where task_id='A'");c.execute("insert into tasks values('LIVE',1,'ACTIVE')");c.execute("insert into task_metadata values('LIVE','implementation',20,'x','')");self.assertEqual(1.0,score_candidates(c)[0]['conflict_risk'])
if __name__=="__main__":unittest.main()
