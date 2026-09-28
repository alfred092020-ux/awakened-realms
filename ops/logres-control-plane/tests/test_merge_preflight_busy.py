from pathlib import Path
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
        close = text.rindex('c.close()', 0, gate)
        reopen = text.index('c=sqlite3.connect(DB,timeout=30)', gate)
        insert = text.index('insert into integration_preflights', reopen)
        self.assertLess(close, gate)
        self.assertLess(gate, reopen)
        self.assertLess(reopen, insert)
        self.assertIn('c.row_factory=sqlite3.Row', text[reopen:insert])

    def test_reopen_after_atomic_database_replacement_writes_canonical_file(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "control.sqlite"
            old = sqlite3.connect(db)
            old.execute("create table verdicts(id integer primary key, value text)")
            old.execute("insert into verdicts(value) values ('before-gate')")
            old.commit()
            old.close()

            replacement = Path(td) / "replacement.sqlite"
            fresh = sqlite3.connect(replacement)
            fresh.execute("create table verdicts(id integer primary key, value text)")
            fresh.execute("insert into verdicts(value) values ('canonical-after-gate')")
            fresh.commit()
            fresh.close()
            replacement.replace(db)

            reopened = sqlite3.connect(db, timeout=30)
            reopened.execute("insert into verdicts(value) values ('preflight-verdict')")
            reopened.commit()
            reopened.close()

            canonical = sqlite3.connect(db)
            values = [row[0] for row in canonical.execute("select value from verdicts order by id")]
            canonical.close()
            self.assertEqual(values, ['canonical-after-gate', 'preflight-verdict'])

    def test_reopen_after_gate_failure_can_persist_failed_verdict(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "control.sqlite"
            c = sqlite3.connect(db)
            c.execute("create table verdicts(status text not null, rc integer not null)")
            c.commit()
            c.close()
            replacement = Path(td) / "replacement.sqlite"
            c = sqlite3.connect(replacement)
            c.execute("create table verdicts(status text not null, rc integer not null)")
            c.commit()
            c.close()
            replacement.replace(db)
            gate_rc = 1
            reopened = sqlite3.connect(db, timeout=30)
            reopened.execute("insert into verdicts(status,rc) values(?,?)", ('FAILED', gate_rc))
            reopened.commit()
            reopened.close()
            canonical = sqlite3.connect(db)
            self.assertEqual(canonical.execute("select status,rc from verdicts").fetchone(), ('FAILED', 1))
            canonical.close()

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
