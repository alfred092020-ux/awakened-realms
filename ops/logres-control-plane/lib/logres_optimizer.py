from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass

from logres_knowledge import ensure_schema as ensure_knowledge_schema
from logres_knowledge import task_knowledge


SATISFIED = {"DONE", "RESOLVED", "INTEGRATED"}


@dataclass(frozen=True)
class OptimizedTask:
    task_id: str
    score: float
    priority: int
    work_type: str
    expected_minutes: int
    critical_path_minutes: int
    downstream_count: int
    knowledge_support: float
    knowledge_gap: float
    engine_success_rate: float
    rationale: tuple[str, ...]

    def to_dict(self) -> dict:
        value = asdict(self)
        value["rationale"] = list(self.rationale)
        return value


def _hard_deps_satisfied(conn: sqlite3.Connection, task_id: str) -> bool:
    rows = conn.execute(
        """select t.status
             from task_dependencies d
             left join tasks t on t.id=d.depends_on
            where d.task_id=? and d.kind='hard'""",
        (task_id,),
    ).fetchall()
    return all((row[0] or "MISSING") in SATISFIED for row in rows)


def _downstream_count(conn: sqlite3.Connection, task_id: str) -> int:
    seen: set[str] = set()
    frontier = [task_id]
    while frontier:
        current = frontier.pop()
        for row in conn.execute(
            "select task_id from task_dependencies where depends_on=?",
            (current,),
        ):
            child = row[0]
            if child not in seen:
                seen.add(child)
                frontier.append(child)
    return len(seen)


def _critical_path(
    conn: sqlite3.Connection,
    task_id: str,
    memo: dict[str, int],
    visiting: set[str],
) -> int:
    if task_id in memo:
        return memo[task_id]
    if task_id in visiting:
        return 0
    visiting.add(task_id)
    row = conn.execute(
        """select t.status,coalesce(m.expected_minutes,60)
             from tasks t
             left join task_metadata m on m.task_id=t.id
            where t.id=?""",
        (task_id,),
    ).fetchone()
    if row is None:
        visiting.remove(task_id)
        return 0
    own = 0 if row[0] in SATISFIED else int(row[1] or 60)
    children = [
        r[0]
        for r in conn.execute(
            """select d.task_id
                 from task_dependencies d
                 left join tasks t on t.id=d.task_id
                where d.depends_on=? and d.kind='hard'
                  and coalesce(t.status,'MISSING')
                      not in ('DONE','RESOLVED','INTEGRATED')""",
            (task_id,),
        )
    ]
    tail = max(
        (_critical_path(conn, child, memo, visiting) for child in children),
        default=0,
    )
    visiting.remove(task_id)
    memo[task_id] = own + tail
    return memo[task_id]


def engine_success_rate(
    conn: sqlite3.Connection,
    *,
    engine: str,
    work_type: str,
) -> float:
    try:
        rows = list(
            conn.execute(
                """select outcome from optimizer_observations
                    where engine=? and (work_type=? or work_type is null)
                    order by id desc limit 30""",
                (engine, work_type),
            )
        )
    except sqlite3.OperationalError:
        return 0.75
    useful_weights = {
        "DONE": 1.0,
        "INTEGRATED": 1.0,
        "PASS": 1.0,
        # A bounded evidence result is useful research even when it cannot
        # satisfy the parent predicate. Treat it as partial success.
        "BLOCKED": 0.65,
        "FAILED": 0.0,
    }
    weighted = [
        useful_weights[row[0]]
        for row in rows
        if row[0] in useful_weights
    ]
    if not weighted:
        return 0.75
    return max(0.10, min(1.0, sum(weighted) / len(weighted)))


