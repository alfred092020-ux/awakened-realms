from pathlib import Path
import os
import sqlite3
import subprocess
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

    def test_production_preflight_persists_packet_after_gate_replaces_database(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repo = root / "repo"; origin = root / "origin.git"
            control = root / "control"; packet_root = control / "merge-preflight"; control.mkdir()
            subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True)
            subprocess.run(["git", "init", "-b", "feat/logres-reconstruction", str(repo)], check=True, capture_output=True)
            for key, value in (("user.name", "Test"), ("user.email", "test@example.invalid")):
                subprocess.run(["git", "-C", str(repo), "config", key, value], check=True)
            (repo / "base.txt").write_text("base\n")
            subprocess.run(["git", "-C", str(repo), "add", "base.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-m", "base"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(origin)], check=True)
            subprocess.run(["git", "-C", str(repo), "push", "-u", "origin", "feat/logres-reconstruction"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "checkout", "-b", "worker/test-candidate"], check=True, capture_output=True)
            (repo / "candidate.txt").write_text("candidate\n")
            subprocess.run(["git", "-C", str(repo), "add", "candidate.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-m", "candidate"], check=True, capture_output=True)
            candidate = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
            subprocess.run(["git", "-C", str(repo), "push", "-u", "origin", "worker/test-candidate"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "checkout", "feat/logres-reconstruction"], check=True, capture_output=True)
            db = control / "control.sqlite"
            c = sqlite3.connect(db)
            c.executescript("create table tasks(id text primary key, priority integer, title text); create table integration_queue(task_id text, sha text, branch text, status text, queued_at text, updated_at text, ready_at text, note text); create table verification(sha text, mode text, status text, ran_at text);")
            c.execute("insert into tasks values(?,?,?)", ("T-1", 0, "test"))
            c.execute("insert into integration_queue values(?,?,?,?,?,?,?,?)", ("T-1", candidate, "worker/test-candidate", "READY_FOR_PREFLIGHT", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00", ""))
            c.commit(); c.close()
            train = root / "train"; train.write_text("#!/bin/sh\nexit 0\n"); train.chmod(0o755)
            brain = root / "brain"; brain.write_text("#!/bin/sh\nexit 0\n"); brain.chmod(0o755)
            gate = root / "gate.py"
            gate.write_text("#!/usr/bin/env python3\nimport os,sqlite3,sys\nfrom pathlib import Path\ndb=Path(sys.argv[1]) if len(sys.argv)>3 else Path(os.environ[\"LOGRES_CONTROL_DB\"])\nr=db.with_suffix(\".replacement\")\ns=sqlite3.connect(db); d=sqlite3.connect(r); s.backup(d); d.execute(\"create table if not exists gate_rotation(marker text)\"); d.execute(\"insert into gate_rotation values(\'replacement-canonical\')\"); d.commit(); d.close(); s.close(); os.replace(r,db); raise SystemExit(75)\n")
            gate.chmod(0o755)
            env = os.environ.copy()
            env.update({"LOGRES_ROOT": str(root), "LOGRES_REPO_ROOT": str(repo), "LOGRES_CONTROL_DB": str(db), "LOGRES_PREFLIGHT_ROOT": str(packet_root), "LOGRES_MERGE_TRAIN": str(train), "LOGRES_GATE": str(gate), "LOGRES_BRAIN": str(brain), "LOGRES_INTEGRATION_LOCK": str(root / "integration.lock"), "LOGRES_FETCH_LOCK": str(root / "fetch.lock")})
            proc = subprocess.run([str(SCRIPT), "run", "--max", "1"], env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertIn("PREFLIGHT_DEFERRED_BUSY", proc.stdout)
            canonical = sqlite3.connect(db)
            row = canonical.execute("select id,status from integration_preflights").fetchone()
            marker = canonical.execute("select marker from gate_rotation").fetchone()
            canonical.close()
            self.assertIsNotNone(row); self.assertEqual(row[1], "DEFERRED_BUSY"); self.assertEqual(marker[0], "replacement-canonical")
            packet = packet_root / f"preflight-{row[0]}.json"
            self.assertTrue(packet.exists()); self.assertIn("DEFERRED_BUSY", packet.read_text())

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
