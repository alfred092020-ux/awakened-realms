import sqlite3,unittest
from logres_executive import *
class T(unittest.TestCase):
 def setUp(self): self.c=sqlite3.connect(':memory:')
 def test_shadow_guardrails(self):
  d=shadow_decide(self.c,'o',{'facts':[],'contradictions':[]},[{'gap':'x'}]); self.assertEqual(d['authority'],AUTHORITY); self.assertFalse(any(d['guardrails'].values()))
 def test_conflict_deep_reconcile(self):
  d=shadow_decide(self.c,'o',{'facts':[],'contradictions':[{'x':1}]},[]); self.assertEqual((d['reasoning_depth'],d['action']['kind']),('DEEP','RECONCILE'))
 def test_outcome_not_lesson(self):
  d=shadow_decide(self.c,'o',{'facts':[],'contradictions':[]},[]); record_outcome(self.c,d['decision_id'],{'worked':False}); self.assertEqual(self.c.execute('select status from executive_decisions').fetchone()[0],'OBSERVED')
