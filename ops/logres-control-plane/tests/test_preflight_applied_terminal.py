import ast
import sqlite3
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
SCRIPT = TEST_DIR.parent / "bin" / "logres-merge-preflight"


def load_mark_stale():
    tree = ast.parse(SCRIPT.read_text())
    fn = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "mark_stale_if_verified"
    )
    module = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {}
    exec(compile(module, str(SCRIPT), "exec"), ns)
    return ns["mark_stale_if_verified"]


def make_db():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """create table integration_preflights(
             id integer primary key,
             status text not null,
             updated_at text,
             note text
           )"""
    )
    return conn


class PreflightAppliedTerminalTests(unittest.TestCase):
    def test_verified_row_can_be_marked_stale(self):
        conn = make_db()
        conn.execute(
            "insert into integration_preflights values(1,'VERIFIED','','')"
        )
        mark = load_mark_stale()
        self.assertTrue(mark(conn, 1, "now", "stale reason"))
        row = conn.execute(
            "select status,note from integration_preflights where id=1"
        ).fetchone()
        self.assertEqual(("STALE", "stale reason"), row)

    def test_applied_wins_verified_to_stale_race(self):
        conn = make_db()
        conn.execute(
            "insert into integration_preflights values(1,'VERIFIED','','')"
        )
        selected = conn.execute(
            "select status from integration_preflights where id=1"
        ).fetchone()[0]
        self.assertEqual("VERIFIED", selected)

        # Simulate the integration process applying this preflight after a
        # stale-checking process selected it but before that process updates it.
        conn.execute(
            "update integration_preflights set status='APPLIED' where id=1"
        )
        mark = load_mark_stale()
        self.assertFalse(mark(conn, 1, "later", "must not overwrite applied"))
        row = conn.execute(
            "select status,note from integration_preflights where id=1"
        ).fetchone()
        self.assertEqual(("APPLIED", ""), row)

    def test_all_stale_writes_use_compare_and_set_helper(self):
        source = SCRIPT.read_text()
        self.assertEqual(1, source.count("set status='STALE'"))
        self.assertIn(
            "where id=? and status='VERIFIED'",
            source,
        )
        self.assertGreaterEqual(
            source.count("mark_stale_if_verified("),
            4,
        )

    def test_lost_stale_race_preserves_applied_ref_path(self):
        source = SCRIPT.read_text()
        block_start = source.index("staled=mark_stale_if_verified(")
        block_end = source.index("base=sync_integration_from_origin()", block_start)
        block = source[block_start:block_end]
        self.assertIn("if staled:", block)
        self.assertIn('"update-ref","-d"', block)
        self.assertIn('fresh["status"]=="APPLIED"', block)
        self.assertLess(
            block.index("if staled:"),
            block.index('"update-ref","-d"'),
        )


if __name__ == "__main__":
    unittest.main()
