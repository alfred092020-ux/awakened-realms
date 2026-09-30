from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from logres_copilot_router import ACTIVE_COPILOT_STATES
from logres_optimizer import rank_task_ids


TERMINAL_JOB_STATES = {"DONE", "BLOCKED", "FAILED", "SUPERSEDED"}
RESEARCH_WORK_TYPES = {"research", "evidence", "analysis", "verification"}
IMPLEMENTATION_WORK_TYPES = {"implementation", "regression", "code"}
CONTROL_PLANE_PREFIX = "ops/logres-control-plane/"
RUNTIME_ONLY_ISOLATION_SURFACE = frozenset({"ops/logres-control-plane/bin/logres-swarm"})

REQUIRED_ISOLATION_SURFACE = frozenset(
    {
        CONTROL_PLANE_PREFIX + "apparmor/usr.bin.bwrap.logres",
        CONTROL_PLANE_PREFIX + "bin/logres-devin-agent",
        CONTROL_PLANE_PREFIX + "bin/logres-devin-isolate",
        CONTROL_PLANE_PREFIX + "bin/logres-swarm",
        CONTROL_PLANE_PREFIX + "config/devin_isolation.json",
        CONTROL_PLANE_PREFIX + "config/devin_workers.json",
        CONTROL_PLANE_PREFIX + "lib/logres_devin_isolation.py",
        CONTROL_PLANE_PREFIX + "lib/logres_swarm.py",
    }
)


def _certified_isolation_surface(certificate: dict) -> dict[str, str]:
    recert = (certificate or {}).get("recertification")
    surface = recert.get("isolation_surface_sha256") if isinstance(recert, dict) else None
    if not isinstance(surface, dict) or not surface:
        return {}
    normalized: dict[str, str] = {}
    for raw_path, raw_digest in surface.items():
        rel = str(raw_path or "").strip().replace("\\", "/")
        digest = str(raw_digest or "").strip().lower()
        if (
            not rel.startswith(CONTROL_PLANE_PREFIX)
            or rel.startswith("/")
            or ".." in Path(rel).parts
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
        ):
            return {}
        normalized[rel] = digest
    return normalized


def isolation_surface_hashes(checkout: Path, certificate: dict) -> dict[str, str]:
    expected = _certified_isolation_surface(certificate)
    if not expected:
        return {}
    root = Path(checkout).resolve()
    current: dict[str, str] = {}
    for rel in sorted(expected):
        target = (root / rel).resolve()
        if root not in target.parents or not target.is_file():
            return {}
        current[rel] = hashlib.sha256(target.read_bytes()).hexdigest()
    return current


@dataclass(frozen=True)
class SwarmCapacity:
    max_workers: int
    active_leases: int
    active_research: int
    active_patch: int
    active_devin: int
    active_copilot: int
    free_slots: int


def isolation_certificate_gate(
    certificate: dict, current_surface: dict, runtime_deployment: dict
) -> tuple[bool, str | None]:
    if not bool((certificate or {}).get("production_ready", False)):
        return False, "isolation_not_certified"
    expected = _certified_isolation_surface(certificate)
    if not expected or not REQUIRED_ISOLATION_SURFACE.issubset(expected):
        return False, "isolation_certificate_surface_missing"
    current = dict(current_surface or {})
    changed = {rel for rel, digest in expected.items() if current.get(rel) != digest}
    security_changed = changed - RUNTIME_ONLY_ISOLATION_SURFACE
    if security_changed:
        return False, "isolation_certificate_stale"
    deployed = (runtime_deployment or {}).get("files")
    if not isinstance(deployed, dict):
        return False, "isolation_runtime_stale"
    for rel, certified_digest in expected.items():
        runtime_rel = rel.removeprefix(CONTROL_PLANE_PREFIX)
        required_digest = current.get(rel) if rel in RUNTIME_ONLY_ISOLATION_SURFACE else certified_digest
        if str(deployed.get(runtime_rel) or "").strip().lower() != required_digest:
            return False, "isolation_runtime_stale"
    return True, None


def isolation_surface_runtime_matches(surface_hashes: dict[str, str], runtime_deployment: dict) -> bool:
    """Require every certified isolation file to match the deployed runtime."""
    deployed = (runtime_deployment or {}).get("files")
    if not isinstance(deployed, dict) or not REQUIRED_ISOLATION_SURFACE.issubset(surface_hashes):
        return False
    for rel, digest in surface_hashes.items():
        if not re.fullmatch(r"[0-9a-f]{64}", str(digest or "").lower()):
            return False
        runtime_rel = rel.removeprefix(CONTROL_PLANE_PREFIX)
        if str(deployed.get(runtime_rel) or "").lower() != str(digest).lower():
            return False
    return True


REQUIRED_PREFLIGHT_CHECKS = frozenset(
    {
        "system_manager",
        "launcher_binaries",
        "worktree_layout",
        "branch_contract",
        "writable_layout",
        "bind_contract",
        "hardening_render",
        "no_broad_privileges",
        "network_netns",
        "network_policy",
        "metadata_loopback_deny",
        "egress_mode",
        "sandbox_binaries",
        "sandbox_apparmor_profile",
        "sandbox_exec_probe",
        "auth_credential_guard",
    }
)


