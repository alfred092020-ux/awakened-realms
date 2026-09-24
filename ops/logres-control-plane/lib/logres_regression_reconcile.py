from __future__ import annotations

import sqlite3


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
    return int(resolved), int(superseded)
