import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lib"))
from logres_workspace_lifecycle import classify
class WorkspaceLifecycleTests(unittest.TestCase):
 def test_active_is_live(self):self.assertEqual("LIVE",classify({"active_lease":True}))
 def test_dirty_never_archive(self):self.assertEqual("KEEP_DIRTY",classify({"dirty":True,"task_status":"DONE","integrated":True}))
 def test_unique_unintegrated_stays_warm(self):self.assertEqual("WARM",classify({"unique_commits":2,"task_status":"DONE","integrated":False}))
 def test_clean_integrated_done_is_candidate(self):self.assertEqual("ARCHIVE_CANDIDATE",classify({"unique_commits":0,"task_status":"DONE","integrated":True}))
 def test_protected_is_live(self):self.assertEqual("LIVE",classify({"protected":True,"dirty":False}))
if __name__=="__main__":unittest.main()