def privileged_network_preflight_ready(
    preflight_report: dict, provision_ok: bool
) -> tuple[bool, str | None]:
    if not provision_ok:
        return False, "network_provision_failed"
    if not isinstance(preflight_report, dict):
        return False, "isolation_preflight_failed"
    checks = preflight_report.get("checks")
    blockers = preflight_report.get("blockers")
    if not isinstance(checks, list) or not checks or not isinstance(blockers, list):
        return False, "isolation_preflight_failed"
    if not str(preflight_report.get("unit") or "").strip():
        return False, "isolation_preflight_missing_unit"
    by_name = {
        str(item.get("name") or ""): item
        for item in checks
        if isinstance(item, dict) and item.get("name")
    }
    if not REQUIRED_PREFLIGHT_CHECKS.issubset(by_name):
        return False, "isolation_preflight_failed"
    required_failures = sorted(
        name
        for name, item in by_name.items()
        if bool(item.get("required")) and not bool(item.get("ok"))
    )
    blocker_names = sorted(str(item) for item in blockers)
    if bool(preflight_report.get("production_ready", False)):
        if required_failures or blocker_names:
            return False, "isolation_preflight_failed"
        return True, None
    if required_failures == ["network_policy"] and blocker_names == ["network_policy"]:
        return True, None
    return False, "isolation_preflight_failed"


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """create table if not exists swarm_jobs(
             id integer primary key autoincrement,
             task_id text not null,
             worker_id text not null,
             engine text not null,
             state text not null,
             pid integer,
             branch text,
             model text,
             session_id text,
             verification text,
             artifact_path text,
             last_error text,
             started_at text not null default (datetime('now')),
             updated_at text not null default (datetime('now')),
             finished_at text
           )"""
    )
    existing = {
        str(row[1])
        for row in conn.execute("pragma table_info(swarm_jobs)").fetchall()
    }
    for name, ddl in (
        ("branch", "text"),
        ("model", "text"),
        ("session_id", "text"),
        ("verification", "text"),
    ):
        if name not in existing:
            conn.execute(f"alter table swarm_jobs add column {name} {ddl}")
    conn.execute(
        "create index if not exists idx_swarm_jobs_state on swarm_jobs(state)"
    )
    conn.execute(
        "create unique index if not exists idx_swarm_jobs_live_task "
        "on swarm_jobs(task_id) where state in ('STARTING','RUNNING')"
    )
    conn.execute(
        """create table if not exists swarm_structural_failures(
             fingerprint text primary key,
             blocker text not null,
             signature_json text not null,
             observation_count integer not null default 0,
             generation integer not null default 1,
             repair_task_id text,
             first_seen_at text not null default (datetime('now')),
             last_seen_at text not null default (datetime('now'))
           )"""
    )
    conn.execute(
        """create table if not exists swarm_structural_failure_tasks(
             fingerprint text not null,
             generation integer not null default 1,
             task_id text not null,
             observation_count integer not null default 0,
             first_seen_at text not null default (datetime('now')),
             last_seen_at text not null default (datetime('now')),
             primary key(fingerprint,generation,task_id)
           )"""
    )
    conn.execute(
        """create table if not exists swarm_failure_repairs(
             task_id text not null,
             fingerprint text not null,
             failure_class text not null,
             observation_count integer not null default 0,
             repair_task_id text,
             last_error text,
             first_seen_at text not null default (datetime('now')),
             last_seen_at text not null default (datetime('now')),
             primary key(task_id,fingerprint)
           )"""
    )
    conn.commit()



def structural_preflight_fingerprint(
    preflight_report: dict, blocker: str | None
) -> dict:
    """Return a stable infrastructure signature with volatile worker details removed."""
    report = preflight_report if isinstance(preflight_report, dict) else {}
    checks = report.get("checks")
    required_failures = sorted(
        {
            str(item.get("name") or "").strip()
            for item in checks or []
            if isinstance(item, dict)
            and bool(item.get("required"))
            and not bool(item.get("ok"))
            and str(item.get("name") or "").strip()
        }
    )
    blockers = sorted(
        {
            str(item).strip()
            for item in (report.get("blockers") or [])
            if str(item).strip()
        }
    )
    if not required_failures:
        required_failures = ["preflight_report_malformed_or_inconsistent"]
    signature = {
        "blocker": str(blocker or "isolation_preflight_failed"),
        "required_failures": required_failures,
        "blockers": blockers,
    }
    encoded = json.dumps(signature, sort_keys=True, separators=(",", ":"))
    return {
        **signature,
        "fingerprint": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        "signature_json": encoded,
    }


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "select 1 from sqlite_master where type='table' and name=?", (name,)
    ).fetchone() is not None


