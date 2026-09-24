import sqlite3,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lib"))
from logres_semantic_dedupe import canonical,duplicates
class DedupeTests(unittest.TestCase):
 def db(self):
  c=sqlite3.connect(":memory:");c.row_factory=sqlite3.Row
  c.executescript("""create table tasks(id text primary key,lane text,title text,note text,status text);
  create table task_metadata(task_id text primary key,work_type text,evidence_policy text);
  create table task_acceptance(task_id text,ordinal integer,criterion text);
  create table task_scopes(task_id text,path_prefix text);
  create table task_dependencies(task_id text,depends_on text);""");return c
 def add(self,c,i,title,criteria):
  c.execute("insert into tasks values(?,?,?,?,?)",(i,'game',title,'','READY'));c.execute("insert into task_metadata values(?,?,?)",(i,'implementation','global original'))
  for n,x in enumerate(criteria):c.execute("insert into task_acceptance values(?,?,?)",(i,n,x))
  c.execute("insert into task_scopes values(?,?)",(i,'src/game/logres'));c.commit()
 def test_order_noise_is_semantically_same(self):
  c=self.db();self.add(c,'A','Build the battle flow',['Verify target','Use evidence']);self.add(c,'B','Build battle flow',['Use evidence','Verify target'])
  self.assertEqual(canonical(c,'A')["semantic_sha"],canonical(c,'B')["semantic_sha"])
 def test_duplicates_reports_group_without_mutation(self):
  c=self.db();self.add(c,'A','Build battle flow',['Verify']);self.add(c,'B','Build the battle flow',['Verify'])
  d=duplicates(c);self.assertEqual(1,len(d));self.assertEqual({'A','B'},set(d[0]['tasks']));self.assertEqual(2,c.execute("select count(*) from tasks").fetchone()[0])
 def test_scope_change_changes_fingerprint(self):
  c=self.db();self.add(c,'A','Build battle',['Verify']);self.add(c,'B','Build battle',['Verify']);c.execute("update task_scopes set path_prefix='src/other' where task_id='B'")
  self.assertNotEqual(canonical(c,'A')["semantic_sha"],canonical(c,'B')["semantic_sha"])
if __name__=="__main__":unittest.main()
