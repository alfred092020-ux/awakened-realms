import json
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Mapping


METRIC_KEYS = frozenset(
    {
        "throughput",
        "failure_rate",
        "verification_latency_seconds",
        "resource_cost",
        "task_quality",
    }
)

TERMINAL_BAD_QUEUE = {"QUARANTINED", "CONFLICT"}
TERMINAL_JOB_FAILURES = {"FAILED", "QUARANTINED"}


def _now() -> float:
    return time.time()


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists devin_evolution_runs(
          experiment_id integer primary key,
          fingerprint text not null unique,
          domain text not null,
          task_id text,
          state text not null,
          reason text not null default '',
          created_epoch real not null,
          updated_epoch real not null default 0,
          baseline_metrics_json text not null,
          after_metrics_json text,
          contract_json text not null,
          measurement_key text,
          measured_value real
        );
        create table if not exists devin_evolution_patterns(
          experiment_id integer primary key,
          fingerprint text not null unique,
          domain text not null,
          task_id text not null,
          state text not null,
          rule_json text not null,
          created_epoch real not null,
          verified_epoch real not null
        );
        create index if not exists idx_devin_evolution_runs_state
          on devin_evolution_runs(state,created_epoch);
        create index if not exists idx_devin_evolution_runs_domain
          on devin_evolution_runs(domain,created_epoch);
        """
    )
    conn.commit()


def load_policy(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("devin evolution policy must be a JSON object")
    return data


def _safe_json_object(raw: Any) -> dict[str, Any]:
    try:
        value = json.loads(str(raw or "{}"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}

def _scope_overlap(left: str, right: str) -> bool:
    a = str(left).rstrip("/") + "/"
    b = str(right).rstrip("/") + "/"
    return a.startswith(b) or b.startswith(a)


def _active_scope_conflict(conn: sqlite3.Connection, scopes: list[str]) -> str | None:
    try:
        rows = conn.execute(
            "select path_prefix,task_id,owner from claims order by path_prefix"
        ).fetchall()
    except sqlite3.OperationalError:
        return None
    for row in rows:
        claimed = str(row["path_prefix"] or "")
        if any(_scope_overlap(scope, claimed) for scope in scopes):
            return (
                f"active ownership conflict with {row['task_id']} "
                f"owner={row['owner']} scope={claimed}"
            )
    return None


def _validate_contract(row: sqlite3.Row, policy: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    source = _safe_json_object(row["source_json"])
    contract = source.get("evolution_contract")
    if not isinstance(contract, dict):
        return None, "explicit machine-readable evolution contract required"
    if int(contract.get("version") or 0) != 1:
        return None, "unsupported evolution contract version"
    domain = str(contract.get("domain") or "").strip()
    title = str(contract.get("title") or "").strip()
    lane = str(contract.get("lane") or "").strip()
    measurement_key = str(contract.get("measurement_key") or "").strip()
    if not domain or not title or not lane:
        return None, "evolution contract requires domain, title, and lane"
    if measurement_key not in METRIC_KEYS:
        return None, "evolution contract measurement_key is not allowlisted"
    if measurement_key != str(row["metric_name"] or ""):
        return None, "evolution contract measurement_key must match governor metric_name"
    scopes = contract.get("scopes")
    acceptance = contract.get("acceptance")
    if not isinstance(scopes, list) or not scopes:
        return None, "explicit non-empty file scopes are required"
    if not isinstance(acceptance, list) or not acceptance:
        return None, "explicit non-empty acceptance criteria are required"
    scopes = [str(item).strip() for item in scopes if str(item).strip()]
    acceptance = [str(item).strip() for item in acceptance if str(item).strip()]
    if not scopes or len(scopes) > int(policy.get("max_scopes", 6)):
        return None, "evolution scope count exceeds policy"
    if not acceptance or len(acceptance) > int(policy.get("max_acceptance", 8)):
        return None, "evolution acceptance count exceeds policy"
    allowed = [str(item) for item in policy.get("allowed_scope_prefixes", [])]
    if not allowed:
        return None, "no evolution scope prefixes are allowlisted"
    for scope in scopes:
        if scope.startswith("/") or ".." in Path(scope).parts:
            return None, f"invalid evolution scope: {scope}"
        if not any(scope.startswith(prefix) for prefix in allowed):
            return None, f"scope outside evolution allowlist: {scope}"
    allowed_lanes = [str(item) for item in policy.get("allowed_lanes", [])]
    if allowed_lanes and lane not in allowed_lanes:
        return None, f"lane outside evolution allowlist: {lane}"
    priority = int(contract.get("priority", 1))
    minutes = int(contract.get("expected_minutes", 60))
    if not 0 <= priority <= 9:
        return None, "priority must be 0..9"
    if not 5 <= minutes <= 240:
        return None, "expected_minutes must be 5..240"
    clean = dict(contract)
    clean["domain"] = domain
    clean["title"] = title
    clean["lane"] = lane
    clean["priority"] = priority
    clean["expected_minutes"] = minutes
    clean["measurement_key"] = measurement_key
    clean["scopes"] = scopes
    clean["acceptance"] = acceptance
    clean["depends"] = [str(x) for x in contract.get("depends", [])]
    clean["depends_integrated"] = [str(x) for x in contract.get("depends_integrated", [])]
    return clean, None

def snapshot_metrics(conn: sqlite3.Connection) -> dict[str, float]:
    done = int(conn.execute(
        "select count(*) from tasks where upper(status)='DONE'"
    ).fetchone()[0])
    jobs = conn.execute(
        "select state from swarm_jobs order by id desc limit 50"
    ).fetchall()
    terminal = [str(row[0] or "").upper() for row in jobs
                if str(row[0] or "").upper() not in {"RUNNING", "STARTING", "QUEUED"}]
    failed = sum(1 for state in terminal if state in TERMINAL_JOB_FAILURES)
    failure_rate = failed / max(1, len(terminal))
    verifications = conn.execute(
        "select status,duration_sec from verification order by ran_at desc limit 50"
    ).fetchall()
    durations = [float(row[1]) for row in verifications if row[1] is not None]
    pass_count = sum(1 for row in verifications if str(row[0] or "").upper() == "PASS")
    verification_latency = sum(durations) / len(durations) if durations else 0.0
    quality = pass_count / max(1, len(verifications))
    return {
        "throughput": float(done),
        "failure_rate": round(failure_rate, 6),
        "verification_latency_seconds": round(verification_latency, 6),
        "resource_cost": float(len(jobs)) + round(sum(durations), 6),
        "task_quality": round(quality, 6),
    }


def _record_run(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    contract: Mapping[str, Any],
    state: str,
    reason: str,
    now_epoch: float,
    task_id: str | None = None,
    baseline: Mapping[str, Any] | None = None,
) -> None:
    conn.execute(
        """insert or replace into devin_evolution_runs(
        experiment_id,fingerprint,domain,task_id,state,reason,created_epoch,
        updated_epoch,baseline_metrics_json,contract_json,measurement_key)
        values(?,?,?,?,?,?,?,?,?,?,?)""",
        (int(row["id"]), str(row["fingerprint"]), str(contract.get("domain") or "unknown"),
         task_id, state, reason, float(now_epoch), float(now_epoch),
         json.dumps(dict(baseline or {}), sort_keys=True),
         json.dumps(dict(contract), sort_keys=True),
         str(contract.get("measurement_key") or "")),
    )
    conn.commit()

def _task_id(policy: Mapping[str, Any], row: sqlite3.Row) -> str:
    prefix = str(policy.get("task_prefix") or "DEVIN-EVOLUTION")
    fingerprint = str(row["fingerprint"] or "")[:8].upper()
    return f"{prefix}-{int(row['id'])}-{fingerprint}"


def _task_command(
    policy: Mapping[str, Any], row: sqlite3.Row, contract: Mapping[str, Any]
) -> list[str]:
    task_id = _task_id(policy, row)
    evidence = {
        "source": "governor_evolution",
        "experiment_id": int(row["id"]),
        "fingerprint": str(row["fingerprint"]),
        "metric_name": str(row["metric_name"]),
        "baseline": float(row["baseline_value"]),
        "target": float(row["success_target"]),
        "rollback_threshold": float(row["rollback_threshold"]),
        "automatic_paid_devin_forbidden": True,
        "direct_merge_deploy_credential_authority": False,
    }
    argv = [
        str(policy["coordinator_bin"]), "add-task", task_id,
        str(contract["priority"]), str(contract["lane"]), str(contract["title"]),
        "--milestone", "post-release", "--work-type", "implementation",
        "--concurrency-key", f"devin-evolution:{contract['domain']}",
        "--minutes", str(contract["expected_minutes"]),
        "--evidence-policy", json.dumps(evidence, sort_keys=True),
    ]
    metric_acceptance = (
        f"Measure {row['metric_name']} against baseline={float(row['baseline_value'])}, "
        f"target={float(row['success_target'])}, rollback={float(row['rollback_threshold'])}; "
        "quarantine on guardrail or rollback breach."
    )
    authority_acceptance = (
        "Integration may occur only through the existing exact-SHA integration queue; "
        "no direct merge, deploy, credential, protected-branch, or budget authority."
    )
    for item in [*contract["acceptance"], metric_acceptance, authority_acceptance]:
        argv += ["--accept", str(item)]
    for scope in contract["scopes"]:
        argv += ["--scope", str(scope)]
    for dep in contract.get("depends", []):
        argv += ["--depends", str(dep)]
    for dep in contract.get("depends_integrated", []):
        argv += ["--depends-integrated", str(dep)]
    return argv


def _run(runner: Callable, argv: list[str]) -> subprocess.CompletedProcess:
    return runner(argv, capture_output=True, text=True, timeout=60)


def _existing_run(conn: sqlite3.Connection, row: sqlite3.Row) -> sqlite3.Row | None:
    return conn.execute(
        "select * from devin_evolution_runs where experiment_id=? or fingerprint=?",
        (int(row["id"]), str(row["fingerprint"])),
    ).fetchone()


def _cooldown_active(conn: sqlite3.Connection, domain: str, now_epoch: float, seconds: int) -> bool:
    row = conn.execute(
        """select max(created_epoch) from devin_evolution_runs
        where domain=? and task_id is not null""",
        (domain,),
    ).fetchone()
    return bool(row and row[0] is not None and float(row[0]) > now_epoch - seconds)

def _open_generated_count(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "select count(*) from devin_evolution_runs where state in ('CREATED','RUNNING')"
    ).fetchone()
    return int(row[0] if row else 0)


def tick(
    conn: sqlite3.Connection,
    policy: Mapping[str, Any],
    *,
    runner: Callable = subprocess.run,
    now_epoch: float | None = None,
) -> dict[str, Any]:
    ensure_schema(conn)
    now_epoch = float(_now() if now_epoch is None else now_epoch)
    report: dict[str, Any] = {"created": [], "quarantined": [], "deferred": []}
    if not bool(policy.get("enabled", False)):
        report["disabled"] = True
        return report
    rows = conn.execute(
        """select * from governor_experiments
        where status='EVALUATED' and recommendation='KEEP'
        order by id"""
    ).fetchall()
    created_limit = max(0, int(policy.get("max_generated_per_tick", 1)))
    open_cap = max(0, int(policy.get("max_open_generated", 2)))
    cooldown = max(0, int(policy.get("cooldown_seconds", 3600)))
    for row in rows:
        if len(report["created"]) >= created_limit:
            break
        if _existing_run(conn, row):
            continue
        contract, error = _validate_contract(row, policy)
        if error or contract is None:
            contract = contract or {"domain": "unknown"}
            _record_run(conn, row, contract, "QUARANTINED", error or "invalid contract", now_epoch)
            report["quarantined"].append(int(row["id"]))
            continue
        conflict = _active_scope_conflict(conn, contract["scopes"])
        if conflict:
            _record_run(conn, row, contract, "QUARANTINED", conflict, now_epoch)
            report["quarantined"].append(int(row["id"]))
            continue
        if _open_generated_count(conn) >= open_cap:
            reason = "hard cap on open generated evolution work reached"
            _record_run(conn, row, contract, "DEFERRED", reason, now_epoch)
            report["deferred"].append(int(row["id"]))
            continue
        if _cooldown_active(conn, contract["domain"], now_epoch, cooldown):
            reason = f"domain cooldown active for {contract['domain']}"
            _record_run(conn, row, contract, "DEFERRED", reason, now_epoch)
            report["deferred"].append(int(row["id"]))
            continue
        baseline = snapshot_metrics(conn)
        task_id = _task_id(policy, row)
        proc = _run(runner, _task_command(policy, row, contract))
        if int(proc.returncode) != 0:
            reason = "coordinator task creation failed: " + str(proc.stderr or proc.stdout)[-500:]
            _record_run(conn, row, contract, "QUARANTINED", reason, now_epoch,
                        task_id=task_id, baseline=baseline)
            report["quarantined"].append(int(row["id"]))
            continue
        _record_run(conn, row, contract, "CREATED", "", now_epoch,
                    task_id=task_id, baseline=baseline)
        report["created"].append(task_id)
        swarm = _run(runner, [str(policy["swarm_bin"]), "tick"])
        if int(swarm.returncode) != 0:
            conn.execute(
                "update devin_evolution_runs set reason=?,updated_epoch=? where experiment_id=?",
                ("guarded swarm dispatch deferred: " + str(swarm.stderr or swarm.stdout)[-500:],
                 now_epoch, int(row["id"])),
            )
            conn.commit()
    return report

def _latest_verification(conn: sqlite3.Connection, branch: str) -> sqlite3.Row | None:
    if not branch:
        return None
    return conn.execute(
        """select * from verification where ref=?
        order by ran_at desc limit 1""",
        (branch,),
    ).fetchone()


def _queue_state(conn: sqlite3.Connection, task_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """select * from integration_queue where task_id=?
        order by coalesce(integrated_at,updated_at,queued_at) desc limit 1""",
        (task_id,),
    ).fetchone()


def _rollback_hit(direction: str, measured: float, threshold: float) -> bool:
    if direction == "lower":
        return measured >= threshold
    if direction == "higher":
        return measured <= threshold
    return True


def _task_has_executable_tests(conn: sqlite3.Connection, task_id: str) -> bool:
    rows = conn.execute(
        "select path_prefix from task_scopes where task_id=?",
        (task_id,),
    ).fetchall()
    for row in rows:
        scope = str(row[0] or "")
        name = Path(scope).name
        if "/tests/" in scope or name.startswith("test_") or ".test." in name:
            return True
    return False


def _quarantine_run(
    conn: sqlite3.Connection, experiment_id: int, task_id: str,
    reason: str, after: Mapping[str, Any] | None = None,
) -> None:
    conn.execute(
        """update devin_evolution_runs set state='QUARANTINED',reason=?,
        updated_epoch=?,after_metrics_json=? where experiment_id=?""",
        (reason, _now(), json.dumps(dict(after or {}), sort_keys=True), experiment_id),
    )
    conn.commit()

def _persist_pattern(
    conn: sqlite3.Connection,
    run: sqlite3.Row,
    contract: Mapping[str, Any],
    task_id: str,
    now_epoch: float,
) -> None:
    rule = {
        "experiment_id": int(run["experiment_id"]),
        "source_fingerprint": str(run["fingerprint"]),
        "domain": str(run["domain"]),
        "verified_task_id": task_id,
        "test_covered": True,
        "scopes": list(contract.get("scopes", [])),
        "acceptance": list(contract.get("acceptance", [])),
        "authority": "NORMAL_BRAIN_TASK_ONLY_NO_DIRECT_MERGE_DEPLOY_CREDENTIAL_BUDGET",
    }
    conn.execute(
        """insert or replace into devin_evolution_patterns(
        experiment_id,fingerprint,domain,task_id,state,rule_json,created_epoch,verified_epoch)
        values(?,?,?,?,?,?,?,?)""",
        (int(run["experiment_id"]), str(run["fingerprint"]), str(run["domain"]),
         task_id, "VERIFIED", json.dumps(rule, sort_keys=True),
         float(run["created_epoch"]), float(now_epoch)),
    )
    conn.commit()


def reconcile_runs(
    conn: sqlite3.Connection,
    policy: Mapping[str, Any],
    *,
    metrics_fn: Callable[[sqlite3.Connection], Mapping[str, float]] = snapshot_metrics,
) -> dict[str, Any]:
    ensure_schema(conn)
    report: dict[str, list[str]] = {"verified": [], "quarantined": [], "pending": []}
    rows = conn.execute(
        """select r.*,g.direction,g.rollback_threshold,g.metric_name
        from devin_evolution_runs r
        join governor_experiments g on g.id=r.experiment_id
        where r.state in ('CREATED','RUNNING') order by r.experiment_id"""
    ).fetchall()
    for run in rows:
        task_id = str(run["task_id"] or "")
        task = conn.execute(
            "select * from tasks where id=?", (task_id,)
        ).fetchone()
        if task is None:
            report["pending"].append(task_id)
            continue
        task_status = str(task["status"] or "").upper()
        if task_status == "BLOCKED_EVIDENCE":
            _quarantine_run(
                conn, int(run["experiment_id"]), task_id,
                "generated task became BLOCKED_EVIDENCE",
            )
            report["quarantined"].append(task_id)
            continue
        try:
            regression = conn.execute(
                """select id,kind,summary from regressions
                where task_id=? and upper(status)='OPEN'
                order by id desc limit 1""",
                (task_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            regression = None
        if regression is not None:
            _quarantine_run(
                conn, int(run["experiment_id"]), task_id,
                f"guardrail regression open: {regression['kind']} {regression['summary']}",
            )
            report["quarantined"].append(task_id)
            continue
        branch = str(task["branch"] or "")
        verification = _latest_verification(conn, branch)
        if verification is not None:
            verification_status = str(verification["status"] or "").upper()
            if verification_status not in {"PASS", "CACHED"}:
                _quarantine_run(
                    conn, int(run["experiment_id"]), task_id,
                    f"verification failed: {verification_status}",
                )
                report["quarantined"].append(task_id)
                continue
        queue = _queue_state(conn, task_id)
        if queue is not None and str(queue["status"] or "").upper() in TERMINAL_BAD_QUEUE:
            state = str(queue["status"] or "").upper()
            _quarantine_run(
                conn, int(run["experiment_id"]), task_id,
                f"integration queue terminal failure: {state}",
            )
            report["quarantined"].append(task_id)
            continue
        if task_status != "DONE" or verification is None:
            report["pending"].append(task_id)
            continue
        if queue is None or str(queue["status"] or "").upper() != "INTEGRATED":
            report["pending"].append(task_id)
            continue
        after = dict(metrics_fn(conn))
        metric_key = str(run["measurement_key"] or run["metric_name"] or "")
        value = after.get(metric_key)
        if not isinstance(value, (int, float)):
            _quarantine_run(
                conn, int(run["experiment_id"]), task_id,
                f"measurement unavailable for {metric_key}", after,
            )
            report["quarantined"].append(task_id)
            continue
        measured = float(value)
        if _rollback_hit(
            str(run["direction"]), measured, float(run["rollback_threshold"])
        ):
            _quarantine_run(
                conn, int(run["experiment_id"]), task_id,
                f"rollback threshold exceeded for {metric_key}: {measured}", after,
            )
            report["quarantined"].append(task_id)
            continue
        conn.execute(
            """update devin_evolution_runs set state='VERIFIED',reason='',
            updated_epoch=?,after_metrics_json=?,measured_value=?
            where experiment_id=?""",
            (_now(), json.dumps(after, sort_keys=True), measured,
             int(run["experiment_id"])),
        )
        conn.commit()
        contract = _safe_json_object(run["contract_json"])
        if _task_has_executable_tests(conn, task_id):
            _persist_pattern(conn, run, contract, task_id, _now())
        report["verified"].append(task_id)
    return report


def status_report(conn: sqlite3.Connection) -> dict[str, Any]:
    ensure_schema(conn)
    runs = [dict(row) for row in conn.execute(
        "select * from devin_evolution_runs order by experiment_id desc limit 50"
    )]
    patterns = [dict(row) for row in conn.execute(
        "select * from devin_evolution_patterns order by verified_epoch desc limit 50"
    )]
    return {
        "runs": runs,
        "patterns": patterns,
        "metrics": snapshot_metrics(conn),
        "authority": "NORMAL_BRAIN_TASK_ONLY_NO_DIRECT_MERGE_DEPLOY_CREDENTIAL_BUDGET",
    }