def record_structural_preflight_failure(
    conn: sqlite3.Connection,
    task_id: str,
    preflight_report: dict,
    blocker: str | None,
    *,
    threshold: int = 2,
) -> dict:
    """Deduplicate repeated structural failures into one bounded repair dependency."""
    ensure_schema(conn)
    signature = structural_preflight_fingerprint(preflight_report, blocker)
    fingerprint = signature["fingerprint"]
    threshold = max(1, int(threshold))
    now = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    row = conn.execute(
        "select * from swarm_structural_failures where fingerprint=?",
        (fingerprint,),
    ).fetchone()
    generation = int(row["generation"] if row is not None else 1)
    existing_repair = str(row["repair_task_id"] or "") if row is not None else ""
    if existing_repair:
        repair_row = conn.execute(
            "select status from tasks where id=?", (existing_repair,)
        ).fetchone()
        if repair_row and str(repair_row[0]) in {
            "DONE", "RESOLVED", "SUPERSEDED", "CANCELLED"
        }:
            generation += 1
            existing_repair = ""
            conn.execute(
                """update swarm_structural_failures
                      set observation_count=0,generation=?,repair_task_id=null,
                          first_seen_at=?,last_seen_at=?
                    where fingerprint=?""",
                (generation, now, now, fingerprint),
            )
            row = conn.execute(
                "select * from swarm_structural_failures where fingerprint=?",
                (fingerprint,),
            ).fetchone()

    if row is None:
        conn.execute(
            """insert into swarm_structural_failures(
                 fingerprint,blocker,signature_json,observation_count,generation,
                 repair_task_id,first_seen_at,last_seen_at
               ) values(?,?,?,1,1,null,?,?)""",
            (
                fingerprint,
                signature["blocker"],
                signature["signature_json"],
                now,
                now,
            ),
        )
        count = 1
        generation = 1
    else:
        conn.execute(
            """update swarm_structural_failures
                  set observation_count=observation_count+1,
                      blocker=?,signature_json=?,last_seen_at=?
                where fingerprint=?""",
            (
                signature["blocker"],
                signature["signature_json"],
                now,
                fingerprint,
            ),
        )
        count = int(
            conn.execute(
                "select observation_count from swarm_structural_failures where fingerprint=?",
                (fingerprint,),
            ).fetchone()[0]
        )

    conn.execute(
        """insert into swarm_structural_failure_tasks(
             fingerprint,generation,task_id,observation_count,first_seen_at,last_seen_at
           ) values(?,?,?,1,?,?)
           on conflict(fingerprint,generation,task_id) do update set
             observation_count=observation_count+1,last_seen_at=excluded.last_seen_at""",
        (fingerprint, generation, task_id, now, now),
    )

    repair_task_id = existing_repair or None
    created = False
    if count >= threshold:
        if not repair_task_id:
            suffix = fingerprint[:8].upper()
            repair_task_id = f"REPAIR-DEVIN-ISOLATION-{suffix}"
            if generation > 1:
                repair_task_id += f"-G{generation}"
            existing = conn.execute(
                "select 1 from tasks where id=?", (repair_task_id,)
            ).fetchone()
            if not existing:
                title = (
                    "Repair repeated Devin isolation preflight failure: "
                    + ", ".join(signature["required_failures"])
                )[:240]
                conn.execute(
                    """insert into tasks(
                         id,priority,lane,title,status,branch,owner,note,updated_at
                       ) values(?,0,'control-plane',?,'READY',null,null,?,?)""",
                    (
                        repair_task_id,
                        title,
                        "Auto-escalated after repeated identical structural Devin "
                        "preflight failures. fingerprint=" + fingerprint,
                        now,
                    ),
                )
                if _table_exists(conn, "task_metadata"):
                    conn.execute(
                        """insert or ignore into task_metadata(
                             task_id,milestone,work_type,concurrency_key,
                             expected_minutes,evidence_policy,created_at,updated_at
                           ) values(?, 'autoflow','manual',?,45,?,?,?)""",
                        (
                            repair_task_id,
                            "devin-isolation-repair:" + fingerprint,
                            "Infrastructure repair. Preserve governed privilege and "
                            "prove one live canary before unblocking dependents.",
                            now,
                            now,
                        ),
                    )
                if _table_exists(conn, "task_acceptance"):
                    for ordinal, criterion in enumerate(
                        (
                            "Identify and repair the structural isolation failure without weakening governed privilege.",
                            "Prove exact lease-bound provision/start and bounded AUTO cleanup.",
                            "Pass focused isolation/swarm tests and one live Devin canary.",
                        ),
                        1,
                    ):
                        conn.execute(
                            "insert into task_acceptance(task_id,ordinal,criterion) values(?,?,?)",
                            (repair_task_id, ordinal, criterion),
                        )
                created = True
            conn.execute(
                "update swarm_structural_failures set repair_task_id=? where fingerprint=?",
                (repair_task_id, fingerprint),
            )

        affected = [
            str(r[0])
            for r in conn.execute(
                """select task_id from swarm_structural_failure_tasks
                     where fingerprint=? and generation=? order by task_id""",
                (fingerprint, generation),
            )
        ]
        for affected_task in affected:
            if affected_task == repair_task_id:
                continue
            if _table_exists(conn, "task_dependencies"):
                conn.execute(
                    """insert or ignore into task_dependencies(
                         task_id,depends_on,kind,rationale
                       ) values(?,?,'hard',?)""",
                    (
                        affected_task,
                        repair_task_id,
                        "Repeated structural Devin preflight failure " + fingerprint,
                    ),
                )
            conn.execute(
                """update tasks
                      set status='BLOCKED_DEP',note=?,updated_at=?
                    where id=? and status in ('READY','ACTIVE','BLOCKED_DEP')""",
                (
                    f"Blocked by structural repair {repair_task_id} "
                    f"(fingerprint={fingerprint}).",
                    now,
                    affected_task,
                ),
            )

    conn.commit()
    return {
        **signature,
        "observation_count": count,
        "generation": generation,
        "repair_task_id": repair_task_id,
        "created": created,
    }


def active_structural_repair(conn: sqlite3.Connection) -> dict | None:
    """Return one open structural repair that globally gates fresh Devin dispatch."""
    ensure_schema(conn)
    row = conn.execute(
        """select f.fingerprint,f.generation,f.repair_task_id,t.status
             from swarm_structural_failures f
             join tasks t on t.id=f.repair_task_id
            where f.repair_task_id is not null
              and t.status not in ('DONE','RESOLVED','SUPERSEDED','CANCELLED')
            order by f.last_seen_at desc,f.fingerprint
            limit 1"""
    ).fetchone()
    if not row:
        return None
    return {
        "fingerprint": str(row["fingerprint"]),
        "generation": int(row["generation"]),
        "repair_task_id": str(row["repair_task_id"]),
        "status": str(row["status"]),
    }

def pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def reconcile_jobs(conn: sqlite3.Connection) -> list[int]:
    ensure_schema(conn)
    stale: list[int] = []
    for row in conn.execute(
        "select id,pid,state from swarm_jobs where state in ('STARTING','RUNNING')"
    ):
        if not pid_alive(row[1]):
            conn.execute(
                """update swarm_jobs
                      set state='FAILED',
                          last_error=coalesce(last_error,'worker process exited'),
                          updated_at=datetime('now'),
                          finished_at=datetime('now')
                    where id=?""",
                (row[0],),
            )
            stale.append(int(row[0]))
    conn.commit()
    return stale


