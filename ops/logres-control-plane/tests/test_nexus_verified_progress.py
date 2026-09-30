import sys, unittest
from pathlib import Path
LIB=Path(__file__).resolve().parent.parent/'lib'; sys.path.insert(0,str(LIB))
from nexus_verified_progress import DecisionInput, capability_for, decide

class VerifiedProgressTests(unittest.TestCase):
    def test_unlock_success_verification_and_cost_drive_evp(self):
        ranked=decide([DecisionInput('leaf',0,'implementation',1,.95,.95,5),DecisionInput('unlocker',0,'implementation',8,.8,.9,20)])
        self.assertEqual('unlocker',ranked[0].task_id)
    def test_priority_is_operator_constraint(self):
        ranked=decide([DecisionInput('p1-huge',1,'implementation',100,1,1,1),DecisionInput('p0-small',0,'implementation',1,.5,.5,60)])
        self.assertEqual('p0-small',ranked[0].task_id)
    def test_reconciliation_mismatch_fails_closed(self):
        receipt=decide([DecisionInput('stale',0,'verification',10,1,1,1,claimed_state='ACTIVE',observed_state='MISSING')])[0]
        self.assertFalse(receipt.eligible); self.assertEqual(0,receipt.expected_verified_progress)
        self.assertEqual('state-mismatch:ACTIVE->MISSING',receipt.reconciliation)
    def test_routes_capability_before_agent(self):
        self.assertEqual('exact-sha-verification',capability_for('verification'))
        self.assertEqual('physical-device-qa',capability_for('android'))
        self.assertEqual('privileged-host-operation',capability_for('privileged'))
    def test_receipt_is_explainable(self):
        receipt=decide([DecisionInput('x',0,'research',3,.9,.8,10,2)])[0].to_dict()
        self.assertEqual('historical-evidence',receipt['capability']); self.assertIn('unlock=3',receipt['rationale']); self.assertIn('verification=0.80',receipt['rationale'])
if __name__=='__main__': unittest.main()
