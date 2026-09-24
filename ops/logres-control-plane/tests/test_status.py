import sqlite3,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lib"))
from logres_status import build_status,render_text
class StatusTests(unittest.TestCase):
 def db(self):
  c=sqlite3.connect(":memory:");c.row_factory=sqlite3.Row
  c.executescript("""create table tasks(id text,title text,status text,note text,updated_at text);
  create table brain_task_leases(task_id text,chat_id text,branch text,progress integer,lease_until_epoch real,renewed_at text);
  create table integration_queue(task_id text,sha text,branch text,status text,updated_at text);
  create table regressions(id integer,status text);
  create table verification(ref text,sha text,mode text,status text,duration_sec real,ran_at text,details text);""")
  return c
 def test_summary_uses_persisted_state(self):
  c=self.db();c.execute("insert into tasks values('T','T','BLOCKED_EVIDENCE','need archive','now')");c.execute("insert into brain_task_leases values('A','w','b',20,99,'now')")
  s=build_status(c);self.assertEqual(1,s["summary"]["active_workers"]);self.assertEqual(1,s["summary"]["evidence_ceilings"]);self.assertIn("mission",s["unavailable"])
 def test_text_is_concise(self):
  s=build_status(self.db());t=render_text(s);self.assertIn("Mission:",t);self.assertIn("Active workers:",t)
if __name__=="__main__":unittest.main()
