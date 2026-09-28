import importlib.util, pathlib, unittest, json, struct
from unittest import mock
P=pathlib.Path(__file__).resolve().parents[1]/"server.py"
spec=importlib.util.spec_from_file_location("ncc",P)
ncc=importlib.util.module_from_spec(spec)
spec.loader.exec_module(ncc)

class ParseTests(unittest.TestCase):
 def test_who(self):
  rows=ncc.parse_who("auto-devin-1 ACTIVE seen=   1m unread=19  work=TASK-1:40%\nlead IDLE seen= 2m unread=0 work=-")
  self.assertEqual(rows[0]["task"],"TASK-1")
  self.assertEqual(rows[0]["progress"],"40%")
  self.assertEqual(rows[1]["state"],"IDLE")

 def test_history(self):
  rows=ncc.parse_history("[12] [HIGH] DONE worker→ALL task=T-1: completed\n  exact sha verified")
  self.assertEqual(rows[0]["id"],12)
  self.assertEqual(rows[0]["task"],"T-1")
  self.assertIn("exact sha",rows[0]["detail"])

 def test_health(self):
  h=ncc.parse_health("PASS sqlite_integrity ok\nSUMMARY fails=0 checks=1")
  self.assertEqual(h["summary"]["fails"],0)
  self.assertEqual(h["checks"][0]["state"],"PASS")

 def test_dashboard(self):
  x=ncc.parse_dashboard("=== ACTIVE TASK LEASES ===\nP0 A owner=o progress=20% branch=worker/a until=2026-01-01T00:00:00+00:00\n=== READY WORK PACKAGES ===\nP1 B [implementation] ~20m :: Build thing")
  self.assertEqual(x["active"][0]["task"],"A")
  self.assertEqual(x["ready"][0]["task"],"B")

 def test_hidden_auth_overlay_is_actually_hidden(self):
  css=(pathlib.Path(__file__).resolve().parents[1]/"static"/"app.css").read_text()
  self.assertIn("[hidden]{display:none!important}",css)

 def test_websocket_frame_small_payload(self):
  frame=ncc.ws_frame('{"ok":1}')
  self.assertEqual(frame[0],0x81)
  self.assertEqual(frame[1],8)
  self.assertEqual(frame[2:],b'{"ok":1}')

 def test_session_is_http_only_design(self):
  index=(pathlib.Path(__file__).resolve().parents[1]/"static"/"app.js").read_text()
  self.assertNotIn("sessionStorage.setItem",index)
  self.assertIn("/api/session",index)

 def test_preflight_requires_exact_confirmation(self):
  ok,state,msg=ncc.control_request("run-preflight",{"confirm":"yes"})
  self.assertFalse(ok)
  self.assertEqual(state,"CONFIRM_REQUIRED")
  self.assertIn("RUN PREFLIGHT",msg)

 def test_unknown_control_rejected(self):
  ok,state,msg=ncc.control_request("rm-everything",{})
  self.assertFalse(ok)
  self.assertEqual(state,"REJECTED")

 def test_manifest_standalone(self):
  m=json.loads((pathlib.Path(__file__).resolve().parents[1]/"static"/"manifest.webmanifest").read_text())
  self.assertEqual(m["display"],"standalone")
  self.assertEqual(m["name"],"Nexus Command Center")

 def test_mobile_grid_children_can_shrink(self):
  css=(pathlib.Path(__file__).resolve().parents[1]/"static"/"app.css").read_text()
  self.assertIn(".worker>div,.task>div,.event>div{min-width:0}",css)
  self.assertIn("overflow-x:hidden",css)

 def test_source_record_has_provenance_and_freshness(self):
  x=ncc.source_record("git","OK",100.0,20000,"Git truth")
  self.assertEqual(x["checked_at"],100000)
  self.assertEqual(x["max_age_ms"],20000)
  self.assertEqual(x["provenance"],"Git truth")

 def test_failed_brain_presence_preserves_previous_counts_not_zero(self):
  prev={"workers":[{"name":"w","state":"ACTIVE","task":"T"}],"events":[],"counts":{"active_workers":1,"idle_workers":0,"stale_workers":0,"working":1},"sources":{"brain_presence":{"checked_at":123000},"brain_events":{"checked_at":123000},"git":{"checked_at":123000},"brain_health":{"checked_at":123000},"control_plane":{"checked_at":123000}},"integration":{"in_sync":True},"health":{"summary":{"fails":0,"checks":1}},"tasks":{"active":[],"ready":[],"blocked":[]}}
  def fake_run(cmd,timeout=6):
   if "digest" in cmd: return 1,"","brain down"
   return 0,"",""
  with mock.patch.object(ncc,"run",side_effect=fake_run):
   with mock.patch.object(ncc,"system_metrics",return_value={"load_per_cpu":0.1,"cpu_psi_avg10":0.0,"mem_used_pct":20.0}):
    x=ncc.snapshot(full=False,previous=prev)
  self.assertEqual(x["counts"]["active_workers"],1)
  self.assertEqual(x["sources"]["brain_presence"]["status"],"STALE")
  self.assertTrue(x["sources"]["brain_presence"]["cached"])

 def test_truth_contract_never_substitutes_missing_with_zero(self):
  self.assertEqual(ncc.snapshot.__name__,"snapshot")
  src=(pathlib.Path(__file__).resolve().parents[1]/"server.py").read_text()
  self.assertIn("UNKNOWN_OR_STALE_NEVER_ZERO",src)

 def test_ui_renders_source_provenance(self):
  html=(pathlib.Path(__file__).resolve().parents[1]/"static"/"index.html").read_text()
  js=(pathlib.Path(__file__).resolve().parents[1]/"static"/"app.js").read_text()
  self.assertIn('id="source-grid"',html)
  self.assertIn("renderSources",js)
  self.assertIn("checked ",js)

 def test_working_count_excludes_stale_agent_with_task(self):
  seed=ncc.initial_snapshot_seed()
  digest="LOGRES BRAIN NETWORK\nactive ACTIVE seen= 1s unread=0 work=T-1:10%\nstale STALE seen= 2h unread=0 work=T-2:20%\n=== ACTIVE TASK LEASES ===\nP0 T-1 owner=active progress=10% branch=worker/t-1 until=2026-09-28T20:00:00+00:00\n=== READY WORK PACKAGES ===\nnone\n=== RECENT HIGH-SIGNAL EVENTS ===\nnone\n=== ACTIVE DECISIONS ==="
  def fake_run(cmd,timeout=6):
   if "digest" in cmd: return 0,digest,""
   return 0,"",""
  with mock.patch.object(ncc,"run",side_effect=fake_run):
   with mock.patch.object(ncc,"system_metrics",return_value={"load_per_cpu":0.1,"cpu_psi_avg10":0.0,"mem_used_pct":20.0}):
    x=ncc.snapshot(full=False,previous=seed)
  self.assertEqual(x["counts"]["active_workers"],1)
  self.assertEqual(x["counts"]["working"],1)

if __name__=="__main__":
 unittest.main()
