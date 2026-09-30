import os,tempfile,unittest
os.environ['NEXUS_NATIVE_API_TOKEN']='test-token';os.environ['NEXUS_NATIVE_API_DB']=tempfile.mktemp(suffix='.sqlite')
import server
class T(unittest.TestCase):
 def setUp(self):
  try:os.unlink(server.DB)
  except FileNotFoundError:pass
 def test_persistent_exact_sha_decision(self):
  b={'id':'a','sha':'1'*40,'reason':'L3','evidence_summary':'receipt'};self.assertEqual(server.register_approval(b)[0],201);self.assertEqual(server.approval_rows('PENDING')[0]['id'],'a')
  self.assertEqual(server.decide_approval({'action':'approve-gate','approval_id':'a','sha':'2'*40})[0],409)
  old=server.run;server.run=lambda *a,**k:(0,'','')
  try:code,obj=server.decide_approval({'action':'approve-gate','approval_id':'a','sha':'1'*40})
  finally:server.run=old
  self.assertEqual(code,200);self.assertEqual(obj['approval']['status'],'APPROVED');self.assertEqual(server.approval_rows('PENDING'),[])
 def test_invalid_sha_and_duplicate(self):
  b={'id':'a','sha':'bad','reason':'x','evidence_summary':'y'};self.assertEqual(server.register_approval(b)[0],400);b['sha']='a'*40;self.assertEqual(server.register_approval(b)[0],201);self.assertEqual(server.register_approval(b)[0],409)
 def test_real_snapshot_contract(self):
  old=server.run
  def fake(cmd,timeout=5):
   s=' '.join(map(str,cmd))
   if 'rev-parse HEAD' in s:return 0,'f'*40,''
   if '--abbrev-ref HEAD' in s:return 0,'feat/logres-reconstruction',''
   if s.endswith(' who'):return 0,'w ACTIVE seen=now unread=0 work=TASK:50%',''
   if 'history --limit 30' in s:return 0,'',''
   if s.endswith(' health'):return 0,'SUMMARY fails=0 checks=1',''
   if s.endswith(' dashboard'):return 0,'=== ACTIVE TASK LEASES ===\nP9 TASK owner=w progress=50% branch=worker/x until=later',''
   return 0,'',''
  server.run=fake
  try:d=server.snapshot(True)
  finally:server.run=old
  self.assertEqual(d['integration']['sha'],'f'*40);self.assertEqual(d['counts']['working'],1);self.assertEqual(d['tasks']['active'][0]['task'],'TASK')
 def test_native_api_has_no_static_web_surface(self):
  text=open(server.__file__).read();self.assertNotIn('serve_static',text);self.assertNotIn('text/html',text);self.assertNotIn('STATIC=',text);self.assertIn('/api/events',text)
if __name__=='__main__':unittest.main()
