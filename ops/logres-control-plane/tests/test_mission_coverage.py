import sqlite3,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lib"))
from logres_mission_coverage import scan
class CoverageTests(unittest.TestCase):
 def db(self):
  c=sqlite3.connect(":memory:"); c.row_factory=sqlite3.Row
  c.executescript("""create table mission_objectives(id text primary key,parent_id text,title text,definition_of_done text,sort_order integer);
  create table mission_links(objective_id text,milestone_id text,task_id text,gate_type text);
  create table tasks(id text primary key,status text,title text,note text);
  create table milestones(id text primary key,status text,title text,definition_of_done text);""")
  return c
 def test_uncovered_is_implementation_gap(self):
  c=self.db(); c.execute("insert into mission_objectives values('A',null,'A','done',1)")
  r=scan(c); self.assertEqual("IMPLEMENTATION_GAP",r["gaps"][0]["gap_kind"])
 def test_evidence_ceiling_is_distinct(self):
  c=self.db(); c.execute("insert into mission_objectives values('A',null,'A','done',1)")
  c.execute("insert into tasks values('T','BLOCKED_EVIDENCE','T','need archive')")
  c.execute("insert into mission_links values('A',null,'T','required')")
  r=scan(c); self.assertEqual("EVIDENCE_CEILING",r["gaps"][0]["gap_kind"])
 def test_complete_leaf_removed_from_gaps(self):
  c=self.db(); c.execute("insert into mission_objectives values('A',null,'A','done',1)")
  c.execute("insert into tasks values('T','DONE','T','')")
  c.execute("insert into mission_links values('A',null,'T','required')")
  r=scan(c); self.assertEqual(0,r["gap_count"]); self.assertEqual(1,r["counts"]["COMPLETE"])
if __name__=="__main__":unittest.main()
