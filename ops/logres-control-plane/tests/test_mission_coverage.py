import json,sqlite3,sys,unittest
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
 def add_leaf(self,c,obj="A",title="A"):
  c.execute("insert into mission_objectives values(?,?,?, ?,1)",(obj,None,title,"done"))
 def add_task(self,c,obj,task="T",status="DONE",note=""):
  c.execute("insert into tasks values(?,?,?,?)",(task,status,task,note))
  c.execute("insert into mission_links values(?,null,?,'required')",(obj,task))
 def coverage_note(self,category,represented=(),ceiling=(),excluded=()):
  return json.dumps({"completion_coverage":{category:{"represented_ids":list(represented),"ceiling_ids":list(ceiling),"excluded_ids":list(excluded)}}},sort_keys=True)
 def test_uncovered_is_implementation_gap(self):
  c=self.db(); self.add_leaf(c)
  r=scan(c); self.assertEqual("IMPLEMENTATION_GAP",r["gaps"][0]["gap_kind"])
 def test_evidence_ceiling_is_distinct(self):
  c=self.db(); self.add_leaf(c)
  self.add_task(c,"A",status="BLOCKED_EVIDENCE")
  r=scan(c); self.assertEqual("EVIDENCE_CEILING",r["gaps"][0]["gap_kind"])
 def test_complete_leaf_removed_from_gaps(self):
  c=self.db(); self.add_leaf(c)
  self.add_task(c,"A")
  r=scan(c); self.assertEqual(0,r["gap_count"]); self.assertEqual(1,r["counts"]["COMPLETE"])
 def test_done_content_task_without_declared_ids_fails_closed(self):
  c=self.db(); self.add_leaf(c,"MAP_CONTENT","Maps")
  self.add_task(c,"MAP_CONTENT")
  r=scan(c)
  self.assertEqual("DECLARED_CONTENT_GAP",r["gaps"][0]["gap_kind"])
  self.assertEqual(1,r["content_completion"]["maps_regions"]["missing_count"])
  self.assertEqual(0,r["content_completion"]["maps_regions"]["represented_count"])
 def test_placeholder_ids_do_not_satisfy_manifest_targets(self):
  c=self.db(); self.add_leaf(c,"MAP_CONTENT","Maps")
  self.add_task(c,"MAP_CONTENT",note=self.coverage_note("maps_regions",represented=["placeholder-map"]))
  r=scan(c)
  summary=r["content_completion"]["maps_regions"]
  self.assertEqual(["millennium-tree-field"],summary["missing_ids"])
  self.assertEqual(["placeholder-map"],summary["undeclared_represented_ids"])
  self.assertEqual("DECLARED_CONTENT_GAP",r["gaps"][0]["gap_kind"])
 def test_content_category_reports_required_represented_and_bounded_counts(self):
  c=self.db(); self.add_leaf(c,"MAP_CONTENT","Maps")
  self.add_task(c,"MAP_CONTENT",note=self.coverage_note("maps_regions",represented=["millennium-tree-field"],ceiling=["millennium-tree-internal-map-id"]))
  r=scan(c)
  summary=r["content_completion"]["maps_regions"]
  self.assertEqual(1,summary["required_count"])
  self.assertEqual(1,summary["represented_count"])
  self.assertEqual(1,summary["ceiling_or_excluded_count"])
  self.assertEqual(0,summary["missing_count"])
  self.assertEqual(0,r["gap_count"])
if __name__=="__main__":unittest.main()
