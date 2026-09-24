from __future__ import annotations

import sqlite3
from collections.abc import Callable


TASK_SATISFIED = {"DONE", "RESOLVED", "INTEGRATED"}
HARD_DEPENDENCY_KINDS = {"hard", "integration"}


def dependency_requires_integration(kind: str | None) -> bool:
    return str(kind or "").lower() == "integration"


def _applied_preflight_result_satisfied(
    conn: sqlite3.Connection,
    depends_on: str,
    candidate_sha: str,
    *,
    integration_head: str,
    ancestor_checker: Callable[[str, str], bool],
) -> bool:
    try:
        rows = conn.execute(
            """
            select p.result_sha
              from integration_preflight_items i
              join integration_preflights p on p.id=i.preflight_id
             where i.task_id=?
               and i.candidate_sha=?
               and p.status in ('APPLIED','STALE')
               and p.verification_mode='full-e2e'
               and p.result_sha is not null
             order by p.id desc
            """,
            (depends_on, candidate_sha),
        ).fetchall()
    except sqlite3.OperationalError:
        # Older/runtime-minimal databases may not have preflight lineage tables.
        # Fail closed here; the direct integrated-ancestor path remains valid.
        # STALE is accepted only through this helper, which is called solely
        # for the exact candidate from an INTEGRATED queue row. This covers
        # post-apply validation races without treating arbitrary stale
        # preflights as canonical integration proof.
        return False

    for row in rows:
        result_sha = str(row[0] or "")
        if len(result_sha) != 40:
            continue
        if ancestor_checker(result_sha, integration_head):
            return True
    return False


def integration_prerequisite_satisfied(
    conn: sqlite3.Connection,
    depends_on: str,
    *,
    integration_head: str | None,
    ancestor_checker: Callable[[str, str], bool],
) -> bool:
    if not integration_head:
        return False

    task = conn.execute(
        "select status from tasks where id=?",
        (depends_on,),
    ).fetchone()
    if task is None or str(task[0] or "") not in TASK_SATISFIED:
        return False

    try:
        rows = conn.execute(
            """select sha
                 from integration_queue
                where task_id=? and status='INTEGRATED'
                order by coalesce(integrated_at,updated_at,queued_at,'') desc,sha""",
            (depends_on,),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = conn.execute(
            """select sha
                 from integration_queue
                where task_id=? and status='INTEGRATED'
                order by sha""",
            (depends_on,),
        ).fetchall()

    for row in rows:
        candidate = str(row[0] or "")
        if len(candidate) != 40:
            continue
        if ancestor_checker(candidate, integration_head):
            return True
        if _applied_preflight_result_satisfied(
            conn,
            depends_on,
            candidate,
            integration_head=integration_head,
            ancestor_checker=ancestor_checker,
        ):
            return True
    return False


def hard_dependency_satisfied(
    conn: sqlite3.Connection,
    *,
    kind: str,
    depends_on: str,
    dep_status: str | None,
    integration_head: str | None,
    ancestor_checker: Callable[[str, str], bool],
) -> bool:
    kind = str(kind or "hard").lower()
    if kind == "hard":
        return str(dep_status or "MISSING") in TASK_SATISFIED
    if kind == "integration":
        return integration_prerequisite_satisfied(
            conn,
            depends_on,
            integration_head=integration_head,
            ancestor_checker=ancestor_checker,
        )
    return True


def hard_dependencies_satisfied(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    integration_head: str | None,
    ancestor_checker: Callable[[str, str], bool],
) -> bool:
    rows = conn.execute(
        """select d.depends_on,d.kind,coalesce(t.status,'MISSING')
             from task_dependencies d
             left join tasks t on t.id=d.depends_on
            where d.task_id=?
              and d.kind in ('hard','integration')
            order by d.depends_on""",
        (task_id,),
    ).fetchall()
    return all(
        hard_dependency_satisfied(
            conn,
            kind=row[1],
            depends_on=str(row[0]),
            dep_status=row[2],
            integration_head=integration_head,
            ancestor_checker=ancestor_checker,
        )
        for row in rows
    )
