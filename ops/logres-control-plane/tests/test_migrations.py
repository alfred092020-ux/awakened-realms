import sqlite3
import tempfile
from pathlib import Path

from logres_migrations import apply, plan


def test_migration_ledger_is_idempotent():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        migration = root / "001_demo.sql"
        migration.write_text("create table if not exists demo(id integer primary key);\n")

        conn = sqlite3.connect(":memory:")
        first = apply(conn, root, dry_run=True)
        assert [x["version"] for x in first["pending"]] == ["001_demo"]

        result = apply(conn, root)
        assert [x["version"] for x in result["applied"]] == ["001_demo"]
        assert conn.execute(
            "select count(*) from schema_migrations"
        ).fetchone()[0] == 1

        second = apply(conn, root)
        assert second["applied"] == []

        migration.write_text(
            "create table if not exists demo(id integer primary key, value text);\n"
        )
        states = {x["version"]: x["state"] for x in plan(conn, root)}
        assert states["001_demo"] == "CHECKSUM_MISMATCH"