def terminal_devin_cleanup_candidates(
    conn: sqlite3.Connection, *, limit: int = 2
) -> list[sqlite3.Row]:
    ensure_schema(conn)
    bounded_limit = max(0, int(limit))
    if bounded_limit == 0:
        return []
    return list(
        conn.execute(
            """select id,task_id,worker_id,branch,session_id,state
                 from swarm_jobs
                where engine='devin'
                  and state in ('DONE','BLOCKED','FAILED','SUPERSEDED')
                  and branch is not null
                  and session_id like 'systemd:%'
                order by id
                limit ?""",
            (bounded_limit,),
        )
    )


def active_copilot_task_ids(conn: sqlite3.Connection) -> set[str]:
    states = tuple(sorted(ACTIVE_COPILOT_STATES))
    placeholders = ",".join("?" for _ in states)
    try:
        rows = conn.execute(
            f"select distinct task_id from copilot_jobs "
            f"where state in ({placeholders})",
            states,
        ).fetchall()
    except sqlite3.OperationalError:
        return set()
    return {str(row[0]) for row in rows if row[0]}


def active_copilot_job_count(conn: sqlite3.Connection) -> int:
    states = tuple(sorted(ACTIVE_COPILOT_STATES))
    placeholders = ",".join("?" for _ in states)
    try:
        return int(
            conn.execute(
                f"select count(*) from copilot_jobs "
                f"where state in ({placeholders})",
                states,
            ).fetchone()[0]
        )
    except sqlite3.OperationalError:
        return 0


def active_swarm_task_ids(conn: sqlite3.Connection) -> set[str]:
    ensure_schema(conn)
    return {
        str(row[0])
        for row in conn.execute(
            "select distinct task_id from swarm_jobs "
            "where state in ('STARTING','RUNNING')"
        )
        if row[0]
    }


def active_swarm_engine_count(conn: sqlite3.Connection, engine: str) -> int:
    ensure_schema(conn)
    return int(
        conn.execute(
            "select count(*) from swarm_jobs "
            "where engine=? and state in ('STARTING','RUNNING')",
            (engine,),
        ).fetchone()[0]
    )


def swarm_capacity(conn: sqlite3.Connection, config: dict) -> SwarmCapacity:
    ensure_schema(conn)
    now = time.time()
    max_workers = int(config.get("swarm", {}).get("max_workers", 6) or 6)
    active_leases = int(
        conn.execute(
            "select count(*) from brain_task_leases "
            "where lease_until_epoch>? and chat_id<>'lead'",
            (now,),
        ).fetchone()[0]
    )
    active_research = active_swarm_engine_count(conn, "research")
    active_patch = active_swarm_engine_count(conn, "openai-patch")
    active_devin = active_swarm_engine_count(conn, "devin")
    active_copilot = active_copilot_job_count(conn)
    # Research and OpenAI patch workers both hold Brain leases, so they are
    # already represented in active_leases. Copilot jobs are external and do
    # not necessarily hold a Brain lease, so only Copilot is added separately.
    free_slots = max(0, max_workers - active_leases - active_copilot)
    return SwarmCapacity(
        max_workers=max_workers,
        active_leases=active_leases,
        active_research=active_research,
        active_patch=active_patch,
        active_devin=active_devin,
        active_copilot=active_copilot,
        free_slots=free_slots,
    )


def ready_tasks(conn: sqlite3.Connection) -> list[dict]:
    owned = active_copilot_task_ids(conn) | active_swarm_task_ids(conn)
    rows = conn.execute(
        """select t.id,t.priority,t.title,t.lane,t.status,
                  coalesce(nullif(m.work_type,''), nullif(t.lane,''), 'implementation') work_type,
                  coalesce(m.expected_minutes,60) expected_minutes,
                  coalesce(m.concurrency_key,'') concurrency_key,
                  coalesce(m.evidence_policy,'') evidence_policy
             from tasks t
             left join task_metadata m on m.task_id=t.id
            where t.status='READY'
            order by t.priority asc,
                     coalesce(m.expected_minutes,60) asc,
                     t.id asc"""
    ).fetchall()
    return [
        dict(row)
        for row in rows
        if str(row["id"]) not in owned
    ]


def classify_engine(task: dict) -> str:
    work_type = str(task.get("work_type") or "").lower()
    if work_type in RESEARCH_WORK_TYPES:
        return "research"
    if work_type in IMPLEMENTATION_WORK_TYPES:
        return "copilot"
    return "manual"


def normalize_task_scope(raw: str) -> str | None:
    scope = str(raw or "").strip().replace("\\", "/")
    if not scope or scope in {".", "*", "/"}:
        return None
    path = Path(scope)
    if path.is_absolute() or ".." in path.parts:
        return None
    normalized = "/".join(part for part in path.parts if part not in {"", "."})
    if not normalized or normalized in {"*", "."}:
        return None
    if any(part in {"*", "**"} for part in Path(normalized).parts):
        return None
    return normalized.rstrip("/")


def planned_scopes_from_packet(text: str) -> list[str]:
    scopes: list[str] = []
    in_scopes = False
    for raw in str(text or "").splitlines():
        stripped = raw.strip()
        if stripped in {"planned file scopes:", "- planned file scopes:"}:
            in_scopes = True
            continue
        if not in_scopes:
            continue
        if not stripped:
            if scopes:
                break
            continue
        if not stripped.startswith("- "):
            break
        scope = normalize_task_scope(stripped[2:])
        if scope is None:
            return []
        if scope not in scopes:
            scopes.append(scope)
    return scopes


def _latest_task_packet(packet_root: Path, task_id: str) -> Path | None:
    if not packet_root.is_dir():
        return None
    prefix = f"{task_id}-"
    candidates = []
    for path in packet_root.iterdir():
        if not path.is_file() or not path.name.startswith(prefix) or path.suffix != ".txt":
            continue
        try:
            stamp = path.stat().st_mtime_ns
        except OSError:
            continue
        candidates.append((stamp, path.name, path))
    if not candidates:
        return None
    return max(candidates)[2]


