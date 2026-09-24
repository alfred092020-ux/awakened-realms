import sqlite3,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lib"))
from logres_mission_contract_proposals import compile_proposals
class ProposalTests(unittest.TestCase):
 def db(self):
  c=sqlite3.connect(":memory:");c.row_factory=sqlite3.Row
  c.executescript("""create table mission_objectives(id text primary key,parent_id text,title text,definition_of_done text,sort_order integer);
  create table mission_links(objective_id text,milestone_id text,task_id text,gate_type text);
  create table tasks(id text primary key,status text,title text,note text);
  create table milestones(id text primary key,status text,title text,definition_of_done text);""");return c
 def test_uncovered_needs_explicit_template(self):
  c=self.db();c.execute("insert into mission_objectives values('A',null,'A','done',1)")
  p=compile_proposals(c)["proposals"][0];self.assertEqual("NEEDS_EXPLICIT_SCOPE_ACCEPTANCE",p["template_status"]);self.assertIsNone(p["task_template"])
 def test_explicit_complete_template_is_emitted(self):
  c=self.db();c.execute("insert into mission_objectives values('A',null,'A','done',1)")
  t={"A":{"title":"Build A","work_type":"implementation","priority":1,"scopes":["src/a"],"acceptance":["A passes"]}}
  p=compile_proposals(c,t)["proposals"][0];self.assertEqual("READY",p["template_status"]);self.assertEqual(["src/a"],p["task_template"]["scopes"])
 def test_incomplete_template_is_not_emitted(self):
  c=self.db();c.execute("insert into mission_objectives values('A',null,'A','done',1)")
  p=compile_proposals(c,{"A":{"title":"x"}})["proposals"][0];self.assertIsNone(p["task_template"])
 def test_evidence_ceiling_forbids_implementation_template(self):
  c=self.db();c.execute("insert into mission_objectives values('A',null,'A','done',1)")
  c.execute("insert into tasks values('E','BLOCKED_EVIDENCE','E','archive needed')");c.execute("insert into mission_links values('A',null,'E','required')")
  t={"A":{"title":"Build A","work_type":"implementation","priority":1,"scopes":["src/a"],"acceptance":["A passes"]}}
  p=compile_proposals(c,t)["proposals"][0];self.assertEqual("FORBIDDEN_EVIDENCE_CEILING",p["template_status"]);self.assertIsNone(p["task_template"]);self.assertEqual("evidence_state",p["suggested_check"]["check_type"])
if __name__=="__main__":unittest.main()
