import unittest
from pathlib import Path
CONTROL=Path(__file__).resolve().parents[1]/'bin/logres-control'
class TestOperationalView(unittest.TestCase):
 def test_dashboard_filters_historical_states(self):
  text=CONTROL.read_text()
  self.assertIn('=== OPERATIONAL FRONTIER ===',text)
  self.assertIn("where status in ('ACTIVE','READY','BLOCKED_DEP','BLOCKED_EVIDENCE')",text)
  self.assertNotIn('=== CRITICAL PATH ===',text)
if __name__=='__main__': unittest.main()
