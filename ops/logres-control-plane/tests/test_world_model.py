import sqlite3,unittest
from logres_world_model import derive_world_model
class T(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:'); self.c.execute('create table tasks(id text,status text)'); self.c.execute('create table integration_queue(status text)')
 def test_conflict(self):
  w=derive_world_model(self.c,git_head='a',origin_head='a',runtime_sha='b'); self.assertFalse(w['healthy']); self.assertEqual(w['contradictions'][0]['code'],'RUNTIME_SHA_MISMATCH')
 def test_read_only(self):
  n=self.c.total_changes; derive_world_model(self.c,git_head='a',origin_head='a'); self.assertEqual(n,self.c.total_changes)
