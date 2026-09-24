import sqlite3,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lib"))
from logres_zero_human import analyze
class ZeroHumanTests(unittest.TestCase):
 def db(self):
  c=sqlite3.connect(":memory:");c.row_factory=sqlite3.Row
  c.executescript("""create table tasks(id text,status text);create table integration_queue(task_id text,status text);
  create table regressions(id integer,status text);create table copilot_jobs(id integer,task_id text,state text);""");return c
 def test_ready_work_can_continue(self):
  c=self.db();c.execute("insert into tasks values('T','READY')");self.assertTrue(analyze(c)["can_continue_without_human"])
 def test_evidence_only_stop_is_explicit(self):
  c=self.db();c.execute("insert into tasks values('T','BLOCKED_EVIDENCE')");r=analyze(c);self.assertFalse(r["can_continue_without_human"]);self.assertEqual("EXTERNAL_EVIDENCE",r["stop_reasons"][0]["code"])
 def test_state_inconsistency_blocks_zero_human(self):
  c=self.db();c.execute("insert into tasks values('T','DONE')");c.execute("insert into copilot_jobs values(1,'T','ACTIVE')");r=analyze(c);self.assertFalse(r["can_continue_without_human"]);self.assertIn("STATE_INCONSISTENCY",{x["code"] for x in r["stop_reasons"]})
 def test_persist_is_analysis_only(self):
  c=self.db();c.execute("insert into tasks values('T','READY')");before=c.execute("select * from tasks").fetchall();r=analyze(c,True);self.assertEqual(before,c.execute("select * from tasks").fetchall());self.assertIn("run_id",r)
if __name__=="__main__":unittest.main()
