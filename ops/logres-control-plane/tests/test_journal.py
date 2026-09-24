import sqlite3, sys, unittest
from pathlib import Path
LIB=Path(__file__).resolve().parents[1]/"lib"; sys.path.insert(0,str(LIB))
from logres_journal import append_event, add_decision, decisions, entity_history
class JournalTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:"); self.c.row_factory=sqlite3.Row
    def tearDown(self): self.c.close()
    def test_append_and_entity_history(self):
        append_event(self.c,actor="a",entity_type="task",entity_id="T1",action="CREATED",payload={"x":1})
        rows=entity_history(self.c,"task","T1")
        self.assertEqual(1,len(rows)); self.assertEqual({"x":1},rows[0]["payload"])
    def test_dedupe_is_idempotent(self):
        a=append_event(self.c,actor="a",entity_type="task",entity_id="T1",action="DONE",dedupe_key="k")
        b=append_event(self.c,actor="b",entity_type="task",entity_id="T1",action="DONE",dedupe_key="k")
        self.assertTrue(a["inserted"]); self.assertFalse(b["inserted"]); self.assertEqual(a["id"],b["id"])
    def test_decision_preserves_why_and_alternatives(self):
        add_decision(self.c,actor="lead",scope="mission",subject="next",why="shortens path",alternatives=["A","B"],selected="B",evidence=["sha:abc"],expected_outcome="progress")
        row=decisions(self.c,"mission")[0]
        self.assertEqual("shortens path",row["why"]); self.assertEqual(["A","B"],row["alternatives"]); self.assertEqual("B",row["selected"])
if __name__=="__main__": unittest.main()
