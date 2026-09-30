import sqlite3,unittest
from logres_executive_replay import replay
class T(unittest.TestCase):
 def test_replay_records_only_advisory_decision(self):
  c=sqlite3.connect(':memory:'); c.execute('create table tasks(id text,status text)'); c.execute("insert into tasks values('x','READY')"); before=c.execute('select * from tasks').fetchall()
  r=replay(c,[{'case_id':'c1','objective_id':'o','world':{'facts':[],'contradictions':[]},'gaps':[{'x':1}],'expected_kind':'INVESTIGATE_OR_EXECUTE'}]); self.assertTrue(r[0]['matched']); self.assertEqual(before,c.execute('select * from tasks').fetchall())
