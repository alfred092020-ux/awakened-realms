import sqlite3,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lib"))
from logres_bottleneck import analyze
class BottleneckTests(unittest.TestCase):
 def db(self):
  c=sqlite3.connect(":memory:");c.row_factory=sqlite3.Row
  c.executescript("""create table tasks(id text,status text);create table integration_queue(task_id text,status text);
  create table regressions(id integer,status text);create table verification(id integer,status text,ran_at text);
  create table brain_events(id integer,event_type text,ts_epoch real);""");return c
 def test_no_runnable_work_is_top_bottleneck(self):
  c=self.db();c.executemany("insert into tasks values(?,?)",[('A','BLOCKED_EVIDENCE'),('B','BLOCKED_DEP')])
  r=analyze(c,now_epoch=1000);self.assertEqual("RUNNABLE_SHORTAGE",r["ranked"][0]["kind"])
 def test_regressions_surface(self):
  c=self.db();c.execute("insert into tasks values('A','READY')");c.executemany("insert into regressions values(?,?)",[(1,'OPEN'),(2,'OPEN')])
  kinds={x["kind"] for x in analyze(c)["ranked"]};self.assertIn("REGRESSION",kinds)
 def test_persist_does_not_change_tasks(self):
  c=self.db();c.execute("insert into tasks values('A','READY')");before=c.execute("select * from tasks").fetchall();r=analyze(c,persist=True);after=c.execute("select * from tasks").fetchall();self.assertEqual(before,after);self.assertIn("observation_id",r)
if __name__=="__main__":unittest.main()
