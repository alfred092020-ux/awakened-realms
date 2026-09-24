#!/usr/bin/env python3
"""Idempotently merge an isolated visual-truth SQLite DB into canonical control.sqlite.

The browser verifier records only into the isolated source. This merger is the
single bounded write boundary into canonical visual_truth_checks.

It performs no target DDL and fails closed if the canonical schema is absent,
the database is locked beyond the bounded busy timeout, or source rows are
malformed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys

COLUMNS = (
    "sha",
    "checkpoint",
    "objective_id",
    "reference_artifact",
    "observed_artifact",
    "viewport_json",
    "device_json",
    "metrics_json",
    "verdict",
    "created_at",
    "created_epoch",
)

MAX_BUSY_TIMEOUT_MS = 15_000


class MergeError(RuntimeError):
    pass


def table_columns(
    conn: sqlite3.Connection,
    schema: str,
    table: str,
) -> tuple[str, ...]:
    rows = conn.execute(
        f"pragma {schema}.table_info({table})"
    ).fetchall()
    return tuple(str(row[1]) for row in rows)


def require_schema(
    conn: sqlite3.Connection,
    schema: str,
) -> None:
    actual = set(
        table_columns(
            conn,
            schema,
            "visual_truth_checks",
        )
    )
    required = {"id", *COLUMNS}
    missing = required - actual
    if missing:
        raise MergeError(
            f"{schema}.visual_truth_checks missing columns: "
            + ",".join(sorted(missing))
        )


def validate_timeout(value: int) -> int:
    if value <= 0 or value > MAX_BUSY_TIMEOUT_MS:
        raise MergeError(
            f"busy timeout must be > 0 and <= {MAX_BUSY_TIMEOUT_MS} ms"
        )
    return value


def merge(
    *,
    source: Path,
    target: Path,
    busy_timeout_ms: int,
) -> dict[str, object]:
    validate_timeout(busy_timeout_ms)
    if not source.is_file():
        raise MergeError(
            f"isolated visual-truth DB missing: {source}"
        )
    if not target.is_file():
        raise MergeError(
            f"canonical control DB missing: {target}"
        )
    try:
        if source.resolve() == target.resolve():
            raise MergeError(
                "source and canonical visual-truth DB must differ"
            )
    except FileNotFoundError:
        pass

    conn = sqlite3.connect(
        target,
        timeout=busy_timeout_ms / 1000.0,
    )
    try:
        conn.execute(
            f"pragma busy_timeout={busy_timeout_ms}"
        )
        require_schema(
            conn,
            "main",
        )
        conn.execute(
            "attach database ? as isolated",
            (str(source),),
        )
        try:
            require_schema(
                conn,
                "isolated",
            )
            source_rows = int(
                conn.execute(
                    "select count(*) from isolated.visual_truth_checks"
                ).fetchone()[0]
            )
            target_before = int(
                conn.execute(
                    "select count(*) from main.visual_truth_checks"
                ).fetchone()[0]
            )

            columns = ",".join(COLUMNS)
            equality = " and ".join(
                f"t.{column} is s.{column}"
                for column in COLUMNS
            )
            sql = f"""
                insert into main.visual_truth_checks({columns})
                select {",".join(f"s.{column}" for column in COLUMNS)}
                  from isolated.visual_truth_checks s
                 where not exists (
                       select 1
                         from main.visual_truth_checks t
                        where {equality}
                 )
                 order by s.id
            """
            conn.execute(
                "begin immediate"
            )
            conn.execute(sql)
            inserted = int(
                conn.execute(
                    "select changes()"
                ).fetchone()[0]
            )
            conn.commit()
            target_after = int(
                conn.execute(
                    "select count(*) from main.visual_truth_checks"
                ).fetchone()[0]
            )
        finally:
            try:
                conn.execute(
                    "detach database isolated"
                )
            except sqlite3.Error:
                pass
    except sqlite3.Error as exc:
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        raise MergeError(
            f"visual-truth merge failed: {exc}"
        ) from exc
    finally:
        conn.close()

    return {
        "status": "PASS",
        "source": str(source),
        "target": str(target),
        "source_rows": source_rows,
        "inserted_rows": inserted,
        "deduped_rows": source_rows - inserted,
        "target_rows_before": target_before,
        "target_rows_after": target_after,
        "busy_timeout_ms": busy_timeout_ms,
        "idempotent_key": list(COLUMNS),
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=__doc__,
    )
    p.add_argument(
        "--source",
        type=Path,
        required=True,
    )
    p.add_argument(
        "--target",
        type=Path,
        required=True,
    )
    p.add_argument(
        "--busy-timeout-ms",
        type=int,
        default=4_000,
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = merge(
            source=args.source,
            target=args.target,
            busy_timeout_ms=args.busy_timeout_ms,
        )
    except (MergeError, OSError) as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error": type(exc).__name__,
                    "message": str(exc),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    print(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
