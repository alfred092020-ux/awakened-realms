import sqlite3,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lib"))
from logres_lifecycle_guard import audit,validate_transition
class LifecycleTests(unittest.TestCase):
 def test_legal_and_illegal_transitions(self):
  self.assertTrue(validate_transition("task","READY","ACTIVE")["valid"])
  self.assertFalse(validate_transition("task","DONE","ACTIVE")["valid"])
 def test_unknown_state_fails_closed(self):
  self.assertFalse(validate_transition("task","READY","MAGIC")["valid"])
 def test_history_audit_names_violation(self):
  c=sqlite3.connect(":memory:");c.row_factory=sqlite3.Row
  c.executescript("""create table tasks(id text,status text);create table task_state_history(id integer primary key,task_id text,status text,ts text);
  insert into tasks values('T','ACTIVE');insert into task_state_history values(1,'T','DONE','a');insert into task_state_history values(2,'T','ACTIVE','b');""")
  r=audit(c);self.assertFalse(r["valid"]);self.assertEqual("T",r["violations"][0]["entity_id"])
 def test_deferred_busy_is_known_terminal_preflight_state(self):
  self.assertTrue(validate_transition("preflight","RUNNING","DEFERRED_BUSY")["valid"])
  self.assertFalse(validate_transition("preflight","DEFERRED_BUSY","APPLIED")["valid"])
  self.assertEqual("ILLEGAL_TRANSITION",validate_transition("preflight","DEFERRED_BUSY","APPLIED")["reason"])
 def test_deferred_busy_current_state_audits_cleanly(self):
  c=sqlite3.connect(":memory:");c.row_factory=sqlite3.Row
  c.execute("create table integration_preflights(id integer,status text)")
  c.execute("insert into integration_preflights values(1,'DEFERRED_BUSY')")
  r=audit(c);self.assertTrue(r["valid"]);self.assertEqual([],r["violations"])
 def test_current_unknown_state_surfaces(self):
  c=sqlite3.connect(":memory:");c.row_factory=sqlite3.Row;c.execute("create table tasks(id text,status text)");c.execute("insert into tasks values('T','ALIEN')")
  r=audit(c);self.assertEqual("UNKNOWN_CURRENT_STATE",r["violations"][0]["reason"])
if __name__=="__main__":unittest.main()