def backfill_ready_task_scopes(
    conn: sqlite3.Connection,
    packet_root: Path,
) -> dict:
    ready = [
        task
        for task in ready_tasks(conn)
        if str(task.get("work_type") or "").lower() in IMPLEMENTATION_WORK_TYPES
    ]
    filled_tasks = 0
    inserted_scopes = 0
    skipped_ambiguous = 0
    for task in ready:
        task_id = str(task["id"])
        existing = conn.execute(
            "select 1 from task_scopes where task_id=? limit 1",
            (task_id,),
        ).fetchone()
        if existing is not None:
            continue

        scopes = []
        for row in conn.execute(
            "select path_prefix from claims where task_id=? order by path_prefix",
            (task_id,),
        ):
            scope = normalize_task_scope(str(row[0]))
            if scope is None:
                scopes = []
                skipped_ambiguous += 1
                break
            if scope not in scopes:
                scopes.append(scope)

        if not scopes:
            packet = _latest_task_packet(packet_root, task_id)
            if packet is None:
                continue
            try:
                scopes = planned_scopes_from_packet(
                    packet.read_text(encoding="utf-8", errors="replace")
                )
            except OSError:
                scopes = []
            if not scopes:
                skipped_ambiguous += 1
                continue

        for scope in scopes:
            conn.execute(
                "insert or ignore into task_scopes(task_id,path_prefix) values(?,?)",
                (task_id, scope),
            )
            inserted_scopes += 1
        filled_tasks += 1

    conn.commit()
    return {
        "tasks": filled_tasks,
        "scopes": inserted_scopes,
        "skipped_ambiguous": skipped_ambiguous,
    }


def _select_tasks(
    conn: sqlite3.Connection,
    limit: int,
    *,
    work_types: set[str],
    engine: str,
    skip_task_ids: set[str] | None = None,
    require_scopes: bool = False,
) -> list[dict]:
    skip_task_ids = skip_task_ids or set()
    selected: list[dict] = []
    keys: set[str] = set()
    claimed = [
        tuple(row)
        for row in conn.execute("select task_id,path_prefix from claims")
    ]
    selected_scopes: list[tuple[str, str]] = []

    task_map = {task["id"]: task for task in ready_tasks(conn)}
    ranked_ids = rank_task_ids(
        conn,
        # Rank the full READY set before applying scope, claim, concurrency,
        # and retry-exhaustion filters. A small ranking window lets a few
        # high-ranked but ineligible tasks starve healthy lower-ranked work.
        limit=max(16, len(task_map), max(1, limit) * 4),
        work_type_filter=work_types,
    )
    for task_id in ranked_ids:
        task = task_map.get(task_id)
        if task is None or task["id"] in skip_task_ids:
            continue
        work_type = str(task.get("work_type") or "").lower()
        if work_type not in work_types:
            continue
        key = task.get("concurrency_key") or task.get("lane") or ""
        if key and key in keys:
            continue
        scopes = [
            str(row[0])
            for row in conn.execute(
                "select path_prefix from task_scopes where task_id=? order by path_prefix",
                (task["id"],),
            )
        ]
        if require_scopes and not scopes:
            continue
        conflict = False
        for scope in scopes:
            a = scope.rstrip("/") + "/"
            for owner_task, prior in claimed + selected_scopes:
                if owner_task == task["id"]:
                    continue
                b = str(prior).rstrip("/") + "/"
                if a.startswith(b) or b.startswith(a):
                    conflict = True
                    break
            if conflict:
                break
        if conflict:
            continue
        selected.append(task)
        if key:
            keys.add(key)
        selected_scopes.extend((task["id"], scope) for scope in scopes)
        if len(selected) >= max(0, limit):
            break
    return selected


def select_research_tasks(
    conn: sqlite3.Connection,
    limit: int,
    *,
    skip_task_ids: set[str] | None = None,
) -> list[dict]:
    return _select_tasks(
        conn,
        limit,
        work_types=RESEARCH_WORK_TYPES,
        engine="research",
        skip_task_ids=skip_task_ids,
    )


def select_implementation_tasks(
    conn: sqlite3.Connection,
    limit: int,
    *,
    skip_task_ids: set[str] | None = None,
) -> list[dict]:
    return _select_tasks(
        conn,
        limit,
        work_types=IMPLEMENTATION_WORK_TYPES,
        engine="openai-patch",
        skip_task_ids=skip_task_ids,
        require_scopes=True,
    )

NON_SEMANTIC_FAILURE_CLASSES = {
    "context",
    "permission_environment",
    "infrastructure",
    "task_ambiguity",
}


def classify_worker_failure(error: str) -> str:
    value = str(error or "").strip().lower()
    if not value:
        return "infrastructure"
    if "devin child produced no repository diff" in value:
        return "no_diff"


    context_markers = (
        "incomplete",
        "truncat",
        "outside the supplied file index",
        "supplied contents",
        "missing context",
        "additional failure-log evidence",
        "no attached failure-log",
        "context path",
        "context bundle",
    )
    if any(marker in value for marker in context_markers):
        return "context"

    permission_markers = (
        "requires confirmation",
        "permission denied",
        "human_only",
        "human-only",
        "read-only",
        "readonly",
        "missing executable",
        "no such file or directory",
        "shell execution is unavailable",
        "not approved",
    )
    if any(marker in value for marker in permission_markers):
        return "permission_environment"

    infrastructure_markers = (
        "network provision",
        "bootstrap failed",
        "worker no longer owns",
        "expected task lease",
        "timed out",
        "timeout",
        "connection",
        "service unavailable",
        "process exited",
        "stale lock",
    )
    if any(marker in value for marker in infrastructure_markers):
        return "infrastructure"

    ambiguity_markers = (
        "ambiguous",
        "underspecified",
        "cannot be specified",
        "cannot safely",
        "inventing behavior",
        "insufficient evidence",
        "additional evidence is required",
    )
    if any(marker in value for marker in ambiguity_markers):
        return "task_ambiguity"

    verification_markers = (
        "test failed",
        "tests failed",
        "build failed",
        "e2e",
        "verification failed",
        "assertion",
        "typecheck",
        "lint failed",
        "performance",
    )
    if any(marker in value for marker in verification_markers):
        return "verification"
    return "semantic"


