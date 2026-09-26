from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_ledger(conn: sqlite3.Connection) -> None:
    conn.execute(
        """create table if not exists schema_migrations(
             version text primary key,
             checksum_sha256 text not null,
             applied_at text not null
           )"""
    )
    conn.commit()


def discover(migration_dir: str | Path) -> list[Path]:
    root = Path(migration_dir)
    return sorted(p for p in root.glob("*.sql") if p.is_file())


def plan(conn: sqlite3.Connection, migration_dir: str | Path) -> list[dict]:
    ensure_ledger(conn)
    applied = {
        row[0]: row[1]
        for row in conn.execute(
            "select version,checksum_sha256 from schema_migrations"
        )
    }
    out = []
    for path in discover(migration_dir):
        version = path.stem
        payload = path.read_bytes()
        checksum = hashlib.sha256(payload).hexdigest()
        previous = applied.get(version)
        state = "APPLIED" if previous else "PENDING"
        if previous and previous != checksum:
            state = "CHECKSUM_MISMATCH"
        out.append(
            {
                "version": version,
                "path": str(path),
                "checksum_sha256": checksum,
                "state": state,
            }
        )
    return out


def apply(conn: sqlite3.Connection, migration_dir: str | Path, *, dry_run: bool = False) -> dict:
    items = plan(conn, migration_dir)
    mismatches = [x for x in items if x["state"] == "CHECKSUM_MISMATCH"]
    if mismatches:
        raise RuntimeError(
            "migration checksum mismatch: "
            + ", ".join(x["version"] for x in mismatches)
        )

    pending = [x for x in items if x["state"] == "PENDING"]
    if dry_run:
        return {"dry_run": True, "pending": pending, "applied": []}

    applied = []
    for item in pending:
        sql = Path(item["path"]).read_text()
        conn.executescript(sql)
        conn.execute(
            """insert into schema_migrations(version,checksum_sha256,applied_at)
               values(?,?,?)""",
            (item["version"], item["checksum_sha256"], _now()),
        )
        conn.commit()
        applied.append(item)
    return {"dry_run": False, "pending": pending, "applied": applied}
