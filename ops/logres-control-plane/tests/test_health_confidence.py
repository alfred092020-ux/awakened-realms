import sqlite3,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lib"))
from logres_health_confidence import decayed,record,subsystem
class HealthConfidenceTests(unittest.TestCase):
 def setUp(self):self.c=sqlite3.connect(":memory:");self.c.row_factory=sqlite3.Row
 def test_confidence_decays(self):self.assertAlmostEqual(.5,decayed(1,100,100),places=6)
 def test_missing_is_unknown(self):self.assertEqual("UNKNOWN",subsystem(self.c,"x",now_epoch=100)["status"])
 def test_fresh_fail_overrides_pass(self):
  record(self.c,"db","old-pass","PASS",1,observed_epoch=0);record(self.c,"db","fresh-fail","FAIL",1,observed_epoch=1000)
  r=subsystem(self.c,"db",now_epoch=1000,half_life_seconds=100);self.assertEqual("FAIL",r["status"])
 def test_stale_pass_does_not_stay_green(self):
  record(self.c,"db","probe","PASS",1,observed_epoch=0)
  r=subsystem(self.c,"db",now_epoch=1000,half_life_seconds=100);self.assertEqual("UNKNOWN",r["status"]);self.assertEqual(0.0,r["confidence"])
if __name__=="__main__":unittest.main()