def worker_failure_fingerprint(error: str) -> dict:
    failure_class = classify_worker_failure(error)
    normalized = str(error or "").strip().lower()
    normalized = re.sub(r"\b[0-9a-f]{7,64}\b", "<sha>", normalized)
    normalized = re.sub(r"\b\d+\b", "<n>", normalized)
    normalized = re.sub(r"\s+", " ", normalized)[:600]
    encoded = f"{failure_class}:{normalized}"
    return {
        "failure_class": failure_class,
        "normalized": normalized,
        "fingerprint": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
    }


def _repair_scopes_for_failure(
    conn: sqlite3.Connection,
    task_id: str,
    failure_class: str,
) -> list[str]:
    original = [
        str(row[0])
        for row in conn.execute(
            "select path_prefix from task_scopes where task_id=? order by path_prefix",
            (task_id,),
        )
    ]
    if failure_class == "context":
        return [
            "ops/logres-control-plane/lib/logres_patch_agent.py",
            "ops/logres-control-plane/bin/logres-patch-agent",
            "ops/logres-control-plane/tests/test_patch_agent.py",
        ]
    if failure_class in {"permission_environment", "infrastructure"}:
        return [
            "ops/logres-control-plane/lib/logres_swarm.py",
            "ops/logres-control-plane/bin/logres-swarm",
            "ops/logres-control-plane/tests/test_swarm.py",
        ]
    return original


MAX_AUTONOMOUS_REPAIR_GENERATION = 3


def _repair_lineage(conn: sqlite3.Connection, task_id: str) -> tuple[str, int]:
    """Return the root mission task and current autonomous repair generation."""
    root_task = task_id
    current = task_id
    generation = 0
    seen: set[str] = set()
    while current.startswith("REPAIR-AUTO-") and current not in seen:
        seen.add(current)
        row = conn.execute(
            """select task_id from swarm_failure_repairs
                 where repair_task_id=?
                 order by last_seen_at desc
                 limit 1""",
            (current,),
        ).fetchone()
        if row is None:
            break
        parent = str(row[0])
        generation += 1
        root_task = parent
        current = parent
    return root_task, generation


def reconcile_failure_repairs(conn: sqlite3.Connection) -> list[str]:
    ensure_schema(conn)
    released: list[str] = []
    rows = conn.execute(
        """select r.task_id,r.repair_task_id,t.status
             from swarm_failure_repairs r
             join tasks t on t.id=r.repair_task_id
            where r.repair_task_id is not null"""
    ).fetchall()
    satisfied = {"DONE", "RESOLVED", "INTEGRATED"}
    terminal_bad = {"SUPERSEDED", "CANCELLED"}
    for row in rows:
        original = str(row["task_id"])
        repair = str(row["repair_task_id"])
        repair_status = str(row["status"])
        if repair_status in satisfied:
            unresolved = 0
            if _table_exists(conn, "task_dependencies"):
                unresolved = int(
                    conn.execute(
                        """select count(*)
                             from task_dependencies d
                             join tasks t on t.id=d.depends_on
                            where d.task_id=? and d.kind='hard'
                              and t.status not in ('DONE','RESOLVED','INTEGRATED')""",
                        (original,),
                    ).fetchone()[0]
                )
            if unresolved == 0:
                conn.execute(
                    """update tasks set status='READY',
                           note=?,updated_at=datetime('now')
                         where id=? and status='BLOCKED_DEP'""",
                    (
                        f"Autonomous repair {repair} satisfied; original mission resumed.",
                        original,
                    ),
                )
                if conn.total_changes:
                    released.append(original)
        elif repair_status in terminal_bad:
            conn.execute(
                """update tasks set note=?,updated_at=datetime('now')
                     where id=? and status='BLOCKED_DEP'""",
                (
                    f"Autonomous repair {repair} ended {repair_status}; lead/debug review required.",
                    original,
                ),
            )
    conn.commit()
    return released


