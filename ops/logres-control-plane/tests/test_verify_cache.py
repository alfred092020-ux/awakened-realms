import sqlite3,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lib"))
from logres_verify_cache import lookup,put_pass
D={"source_sha":"a"*40,"lock_hash":"l","config_hash":"c","evidence_version":"e","env_hash":"v","mode":"full-e2e"}
class VerifyCacheTests(unittest.TestCase):
 def setUp(self):self.c=sqlite3.connect(":memory:");self.c.row_factory=sqlite3.Row
 def test_complete_key_round_trip(self):
  self.assertFalse(lookup(self.c,D)["hit"]);put_pass(self.c,D,{"log":"x"});self.assertTrue(lookup(self.c,D)["hit"])
 def test_dimension_change_misses(self):
  put_pass(self.c,D);d=dict(D);d["env_hash"]="other";self.assertFalse(lookup(self.c,d)["hit"])
 def test_missing_dimension_fails_closed(self):
  d=dict(D);del d["lock_hash"]
  with self.assertRaises(ValueError):lookup(self.c,d)
 def test_non_exact_sha_rejected(self):
  d=dict(D);d["source_sha"]="abc"
  with self.assertRaises(ValueError):put_pass(self.c,d)
if __name__=="__main__":unittest.main()
