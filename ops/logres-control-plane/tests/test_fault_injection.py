import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lib"))
from logres_fault_injection import list_scenarios,run_all,simulate
class FaultTests(unittest.TestCase):
 def test_required_scenarios_exist(self):
  names=set(list_scenarios())
  for x in ("supervisor_loss","sqlite_lock","remote_outage","expired_lease","duplicate_event","stale_claim","preflight_crash","network_loss","malformed_research","conflicting_branch"):self.assertIn(x,names)
 def test_synthetic_state_only(self):
  state={"supervisor_alive":True};r=simulate("supervisor_loss",state);self.assertTrue(state["supervisor_alive"]);self.assertFalse(r["injected_state"]["supervisor_alive"]);self.assertTrue(r["sandbox_only"])
 def test_missing_protection_fails_deterministically(self):
  r=simulate("network_loss",{},{"no_unsafe_merge":False});self.assertEqual("FAIL",r["verdict"])
 def test_default_recovery_contracts_pass(self):self.assertTrue(all(x["verdict"]=="PASS" for x in run_all()))
if __name__=="__main__":unittest.main()
