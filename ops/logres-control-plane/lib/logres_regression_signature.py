from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Iterable


VERIFY_PATH_RE = re.compile(r"/dev/shm/logres/verify-farm-[^/\s]+")
WORKTREE_RE = re.compile(r"/home/ubuntu/logres/work/[^/\s]+")
VERIFY_LOG_RE = re.compile(r"/home/ubuntu/logres/logs/verify-farm-[^/\s]+")
SHA_RE = re.compile(r"\b[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?\b")
STAMP_RE = re.compile(r"\b\d{8}T\d{6}(?:Z)?\b")
DURATION_RE = re.compile(r"\b\d+(?:\.\d+)?(?:ms|s)\b", re.I)
PORT_RE = re.compile(r"(?<=:)\d{4,5}\b")
LINE_COL_RE = re.compile(r":\d+:\d+\b")
PID_RE = re.compile(r"\bpid[=: ]+\d+\b", re.I)
NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_.-])\d+(?:\.\d+)?(?![A-Za-z0-9_.-])")


KNOWN_FAMILIES = (
    (
        "behavior-trace-output-required",
        lambda low: "logres_behavior_trace_out is required" in low,
    ),
    (
        "visual-truth-sqlite-locked",
        lambda low: (
            "sqlite3.operationalerror: database is locked" in low
            and ("visual truth" in low or "logres-visual-truth" in low)
        ),
    ),
    (
        "sqlite-database-locked",
        lambda low: "sqlite3.operationalerror: database is locked" in low,
    ),
    (
        "visual-truth-record-timeout",
        lambda low: (
            "visual truth recording timed out" in low
            or (
                "subprocess.timeoutexpired" in low
                and "logres-visual-truth" in low
            )
        ),
    ),
)


