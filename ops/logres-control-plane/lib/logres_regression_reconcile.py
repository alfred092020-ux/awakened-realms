from __future__ import annotations

import sqlite3


TERMINAL_REGRESSION_STATES = ("RESOLVED", "SUPERSEDED")
TERMINAL_TASK_STATES = ("DONE", "RESOLVED", "SUPERSEDED", "CANCELLED")


def repair_task_regression_terminal(
    conn: sqlite3.Connection,
    task_id: str,
) -> bool:
    row = conn.execute(
        """
        select 1
          from regressions
         where task_id=?
           and status in ('RESOLVED','SUPERSEDED')
         limit 1
        """,
        (task_id,),
    ).fetchone()
    return row is not None


def _supersede_descendant_conflicts(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        select child.id, child.task_id
          from regressions child
         where child.status='OPEN'
           and child.kind='integration-conflict'
           and exists (
             select 1
               from integration_queue parent_q
               join regressions parent_r
                 on parent_r.task_id=parent_q.task_id
              where parent_q.branch=child.ref
                and parent_q.sha=child.sha
                and parent_r.status in ('RESOLVED','SUPERSEDED')
           )
        """
    ).fetchall()
    if not rows:
        return 0

    ids = [int(row[0]) for row in rows]
    task_ids = [str(row[1]) for row in rows if row[1]]
    placeholders = ",".join("?" for _ in ids)
    conn.execute(
        f"update regressions set status='SUPERSEDED' "
        f"where id in ({placeholders}) and status='OPEN'",
        ids,
    )

    if task_ids:
        task_placeholders = ",".join("?" for _ in task_ids)
        params = [*task_ids, *TERMINAL_TASK_STATES]
        conn.execute(
            f"update tasks set status='SUPERSEDED' "
            f"where id in ({task_placeholders}) "
            f"and status not in ({','.join('?' for _ in TERMINAL_TASK_STATES)})",
            params,
        )
    return len(ids)


def _supersede_terminal_repair_queue_rows(conn: sqlite3.Connection) -> int:
    return int(
        conn.execute(
            """
            update integration_queue
               set status='SUPERSEDED'
             where status not in ('INTEGRATED','SUPERSEDED')
               and exists (
                 select 1
                   from regressions r
                  where r.task_id=integration_queue.task_id
                    and r.status in ('RESOLVED','SUPERSEDED')
               )
            """
        ).rowcount
    )


def reconcile_regression_states(conn: sqlite3.Connection) -> tuple[int, int]:
    resolved = conn.execute(
        """
        update regressions
           set status='RESOLVED'
         where status='OPEN'
           and task_id is not null
           and exists (
             select 1 from integration_queue iq
              where iq.task_id=regressions.task_id
                and iq.status='INTEGRATED'
           )
        """
    ).rowcount

    superseded = conn.execute(
        """
        update regressions
           set status='SUPERSEDED'
         where status='OPEN'
           and task_id is not null
           and exists (
             select 1 from tasks t
              where t.id=regressions.task_id
                and t.status='SUPERSEDED'
           )
        """
    ).rowcount

    superseded += _supersede_descendant_conflicts(conn)
    _supersede_terminal_repair_queue_rows(conn)
    return int(resolved), int(superseded)
