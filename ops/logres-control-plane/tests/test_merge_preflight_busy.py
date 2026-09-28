from pathlib import Path
import ast
import os
import sqlite3
import tempfile
import unittest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "bin"
    / "logres-merge-preflight"
)


class MergePreflightBusyTests(unittest.TestCase):
    def test_gate_busy_is_deferred_not_failed_or_quarantined(self):
        text = SCRIPT.read_text()
        self.assertIn('elif gp.returncode==75:', text)
        self.assertIn('state="DEFERRED_BUSY"', text)
        self.assertIn('PREFLIGHT_DEFERRED_BUSY', text)

        packet_index = text.index('c.commit(); p=packet(c,pid)')
        busy_index = text.index(
            '        if gp.returncode==75:',
            packet_index,
        )
        failure_index = text.index(
            '        if gp.returncode:',
            busy_index + 1,
        )
        regression_index = text.index(
            'logres-regression-capture',
            busy_index,
        )
        quarantine_index = text.index(
            'QUARANTINED after exact-SHA full-e2e',
            busy_index,
        )

        self.assertLess(busy_index, failure_index)
        self.assertLess(busy_index, regression_index)
        self.assertLess(busy_index, quarantine_index)

    def test_gate_reopens_canonical_db_before_persisting_packet(self):
        text = SCRIPT.read_text()
        gate = text.index('gp=subprocess.run([GATE,"candidate",result_sha]')
        close = text.rindex('close_canonical_db_for_gate(c)', 0, gate)
        reopen = text.index('c=reopen_canonical_db_after_gate()', gate)
        insert = text.index('insert into integration_preflights', reopen)
        self.assertLess(close, gate)
        self.assertLess(gate, reopen)
        self.assertLess(reopen, insert)

    def test_reopen_targets_replaced_canonical_sqlite_file(self):
        tree = ast.parse(SCRIPT.read_text())
        funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {
            'close_canonical_db_for_gate', 'reopen_canonical_db_after_gate'
        }]
        self.assertEqual({f.name for f in funcs}, {
            'close_canonical_db_for_gate', 'reopen_canonical_db_after_gate'
        })
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'control.sqlite'
            old = sqlite3.connect(db)
            old.execute('create table marker(value text)')
            old.execute("insert into marker values('old')")
            old.commit()
            ns = {'sqlite3': sqlite3, 'DB': db, 'ensure': lambda c: None}
            exec(compile(ast.Module(body=funcs, type_ignores=[]), str(SCRIPT), 'exec'), ns)
            ns['close_canonical_db_for_gate'](old)

            replacement = Path(td) / 'replacement.sqlite'
            r = sqlite3.connect(replacement)
            r.execute('create table marker(value text)')
            r.execute("insert into marker values('replacement')")
            r.execute('create table integration_preflights(id integer primary key, status text)')
            r.commit(); r.close()
            os.replace(replacement, db)

            fresh = ns['reopen_canonical_db_after_gate']()
            self.assertEqual(fresh.execute('select value from marker').fetchone()[0], 'replacement')
            fresh.execute("insert into integration_preflights(status) values('DEFERRED_BUSY')")
            fresh.commit(); fresh.close()
            check = sqlite3.connect(db)
            try:
                self.assertEqual(check.execute('select status from integration_preflights').fetchone()[0], 'DEFERRED_BUSY')
            finally:
                check.close()

    def test_busy_preflight_keeps_queue_mutation_out_of_busy_branch(self):
        text = SCRIPT.read_text()
        packet_index = text.index('c.commit(); p=packet(c,pid)')
        start = text.index(
            '        if gp.returncode==75:',
            packet_index,
        )
        end = text.index(
            '        if gp.returncode:',
            start + 1,
        )
        block = text[start:end]
        self.assertNotIn('update integration_queue', block)
        self.assertNotIn('regression-capture', block)
        self.assertNotIn('QUARANTINED', block)
        self.assertIn('return', block)
        self.assertNotIn('raise SystemExit(75)', block)


if __name__ == "__main__":
    unittest.main()
