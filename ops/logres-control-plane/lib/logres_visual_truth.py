from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID = {"PASS", "FAIL", "REVIEW"}
SPOOL_SCHEMA = 1


def ensure_schema(conn):
    conn.executescript(
        """
        create table if not exists visual_truth_checks(
          id integer primary key autoincrement,
          sha text not null,
          checkpoint text not null,
          objective_id text,
          reference_artifact text,
          observed_artifact text not null,
          viewport_json text not null default '{}',
          device_json text not null default '{}',
          metrics_json text not null default '{}',
          verdict text not null,
          created_at text not null,
          created_epoch real not null
        );
        create index if not exists visual_truth_checkpoint_idx
          on visual_truth_checks(checkpoint,id);
        """
    )
    conn.commit()


def _payload(
    *,
    sha: str,
    checkpoint: str,
    observed_artifact: str,
    verdict: str,
    reference_artifact: str | None = None,
    objective_id: str | None = None,
    viewport: dict[str, Any] | None = None,
    device: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    verdict = verdict.upper()
    if verdict not in VALID:
        raise ValueError("invalid verdict")
    if len(sha) != 40:
        raise ValueError("exact 40-character SHA required")
    if verdict == "PASS" and (not reference_artifact or not metrics):
        raise ValueError(
            "PASS requires explicit reference artifact and measurement metrics"
        )
    stamp = created_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    epoch = datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
    return {
        "sha": sha,
        "checkpoint": checkpoint,
        "objective_id": objective_id,
        "reference_artifact": reference_artifact,
        "observed_artifact": observed_artifact,
        "viewport": viewport or {},
        "device": device or {},
        "metrics": metrics or {},
        "verdict": verdict,
        "created_at": stamp,
        "created_epoch": epoch,
    }


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _insert_payload(conn: sqlite3.Connection, payload: dict[str, Any]) -> int:
    cur = conn.execute(
        """insert into visual_truth_checks(
          sha,checkpoint,objective_id,reference_artifact,observed_artifact,
          viewport_json,device_json,metrics_json,verdict,created_at,created_epoch
        ) values(?,?,?,?,?,?,?,?,?,?,?)""",
        (
            payload["sha"],
            payload["checkpoint"],
            payload["objective_id"],
            payload["reference_artifact"],
            payload["observed_artifact"],
            json.dumps(payload["viewport"], sort_keys=True),
            json.dumps(payload["device"], sort_keys=True),
            json.dumps(payload["metrics"], sort_keys=True),
            payload["verdict"],
            payload["created_at"],
            payload["created_epoch"],
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def record(
    conn,
    *,
    sha,
    checkpoint,
    observed_artifact,
    verdict,
    reference_artifact=None,
    objective_id=None,
    viewport=None,
    device=None,
    metrics=None,
    created_at=None,
):
    payload = _payload(
        sha=sha,
        checkpoint=checkpoint,
        observed_artifact=observed_artifact,
        verdict=verdict,
        reference_artifact=reference_artifact,
        objective_id=objective_id,
        viewport=viewport,
        device=device,
        metrics=metrics,
        created_at=created_at,
    )
    return _insert_payload(conn, payload)


def _is_lock_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return "database is locked" in message or "database is busy" in message


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _spool_payload(spool_dir: Path, payload: dict[str, Any]) -> Path:
    spool_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    fingerprint = _fingerprint(payload)
    final = spool_dir / f"{fingerprint}.json"
    if final.exists():
        return final
    envelope = {
        "schema": SPOOL_SCHEMA,
        "fingerprint": fingerprint,
        "record": payload,
    }
    raw = json.dumps(envelope, indent=2, sort_keys=True) + "\n"
    tmp = spool_dir / (
        f".{fingerprint}.{os.getpid()}.{time.time_ns()}.tmp"
    )
    try:
        with tmp.open("x", encoding="utf-8") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, final)
        _fsync_dir(spool_dir)
    finally:
        if tmp.exists():
            tmp.unlink()
    return final


def durable_record(
    conn: sqlite3.Connection,
    spool_dir: Path,
    **kwargs: Any,
) -> dict[str, Any]:
    payload = _payload(**kwargs)
    fingerprint = _fingerprint(payload)
    try:
        row_id = _insert_payload(conn, payload)
    except sqlite3.OperationalError as exc:
        if not _is_lock_error(exc):
            raise
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        path = _spool_payload(spool_dir, payload)
        return {
            "id": None,
            "spooled": True,
            "fingerprint": fingerprint,
            "spool_path": str(path),
        }
    return {
        "id": row_id,
        "spooled": False,
        "fingerprint": fingerprint,
        "spool_path": None,
    }


def _record_exists(
    conn: sqlite3.Connection,
    payload: dict[str, Any],
) -> bool:
    row = conn.execute(
        """select 1
             from visual_truth_checks
            where sha=?
              and checkpoint=?
              and objective_id is ?
              and reference_artifact is ?
              and observed_artifact=?
              and viewport_json=?
              and device_json=?
              and metrics_json=?
              and verdict=?
              and created_at=?
            limit 1""",
        (
            payload["sha"],
            payload["checkpoint"],
            payload["objective_id"],
            payload["reference_artifact"],
            payload["observed_artifact"],
            json.dumps(payload["viewport"], sort_keys=True),
            json.dumps(payload["device"], sort_keys=True),
            json.dumps(payload["metrics"], sort_keys=True),
            payload["verdict"],
            payload["created_at"],
        ),
    ).fetchone()
    return row is not None


def _load_spool(path: Path) -> dict[str, Any]:
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        if envelope.get("schema") != SPOOL_SCHEMA:
            raise ValueError("unsupported spool schema")
        payload = envelope["record"]
        expected = _fingerprint(payload)
        if envelope.get("fingerprint") != expected:
            raise ValueError("spool fingerprint mismatch")
        normalized = _payload(
            sha=payload["sha"],
            checkpoint=payload["checkpoint"],
            observed_artifact=payload["observed_artifact"],
            verdict=payload["verdict"],
            reference_artifact=payload.get("reference_artifact"),
            objective_id=payload.get("objective_id"),
            viewport=payload.get("viewport"),
            device=payload.get("device"),
            metrics=payload.get("metrics"),
            created_at=payload["created_at"],
        )
        if payload != normalized:
            raise ValueError("spool record envelope is not canonical")
        return normalized
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"malformed visual-truth spool {path.name}: {exc}") from exc


def _quarantine_spool(path: Path) -> Path:
    quarantine = path.parent / "quarantine"
    quarantine.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = quarantine / path.name
    os.replace(path, target)
    _fsync_dir(quarantine)
    _fsync_dir(path.parent)
    return target


def flush_spool(
    conn: sqlite3.Connection,
    spool_dir: Path,
    *,
    busy_timeout_ms: int = 50,
) -> dict[str, Any]:
    if not spool_dir.exists():
        return {
            "flushed": 0,
            "deduped": 0,
            "remaining": 0,
            "blocked": False,
        }

    previous_timeout = int(
        (conn.execute("pragma busy_timeout").fetchone() or [0])[0]
    )
    conn.execute(f"pragma busy_timeout={max(0, int(busy_timeout_ms))}")
    flushed = 0
    deduped = 0
    blocked = False
    try:
        for path in sorted(spool_dir.glob("*.json")):
            try:
                payload = _load_spool(path)
            except ValueError:
                target = _quarantine_spool(path)
                raise RuntimeError(
                    f"quarantined malformed visual-truth spool: {target}"
                )
            try:
                if _record_exists(conn, payload):
                    deduped += 1
                else:
                    _insert_payload(conn, payload)
                    flushed += 1
            except sqlite3.OperationalError as exc:
                if not _is_lock_error(exc):
                    raise
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
                blocked = True
                break
            path.unlink()
            _fsync_dir(spool_dir)
    finally:
        conn.execute(f"pragma busy_timeout={previous_timeout}")

    remaining = len(list(spool_dir.glob("*.json")))
    return {
        "flushed": flushed,
        "deduped": deduped,
        "remaining": remaining,
        "blocked": blocked,
    }


def _row(r):
    return {
        "id": r[0],
        "sha": r[1],
        "checkpoint": r[2],
        "objective_id": r[3],
        "reference_artifact": r[4],
        "observed_artifact": r[5],
        "viewport": json.loads(r[6]),
        "device": json.loads(r[7]),
        "metrics": json.loads(r[8]),
        "verdict": r[9],
        "created_at": r[10],
    }


def history(conn, checkpoint):
    return [
        _row(r)
        for r in conn.execute(
            """select id,sha,checkpoint,objective_id,reference_artifact,
              observed_artifact,viewport_json,device_json,metrics_json,
              verdict,created_at
              from visual_truth_checks
              where checkpoint=?
              order by id""",
            (checkpoint,),
        )
    ]


def latest(conn, checkpoint=None):
    if checkpoint:
        r = conn.execute(
            """select id,sha,checkpoint,objective_id,reference_artifact,
              observed_artifact,viewport_json,device_json,metrics_json,
              verdict,created_at
              from visual_truth_checks
              where checkpoint=?
              order by id desc limit 1""",
            (checkpoint,),
        ).fetchone()
        return None if not r else _row(r)
    rows = conn.execute(
        """select v.id,v.sha,v.checkpoint,v.objective_id,v.reference_artifact,
          v.observed_artifact,v.viewport_json,v.device_json,v.metrics_json,
          v.verdict,v.created_at
          from visual_truth_checks v
          join (
            select checkpoint,max(id) id
            from visual_truth_checks
            group by checkpoint
          ) x on x.id=v.id
          order by v.checkpoint"""
    )
    return [_row(r) for r in rows]


def regressions(conn):
    out = []
    for row in latest(conn):
        hist = history(conn, row["checkpoint"])
        prior_pass = any(x["verdict"] == "PASS" for x in hist[:-1])
        if prior_pass and row["verdict"] == "FAIL":
            out.append(row)
    return out
