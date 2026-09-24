from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


GENERATED_NOTE_MARKERS = (
    "autoflow research child from ai evidence routing",
    "auto-routed from brain event",
)
TERMINAL = {"DONE", "RESOLVED", "SUPERSEDED", "CANCELLED"}
SATURATED_CHILD_STATES = {"BLOCKED_EVIDENCE", "SUPERSEDED", "CANCELLED"}
MAX_GENERATED_DEPTH = 1


@dataclass(frozen=True)
class FrontierClaim:
    root_task_id: str
    parent_task_id: str
    predicate_sha: str
    predicate: str
    frontier_id: int | None
    child_task_id: str | None
    state: str
    create_allowed: bool
    reason: str
    parent_depth: int


@dataclass(frozen=True)
class Lineage:
    child_task_id: str
    parent_task_id: str | None
    root_task_id: str
    predicate_sha: str
    origin_kind: str
    origin_id: str | None
    depth: int


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists research_frontier(
          id integer primary key autoincrement,
          root_task_id text not null,
          predicate_sha text not null,
          predicate text not null,
          state text not null default 'OPEN',
          child_task_id text,
          origin_kind text not null,
          origin_id text,
          attempts integer not null default 0,
          max_attempts integer not null default 1,
          last_event_id integer,
          last_artifact_sha text,
          note text not null default '',
          created_at text not null,
          updated_at text not null,
          unique(root_task_id,predicate_sha)
        );
        create index if not exists idx_research_frontier_state
          on research_frontier(state);
        create index if not exists idx_research_frontier_child
          on research_frontier(child_task_id);

        create table if not exists research_lineage(
          child_task_id text primary key,
          parent_task_id text,
          root_task_id text not null,
          predicate_sha text not null,
          origin_kind text not null,
          origin_id text,
          depth integer not null,
          created_at text not null
        );
        create index if not exists idx_research_lineage_root
          on research_lineage(root_task_id);
        """
    )
    conn.commit()


def normalize_predicate(text: str, parent_task_id: str | None = None) -> str:
    value = str(text or "").strip().lower()
    if parent_task_id:
        value = value.replace(parent_task_id.lower(), "<task>")
    value = re.sub(r"\bbrain event\s+\d+\b", "brain event <n>", value)
    value = re.sub(r"\broute\s+\d+\b", "route <n>", value)
    value = re.sub(r"\b[0-9a-f]{8,64}\b", "<hex>", value)
    value = re.sub(r"\s+", " ", value)
    value = value.strip(" .;:-")
    return value or "unresolved evidence predicate"


def predicate_sha(text: str, parent_task_id: str | None = None) -> str:
    normalized = normalize_predicate(text, parent_task_id)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def task_row(conn: sqlite3.Connection, task_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "select * from tasks where id=?",
        (task_id,),
    ).fetchone()


def task_metadata(conn: sqlite3.Connection, task_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "select * from task_metadata where task_id=?",
        (task_id,),
    ).fetchone()


def is_generated_research_task(
    conn: sqlite3.Connection,
    task_id: str | None,
) -> bool:
    if not task_id:
        return False
    ensure_schema(conn)
    if conn.execute(
        "select 1 from research_lineage where child_task_id=?",
        (task_id,),
    ).fetchone():
        return True
    task = task_row(conn, task_id)
    meta = task_metadata(conn, task_id)
    if task is None or meta is None:
        return False
    if str(meta["work_type"] or "").lower() != "research":
        return False
    note = str(task["note"] or "").lower()
    milestone = str(meta["milestone"] or "").lower()
    return (
        milestone == "autoflow"
        or any(marker in note for marker in GENERATED_NOTE_MARKERS)
    )


def _inferred_parent(conn: sqlite3.Connection, child_task_id: str) -> str | None:
    row = conn.execute(
        """select depends_on
             from task_dependencies
            where task_id=? and kind='evidence'
            order by rowid limit 1""",
        (child_task_id,),
    ).fetchone()
    if row:
        return str(row[0])

    row = conn.execute(
        """select task_id
             from task_dependencies
            where depends_on=? and kind='hard'
              and lower(coalesce(rationale,'')) like '%auto-routed blocker%'
            order by rowid limit 1""",
        (child_task_id,),
    ).fetchone()
    if row:
        return str(row[0])
    return None


def lineage_for_task(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    backfill: bool = False,
    _seen: set[str] | None = None,
) -> Lineage | None:
    ensure_schema(conn)
    row = conn.execute(
        """select child_task_id,parent_task_id,root_task_id,predicate_sha,
                  origin_kind,origin_id,depth
             from research_lineage where child_task_id=?""",
        (task_id,),
    ).fetchone()
    if row:
        return Lineage(
            child_task_id=row[0],
            parent_task_id=row[1],
            root_task_id=row[2],
            predicate_sha=row[3],
            origin_kind=row[4],
            origin_id=row[5],
            depth=int(row[6]),
        )

    if not is_generated_research_task(conn, task_id):
        return None

    seen = set() if _seen is None else set(_seen)
    if task_id in seen:
        return None
    seen.add(task_id)

    parent = _inferred_parent(conn, task_id)
    if not parent:
        return Lineage(
            child_task_id=task_id,
            parent_task_id=None,
            root_task_id=task_id,
            predicate_sha="",
            origin_kind="LEGACY_INFERRED",
            origin_id=None,
            depth=1,
        )

    parent_lineage = lineage_for_task(
        conn,
        parent,
        backfill=backfill,
        _seen=seen,
    )
    if parent_lineage is None:
        root = parent
        depth = 1
    else:
        root = parent_lineage.root_task_id
        depth = parent_lineage.depth + 1

    criteria = [
        str(r[0])
        for r in conn.execute(
            "select criterion from task_acceptance where task_id=? order by ordinal",
            (task_id,),
        )
    ]
    task = task_row(conn, task_id)
    text = " | ".join(criteria) or str(task["title"] if task else task_id)
    psha = predicate_sha(text, parent)

    lineage = Lineage(
        child_task_id=task_id,
        parent_task_id=parent,
        root_task_id=root,
        predicate_sha=psha,
        origin_kind="LEGACY_INFERRED",
        origin_id=None,
        depth=depth,
    )
    if backfill:
        conn.execute(
            """insert or ignore into research_lineage(
                 child_task_id,parent_task_id,root_task_id,predicate_sha,
                 origin_kind,origin_id,depth,created_at
               ) values(?,?,?,?,?,?,?,?)""",
            (
                lineage.child_task_id,
                lineage.parent_task_id,
                lineage.root_task_id,
                lineage.predicate_sha,
                lineage.origin_kind,
                lineage.origin_id,
                lineage.depth,
                _now(),
            ),
        )
        conn.commit()
    return lineage


def root_and_depth(conn: sqlite3.Connection, task_id: str) -> tuple[str, int]:
    lineage = lineage_for_task(conn, task_id)
    if lineage is None:
        return task_id, 0
    return lineage.root_task_id, lineage.depth


def _sync_frontier_row(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
) -> sqlite3.Row:
    child = row["child_task_id"]
    if not child:
        return row
    status_row = conn.execute(
        "select status from tasks where id=?",
        (child,),
    ).fetchone()
    if not status_row:
        return row
    status = str(status_row[0] or "")
    state = str(row["state"])
    if status in {"DONE", "RESOLVED"}:
        state = "RESOLVED"
    elif status in SATURATED_CHILD_STATES:
        state = "SATURATED"
    elif status in {"READY", "ACTIVE", "BLOCKED_DEP"}:
        state = "OPEN"

    if state != row["state"]:
        conn.execute(
            "update research_frontier set state=?,updated_at=? where id=?",
            (state, _now(), row["id"]),
        )
        conn.commit()
        row = conn.execute(
            "select * from research_frontier where id=?",
            (row["id"],),
        ).fetchone()
    return row


def claim_frontier(
    conn: sqlite3.Connection,
    *,
    parent_task_id: str,
    predicate_text: str,
    origin_kind: str,
    origin_id: str | int | None = None,
    max_attempts: int = 1,
) -> FrontierClaim:
    ensure_schema(conn)
    root, parent_depth = root_and_depth(conn, parent_task_id)
    normalized = normalize_predicate(predicate_text, parent_task_id)
    psha = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    if parent_depth >= MAX_GENERATED_DEPTH:
        return FrontierClaim(
            root_task_id=root,
            parent_task_id=parent_task_id,
            predicate_sha=psha,
            predicate=normalized,
            frontier_id=None,
            child_task_id=None,
            state="SATURATED",
            create_allowed=False,
            reason=(
                f"generated research depth ceiling reached "
                f"({parent_depth}/{MAX_GENERATED_DEPTH})"
            ),
            parent_depth=parent_depth,
        )

    row = conn.execute(
        "select * from research_frontier where root_task_id=? and predicate_sha=?",
        (root, psha),
    ).fetchone()
    if row:
        row = _sync_frontier_row(conn, row)
        state = str(row["state"])
        attempts = int(row["attempts"] or 0)
        child = row["child_task_id"]
        if state == "RESOLVED":
            return FrontierClaim(
                root, parent_task_id, psha, normalized, int(row["id"]),
                child, state, False, "predicate already resolved", parent_depth
            )
        if child and state == "OPEN":
            return FrontierClaim(
                root, parent_task_id, psha, normalized, int(row["id"]),
                child, state, False, "equivalent research frontier already open",
                parent_depth
            )
        if attempts >= int(row["max_attempts"] or max_attempts):
            if state != "SATURATED":
                conn.execute(
                    "update research_frontier set state='SATURATED',updated_at=? where id=?",
                    (_now(), row["id"]),
                )
                conn.commit()
            return FrontierClaim(
                root, parent_task_id, psha, normalized, int(row["id"]),
                child, "SATURATED", False,
                "research attempt ceiling reached", parent_depth
            )

        return FrontierClaim(
            root, parent_task_id, psha, normalized, int(row["id"]),
            child, state, True, "frontier eligible for bounded research",
            parent_depth
        )

    now = _now()
    cur = conn.execute(
        """insert into research_frontier(
             root_task_id,predicate_sha,predicate,state,child_task_id,
             origin_kind,origin_id,attempts,max_attempts,created_at,updated_at
           ) values(?,?,?,'OPEN',null,?,?,0,?,?,?)""",
        (
            root,
            psha,
            normalized,
            origin_kind,
            str(origin_id) if origin_id is not None else None,
            max(1, int(max_attempts)),
            now,
            now,
        ),
    )
    conn.commit()
    return FrontierClaim(
        root_task_id=root,
        parent_task_id=parent_task_id,
        predicate_sha=psha,
        predicate=normalized,
        frontier_id=int(cur.lastrowid),
        child_task_id=None,
        state="OPEN",
        create_allowed=True,
        reason="new bounded research frontier",
        parent_depth=parent_depth,
    )


def register_child(
    conn: sqlite3.Connection,
    claim: FrontierClaim,
    *,
    child_task_id: str,
    origin_kind: str,
    origin_id: str | int | None = None,
) -> Lineage:
    ensure_schema(conn)
    depth = claim.parent_depth + 1
    if depth > MAX_GENERATED_DEPTH:
        raise ValueError(
            f"generated research depth {depth} exceeds {MAX_GENERATED_DEPTH}"
        )
    lineage = Lineage(
        child_task_id=child_task_id,
        parent_task_id=claim.parent_task_id,
        root_task_id=claim.root_task_id,
        predicate_sha=claim.predicate_sha,
        origin_kind=origin_kind,
        origin_id=str(origin_id) if origin_id is not None else None,
        depth=depth,
    )
    conn.execute(
        """insert or replace into research_lineage(
             child_task_id,parent_task_id,root_task_id,predicate_sha,
             origin_kind,origin_id,depth,created_at
           ) values(?,?,?,?,?,?,?,?)""",
        (
            lineage.child_task_id,
            lineage.parent_task_id,
            lineage.root_task_id,
            lineage.predicate_sha,
            lineage.origin_kind,
            lineage.origin_id,
            lineage.depth,
            _now(),
        ),
    )
    if claim.frontier_id is not None:
        conn.execute(
            """update research_frontier
                  set child_task_id=?,attempts=attempts+1,state='OPEN',
                      origin_kind=?,origin_id=?,updated_at=?
                where id=?""",
            (
                child_task_id,
                origin_kind,
                str(origin_id) if origin_id is not None else None,
                _now(),
                claim.frontier_id,
            ),
        )
    conn.commit()
    return lineage


def mark_frontier_from_child(
    conn: sqlite3.Connection,
    child_task_id: str,
) -> str | None:
    ensure_schema(conn)
    row = conn.execute(
        "select * from research_frontier where child_task_id=?",
        (child_task_id,),
    ).fetchone()
    if not row:
        return None
    synced = _sync_frontier_row(conn, row)
    return str(synced["state"])


def recursive_generated_tasks(
    conn: sqlite3.Connection,
    *,
    backfill: bool = False,
) -> list[dict]:
    ensure_schema(conn)
    rows = conn.execute(
        """select t.id,t.status,t.note,m.work_type,m.milestone
             from tasks t
             left join task_metadata m on m.task_id=t.id
            where lower(coalesce(m.work_type,''))='research'"""
    ).fetchall()
    out: list[dict] = []
    for row in rows:
        tid = str(row["id"])
        if not is_generated_research_task(conn, tid):
            continue
        lineage = lineage_for_task(conn, tid, backfill=backfill)
        if lineage and lineage.depth > MAX_GENERATED_DEPTH:
            leased = conn.execute(
                "select 1 from brain_task_leases where task_id=?",
                (tid,),
            ).fetchone() is not None
            out.append(
                {
                    "task_id": tid,
                    "status": row["status"],
                    "root_task_id": lineage.root_task_id,
                    "parent_task_id": lineage.parent_task_id,
                    "depth": lineage.depth,
                    "leased": leased,
                }
            )
    return out


def reconcile(
    conn: sqlite3.Connection,
    *,
    apply: bool = False,
) -> dict:
    ensure_schema(conn)

    # Backfill explicit lineage for every historical generated research task.
    generated = [
        str(r[0])
        for r in conn.execute(
            """select t.id
                 from tasks t
                 left join task_metadata m on m.task_id=t.id
                where lower(coalesce(m.work_type,''))='research'"""
        )
        if is_generated_research_task(conn, str(r[0]))
    ]
    for task_id in generated:
        lineage_for_task(conn, task_id, backfill=True)

    # Materialize first-level historical escalations as frontiers so old
    # bounded research remains visible to the dedupe/saturation layer.
    direct_lineages = list(
        conn.execute(
            """select child_task_id,parent_task_id,root_task_id,predicate_sha,
                      origin_kind,origin_id,depth
                 from research_lineage where depth=1"""
        )
    )
    for line in direct_lineages:
        child_id = str(line["child_task_id"])
        child = task_row(conn, child_id)
        if child is None:
            continue
        criteria = [
            str(r[0])
            for r in conn.execute(
                "select criterion from task_acceptance where task_id=? order by ordinal",
                (child_id,),
            )
        ]
        predicate = normalize_predicate(
            " | ".join(criteria) or str(child["title"] or child_id),
            line["parent_task_id"],
        )
        child_status = str(child["status"] or "")
        if child_status in {"DONE", "RESOLVED"}:
            frontier_state = "RESOLVED"
        elif child_status in SATURATED_CHILD_STATES:
            frontier_state = "SATURATED"
        else:
            frontier_state = "OPEN"
        now = _now()
        conn.execute(
            """insert or ignore into research_frontier(
                 root_task_id,predicate_sha,predicate,state,child_task_id,
                 origin_kind,origin_id,attempts,max_attempts,note,
                 created_at,updated_at
               ) values(?,?,?,?,?,?,?,?,1,?,?,?)""",
            (
                str(line["root_task_id"]),
                str(line["predicate_sha"]),
                predicate,
                frontier_state,
                child_id,
                str(line["origin_kind"] or "LEGACY_INFERRED"),
                line["origin_id"],
                1,
                "Backfilled from historical generated research lineage.",
                now,
                now,
            ),
        )
    conn.commit()

    # Synchronize active frontier rows from child task state.
    frontier_rows = list(conn.execute("select * from research_frontier"))
    for row in frontier_rows:
        _sync_frontier_row(conn, row)

    recursive = recursive_generated_tasks(conn, backfill=True)
    superseded: list[str] = []
    skipped_leased: list[str] = []
    if apply:
        now = _now()
        for item in recursive:
            task_id = item["task_id"]
            status = str(item["status"] or "")
            if item["leased"] or status == "ACTIVE":
                skipped_leased.append(task_id)
                continue
            if status in TERMINAL:
                continue
            old = task_row(conn, task_id)
            note = str(old["note"] or "") if old else ""
            suffix = (
                "Frontier governor superseded recursive generated research "
                f"descendant at depth {item['depth']}; all evidence artifacts "
                "remain preserved."
            )
            merged_note = (note.rstrip() + "\n" + suffix).strip()
            conn.execute(
                """update tasks
                      set status='SUPERSEDED',note=?,updated_at=?
                    where id=?""",
                (merged_note, now, task_id),
            )
            conn.execute("delete from claims where task_id=?", (task_id,))
            superseded.append(task_id)

        # Root tasks already blocked on evidence inherit an explicit ceiling
        # marker when every first-level generated research child is terminal or
        # saturated. This prevents a later advisory AI event from reopening the
        # same historical search indefinitely.
        roots = {
            str(r[0])
            for r in conn.execute(
                "select distinct root_task_id from research_lineage where depth=1"
            )
        }
        for root in roots:
            root_row = task_row(conn, root)
            if root_row is None or root_row["status"] != "BLOCKED_EVIDENCE":
                continue
            statuses = {
                str(r[0] or "MISSING")
                for r in conn.execute(
                    """select t.status
                         from research_lineage l
                         left join tasks t on t.id=l.child_task_id
                        where l.root_task_id=? and l.depth=1""",
                    (root,),
                )
            }
            if not statuses or not statuses.issubset(
                {
                    "DONE",
                    "RESOLVED",
                    "BLOCKED_EVIDENCE",
                    "SUPERSEDED",
                    "CANCELLED",
                }
            ):
                continue
            old_note = str(root_row["note"] or "").rstrip()
            if "evidence ceiling" not in old_note.lower():
                marker = (
                    "Evidence ceiling reached after bounded generated research; "
                    "wait for genuinely new primary evidence before reopening."
                )
                conn.execute(
                    "update tasks set note=?,updated_at=? where id=?",
                    ((old_note + "\n" + marker).strip(), now, root),
                )

        # A root whose auto-routed hard children have all reached an evidence
        # ceiling should be BLOCKED_EVIDENCE, not permanently BLOCKED_DEP.
        root_candidates = {
            str(r[0])
            for r in conn.execute(
                """select distinct task_id
                     from task_dependencies
                    where kind='hard'
                      and lower(coalesce(rationale,'')) like '%auto-routed blocker%'"""
            )
        }
        for root in root_candidates:
            deps = list(
                conn.execute(
                    """select d.depends_on,t.status
                         from task_dependencies d
                         left join tasks t on t.id=d.depends_on
                        where d.task_id=? and d.kind='hard'
                          and lower(coalesce(d.rationale,'')) like '%auto-routed blocker%'""",
                    (root,),
                )
            )
            if not deps:
                continue
            states = {str(row[1] or "MISSING") for row in deps}
            if not states.issubset(
                {"DONE", "RESOLVED", "BLOCKED_EVIDENCE", "SUPERSEDED", "CANCELLED"}
            ):
                continue
            root_row = task_row(conn, root)
            if root_row and root_row["status"] == "BLOCKED_DEP":
                old_note = str(root_row["note"] or "").rstrip()
                marker = (
                    "Evidence ceiling reached after bounded auto-routed "
                    "research. Wait for genuinely new evidence rather than "
                    "spawning recursive unblock tasks."
                )
                conn.execute(
                    """update tasks
                          set status='BLOCKED_EVIDENCE',
                              note=?,updated_at=?
                        where id=?""",
                    ((old_note + "\n" + marker).strip(), now, root),
                )
                conn.execute(
                    """update task_dependencies
                          set kind='evidence',
                              rationale=rationale || ' [frontier saturated]'
                        where task_id=? and kind='hard'
                          and lower(coalesce(rationale,'')) like '%auto-routed blocker%'""",
                    (root,),
                )
        conn.commit()

    stats = {
        "generated_tasks": len(generated),
        "recursive_candidates": len(recursive),
        "superseded": len(superseded),
        "skipped_leased": len(skipped_leased),
        "frontiers": int(
            conn.execute("select count(*) from research_frontier").fetchone()[0]
        ),
        "open_frontiers": int(
            conn.execute(
                "select count(*) from research_frontier where state='OPEN'"
            ).fetchone()[0]
        ),
        "saturated_frontiers": int(
            conn.execute(
                "select count(*) from research_frontier where state='SATURATED'"
            ).fetchone()[0]
        ),
    }
    return {
        "apply": apply,
        "stats": stats,
        "recursive": recursive,
        "superseded_task_ids": superseded,
        "skipped_leased_task_ids": skipped_leased,
    }
