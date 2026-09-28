import importlib.machinery, importlib.util, pathlib, unittest
from unittest.mock import patch
P=pathlib.Path(__file__).parents[1]/'bin/logres-phone-agent'
spec=importlib.util.spec_from_loader('phone_agent',importlib.machinery.SourceFileLoader('phone_agent',str(P))); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class TestPhoneAgent(unittest.TestCase):
 def test_signature_stable(self): self.assertEqual(m.sign('k',b'{}'),m.sign('k',b'{}')); self.assertNotEqual(m.sign('k',b'{}'),m.sign('x',b'{}'))
 def test_outbound_only_no_arbitrary_shell(self):
  s=P.read_text(); self.assertIn('/phone-agent/poll',s); self.assertNotIn("op=='shell_read'",s); self.assertNotIn('shell=True',s); self.assertNotIn('ssh -R',s)
 def test_unknown_rejected(self): self.assertEqual(m.dispatch('shell_read',{'command':'id'})['exitCode'],64)
 @patch.object(m,'run')
 def test_app_stop_is_argv(self,r): r.return_value={'exitCode':0}; m.dispatch('app_stop',{'package':'com.example.app'}); r.assert_called_once_with(['adb','shell','am','force-stop','com.example.app'])
 def test_package_injection_rejected(self):
  with self.assertRaises(ValueError): m.dispatch('app_stop',{'package':'x;id'})
 @patch.object(m,'run')
 def test_perf_allowlist(self,r):
  r.return_value={'exitCode':0}; m.dispatch('perf',{'service':'gfxinfo','package':'com.x'}); r.assert_called_once_with(['adb','shell','dumpsys','gfxinfo','com.x'])
  with self.assertRaises(ValueError): m.dispatch('perf',{'service':'activity'})
if __name__=='__main__': unittest.main()