def normalize_failure_text(text: str) -> str:
    value = str(text or "").strip()
    value = VERIFY_PATH_RE.sub("<VERIFY_WT>", value)
    value = WORKTREE_RE.sub("<WORKTREE>", value)
    value = VERIFY_LOG_RE.sub("<VERIFY_LOG>", value)
    value = SHA_RE.sub("<SHA>", value)
    value = STAMP_RE.sub("<STAMP>", value)
    value = DURATION_RE.sub("<TIME>", value)
    value = PORT_RE.sub("<PORT>", value)
    value = LINE_COL_RE.sub(":<LINE>", value)
    value = PID_RE.sub("pid=<PID>", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _interesting_lines(text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in str(text or "").splitlines():
        low = raw.lower()
        if not (
            "error" in low
            or "fail" in low
            or "timeout" in low
            or "expected" in low
            or "received" in low
            or "exception" in low
            or "traceback" in low
            or re.search(r"\b[1-9]\d* failed\b", low)
        ):
            continue
        line = normalize_failure_text(raw)
        if not line or line in seen:
            continue
        seen.add(line)
        out.append(line)
    return out


def semantic_signature(kind: str, text: str, summary: str = "") -> str:
    low = str(text or "").lower()
    for family, predicate in KNOWN_FAMILIES:
        if predicate(low):
            return f"{kind.strip().lower()}::{family}"

    interesting = _interesting_lines(text)
    if interesting:
        # The tail usually contains the deepest exception/assertion rather than
        # wrapper noise. Keep enough context to distinguish real product bugs.
        payload = interesting[-24:]
    else:
        payload = [normalize_failure_text(summary or text or kind)]

    normalized_summary = normalize_failure_text(summary)
    if normalized_summary:
        payload.insert(0, f"summary={normalized_summary}")

    return kind.strip().lower() + "::" + "\n".join(payload)


def semantic_fingerprint(kind: str, text: str, summary: str = "") -> tuple[str, str]:
    signature = semantic_signature(kind, text, summary)
    fingerprint = hashlib.sha256(signature.encode("utf-8")).hexdigest()
    return fingerprint, signature


def read_logs(paths: Iterable[str], *, tail_bytes: int = 120000) -> tuple[list[tuple[str, str]], str]:
    texts: list[tuple[str, str]] = []
    for name in paths:
        path = Path(str(name))
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        texts.append((str(path), text[-tail_bytes:]))
    combined = "\n".join(text for _, text in texts)
    return texts, combined


def row_logs(row: sqlite3.Row) -> list[str]:
    try:
        value = json.loads(row["logs_json"] or "[]")
    except (json.JSONDecodeError, TypeError):
        return []
    return [str(item) for item in value] if isinstance(value, list) else []


def row_semantic_fingerprint(row: sqlite3.Row) -> tuple[str, str]:
    _, combined = read_logs(row_logs(row))
    if not combined.strip():
        # Missing historical logs are not evidence that two failures share a
        # root cause. Keep the legacy row isolated rather than deduping from a
        # generic summary alone.
        legacy = str(row["fingerprint"] or "")
        signature = f"{str(row['kind'] or '').lower()}::legacy-log-unavailable::{legacy}"
        return hashlib.sha256(signature.encode("utf-8")).hexdigest(), signature
    return semantic_fingerprint(
        str(row["kind"] or ""),
        combined,
        str(row["summary"] or ""),
    )




def semantic_groups(
    conn: sqlite3.Connection,
    *,
    statuses: tuple[str, ...] = ("OPEN",),
) -> list[dict]:
    marks = ",".join("?" for _ in statuses)
    rows = list(
        conn.execute(
            f"""select * from regressions
                 where status in ({marks})
                 order by id""",
            statuses,
        )
    )
    grouped: dict[tuple[str, str], list[sqlite3.Row]] = {}
    signatures: dict[tuple[str, str], str] = {}
    for row in rows:
        fingerprint, signature = row_semantic_fingerprint(row)
        key = (str(row["kind"] or ""), fingerprint)
        grouped.setdefault(key, []).append(row)
        signatures[key] = signature

    result: list[dict] = []
    for (kind, fingerprint), members in grouped.items():
        if len(members) < 2:
            continue
        result.append(
            {
                "kind": kind,
                "semantic_fingerprint": fingerprint,
                "signature": signatures[(kind, fingerprint)],
                "regression_ids": [int(row["id"]) for row in members],
                "task_ids": [
                    str(row["task_id"])
                    for row in members
                    if row["task_id"]
                ],
            }
        )
    return sorted(
        result,
        key=lambda item: (
            item["kind"],
            item["semantic_fingerprint"],
        ),
    )


def reconcile_semantic_duplicates(
    conn: sqlite3.Connection,
    *,
    apply: bool = False,
) -> dict:
    groups = semantic_groups(conn)
    active_tasks = {
        str(row[0])
        for row in conn.execute(
            """select task_id from brain_task_leases
                where lease_until_epoch>cast(strftime('%s','now') as real)"""
        )
    } if _table_exists(conn, "brain_task_leases") else set()

    actions: list[dict] = []
    skipped: list[dict] = []

    for group in groups:
        rows = [
            conn.execute(
                "select * from regressions where id=?",
                (regression_id,),
            ).fetchone()
            for regression_id in group["regression_ids"]
        ]
        rows = [row for row in rows if row is not None]
        if not rows:
            continue

        # Never supersede a repair that is actively being worked. If one is
        # active, it becomes the canonical representative of the semantic
        # failure family; otherwise preserve the oldest evidence row.
        canonical = min(
            rows,
            key=lambda row: (
                0 if str(row["task_id"] or "") in active_tasks else 1,
                int(row["id"]),
            ),
        )
        canonical_task = str(canonical["task_id"] or "")

        for row in rows:
            if int(row["id"]) == int(canonical["id"]):
                continue
            task_id = str(row["task_id"] or "")
            if task_id and task_id in active_tasks:
                skipped.append(
                    {
                        "regression_id": int(row["id"]),
                        "task_id": task_id,
                        "reason": "active lease",
                        "canonical_regression_id": int(canonical["id"]),
                    }
                )
                continue

            action = {
                "regression_id": int(row["id"]),
                "task_id": task_id or None,
                "canonical_regression_id": int(canonical["id"]),
                "canonical_task_id": canonical_task or None,
                "semantic_fingerprint": group["semantic_fingerprint"],
                "kind": group["kind"],
            }
            actions.append(action)
            if not apply:
                continue

            conn.execute(
                """update regressions
                      set status='SUPERSEDED'
                    where id=? and status='OPEN'""",
                (row["id"],),
            )
            if task_id:
                task = conn.execute(
                    "select status,lane,coalesce(note,'') from tasks where id=?",
                    (task_id,),
                ).fetchone()
                if task is not None:
                    status = str(task[0] or "")
                    lane = str(task[1] or "")
                    if lane == "regression" and status not in {
                        "DONE",
                        "RESOLVED",
                        "SUPERSEDED",
                        "CANCELLED",
                    }:
                        note = str(task[2] or "").rstrip()
                        marker = (
                            "Semantic duplicate of "
                            f"{canonical_task or ('regression '+str(canonical['id']))}; "
                            f"regression row {row['id']} and logs preserved; "
                            f"signature={group['semantic_fingerprint'][:12]}."
                        )
                        conn.execute(
                            """update tasks
                                  set status='SUPERSEDED',owner=null,
                                      note=?,updated_at=datetime('now')
                                where id=?""",
                            ((note + "\n" + marker).strip(), task_id),
                        )
                        conn.execute(
                            "delete from claims where task_id=?",
                            (task_id,),
                        ) if _table_exists(conn, "claims") else None
                        conn.execute(
                            "delete from brain_task_leases where task_id=?",
                            (task_id,),
                        ) if _table_exists(conn, "brain_task_leases") else None
                if _table_exists(conn, "integration_queue"):
                    conn.execute(
                        """update integration_queue
                              set status='SUPERSEDED',
                                  updated_at=datetime('now'),
                                  note=case
                                    when coalesce(note,'')='' then ?
                                    else note || char(10) || ?
                                  end
                            where task_id=?
                              and status not in (
                                'INTEGRATED','SUPERSEDED','QUARANTINED'
                              )""",
                        (
                            f"Semantic duplicate of {canonical_task or canonical['id']}.",
                            f"Semantic duplicate of {canonical_task or canonical['id']}.",
                            task_id,
                        ),
                    )

    if apply:
        conn.commit()
    return {
        "apply": apply,
        "groups": groups,
        "actions": actions,
        "skipped": skipped,
        "counts": {
            "groups": len(groups),
            "duplicates": len(actions),
            "skipped": len(skipped),
        },
    }


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        """select 1 from sqlite_master
            where type='table' and name=?""",
        (name,),
    ).fetchone() is not None


def find_semantic_duplicate(
    conn: sqlite3.Connection,
    *,
    kind: str,
    fingerprint: str,
    statuses: tuple[str, ...] = ("OPEN",),
) -> sqlite3.Row | None:
    marks = ",".join("?" for _ in statuses)
    rows = conn.execute(
        f"""select * from regressions
             where kind=? and status in ({marks})
             order by id""",
        (kind, *statuses),
    )
    for row in rows:
        existing, _ = row_semantic_fingerprint(row)
        if existing == fingerprint:
            return row
    return None
