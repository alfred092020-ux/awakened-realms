import importlib.machinery, importlib.util, sqlite3, tempfile, unittest
from pathlib import Path
from unittest import mock
ROOT=Path(__file__).resolve().parents[1]
def load(name,file):
    loader=importlib.machinery.SourceFileLoader(name,str(ROOT/'bin'/file)); spec=importlib.util.spec_from_loader(name,loader); m=importlib.util.module_from_spec(spec); loader.exec_module(m); return m
brain=load('brain_readonly_test','logres-brain')
coord=load('coord_readonly_test','logres-coordinator')
class ReadOnlyConnectionTests(unittest.TestCase):
    def test_brain_readonly_connection_does_not_run_schema_or_refresh(self):
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/'c.sqlite'; c=sqlite3.connect(db); c.execute('create table x(v)'); c.commit(); c.close()
            with mock.patch.object(brain,'DB',db), mock.patch.object(brain,'ensure_schema') as ensure, mock.patch.object(brain,'refresh_integration_sha') as refresh:
                ro=brain.conn(readonly=True); self.assertEqual(0,ro.execute('select count(*) from x').fetchone()[0]); ro.close()
                ensure.assert_not_called(); refresh.assert_not_called()
    def test_coordinator_readonly_connection_does_not_run_schema(self):
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/'c.sqlite'; c=sqlite3.connect(db); c.execute('create table x(v)'); c.commit(); c.close()
            with mock.patch.object(coord,'DB',db), mock.patch.object(coord,'ensure') as ensure:
                ro=coord.conn(readonly=True); self.assertEqual(0,ro.execute('select count(*) from x').fetchone()[0]); ro.close(); ensure.assert_not_called()
    def test_readonly_connections_succeed_while_writer_transaction_is_open(self):
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/'c.sqlite'; w=sqlite3.connect(db); w.execute('pragma journal_mode=WAL'); w.execute('create table x(v)'); w.commit(); w.execute('begin immediate')
            with mock.patch.object(brain,'DB',db):
                ro=brain.conn(readonly=True); self.assertEqual(0,ro.execute('select count(*) from x').fetchone()[0]); ro.close()
            with mock.patch.object(coord,'DB',db):
                ro=coord.conn(readonly=True); self.assertEqual(0,ro.execute('select count(*) from x').fetchone()[0]); ro.close()
            w.rollback(); w.close()
class ReadCommandTests(unittest.TestCase):
    def test_digest_no_longer_expires_leases(self):
        src=(ROOT/'bin'/'logres-brain').read_text(); body=src.split('def cmd_digest',1)[1].split('def cmd_history',1)[0]; self.assertNotIn('expire_leases(',body)
    def test_observational_coordinator_commands_do_not_reconcile(self):
        src=(ROOT/'bin'/'logres-coordinator').read_text()
        for name,next_name in [('cmd_plan','cmd_brief'),('cmd_brief','cmd_acquire'),('cmd_next','cmd_add')]:
            body=src.split('def '+name,1)[1].split('def '+next_name,1)[0]; self.assertNotIn('reconcile(c,False)',body)
if __name__=='__main__': unittest.main()
