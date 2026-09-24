import sqlite3,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lib"))
from logres_visual_truth import latest,record,regressions
S="a"*40
class VisualTruthTests(unittest.TestCase):
 def setUp(self): self.c=sqlite3.connect(":memory:"); self.c.row_factory=sqlite3.Row
 def test_pass_requires_reference_and_metrics(self):
  with self.assertRaises(ValueError): record(self.c,sha=S,checkpoint="title",observed_artifact="o.png",verdict="PASS")
 def test_latest_is_append_only(self):
  record(self.c,sha=S,checkpoint="title",observed_artifact="o1",verdict="REVIEW")
  record(self.c,sha=S,checkpoint="title",observed_artifact="o2",verdict="FAIL")
  self.assertEqual("o2",latest(self.c,"title")["observed_artifact"])
 def test_regression_requires_prior_pass_then_fail(self):
  record(self.c,sha=S,checkpoint="title",observed_artifact="o1",verdict="PASS",reference_artifact="r",metrics={"ssim":1})
  record(self.c,sha=S,checkpoint="title",observed_artifact="o2",verdict="FAIL",reference_artifact="r",metrics={"ssim":.5})
  self.assertEqual(1,len(regressions(self.c)))
if __name__=="__main__":unittest.main()