def record_swarm_observations(conn: sqlite3.Connection) -> int:
    ensure_knowledge_schema(conn)

    # Add immutable source-job identity lazily so observation ingestion remains
    # idempotent across upgrades from the initial knowledge schema.
    columns = {
        row[1]
        for row in conn.execute("pragma table_info(optimizer_observations)")
    }
    if "source_job_id" not in columns:
        conn.execute(
            "alter table optimizer_observations add column source_job_id integer"
        )
        conn.execute(
            "create unique index if not exists idx_optimizer_source_job "
            "on optimizer_observations(source_job_id) "
            "where source_job_id is not null"
        )
        conn.commit()

    try:
        rows = list(
            conn.execute(
                """select s.id,s.task_id,s.engine,s.state,s.started_at,s.finished_at,
                          m.work_type,
                          (select sum(coalesce(u.estimated_cost_usd,0))
                             from api_usage u where u.task_id=s.task_id) cost,
                          s.artifact_path,s.last_error
                     from swarm_jobs s
                     left join task_metadata m on m.task_id=s.task_id
                    where s.state in ('DONE','BLOCKED','FAILED')
                      and not exists(
                        select 1 from optimizer_observations o
                         where o.source_job_id=s.id
                      )"""
            )
        )
    except sqlite3.OperationalError:
        return 0

    inserted = 0
    for row in rows:
        if conn.execute(
            "select 1 from optimizer_observations where source_job_id=?",
            (row[0],),
        ).fetchone():
            continue
        duration = None
        if row[4] and row[5]:
            try:
                duration = float(
                    conn.execute(
                        "select (julianday(?) - julianday(?))*86400.0",
                        (row[5], row[4]),
                    ).fetchone()[0]
                )
            except (TypeError, ValueError):
                duration = None
        if row[3] == "FAILED" and not row[8]:
            # Transport, credential, schema and process failures are control-
            # plane reliability signals, not evidence that the research/code
            # engine is bad at the task. Preserve them but exclude from the
            # engine-success denominator.
            outcome = "INFRA_FAILURE"
        else:
            outcome = {
                "DONE": "DONE",
                "BLOCKED": "BLOCKED",
                "FAILED": "FAILED",
            }.get(row[3], row[3])
        conn.execute(
            """insert into optimizer_observations(
                 task_id,engine,work_type,outcome,duration_seconds,
                 estimated_cost_usd,source_job_id
               ) values(?,?,?,?,?,?,?)""",
            (row[1], row[2], row[6], outcome, duration, row[7], row[0]),
        )
        inserted += 1
    conn.commit()
    return inserted


def score_ready_tasks(
    conn: sqlite3.Connection,
    *,
    work_type_filter: set[str] | None = None,
) -> list[OptimizedTask]:
    ensure_knowledge_schema(conn)
    memo: dict[str, int] = {}
    scored: list[OptimizedTask] = []
    rows = conn.execute(
        """select t.id,t.priority,t.title,
                  coalesce(m.work_type,'implementation') work_type,
                  coalesce(m.expected_minutes,60) expected_minutes,
                  coalesce(m.evidence_policy,'') evidence_policy
             from tasks t
             left join task_metadata m on m.task_id=t.id
            where t.status='READY'"""
    )
    for row in rows:
        task_id = row[0]
        work_type = str(row[3])
        if work_type_filter and work_type not in work_type_filter:
            continue
        if not _hard_deps_satisfied(conn, task_id):
            continue

        priority = int(row[1] if row[1] is not None else 9)
        expected = max(5, int(row[4] or 60))
        downstream = _downstream_count(conn, task_id)
        critical = _critical_path(conn, task_id, memo, set())
        knowledge = task_knowledge(conn, task_id)
        support = knowledge.support_score
        gap = 1.0 - support

        engine = "research" if work_type in {"research", "evidence", "analysis"} else "copilot"
        success = engine_success_rate(conn, engine=engine, work_type=work_type)

        # Priority is a hard strategic axis. Within a priority band, favor
        # work that shortens the longest dependency chain, unlocks descendants,
        # closes high-value evidence gaps, has a reliable engine, and is cheap.
        score = 1_000_000.0 - priority * 100_000.0
        score += critical * 180.0
        score += downstream * 8_000.0
        score += success * 10_000.0
        score -= expected * 35.0

        rationale = [
            f"P{priority}",
            f"critical={critical}m",
            f"unlocks={downstream}",
            f"expected={expected}m",
            f"engine_success={success:.2f}",
        ]

        if work_type in {"research", "evidence", "analysis"}:
            evidence_bonus = gap * 18_000.0
            if "global" in str(row[5]).lower():
                evidence_bonus *= 1.20
                rationale.append("Global-evidence-gap")
            score += evidence_bonus
            rationale.append(f"knowledge_gap={gap:.2f}")
            rationale.append(
                f"support={support:.2f}/{knowledge.discovery_count} discoveries"
            )

        scored.append(
            OptimizedTask(
                task_id=task_id,
                score=round(score, 3),
                priority=priority,
                work_type=work_type,
                expected_minutes=expected,
                critical_path_minutes=critical,
                downstream_count=downstream,
                knowledge_support=round(support, 4),
                knowledge_gap=round(gap, 4),
                engine_success_rate=round(success, 4),
                rationale=tuple(rationale),
            )
        )

    scored.sort(key=lambda item: (-item.score, item.task_id))
    return scored


def rank_task_ids(
    conn: sqlite3.Connection,
    *,
    limit: int = 8,
    work_type_filter: set[str] | None = None,
) -> list[str]:
    return [
        item.task_id
        for item in score_ready_tasks(
            conn,
            work_type_filter=work_type_filter,
        )[: max(1, limit)]
    ]
