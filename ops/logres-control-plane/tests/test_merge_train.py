import importlib.machinery
import importlib.util
import sqlite3
import unittest
from pathlib import Path
from unittest import mock


TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent


def load_script(name: str, filename: str):
    path = CONTROL_ROOT / "bin" / filename
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


merge_train = load_script("logres_merge_train_test_module", "logres-merge-train")


def make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        create table tasks(
          id text primary key, priority integer, title text, status text
        );
        create table integration_queue(
          task_id text not null,
          sha text not null,
          branch text not null,
          status text not null,
          verification_mode text,
          queued_at text not null,
          updated_at text not null,
          note text not null default '',
          ready_at text,
          integrated_at text,
          primary key(task_id,sha)
        );
        create table verification(
          ref text,sha text,mode text,status text,
          duration_sec real,ran_at text,details text
        );
        create table regressions(
          id integer primary key autoincrement,
          fingerprint text unique,
          task_id text,
          kind text,
          ref text,
          sha text,
          summary text,
          logs_json text,
          created_at text,
          created_epoch real,
          status text
        );
        """
    )
    conn.execute(
        "insert into tasks(id,priority,title,status) values('T1',0,'T1','ACTIVE')"
    )
    return conn


class MergeTrainQuarantineTests(unittest.TestCase):
    def _seed(self, conn, status, *, verification_mode="fast"):
        sha = "a" * 40
        conn.execute(
            """insert into integration_queue(
                 task_id,sha,branch,status,verification_mode,
                 queued_at,updated_at,note
               ) values('T1',?,'worker/t1',?,?, 'old','old','sentinel')""",
            (sha, status, verification_mode),
        )
        conn.commit()
        return sha

    def test_terminal_done_owner_keeps_verified_candidate_without_brain_report(self):
        conn = make_db()
        sha = self._seed(conn, "READY_FOR_PREFLIGHT")
        conn.execute("update tasks set status='DONE' where id='T1'")
        conn.execute("insert into verification(ref,sha,mode,status,duration_sec,ran_at,details) values('worker/t1',?,'fast','PASS',1,'now','ok')",(sha,))
        conn.commit()
        with mock.patch.object(merge_train, "fetch_origin"), \
             mock.patch.object(merge_train, "run") as run, \
             mock.patch.object(merge_train, "sha", return_value=sha), \
             mock.patch.object(merge_train, "ancestor", return_value=False), \
             mock.patch.object(merge_train, "patch_equivalent", return_value=False), \
             mock.patch.object(merge_train, "clean_merge_possible", return_value=(True,"")), \
             mock.patch.object(merge_train, "supersede_repaired_conflicts", return_value=0), \
             mock.patch.object(merge_train.subprocess, "run") as subprocess_run:
            run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            merge_train.refresh(conn)
        row=conn.execute("select status from integration_queue where task_id='T1'").fetchone()
        self.assertEqual('READY_FOR_PREFLIGHT',row['status'])
        subprocess_run.assert_not_called()

    def test_terminal_owner_scope_failure_is_retained_without_brain_report(self):
        conn = make_db(); sha=self._seed(conn,"READY_FOR_PREFLIGHT")
        conn.execute("update tasks set status='DONE' where id='T1'"); conn.commit()
        with mock.patch.object(merge_train,"fetch_origin"), mock.patch.object(merge_train,"run") as run, mock.patch.object(merge_train,"sha",return_value=sha), mock.patch.object(merge_train,"ancestor",return_value=False), mock.patch.object(merge_train,"patch_equivalent",return_value=False), mock.patch.object(merge_train,"supersede_repaired_conflicts",return_value=0), mock.patch.object(merge_train.subprocess,"run") as subprocess_run:
            run.return_value=mock.Mock(returncode=1,stdout="scope violation",stderr=""); merge_train.refresh(conn)
        row=conn.execute("select status,note from integration_queue where task_id='T1'").fetchone()
        self.assertEqual('SCOPE_VIOLATION',row['status']); self.assertIn('terminal (DONE)',row['note']); subprocess_run.assert_not_called()

    def test_refresh_does_not_touch_quarantined_fast_pass_row(self):
        conn = make_db()
        sha = self._seed(conn, "QUARANTINED", verification_mode="fast")
        conn.execute(
            """insert into verification(
                 ref,sha,mode,status,duration_sec,ran_at,details
               ) values('worker/t1',?,'fast','PASS',1,'now','ok')""",
            (sha,),
        )
        conn.commit()

        with mock.patch.object(merge_train, "fetch_origin"),              mock.patch.object(merge_train, "run") as run,              mock.patch.object(merge_train, "sha", return_value="f" * 40),              mock.patch.object(merge_train, "supersede_repaired_conflicts", return_value=0):
            run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            changed = merge_train.refresh(conn)

        self.assertEqual(0, changed)
        row = conn.execute(
            "select status,note from integration_queue where task_id='T1' and sha=?",
            (sha,),
        ).fetchone()
        self.assertEqual("QUARANTINED", row["status"])
        self.assertEqual("sentinel", row["note"])

    def test_refresh_does_not_touch_quarantined_full_e2e_pass_row(self):
        conn = make_db()
        sha = self._seed(conn, "QUARANTINED", verification_mode="full-e2e")
        conn.execute(
            """insert into verification(
                 ref,sha,mode,status,duration_sec,ran_at,details
               ) values('worker/t1',?,'full-e2e','PASS',1,'now','ok')""",
            (sha,),
        )
        conn.commit()

        with mock.patch.object(merge_train, "fetch_origin"),              mock.patch.object(merge_train, "run") as run,              mock.patch.object(merge_train, "sha", return_value="f" * 40),              mock.patch.object(merge_train, "supersede_repaired_conflicts", return_value=0):
            run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            changed = merge_train.refresh(conn)

        self.assertEqual(0, changed)
        row = conn.execute(
            "select status,verification_mode from integration_queue where task_id='T1' and sha=?",
            (sha,),
        ).fetchone()
        self.assertEqual("QUARANTINED", row["status"])
        self.assertEqual("full-e2e", row["verification_mode"])

    def test_default_status_view_hides_terminal_quarantine(self):
        source = (CONTROL_ROOT / "bin" / "logres-merge-train").read_text()
        self.assertIn(
            "where q.status not in ('INTEGRATED','SUPERSEDED','QUARANTINED')",
            source,
        )
        self.assertIn(
            'else "where q.status not in (\'INTEGRATED\',\'SUPERSEDED\',\'QUARANTINED\')"',
            source,
        )


if __name__ == "__main__":
    unittest.main()
