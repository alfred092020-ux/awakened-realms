import pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).parents[1]/'lib'))
from logres_phone_agent_broker import Broker,valid_signature
class TestBroker(unittest.TestCase):
 def test_lifecycle(self):
  with tempfile.TemporaryDirectory() as d:
   b=Broker(pathlib.Path(d)/'x.sqlite'); j=b.enqueue('s1','status'); self.assertEqual(b.poll('s1')['id'],j); self.assertIsNone(b.poll('s1')); self.assertTrue(b.complete('s1',j,{'exitCode':0})); self.assertEqual(b.get(j)['state'],'DONE')
 def test_allowlist(self):
  with tempfile.TemporaryDirectory() as d:
   b=Broker(pathlib.Path(d)/'x.sqlite')
   for op in ('device_info','packages','app_start','input_tap','ui_dump','perf','instrument','screenrecord','pull_file','push_file'): b.enqueue('s1',op,{})
   for op in ('shell_read','shell_mutate'):
    with self.assertRaises(ValueError): b.enqueue('s1',op,{})
 def test_signature(self):
  import hashlib,hmac
  body=b'{}'; sig=hmac.new(b'k',body,hashlib.sha256).hexdigest(); self.assertTrue(valid_signature('k',body,sig)); self.assertFalse(valid_signature('x',body,sig))
if __name__=='__main__': unittest.main()
