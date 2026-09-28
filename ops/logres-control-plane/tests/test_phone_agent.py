import importlib.machinery, importlib.util, pathlib, unittest
P=pathlib.Path(__file__).parents[1]/'bin/logres-phone-agent'
spec=importlib.util.spec_from_loader('phone_agent', importlib.machinery.SourceFileLoader('phone_agent', str(P))); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class TestPhoneAgent(unittest.TestCase):
 def test_signature_stable(self):
  self.assertEqual(m.sign('k',b'{}'), m.sign('k',b'{}'))
  self.assertNotEqual(m.sign('k',b'{}'), m.sign('x',b'{}'))
 def test_script_is_outbound_only(self):
  s=P.read_text(); self.assertIn('/phone-agent/poll',s); self.assertNotIn('ssh -R',s)
if __name__=='__main__': unittest.main()
