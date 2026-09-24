#!/usr/bin/env python3
"""Idempotently merge isolated behavior-trace records into canonical control.sqlite."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import time

COLUMNS = (
    "sha",
    "objective_id",
    "checkpoint",
    "expected_json",
    "observed_json",
    "divergence_json",
    "provenance_json",
    "verdict",
)
MAX_BUSY_TIMEOUT_MS = 15_000
MAX_LOCK_ATTEMPTS = 4
LOCK_RETRY_BASE_SECONDS = 0.10


class MergeError(RuntimeError):
    pass


def table_columns(conn: sqlite3.Connection, schema: str) -> set[str]:
    return {
        str(row[1])
        for row in conn.execute(
            f"pragma {schema}.table_info(behavior_trace_checks)"
        )
    }


def require_schema(conn: sqlite3.Connection, schema: str) -> None:
    required = {"id", *COLUMNS, "created_at"}
    missing = required - table_columns(conn, schema)
    if missing:
        raise MergeError(
            f"{schema}.behavior_trace_checks missing columns: "
            + ",".join(sorted(missing))
        )


def validate_timeout(value: int) -> int:
    if value <= 0 or value > MAX_BUSY_TIMEOUT_MS:
        raise MergeError(
            f"busy timeout must be > 0 and <= {MAX_BUSY_TIMEOUT_MS} ms"
        )
    return value


def _merge_once(*, source: Path, target: Path, busy_timeout_ms: int) -> dict:
    validate_timeout(busy_timeout_ms)
    if not source.is_file():
        raise MergeError(f"isolated behavior-trace DB missing: {source}")
    if not target.is_file():
        raise MergeError(f"canonical control DB missing: {target}")
    if source.resolve() == target.resolve():
        raise MergeError("source and canonical behavior-trace DB must differ")

    conn = sqlite3.connect(target, timeout=busy_timeout_ms / 1000.0)
    try:
        conn.execute(f"pragma busy_timeout={busy_timeout_ms}")
        require_schema(conn, "main")
        conn.execute("attach database ? as isolated", (str(source),))
        try:
            require_schema(conn, "isolated")
            source_rows = int(
                conn.execute(
                    "select count(*) from isolated.behavior_trace_checks"
                ).fetchone()[0]
            )
            target_before = int(
                conn.execute(
                    "select count(*) from main.behavior_trace_checks"
                ).fetchone()[0]
            )
            equality = " and ".join(
                f"t.{column} is s.{column}" for column in COLUMNS
            )
            conn.execute("begin immediate")
            conn.execute(
                f"""
                insert into main.behavior_trace_checks(
                  {",".join(COLUMNS)},created_at
                )
                select {",".join(f"s.{column}" for column in COLUMNS)},
                       s.created_at
                  from isolated.behavior_trace_checks s
                 where not exists (
                       select 1
                         from main.behavior_trace_checks t
                        where {equality}
                 )
                 order by s.id
                """
            )
            inserted = int(conn.execute("select changes()").fetchone()[0])
            conn.commit()
            target_after = int(
                conn.execute(
                    "select count(*) from main.behavior_trace_checks"
                ).fetchone()[0]
            )
        finally:
            try:
                conn.execute("detach database isolated")
            except sqlite3.Error:
                pass
    except sqlite3.Error as exc:
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        raise MergeError(f"behavior-trace merge failed: {exc}") from exc
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


def is_lock_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "database is locked" in text or "database is busy" in text


def merge(*, source: Path, target: Path, busy_timeout_ms: int) -> dict:
    last_error: MergeError | None = None
    for attempt in range(1, MAX_LOCK_ATTEMPTS + 1):
        try:
            result = _merge_once(
                source=source,
                target=target,
                busy_timeout_ms=busy_timeout_ms,
            )
            result["lock_retry_count"] = attempt - 1
            result["lock_attempts"] = attempt
            return result
        except MergeError as exc:
            if not is_lock_error(exc):
                raise
            last_error = exc
            if attempt >= MAX_LOCK_ATTEMPTS:
                break
            time.sleep(LOCK_RETRY_BASE_SECONDS * (2 ** (attempt - 1)))
    assert last_error is not None
    raise MergeError(
        f"{last_error}; exhausted {MAX_LOCK_ATTEMPTS} bounded lock attempts"
    ) from last_error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--busy-timeout-ms", type=int, default=4_000)
    args = parser.parse_args()
    try:
        result = merge(
            source=args.source,
            target=args.target,
            busy_timeout_ms=args.busy_timeout_ms,
        )
    except (MergeError, OSError) as exc:
        print(json.dumps({
            "status": "FAIL",
            "error": type(exc).__name__,
            "message": str(exc),
        }, indent=2, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
