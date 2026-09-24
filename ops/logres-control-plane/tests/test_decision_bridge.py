import sqlite3,sys,unittest,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lib"))
from logres_decision_bridge import apply,plan,status
class DecisionBridgeTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:"); self.c.row_factory=sqlite3.Row
        self.c.executescript("""
        create table brain_events(
          id integer primary key,event_type text,ts text,sender text,task_id text,
          subject text,body text,artifact_path text,artifact_sha256 text,meta_json text
        );
        """)
    def tearDown(self): self.c.close()
    def add(self,meta="{}",task="T1"):
        self.c.execute("insert into brain_events values(1,'DECISION','2026-09-24T00:00:00+00:00','lead',?,'Choose A','Because evidence','/tmp/e','abc',?)",(task,meta))
        self.c.commit()
    def test_only_explicit_decisions_are_imported(self):
        self.add()
        self.c.execute("insert into brain_events values(2,'INFO','x','lead',null,'i','b',null,null,'{}')")
        self.assertEqual(1,len(plan(self.c)))
    def test_import_is_idempotent(self):
        self.add()
        self.assertEqual(1,len(apply(self.c)))
        self.assertEqual(0,len(apply(self.c)))
        self.assertEqual({"explicit_brain_decisions":1,"imported":1,"pending":0},status(self.c))
    def test_does_not_invent_alternatives(self):
        self.add()
        row=plan(self.c)[0]
        self.assertEqual([],row["alternatives"])
        self.assertEqual("Choose A",row["selected"])
        self.assertEqual("Because evidence",row["why"])
    def test_explicit_meta_is_preserved(self):
        self.add(json.dumps({"alternatives":["B","C"],"selected":"A","expected_outcome":"faster","scope":"architecture"}),task=None)
        row=plan(self.c)[0]
        self.assertEqual(["B","C"],row["alternatives"])
        self.assertEqual("A",row["selected"])
        self.assertEqual("faster",row["expected_outcome"])
        self.assertEqual("architecture",row["scope"])
if __name__=="__main__": unittest.main()
