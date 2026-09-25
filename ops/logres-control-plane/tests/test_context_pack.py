import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "lib"),
)

from logres_context_pack import (
    TaskNotFoundError,
    UnderspecifiedTaskError,
    build_pack,
    canonical_json,
    render_text,
)

CONTROL_ROOT = Path(__file__).resolve().parents[1]
CLI = CONTROL_ROOT / "bin" / "logres-context-pack"


def make_conn(full: bool = True) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        create table tasks(
            id text primary key, title text, priority integer,
            lane text, status text, note text, branch text, owner text);
        create table task_acceptance(
            task_id text, ordinal integer, criterion text);
        create table task_scopes(task_id text, path_prefix text);
        create table task_dependencies(
            task_id text, depends_on text, kind text, rationale text);
        create table claims(
            path_prefix text, task_id text, owner text, branch text);
        """
    )
    if full:
        conn.executescript(
            """
            create table task_recovery(
                id integer primary key, task_id text, status text,
                branch text, worktree text, manifest_path text,
                created_at text, note text);
            create table brain_decisions(
                id integer primary key, ts text, author text, scope text,
                subject text, decision text, status text, task_id text);
            """
        )
    conn.execute(
        "insert into tasks values(?,?,?,?,?,?,?,?)",
        ("T-1", "Implement widget", 2, "core", "READY",
         "details", "worker/t1", "devin"),
    )
    conn.execute(
        "insert into tasks values(?,?,?,?,?,?,?,?)",
        ("T-0", "Prior task", 2, "core", "DONE", "", "worker/t0", "devin"),
    )
    conn.executemany(
        "insert into task_acceptance values(?,?,?)",
        [("T-1", 1, "widget renders"), ("T-1", 2, "tests pass")],
    )
    conn.executemany(
        "insert into task_scopes values(?,?)",
        [("T-1", "src/widget/"), ("T-1", "tests/widget/")],
    )
    conn.execute(
        "insert into task_dependencies values(?,?,?,?)",
        ("T-1", "T-0", "blocks", "needs base"),
    )
    conn.commit()
    return conn


def base_evidence():
    return [
        {"id": "e1", "source": "index", "path": "a.py",
         "snippet": "small", "authority": "HIGH", "confidence": "HIGH",
         "relevance": 0.9},
    ]


class BuildPackTests(unittest.TestCase):
    def setUp(self):
        self.conn = make_conn()

    def test_deterministic_identical_pack_and_render(self):
        e = base_evidence()
        p1 = build_pack(self.conn, "T-1", evidence=e)
        p2 = build_pack(self.conn, "T-1", evidence=e)
        self.assertEqual(canonical_json(p1), canonical_json(p2))
        self.assertEqual(render_text(p1), render_text(p2))

    def test_acceptance_scopes_dependencies_preserved(self):
        p = build_pack(self.conn, "T-1")
        self.assertEqual(p["acceptance_criteria"],
                         ["widget renders", "tests pass"])
        self.assertEqual(p["scopes"], ["src/widget/", "tests/widget/"])
        dep = p["dependencies"][0]
        self.assertEqual(dep["task_id"], "T-0")
        self.assertTrue(dep["satisfied"])
        self.assertEqual(dep["status"], "DONE")

    def test_underspecified_task_rejected(self):
        self.conn.execute(
            "insert into tasks values(?,?,?,?,?,?,?,?)",
            ("T-9", "keep going on the thing", 1, "core", "READY",
             "as before", "w", "o"))
        self.conn.commit()
        with self.assertRaises(UnderspecifiedTaskError):
            build_pack(self.conn, "T-9")

    def test_underspecified_phrase_allowed_when_resolvable(self):
        # phrase present but acceptance+scopes exist -> pack still builds,
        # marker recorded
        self.conn.execute(
            "update tasks set note='keep going' where id='T-1'")
        p = build_pack(self.conn, "T-1")
        self.assertEqual(p["underspecified_marker"], "keep going")

    def test_unknown_task_raises(self):
        with self.assertRaises(TaskNotFoundError):
            build_pack(self.conn, "NOPE")

    def test_large_evidence_content_addressed(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * 5000)
            path = f.name
        try:
            ev = [{"source": "fs", "path": path, "authority": "HIGH"}]
            p = build_pack(self.conn, "T-1", evidence=ev)
            e = p["evidence"][0]
            self.assertTrue(e["content_addressed"])
            self.assertEqual(e["bytes"], 5000)
            self.assertEqual(len(e["sha256"]), 64)
            self.assertIn(f"{path}#sha256:", e["ref"])
            self.assertNotIn("snippet", e)
        finally:
            os.unlink(path)

    def test_budget_truncation_drops_optional_first(self):
        ev = [{"id": f"e{i}", "source": "s", "path": f"f{i}.py",
               "snippet": "S" * 500, "authority": "LOW"}
              for i in range(10)]
        cfg = {"max_bytes": 3000}
        p = build_pack(self.conn, "T-1", config=cfg, evidence=ev)
        self.assertTrue(p["budget"]["truncated"])
        self.assertIn("evidence_snippets", p["budget"]["dropped"])
        # critical fields survive
        self.assertEqual(p["acceptance_criteria"],
                         ["widget renders", "tests pass"])
        self.assertEqual(p["scopes"], ["src/widget/", "tests/widget/"])
        self.assertEqual(p["task_id"], "T-1")
        for e in p["evidence"]:
            self.assertIn("sha256", e)

    def test_evidence_ceilings_survive(self):
        ev = [
            {"id": "u", "source": "s", "snippet": "x",
             "status": "UNRESOLVED", "authority": "UNRESOLVED"},
            {"id": "c", "source": "s", "snippet": "y",
             "status": "EVIDENCE_CONFLICT", "authority": "EVIDENCE_CONFLICT"},
        ]
        p = build_pack(self.conn, "T-1", evidence=ev)
        self.assertEqual(p["evidence_ceilings"],
                         ["EVIDENCE_CONFLICT", "UNRESOLVED"])
        statuses = {e["id"]: e["status"] for e in p["evidence"]}
        self.assertEqual(statuses["u"], "UNRESOLVED")
        self.assertEqual(statuses["c"], "EVIDENCE_CONFLICT")

    def test_overlapping_claim_conflicts(self):
        self.conn.execute(
            "insert into claims values(?,?,?,?)",
            ("src/", "T-OTHER", "alice", "worker/other"))
        self.conn.execute(
            "insert into claims values(?,?,?,?)",
            ("unrelated/", "T-FAR", "bob", "worker/far"))
        self.conn.commit()
        p = build_pack(self.conn, "T-1")
        conflicts = p["claims"]["conflicts"]
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["task_id"], "T-OTHER")
        self.assertIn("CLAIM CONFLICTS", render_text(p))

    def test_secret_redaction(self):
        ev = [{"id": "sec", "source": "s",
               "snippet": "api_key = 'AKIAIOSFODNN7EXAMPLE' "
                          "token=ghp_abcdefghijklmnop1234567890"}]
        p = build_pack(self.conn, "T-1", evidence=ev)
        blob = canonical_json(p) + render_text(p)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", blob)
        self.assertNotIn("ghp_abcdefghijklmnop1234567890", blob)
        self.assertGreaterEqual(p["redactions"], 1)
        self.assertIn("[REDACTED]", blob)

    def test_engine_neutral_canonical_output(self):
        p = build_pack(self.conn, "T-1")
        self.assertEqual(p["engine"], "engine-neutral")
        self.assertEqual(p["schema"], "logres.context-pack/v1")
        # canonical json is stable: sorted keys, parseable
        parsed = json.loads(canonical_json(p))
        self.assertEqual(parsed["task_id"], "T-1")

    def test_recovery_and_decisions_included(self):
        self.conn.execute(
            "insert into task_recovery(task_id,status,branch,worktree,"
            "manifest_path,created_at,note) values(?,?,?,?,?,?,?)",
            ("T-1", "FAILED", "worker/t1", "/tmp/wt", "m.json",
             "2026-01-01", "attempt 1"))
        self.conn.execute(
            "insert into brain_decisions(ts,author,scope,subject,decision,"
            "status,task_id) values(?,?,?,?,?,?,?)",
            ("2026-01-01", "brain", "core", "use sqlite",
             "canonical store", "ACTIVE", "T-1"))
        self.conn.commit()
        p = build_pack(self.conn, "T-1")
        self.assertEqual(p["recovery"]["status"], "FAILED")
        self.assertEqual(p["recovery"]["worktree"], "/tmp/wt")
        self.assertEqual(len(p["decisions"]), 1)
        self.assertEqual(p["decisions"][0]["subject"], "use sqlite")
        text = render_text(p)
        self.assertIn("Recovery:", text)
        self.assertIn("Decisions:", text)

    def test_graceful_optional_table_absence(self):
        conn = make_conn(full=False)
        conn.execute("drop table claims")
        p = build_pack(conn, "T-1")
        self.assertIsNone(p["recovery"])
        self.assertEqual(p["decisions"], [])
        self.assertEqual(p["claims"], {"own": [], "conflicts": []})

    def test_integration_sha_override(self):
        p = build_pack(self.conn, "T-1", integration_sha="abc123")
        self.assertEqual(p["integration"]["integration_sha"], "abc123")


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "control.sqlite"
        conn = sqlite3.connect(self.db)
        mem = make_conn()
        mem.backup(conn)
        conn.close()
        mem.close()

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            capture_output=True, text=True,
        )

    def test_cli_json_output(self):
        r = self.run_cli("T-1", "--db", str(self.db), "--output", "json")
        self.assertEqual(r.returncode, 0, r.stderr)
        p = json.loads(r.stdout)
        self.assertEqual(p["task_id"], "T-1")

    def test_cli_both_and_file(self):
        out = Path(self.tmp.name) / "pack.txt"
        r = self.run_cli("T-1", "--db", str(self.db), "--output", "both",
                         "--output-file", str(out),
                         "--integration-sha", "deadbeef")
        self.assertEqual(r.returncode, 0, r.stderr)
        text = out.read_text()
        self.assertIn("CONTEXT PACK", text)
        self.assertIn("deadbeef", text)
        self.assertEqual(r.stdout, "")

    def test_cli_unknown_task_fails(self):
        r = self.run_cli("NOPE", "--db", str(self.db))
        self.assertNotEqual(r.returncode, 0)

    def test_cli_underspecified_fails(self):
        conn = sqlite3.connect(self.db)
        conn.execute(
            "insert into tasks values(?,?,?,?,?,?,?,?)",
            ("T-9", "continue previous work", 1, "core", "READY",
             "", "w", "o"))
        conn.commit()
        conn.close()
        r = self.run_cli("T-9", "--db", str(self.db))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("under-specified", r.stderr)

    def test_cli_deterministic(self):
        a = self.run_cli("T-1", "--db", str(self.db), "--output", "json")
        b = self.run_cli("T-1", "--db", str(self.db), "--output", "json")
        self.assertEqual(a.stdout, b.stdout)


if __name__ == "__main__":
    unittest.main()
