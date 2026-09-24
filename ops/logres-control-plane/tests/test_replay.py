import sqlite3,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lib"))
from logres_replay import capture,replay_at
class ReplayTests(unittest.TestCase):
 def db(self):
  c=sqlite3.connect(":memory:"); c.row_factory=sqlite3.Row
  c.executescript("""create table tasks(id text primary key,priority integer,lane text,title text,status text,branch text,owner text,note text,updated_at text);
  create table brain_events(id integer primary key); create table task_state_history(id integer primary key);
  create table verification(ref text,sha text,mode text,status text,duration_sec real,ran_at text,details text);
  create table integration_queue(task_id text,sha text,branch text,status text,verification_mode text,queued_at text,updated_at text,ready_at text,integrated_at text);
  create table brain_task_leases(task_id text,chat_id text,branch text,lease_until_epoch real,acquired_at text,renewed_at text,progress integer,note text);""")
  return c
 def test_replay_uses_nearest_snapshot(self):
  c=self.db(); c.execute("insert into tasks values('T',1,'x','T','READY',null,null,'','now')")
  capture(c,"a"*40,ts="2026-09-24T10:00:00+00:00",ts_epoch=100)
  c.execute("update tasks set status='DONE' where id='T'")
  capture(c,"b"*40,ts="2026-09-24T11:00:00+00:00",ts_epoch=200)
  r=replay_at(c,150); self.assertTrue(r["available"]); self.assertEqual("READY",r["payload"]["tasks"][0]["status"])
 def test_before_first_snapshot_fails_closed(self):
  c=self.db(); capture(c,"a"*40,ts_epoch=100,ts="2026-09-24T10:00:00+00:00")
  self.assertFalse(replay_at(c,99)["available"])
 def test_missing_optional_tables_are_explicit(self):
  c=self.db(); s=capture(c,"a"*40,ts_epoch=100,ts="2026-09-24T10:00:00+00:00"); r=replay_at(c,100)
  self.assertIn("mission",r["payload"]["unavailable_historical_fields"])
if __name__=="__main__":unittest.main()
