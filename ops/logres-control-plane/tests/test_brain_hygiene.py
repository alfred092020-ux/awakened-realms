import os,sqlite3,subprocess,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HYGIENE=ROOT/'bin/logres-brain-hygiene'
CONTROL=ROOT/'bin/logres-control'
class BrainHygieneTest(unittest.TestCase):
 def make_db(self,path):
  c=sqlite3.connect(path)
  c.executescript('''create table tasks(id text primary key,priority integer,lane text,title text,status text,branch text,owner text,note text,updated_at text); create table brain_task_leases(task_id text,lease_until_epoch real);''')
  rows=[
   ('REG-INTEGRATION-CONFLICT-OLD',0,'regression','Fix automated integration-conflict regression: Resolve integration conflict for X at abcdef123456 against 111111111111','READY','','','','2026-09-30T01:00:00+00:00'),
   ('REG-INTEGRATION-CONFLICT-NEW',0,'regression','Fix automated integration-conflict regression: Resolve integration conflict for X at abcdef123456 against 222222222222','READY','','','','2026-09-30T02:00:00+00:00'),
   ('REPAIR-OLD',0,'implementation','Diagnose and repair semantic failure blocking REG-INTEGRATION-CONFLICT-OLD','READY','','','','2026-09-30T01:10:00+00:00'),
   ('DONE-1',0,'x','history','DONE','','','','2026-09-29T00:00:00+00:00')]
  c.executemany('insert into tasks values(?,?,?,?,?,?,?,?,?)',rows); c.commit(); c.close()
 def test_dry_run_never_mutates(self):
  with tempfile.TemporaryDirectory() as td:
   db=Path(td)/'c.sqlite'; self.make_db(db); env={**os.environ,'LOGRES_CONTROL_DB':str(db),'LOGRES_ROOT':td}
   p=subprocess.run([str(HYGIENE)],env=env,text=True,capture_output=True); self.assertEqual(p.returncode,0,p.stderr)
   c=sqlite3.connect(db); states=dict(c.execute('select id,status from tasks'))
   self.assertEqual(states['REG-INTEGRATION-CONFLICT-OLD'],'READY'); self.assertEqual(states['REPAIR-OLD'],'READY')
 def test_compacts_rebased_conflict_lineage_and_child(self):
  with tempfile.TemporaryDirectory() as td:
   db=Path(td)/'c.sqlite'; self.make_db(db); env={**os.environ,'LOGRES_CONTROL_DB':str(db),'LOGRES_ROOT':td}
   p=subprocess.run([str(HYGIENE),'--apply'],env=env,text=True,capture_output=True); self.assertEqual(p.returncode,0,p.stderr)
   c=sqlite3.connect(db); states=dict(c.execute('select id,status from tasks'))
   self.assertEqual(states['REG-INTEGRATION-CONFLICT-OLD'],'SUPERSEDED'); self.assertEqual(states['REPAIR-OLD'],'SUPERSEDED'); self.assertEqual(states['REG-INTEGRATION-CONFLICT-NEW'],'READY'); self.assertEqual(states['DONE-1'],'DONE')
 def test_operational_dashboard_filters_history(self):
  text=CONTROL.read_text(); self.assertIn('=== OPERATIONAL FRONTIER ===',text); self.assertIn("where status in ('ACTIVE','READY','BLOCKED_DEP','BLOCKED_EVIDENCE')",text); self.assertNotIn('=== CRITICAL PATH ===',text)
if __name__=='__main__': unittest.main()
