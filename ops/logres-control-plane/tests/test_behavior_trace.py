import sqlite3,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lib"))
from logres_behavior_trace import compare,record
S="b"*40
class BehaviorTraceTests(unittest.TestCase):
 def setUp(self): self.c=sqlite3.connect(":memory:"); self.c.row_factory=sqlite3.Row
 def test_identical_trace_passes(self):
  t={"events":["field","encounter","battle"],"final_state":{"mode":"battle"}}
  r=record(self.c,sha=S,checkpoint="entry",expected=t,observed=t); self.assertEqual("PASS",r["verdict"])
 def test_event_divergence_fails(self):
  e={"events":["a","b"],"final_state":1}; o={"events":["a","x"],"final_state":1}
  r=record(self.c,sha=S,checkpoint="x",expected=e,observed=o); self.assertEqual("FAIL",r["verdict"]); self.assertEqual(1,len(r["divergence"]["event_mismatches"]))
 def test_missing_expected_trace_fails_closed(self):
  with self.assertRaises(ValueError): record(self.c,sha=S,checkpoint="x",expected={},observed={"events":[]})
if __name__=="__main__":unittest.main()
