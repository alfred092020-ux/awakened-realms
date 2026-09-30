import os,unittest
os.environ['NEXUS_NATIVE_API_TOKEN']='test-token'
import server
class T(unittest.TestCase):
 def setUp(self): server.APPROVALS.clear()
 def test_pending_contract(self):
  server.APPROVALS['a']={'id':'a','sha':'1'*40,'reason':'L3','evidence_summary':'seven checkpoints','status':'PENDING'}
  self.assertEqual(server.pending()[0]['sha'],'1'*40)
 def test_decision_model(self):
  a={'id':'a','sha':'2'*40,'reason':'review','evidence_summary':'receipt','status':'PENDING'};server.APPROVALS['a']=a;a['status']='APPROVED';self.assertEqual(server.pending(),[])
if __name__=='__main__':unittest.main()
