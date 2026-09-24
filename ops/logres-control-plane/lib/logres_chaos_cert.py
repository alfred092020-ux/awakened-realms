from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from logres_frontier import claim_frontier, ensure_schema as ensure_frontier_schema, register_child
from logres_resource_broker import choose_remote_role, plan_workload
from logres_route_store import RouteSpec, claim_route, ensure_route_schema
from logres_supervisor import ScheduledJob, tick


CERT_SCHEMA = 1


@dataclass(frozen=True)
class ProbeResult:
    name: str
    passed: bool
    duration_seconds: float
    detail: dict

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "duration_seconds": round(self.duration_seconds, 4),
            "detail": self.detail,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _timed(name: str, fn) -> ProbeResult:
    started = time.monotonic()
    try:
        detail = fn()
        passed = bool(detail.pop("passed", True))
    except Exception as exc:
        detail = {
            "exception": type(exc).__name__,
            "message": str(exc),
        }
        passed = False
    return ProbeResult(
        name=name,
        passed=passed,
        duration_seconds=time.monotonic() - started,
        detail=detail,
    )


def _create_frontier_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table tasks(
          id text primary key,
          priority integer not null default 0,
          lane text not null,
          title text not null,
          status text not null,
          branch text,
          owner text,
          note text,
          updated_at text
        );
        create table task_metadata(
          task_id text primary key,
          milestone text,
          work_type text,
          concurrency_key text,
          expected_minutes integer,
          evidence_policy text,
          created_at text,
          updated_at text
        );
        create table task_acceptance(
          task_id text,
          ordinal integer,
          criterion text
        );
        create table task_dependencies(
          task_id text,
          depends_on text,
          kind text,
          rationale text
        );
        create table brain_task_leases(
          task_id text,
          chat_id text,
          branch text,
          lease_until_epoch real
        );
        create table claims(
          task_id text,
          path_prefix text
        );
        """
    )
    ensure_frontier_schema(conn)


def _probe_route_lock_retry(tmp: Path) -> dict:
    db_path = tmp / "route-lock.sqlite"
    setup = sqlite3.connect(db_path)
    setup.execute("pragma journal_mode=wal")
    ensure_route_schema(setup)
    setup.close()

    holder = sqlite3.connect(db_path, timeout=0)
    holder.execute("pragma busy_timeout=0")
    holder.execute("begin immediate")
    holder.execute(
        """insert into route_jobs(
             dedupe_key,route_kind,state,meta_json,created_at,updated_at
           ) values('holder','TEST','NEW','{}','now','now')"""
    )

    result: dict = {}
    ready = threading.Event()

    def worker() -> None:
        conn = sqlite3.connect(db_path, timeout=0)
        conn.execute("pragma busy_timeout=0")
        ready.set()
        started = time.monotonic()
        try:
            job = claim_route(
                conn,
                RouteSpec(
                    dedupe_key="retry-probe",
                    route_kind="TEST",
                    task_id="sandbox",
                ),
            )
            result["route_id"] = job.id
            result["elapsed_seconds"] = round(
                time.monotonic() - started,
                4,
            )
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            conn.close()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    ready.wait(timeout=1)
    time.sleep(0.07)
    holder.commit()
    holder.close()
    thread.join(timeout=3)

    passed = (
        not thread.is_alive()
        and "route_id" in result
        and "error" not in result
        and float(result.get("elapsed_seconds", 0)) >= 0.04
    )
    return {
        "passed": passed,
        "writer_lock_was_real": True,
        "worker_completed": not thread.is_alive(),
        **result,
    }


def _probe_route_dedupe(tmp: Path) -> dict:
    db = sqlite3.connect(tmp / "route-dedupe.sqlite")
    ensure_route_schema(db)
    spec = RouteSpec(
        dedupe_key="same-semantic-effect",
        route_kind="TEST",
        task_id="sandbox",
    )
    first = claim_route(db, spec)
    second = claim_route(db, spec)
    count = db.execute(
        "select count(*) from route_jobs where dedupe_key=?",
        (spec.dedupe_key,),
    ).fetchone()[0]
    db.close()
    return {
        "passed": first.id == second.id and count == 1,
        "first_id": first.id,
        "second_id": second.id,
        "row_count": count,
    }


def _probe_frontier_dedupe(tmp: Path) -> dict:
    db = sqlite3.connect(tmp / "frontier.sqlite")
    db.row_factory = sqlite3.Row
    _create_frontier_schema(db)
    db.execute(
        """insert into tasks(
             id,priority,lane,title,status,branch,owner,note,updated_at
           ) values('ROOT',0,'research','root','READY',null,null,'','now')"""
    )
    db.execute(
        """insert into task_metadata(
             task_id,milestone,work_type,concurrency_key,expected_minutes,
             evidence_policy,created_at,updated_at
           ) values(
             'ROOT','sandbox','research','sandbox',10,
             'Global evidence required','now','now'
           )"""
    )
    db.commit()

    first = claim_frontier(
        db,
        parent_task_id="ROOT",
        predicate_text="recover exact historical packet pairing",
        origin_kind="CHAOS_CERT",
        origin_id="first",
    )
    db.execute(
        """insert into tasks(
             id,priority,lane,title,status,branch,owner,note,updated_at
           ) values(
             'CHILD',0,'research','child','READY',null,null,
             'Autoflow research child from AI evidence routing.','now'
           )"""
    )
    db.execute(
        """insert into task_metadata(
             task_id,milestone,work_type,concurrency_key,expected_minutes,
             evidence_policy,created_at,updated_at
           ) values(
             'CHILD','autoflow','research','sandbox',10,
             'Global evidence required','now','now'
           )"""
    )
    db.commit()
    register_child(
        db,
        first,
        child_task_id="CHILD",
        origin_kind="CHAOS_CERT",
        origin_id="first",
    )
    second = claim_frontier(
        db,
        parent_task_id="ROOT",
        predicate_text="recover exact historical packet pairing",
        origin_kind="CHAOS_CERT",
        origin_id="repeat",
    )
    rows = db.execute(
        "select count(*) from research_frontier"
    ).fetchone()[0]
    db.close()
    return {
        "passed": (
            first.create_allowed
            and not second.create_allowed
            and second.child_task_id == "CHILD"
            and rows == 1
        ),
        "first_create_allowed": first.create_allowed,
        "second_create_allowed": second.create_allowed,
        "second_child": second.child_task_id,
        "frontier_rows": rows,
        "reason": second.reason,
    }


def _write_pool_result(
    root: Path,
    job: str,
    role: str,
    *,
    duration: float,
) -> None:
    path = root / job / role / "pool-result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": 1,
                "role": role,
                "status": "success",
                "exit_code": 0,
                "duration_seconds": duration,
                "npm_script": "test",
            }
        )
    )


def _probe_resource_broker(tmp: Path) -> dict:
    artifacts = tmp / "remote-pool"
    _write_pool_result(artifacts, "heavy-history", "heavy", duration=40)
    _write_pool_result(artifacts, "light-history", "light", duration=10)
    health = [
        {
            "role": "heavy",
            "reachable": True,
            "available_slots": 2,
            "max_slots": 2,
            "cpu_count": 8,
            "memory_available_bytes": 8 * 1024**3,
        },
        {
            "role": "light",
            "reachable": True,
            "available_slots": 1,
            "max_slots": 1,
            "cpu_count": 4,
            "memory_available_bytes": 4 * 1024**3,
        },
    ]
    selected = choose_remote_role(
        health,
        artifacts,
        npm_script="test",
    )
    outage = [
        {**row, "reachable": False, "available_slots": 0}
        for row in health
    ]
    fallback = plan_workload(
        workload="verification",
        health_rows=outage,
        artifact_root=artifacts,
        npm_script="test",
    )
    private = plan_workload(
        workload="research",
        sensitivity="local_only",
        openai_allowed=True,
    )
    return {
        "passed": (
            selected in {"heavy", "light"}
            and fallback.selected_lane == "local"
            and private.selected_lane == "local"
        ),
        "selected_remote_role": selected,
        "remote_outage_lane": fallback.selected_lane,
        "private_research_lane": private.selected_lane,
    }


def _probe_supervisor_single_flight(tmp: Path) -> dict:
    root = tmp / "supervisor-root"
    root.mkdir(parents=True, exist_ok=True)
    heartbeat = root / "heartbeat.json"
    probe_file = root / "probe.txt"
    command = (
        "/bin/sh",
        "-c",
        f"printf x >> {probe_file}",
    )
    job = ScheduledJob(
        "sandbox_probe",
        command,
        60,
        5,
    )
    first = tick(
        root,
        heartbeat,
        jobs=(job,),
        now_epoch=100.0,
    )
    second = tick(
        root,
        heartbeat,
        jobs=(job,),
        now_epoch=101.0,
    )
    contents = probe_file.read_text() if probe_file.exists() else ""
    state = json.loads(heartbeat.read_text())
    return {
        "passed": (
            first["ran"] == ["sandbox_probe"]
            and second["ran"] == []
            and contents == "x"
            and state["last_runs"]["sandbox_probe"]["rc"] == 0
        ),
        "first_ran": first["ran"],
        "second_ran": second["ran"],
        "effect_count": len(contents),
        "recorded_rc": state["last_runs"]["sandbox_probe"]["rc"],
    }


def run_probes() -> list[ProbeResult]:
    with tempfile.TemporaryDirectory(prefix="logres-chaos-cert-") as td:
        root = Path(td)
        return [
            _timed("sqlite_writer_lock_retry", lambda: _probe_route_lock_retry(root)),
            _timed("route_semantic_dedupe", lambda: _probe_route_dedupe(root)),
            _timed("research_frontier_dedupe", lambda: _probe_frontier_dedupe(root)),
            _timed("resource_broker_fallback", lambda: _probe_resource_broker(root)),
            _timed("supervisor_single_effect", lambda: _probe_supervisor_single_flight(root)),
        ]


def canonical_sha(repo: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        text=True,
    ).strip()


def _cert_hash(payload: dict) -> str:
    body = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def certify(
    *,
    repo: Path,
    artifact_root: Path,
    shadow: bool,
) -> dict:
    if not shadow:
        raise ValueError(
            "chaos certification is shadow-only; pass --shadow"
        )
    probes = run_probes()
    payload = {
        "schema": CERT_SCHEMA,
        "kind": "logres-chaos-certification",
        "mode": "shadow",
        "sandbox_only": True,
        "production_control_db_opened": False,
        "canonical_sha": canonical_sha(repo),
        "created_at": _utc_now(),
        "probe_count": len(probes),
        "passed_count": sum(1 for probe in probes if probe.passed),
        "verdict": (
            "PASS"
            if probes and all(probe.passed for probe in probes)
            else "FAIL"
        ),
        "probes": [probe.to_dict() for probe in probes],
        "authority": {
            "merge": False,
            "deploy": False,
            "push": False,
            "production_db_write": False,
        },
    }
    payload["certification_sha256"] = _cert_hash(payload)

    artifact_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = artifact_root / (
        f"chaos-cert-{payload['canonical_sha'][:12]}-{stamp}.json"
    )
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temp, path)
    payload["artifact_path"] = str(path)
    return payload
