from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class SupersedeTarget:
    regression_id: int
    task_id: str
    kind: str
    ref: str
    failed_preflight_id: int
    failed_tasks: tuple[str, ...]


def _tasks(raw: str | None) -> frozenset[str]:
    try:
        values = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return frozenset()
    if not isinstance(values, list):
        return frozenset()
    return frozenset(str(value) for value in values if str(value).strip())


def successful_preflight(conn: sqlite3.Connection, preflight_id: int) -> sqlite3.Row:
    row = conn.execute(
        "select * from integration_preflights where id=?",
        (preflight_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"unknown preflight: {preflight_id}")
    if str(row["status"]) not in {"VERIFIED", "APPLIED"}:
        raise ValueError(
            f"preflight {preflight_id} is {row['status']}; VERIFIED/APPLIED required"
        )
    if not _tasks(row["tasks_json"]):
        raise ValueError(f"preflight {preflight_id} has no task set")
    return row


def plan_supersede(
    conn: sqlite3.Connection,
    preflight_id: int,
) -> list[SupersedeTarget]:
    success = successful_preflight(conn, preflight_id)
    success_tasks = _tasks(success["tasks_json"])
    created_epoch = float(success["created_epoch"])
    targets: list[SupersedeTarget] = []
    seen: set[int] = set()

    regressions = conn.execute(
        """select *
             from regressions
            where status='OPEN'
              and kind='merge-preflight'
              and created_epoch < ?
            order by created_epoch desc,id desc""",
        (created_epoch,),
    ).fetchall()

    for regression in regressions:
        ref = str(regression["ref"] or "")
        if not ref:
            continue
        failed = conn.execute(
            """select *
                 from integration_preflights
                where result_sha=? and status='FAILED'
                order by id desc
                limit 1""",
            (ref,),
        ).fetchone()
        if failed is None:
            continue
        failed_tasks = _tasks(failed["tasks_json"])
        if not failed_tasks or not failed_tasks.issubset(success_tasks):
            continue

        rows = [regression]
        rows.extend(
            conn.execute(
                """select *
                     from regressions
                    where status='OPEN'
                      and kind='candidate-verify'
                      and ref=?
                    order by id""",
                (ref,),
            ).fetchall()
        )
        for row in rows:
            row_id = int(row["id"])
            if row_id in seen:
                continue
            seen.add(row_id)
            targets.append(
                SupersedeTarget(
                    regression_id=row_id,
                    task_id=str(row["task_id"] or ""),
                    kind=str(row["kind"] or ""),
                    ref=ref,
                    failed_preflight_id=int(failed["id"]),
                    failed_tasks=tuple(sorted(failed_tasks)),
                )
            )
    return sorted(targets, key=lambda item: item.regression_id)


def apply_supersede(
    conn: sqlite3.Connection,
    preflight_id: int,
    *,
    active_task_ids: set[str] | None = None,
) -> dict:
    active = active_task_ids or set()
    targets = plan_supersede(conn, preflight_id)
    changed: list[dict] = []
    preserved_active: list[str] = []

    for target in targets:
        cursor = conn.execute(
            "update regressions set status='SUPERSEDED' where id=? and status='OPEN'",
            (target.regression_id,),
        )
        if cursor.rowcount != 1:
            continue

        task_id = target.task_id
        if task_id:
            if task_id in active:
                preserved_active.append(task_id)
            else:
                conn.execute(
                    """update tasks
                          set status='SUPERSEDED',
                              owner=null,
                              branch=null,
                              note=?,
                              updated_at=datetime('now')
                        where id=?
                          and status not in ('DONE','RESOLVED','SUPERSEDED','CANCELLED')""",
                    (
                        f"Superseded by successful preflight {preflight_id}; "
                        f"failed preflight {target.failed_preflight_id} task set "
                        f"is a subset of the successful batch.",
                        task_id,
                    ),
                )
                conn.execute(
                    """update integration_queue
                          set status='SUPERSEDED',
                              updated_at=datetime('now'),
                              note=coalesce(note,'') || ?
                        where task_id=?
                          and status not in ('INTEGRATED','SUPERSEDED')""",
                    (
                        f" | superseded by successful preflight {preflight_id}",
                        task_id,
                    ),
                )

        changed.append(
            {
                "regression_id": target.regression_id,
                "task_id": task_id,
                "kind": target.kind,
                "ref": target.ref,
                "failed_preflight_id": target.failed_preflight_id,
                "failed_tasks": list(target.failed_tasks),
            }
        )

    conn.commit()
    return {
        "preflight_id": preflight_id,
        "superseded": changed,
        "preserved_active_tasks": sorted(set(preserved_active)),
    }
