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
    proof: str
    failed_preflight_id: int | None
    failed_tasks: tuple[str, ...]


def _tasks(raw: str | None) -> frozenset[str]:
    try:
        values = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return frozenset()
    if not isinstance(values, list):
        return frozenset()
    return frozenset(str(value) for value in values if str(value).strip())


def _successful_task_coverage(
    conn: sqlite3.Connection,
    success_tasks: frozenset[str],
) -> tuple[frozenset[str], frozenset[str]]:
    """Expand successful task coverage by one explicit verified carrier hop.

    The expansion is intentionally narrow:
    - only task_dependencies.kind == integration_carrier
    - the carrier itself must be in the successful preflight task set
    - the carrier must have an INTEGRATED queue row
    - newly covered originals are not recursively expanded
    """
    covered = set(success_tasks)
    carrier_covered: set[str] = set()
    if not success_tasks:
        return frozenset(), frozenset()

    try:
        rows = conn.execute(
            """select task_id,depends_on
                 from task_dependencies
                where kind='integration_carrier'
                order by task_id,depends_on"""
        ).fetchall()
    except sqlite3.OperationalError:
        # Runtime-minimal / historical DBs may not expose task_dependencies.
        # Missing explicit lineage must fail closed rather than infer carriers.
        return frozenset(covered), frozenset()

    for row in rows:
        original = str(row[0] or "")
        carrier = str(row[1] or "")
        if not original or carrier not in success_tasks:
            continue

        try:
            integrated = conn.execute(
                """select 1
                     from integration_queue
                    where task_id=? and status='INTEGRATED'
                    limit 1""",
                (carrier,),
            ).fetchone()
        except sqlite3.OperationalError:
            integrated = None

        if integrated is None:
            continue

        covered.add(original)
        carrier_covered.add(original)

    return frozenset(covered), frozenset(carrier_covered)


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
    covered_tasks, carrier_covered_tasks = _successful_task_coverage(
        conn,
        success_tasks,
    )
    created_epoch = float(success["created_epoch"])
    targets: list[SupersedeTarget] = []
    seen: set[int] = set()

    success_result = str(success["result_sha"] or "")
    verification_mode = (
        str(success["verification_mode"] or "")
        if "verification_mode" in success.keys()
        else ""
    )
    if (
        len(success_result) == 40
        and verification_mode == "full-e2e"
    ):
        exact_rows = conn.execute(
            """select *
                 from regressions
                where status='OPEN'
                  and kind in ('candidate-verify','merge-preflight')
                  and ref=?
                  and created_epoch < ?
                order by id""",
            (success_result, created_epoch),
        ).fetchall()
        for row in exact_rows:
            row_id = int(row["id"])
            seen.add(row_id)
            targets.append(
                SupersedeTarget(
                    regression_id=row_id,
                    task_id=str(row["task_id"] or ""),
                    kind=str(row["kind"] or ""),
                    ref=success_result,
                    proof="exact-result-sha",
                    failed_preflight_id=None,
                    failed_tasks=(),
                )
            )

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
        if not failed_tasks or not failed_tasks.issubset(covered_tasks):
            continue

        proof = (
            "failed-task-carrier-subset"
            if any(task in carrier_covered_tasks for task in failed_tasks)
            else "failed-task-subset"
        )

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
                    proof=proof,
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
                if target.proof == "exact-result-sha":
                    note = (
                        f"Superseded by successful full-e2e preflight "
                        f"{preflight_id} at exact result SHA {target.ref}."
                    )
                elif target.proof == "failed-task-carrier-subset":
                    note = (
                        f"Superseded by successful preflight {preflight_id}; "
                        f"failed preflight {target.failed_preflight_id} task set "
                        f"is covered by explicit integrated carrier lineage."
                    )
                else:
                    note = (
                        f"Superseded by successful preflight {preflight_id}; "
                        f"failed preflight {target.failed_preflight_id} task set "
                        f"is a subset of the successful batch."
                    )
                conn.execute(
                    """update tasks
                          set status='SUPERSEDED',
                              owner=null,
                              branch=null,
                              note=?,
                              updated_at=datetime('now')
                        where id=?
                          and status not in ('DONE','RESOLVED','SUPERSEDED','CANCELLED')""",
                    (note, task_id),
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
                "proof": target.proof,
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
