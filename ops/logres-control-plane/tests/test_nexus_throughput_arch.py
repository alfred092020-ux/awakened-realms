import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'lib'))
from nexus_throughput_arch import *
class T(unittest.TestCase):
 def test_risk_aware(self):
  self.assertIn('e2e',risk_plan(['ops/logres-control-plane/bin/x']).lanes)
  self.assertNotIn('e2e',risk_plan(['src/ui/Button.tsx']).lanes)
 def test_resource_pressure_limits_heavy(self):
  self.assertEqual(1,risk_plan(['server/x'],cpu_count=8,load=8,memory_free_ratio=.1).heavy_slots)
  self.assertGreater(risk_plan(['server/x'],cpu_count=16,load=0,memory_free_ratio=1).heavy_slots,1)
 def test_same_strategy_failure_never_blind_retries(self):
  fp=strategy_fingerprint('t','s','e','boom 42')
  d=retry_decision(prior_fingerprints=[fp],task_id='t',strategy='s',environment='e',failure='boom 42',transient=True)
  self.assertFalse(d['retry']); self.assertEqual('diagnose-change-one-variable',d['action'])
 def test_speculative_receipt_reuse_is_impact_scoped(self):
  r={'base_sha':'a','paths':['src/ui/a'],'independent':True}
  self.assertTrue(speculative_receipt_valid(r,new_base_sha='b',changed_paths=['server/x']))
  self.assertFalse(speculative_receipt_valid(r,new_base_sha='b',changed_paths=['src/ui/a']))
 def test_stage_receipt_is_measurable(self):
  r=stage_receipt('verify',task_id='t',artifact='a',expected_seconds=30,now=10)
  self.assertEqual(10,r['heartbeat_epoch']); self.assertEqual(30,r['expected_seconds'])
 def test_authority_chain_requires_independence(self):
  self.assertTrue(authority_chain('b','v','i','o')['eligible'])
  self.assertFalse(authority_chain('b','b','i','o')['eligible'])
 def test_new_operator_intent_dominates_old(self):
  self.assertFalse(operator_intent_wins(20,10)); self.assertTrue(operator_intent_wins(20,21))
if __name__=='__main__': unittest.main()
