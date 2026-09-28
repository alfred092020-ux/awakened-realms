import importlib.util, pathlib, unittest
P=pathlib.Path(__file__).resolve().parents[1]/"server.py"
spec=importlib.util.spec_from_file_location("ncc",P); ncc=importlib.util.module_from_spec(spec);spec.loader.exec_module(ncc)
class ParseTests(unittest.TestCase):
 def test_who(self):
  rows=ncc.parse_who("auto-devin-1 ACTIVE seen=   1m unread=19  work=TASK-1:40%\nlead IDLE seen= 2m unread=0 work=-")
  self.assertEqual(rows[0]["task"],"TASK-1"); self.assertEqual(rows[0]["progress"],"40%"); self.assertEqual(rows[1]["state"],"IDLE")
 def test_history(self):
  rows=ncc.parse_history("[12] [HIGH] DONE worker→ALL task=T-1: completed\n  exact sha verified")
  self.assertEqual(rows[0]["id"],12); self.assertEqual(rows[0]["task"],"T-1"); self.assertIn("exact sha",rows[0]["detail"])
 def test_health(self):
  h=ncc.parse_health("PASS sqlite_integrity ok\nSUMMARY fails=0 checks=1")
  self.assertEqual(h["summary"]["fails"],0); self.assertEqual(h["checks"][0]["state"],"PASS")
 def test_dashboard(self):
  x=ncc.parse_dashboard("=== ACTIVE TASK LEASES ===\nP0 A owner=o progress=20% branch=worker/a until=2026-01-01T00:00:00+00:00\n=== READY WORK PACKAGES ===\nP1 B [implementation] ~20m :: Build thing")
  self.assertEqual(x["active"][0]["task"],"A"); self.assertEqual(x["ready"][0]["task"],"B")
 def test_hidden_auth_overlay_is_actually_hidden(self):
  css=(pathlib.Path(__file__).resolve().parents[1]/"static"/"app.css").read_text()
  self.assertIn("[hidden]{display:none!important}",css)
if __name__=="__main__": unittest.main()