def route_repeated_worker_failures(
    conn: sqlite3.Connection,
    *,
    threshold: int = 2,
    max_repair_generation: int = MAX_AUTONOMOUS_REPAIR_GENERATION,
) -> list[dict]:
    ensure_schema(conn)
    reconcile_failure_repairs(conn)
    threshold = max(2, int(threshold))
    max_repair_generation = max(1, int(max_repair_generation))
    routed: list[dict] = []
    tasks = conn.execute(
        """select distinct t.id
             from tasks t
             join swarm_jobs j on j.task_id=t.id
            where t.status='READY' and j.state='FAILED'
            order by t.id"""
    ).fetchall()
    now = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    for task_row in tasks:
        task_id = str(task_row[0])
        root_task_id, current_generation = _repair_lineage(conn, task_id)
        failures = conn.execute(
            """select id,last_error,engine,artifact_path
                 from swarm_jobs
                where task_id=? and state='FAILED'
                order by id desc limit 12""",
            (task_id,),
        ).fetchall()
        groups: dict[str, list[sqlite3.Row]] = {}
        signatures: dict[str, dict] = {}
        for row in failures:
            sig = worker_failure_fingerprint(str(row["last_error"] or ""))
            signatures[sig["fingerprint"]] = sig
            groups.setdefault(sig["fingerprint"], []).append(row)

        for fingerprint, rows in groups.items():
            if len(rows) < threshold:
                continue
            signature = signatures[fingerprint]
            failure_class = signature["failure_class"]
            existing = conn.execute(
                """select repair_task_id from swarm_failure_repairs
                    where task_id=? and fingerprint=?""",
                (task_id, fingerprint),
            ).fetchone()
            repair_task_id = str(existing[0] or "") if existing else ""
            if repair_task_id:
                repair = conn.execute(
                    "select status from tasks where id=?",
                    (repair_task_id,),
                ).fetchone()
                if repair and str(repair[0]) not in {
                    "DONE", "RESOLVED", "INTEGRATED",
                    "SUPERSEDED", "CANCELLED",
                }:
                    continue

            next_generation = current_generation + 1
            if next_generation > max_repair_generation:
                conn.execute(
                    """update tasks
                          set note=?,updated_at=datetime('now')
                        where id=?""",
                    (
                        "Autonomous repair generation ceiling reached "
                        f"({max_repair_generation}) for root mission {root_task_id}; "
                        "no recursive repair task created.",
                        task_id,
                    ),
                )
                conn.commit()
                continue

            repair_base = (
                f"REPAIR-AUTO-{root_task_id[:80]}-{fingerprint[:8].upper()}"
            )
            repair_task_id = (
                repair_base
                if next_generation == 1
                else f"{repair_base}-G{next_generation}"
            )[:150]
            scopes = _repair_scopes_for_failure(
                conn, task_id, failure_class
            )
            if not scopes:
                continue

            if not conn.execute(
                "select 1 from tasks where id=?", (repair_task_id,)
            ).fetchone():
                title = (
                    f"Diagnose and repair {failure_class} failure blocking {task_id}"
                )[:240]
                conn.execute(
                    """insert into tasks(
                         id,priority,lane,title,status,branch,owner,note,updated_at
                       ) values(?,0,'control-plane',?,'READY',null,null,?,?)""",
                    (
                        repair_task_id,
                        title,
                        (
                            "Auto-generated after repeated identical autonomous "
                            f"failures. root={root_task_id} failed_task={task_id} "
                            f"generation={next_generation}/{max_repair_generation} "
                            f"class={failure_class} fingerprint={fingerprint}"
                        ),
                        now,
                    ),
                )
                if _table_exists(conn, "task_metadata"):
                    conn.execute(
                        """insert or ignore into task_metadata(
                             task_id,milestone,work_type,concurrency_key,
                             expected_minutes,evidence_policy,created_at,updated_at
                           ) values(?,'AUTONOMY-COMPLETION','implementation',
                                    ?,45,?,?,?)""",
                        (
                            repair_task_id,
                            "failure-repair:" + fingerprint,
                            (
                                "Diagnose root cause, reproduce the smallest failing "
                                "case, repair it without weakening safety, rerun the "
                                "failing check, then broader verification."
                            ),
                            now,
                            now,
                        ),
                    )
                for scope in scopes:
                    conn.execute(
                        """insert or ignore into task_scopes(task_id,path_prefix)
                           values(?,?)""",
                        (repair_task_id, scope),
                    )
                if _table_exists(conn, "task_acceptance"):
                    criteria = (
                        f"Classify and reproduce the {failure_class} failure for {task_id}.",
                        f"Repair autonomous generation {next_generation} for root mission {root_task_id} rather than repeating the same worker attempt.",
                        "Rerun the smallest failing check and the relevant broader verification gate.",
                        f"Return {task_id} and root mission {root_task_id} to autonomous eligibility after the repair chain integrates.",
                    )
                    for ordinal, criterion in enumerate(criteria, 1):
                        conn.execute(
                            "insert into task_acceptance(task_id,ordinal,criterion) values(?,?,?)",
                            (repair_task_id, ordinal, criterion),
                        )

            conn.execute(
                """insert into swarm_failure_repairs(
                     task_id,fingerprint,failure_class,observation_count,
                     repair_task_id,last_error,first_seen_at,last_seen_at
                   ) values(?,?,?,?,?,?,?,?)
                   on conflict(task_id,fingerprint) do update set
                     failure_class=excluded.failure_class,
                     observation_count=excluded.observation_count,
                     repair_task_id=excluded.repair_task_id,
                     last_error=excluded.last_error,
                     last_seen_at=excluded.last_seen_at""",
                (
                    task_id,
                    fingerprint,
                    failure_class,
                    len(rows),
                    repair_task_id,
                    str(rows[0]["last_error"] or "")[:2000],
                    now,
                    now,
                ),
            )
            if _table_exists(conn, "task_dependencies"):
                dependency_targets = [task_id]
                if root_task_id != task_id:
                    dependency_targets.append(root_task_id)
                for dependency_task in dependency_targets:
                    conn.execute(
                        """insert or ignore into task_dependencies(
                             task_id,depends_on,kind,rationale
                           ) values(?,?,'hard',?)""",
                        (
                            dependency_task,
                            repair_task_id,
                            (
                                "Repeated identical autonomous failure requires root-cause "
                                f"repair generation {next_generation} first. "
                                f"class={failure_class} fingerprint={fingerprint}"
                            ),
                        ),
                    )
            blocked_tasks = [task_id]
            if root_task_id != task_id:
                blocked_tasks.append(root_task_id)
            for blocked_task in blocked_tasks:
                conn.execute(
                    """update tasks
                          set status='BLOCKED_DEP',note=?,updated_at=?
                        where id=? and status in ('READY','ACTIVE','BLOCKED_DEP')""",
                    (
                        (
                            f"Blocked on autonomous repair {repair_task_id} generation "
                            f"{next_generation}/{max_repair_generation} after "
                            f"{len(rows)} repeated {failure_class} failures."
                        ),
                        now,
                        blocked_task,
                    ),
                )
            routed.append(
                {
                    "task_id": task_id,
                    "repair_task_id": repair_task_id,
                    "failure_class": failure_class,
                    "fingerprint": fingerprint,
                    "observations": len(rows),
                    "root_task_id": root_task_id,
                    "generation": next_generation,
                }
            )
            break
    conn.commit()
    return routed


