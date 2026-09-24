import sqlite3,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lib"))
from logres_architecture_pressure import evaluate,persist
class PressureTests(unittest.TestCase):
 def test_low_system_is_low(self):
  r=evaluate({"worker_utilization":.75,"decision_records":10,"significant_events":50})
  self.assertEqual("LOW",r["level"])
 def test_workspace_entropy_surfaces_recommendation(self):
  r=evaluate({"worktrees":160,"local_branches":200,"remote_branches":300,"worker_utilization":.75,"decision_records":10,"significant_events":50})
  self.assertIn("WORKSPACE_LIFECYCLE",{x["kind"] for x in r["recommendations"]})
 def test_blocked_pressure_is_separate_dimension(self):
  r=evaluate({"incomplete_tasks":10,"blocked_evidence":6,"blocked_dep":2,"worker_utilization":.75,"decision_records":10,"significant_events":50})
  self.assertGreaterEqual(r["dimensions"]["blocked_pressure"],.8)
 def test_persist_is_append_only(self):
  c=sqlite3.connect(":memory:");payload=evaluate({})
  a=persist(c,payload);b=persist(c,payload);self.assertEqual((1,2),(a,b));self.assertEqual(2,c.execute("select count(*) from architecture_pressure_observations").fetchone()[0])
if __name__=="__main__":unittest.main()