def _devin_infrastructure_failure(row: sqlite3.Row) -> bool:
    if str(row["engine"] or "") != "devin":
        return False
    artifact_path = str(row["artifact_path"] or "").strip()
    if not artifact_path:
        return True
    try:
        artifact = json.loads(Path(artifact_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    log_path = str(artifact.get("log") or "").strip()
    if not log_path:
        return False
    try:
        text = Path(log_path).read_text(encoding="utf-8", errors="replace")[-20000:].lower()
    except OSError:
        return False
    confirmation_denial = (
        "rejected a tool call that requires confirmation" in text
        and "non-interactive mode" in text
    )
    legacy_sandbox_shell_denial = (
        "devin child produced no repository diff" in str(row["last_error"] or "").lower()
        and "--sandbox always uses the autonomous permission mode" in text
        and "shell execution is unavailable" in text
    )
    return confirmation_denial or legacy_sandbox_shell_denial


def prior_failures(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    engine: str | None = None,
) -> int:
    ensure_schema(conn)
    sql = """select engine,artifact_path,last_error from swarm_jobs
               where task_id=? and state='FAILED'"""
    params: list[str] = [task_id]
    if engine:
        sql += " and engine=?"
        params.append(engine)
    rows = conn.execute(sql, tuple(params)).fetchall()
    count = 0
    for row in rows:
        if (
            str(row["engine"] or "") == "research"
            and not str(row["artifact_path"] or "").strip()
        ):
            continue
        if _devin_infrastructure_failure(row):
            continue
        failure_class = classify_worker_failure(str(row["last_error"] or ""))
        if failure_class in NON_SEMANTIC_FAILURE_CLASSES:
            if (
                engine == "openai-patch"
                and task_id.startswith("REPAIR-AUTO-")
            ):
                count += 1
            continue
        count += 1
    return count


def worker_ids(config: dict) -> list[str]:
    count = int(config.get("swarm", {}).get("research_workers", 2) or 2)
    return [f"auto-research-{i}" for i in range(1, max(1, count) + 1)]


def available_worker_ids(conn: sqlite3.Connection, config: dict) -> list[str]:
    now = time.time()
    busy = {
        row[0]
        for row in conn.execute(
            "select chat_id from brain_task_leases where lease_until_epoch>?",
            (now,),
        )
    }
    return [worker for worker in worker_ids(config) if worker not in busy]


def patch_worker_ids(config: dict) -> list[str]:
    impl = config.get("implementation", {})
    count = int(impl.get("workers", 1) or 1)
    return [f"auto-patch-{i}" for i in range(1, max(1, count) + 1)]


def available_patch_worker_ids(
    conn: sqlite3.Connection,
    config: dict,
) -> list[str]:
    now = time.time()
    busy = {
        str(row[0])
        for row in conn.execute(
            "select chat_id from brain_task_leases where lease_until_epoch>?",
            (now,),
        )
    }
    return [worker for worker in patch_worker_ids(config) if worker not in busy]


def devin_worker_ids(config: dict) -> list[str]:
    router = config.get("router", {}) if isinstance(config, dict) else {}
    count = int(router.get("workers", 2) or 2)
    return [f"auto-devin-{i}" for i in range(1, max(1, count) + 1)]


def available_devin_worker_ids(
    conn: sqlite3.Connection,
    config: dict,
) -> list[str]:
    now = time.time()
    busy = {
        str(row[0])
        for row in conn.execute(
            "select chat_id from brain_task_leases where lease_until_epoch>?",
            (now,),
        )
    }
    return [worker for worker in devin_worker_ids(config) if worker not in busy]


def register_worker(root: Path, worker_id: str) -> None:
    subprocess.run(
        [str(root / "bin/logres-brain"), "join", worker_id, "--name", worker_id],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def acquire_task(root: Path, worker_id: str, task_id: str) -> str | None:
    proc = subprocess.run(
        [
            str(root / "bin/logres-coordinator"),
            "acquire",
            worker_id,
            "--task",
            task_id,
            "--minutes",
            "120",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode:
        return None
    match = re.search(r"ACQUIRED task=\S+ branch=(\S+)", proc.stdout)
    return match.group(1) if match else None


def create_job(
    conn: sqlite3.Connection,
    task_id: str,
    worker_id: str,
    engine: str,
    *,
    branch: str | None = None,
    model: str | None = None,
    verification: str | None = None,
) -> int:
    ensure_schema(conn)
    cur = conn.execute(
        """insert into swarm_jobs(
             task_id,worker_id,engine,state,branch,model,verification
           ) values(?,?,?,'STARTING',?,?,?)""",
        (task_id, worker_id, engine, branch, model, verification),
    )
    conn.commit()
    return int(cur.lastrowid)


def mark_job_running(
    conn: sqlite3.Connection,
    job_id: int,
    pid: int,
    *,
    session_id: str | None = None,
) -> None:
    conn.execute(
        """update swarm_jobs
              set state='RUNNING',pid=?,session_id=coalesce(?,session_id),
                  updated_at=datetime('now')
            where id=?""",
        (pid, session_id, job_id),
    )
    conn.commit()


def status_dict(conn: sqlite3.Connection, config: dict) -> dict:
    cap = swarm_capacity(conn, config)
    jobs = [
        dict(row)
        for row in conn.execute(
            "select * from swarm_jobs order by id desc limit 20"
        )
    ]
    return {
        "enabled": bool(config.get("swarm", {}).get("enabled", False)),
        "capacity": {
            "max_workers": cap.max_workers,
            "active_leases": cap.active_leases,
            "active_research": cap.active_research,
            "active_patch": cap.active_patch,
            "active_devin": cap.active_devin,
            "active_copilot": cap.active_copilot,
            "free_slots": cap.free_slots,
        },
        "ready": [
            {
                "task_id": task["id"],
                "engine": classify_engine(task),
                "priority": task["priority"],
                "work_type": task["work_type"],
            }
            for task in ready_tasks(conn)
        ],
        "jobs": jobs,
    }


def load_config(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
