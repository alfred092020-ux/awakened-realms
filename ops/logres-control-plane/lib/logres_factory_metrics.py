"""Deterministic factory metrics for the Logres control plane.

Reads the existing Brain control database (control.sqlite), local git, and
host /proc sources. Never creates another database. Every signal is either a
measured value or ``{"value": null, "status": "unavailable", "reason": ...}``;
no signal is invented and there is no subjective self-scoring.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Iterable, Mapping

DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "factory_metrics.json"
)

DEFAULT_CONFIG = {
    "version": 1,
    "domains": {
        "game_prefixes": ["game/", "client/", "src/", "assets/"],
        "infra_prefixes": ["ops/", "tools/", "infra/", "bin/", "lib/", "tests/"],
    },
    "windows_seconds": {"hour": 3600, "day": 86400},
    "worker_capacity": 4,
    "verifier_saturation_backlog": 8,
    "baseline_tolerance_ratio": 0.05,
    "devin_models_timeout_sec": 10,
    "repo_path_env": "LOGRES_ROOT",
}

def load_config(path: Path | None = None) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    try:
        raw = json.loads((path or DEFAULT_CONFIG_PATH).read_text())
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                    merged = dict(cfg[k])
                    merged.update(v)
                    cfg[k] = merged
                else:
                    cfg[k] = v
    except (OSError, json.JSONDecodeError):
        pass
    return cfg


def classify_scope(path: str, cfg: Mapping) -> str:
    """Classify a path prefix as 'game' progress or 'infra' control-plane churn."""
    p = str(path or "").lstrip("/")
    dom = cfg.get("domains") or {}
    for pref in dom.get("game_prefixes") or []:
        if p.startswith(pref):
            return "game"
    for pref in dom.get("infra_prefixes") or []:
        if p.startswith(pref):
            return "infra"
    return "unknown"


def _exists(conn, name: str) -> bool:
    return (
        conn.execute(
            "select 1 from sqlite_master where type='table' and name=?", (name,)
        ).fetchone()
        is not None
    )


def _columns(conn, name: str) -> set[str]:
    try:
        return {r[1] for r in conn.execute(f"pragma table_info({name})")}
    except sqlite3.Error:
        return set()


def _unavailable(reason: str, unit: str = "", domain: str = "infra") -> dict:
    return {"value": None, "status": "unavailable", "reason": reason,
            "unit": unit, "domain": domain}


def _ok(value, unit: str, domain: str, **extra) -> dict:
    m = {"value": value, "status": "ok", "unit": unit, "domain": domain}
    m.update(extra)
    return m


def _safe(fn, unit: str, domain: str) -> dict:
    try:
        return fn()
    except Exception as exc:  # never invent a signal
        return _unavailable(f"{type(exc).__name__}: {exc}", unit, domain)


def _percentile(items: list[float], q: float) -> float | None:
    if not items:
        return None
    items = sorted(items)
    idx = max(0, min(len(items) - 1, int(q * len(items) + 0.999) - 1))
    return items[idx]


def _summ(values: Iterable[float]) -> dict:
    vals = [float(v) for v in values if v is not None and float(v) >= 0]
    return {
        "samples": len(vals),
        "median": (sorted(vals)[len(vals) // 2] if vals else None),
        "p95": _percentile(vals, 0.95),
    }


def _task_domain_map(conn, cfg) -> dict[str, str] | None:
    """Map task_id -> domain via task_scopes; None when table missing."""
    if not _exists(conn, "task_scopes"):
        return None
    cols = _columns(conn, "task_scopes")
    tid_col = "task_id" if "task_id" in cols else ("id" if "id" in cols else None)
    path_col = "path_prefix" if "path_prefix" in cols else None
    if not tid_col or not path_col:
        return None
    out: dict[str, str] = {}
    for row in conn.execute(f"select {tid_col},{path_col} from task_scopes"):
        dom = classify_scope(row[1], cfg)
        prev = out.get(row[0])
        if prev != "game":  # game scope wins over infra/unknown
            out[row[0]] = dom if prev is None or dom == "game" else prev
    return out


# --- individual metric collectors ----------------------------------------

def m_integrations(conn, cfg, now):
    if not _exists(conn, "integration_queue"):
        return _unavailable("table integration_queue missing", "count", "game")
    cols = _columns(conn, "integration_queue")
    tcol = next(
        (c for c in ("integrated_at", "updated_at", "queued_at") if c in cols), None
    )
    if not tcol:
        return _unavailable("no usable timestamp column", "count", "game")
    domain_map = _task_domain_map(conn, cfg)
    rows = conn.execute(
        f"select task_id,{tcol} from integration_queue where status='INTEGRATED'"
    ).fetchall()
    counts = {"hour": {"game": 0, "infra": 0, "unknown": 0},
              "day": {"game": 0, "infra": 0, "unknown": 0}}
    wins = cfg["windows_seconds"]
    for task_id, ts in rows:
        try:
            tsf = float(ts)
        except (TypeError, ValueError):
            continue
        dom = (domain_map or {}).get(task_id, "unknown")
        for w in ("hour", "day"):
            if now - wins[w] <= tsf <= now:
                counts[w][dom] += 1
    return _ok(counts, "count", "game",
               definition="verified integrations per hour/day, split by task scope domain")


def _latency_samples(conn, sql_ready, sql_late, args=()):
    """Return list of (completed_ts, duration) pairs from two event queries."""
    ready = {r[0]: float(r[1]) for r in conn.execute(sql_ready, args)}
    pairs = []
    for tid, late_ts in conn.execute(sql_late, args):
        if tid in ready and late_ts is not None:
            d = float(late_ts) - ready[tid]
            if d >= 0:
                pairs.append((float(late_ts), d))
    return pairs


def m_ready_to_lease(conn, cfg, now):
    if not (_exists(conn, "task_state_history") and _exists(conn, "lease_history")):
        return _unavailable("task_state_history/lease_history missing", "seconds")
    pairs = _latency_samples(
        conn,
        "select task_id,min(ts_epoch) from task_state_history "
        "where status='READY' group by task_id",
        "select task_id,min(ts_epoch) from lease_history "
        "where action='ACQUIRE' group by task_id",
    )
    return _ok(_summ(d for _, d in pairs), "seconds", "infra",
               definition="READY timestamp -> first lease ACQUIRE")


def m_work_latency(conn, cfg, now):
    if not (_exists(conn, "task_state_history") and _exists(conn, "lease_history")):
        return _unavailable("task_state_history/lease_history missing", "seconds")
    pairs = _latency_samples(
        conn,
        "select task_id,min(ts_epoch) from lease_history "
        "where action='ACQUIRE' group by task_id",
        "select task_id,min(ts_epoch) from task_state_history "
        "where status='DONE' group by task_id",
    )
    return _ok(_summ(d for _, d in pairs), "seconds", "infra",
               definition="lease ACQUIRE -> DONE timestamp")


def m_verifier_queue(conn, cfg, now):
    if not _exists(conn, "integration_queue"):
        return _unavailable("integration_queue missing", "seconds")
    cols = _columns(conn, "integration_queue")
    if not {"queued_at", "verified_at"} <= cols and not {"queued_at", "updated_at"} <= cols:
        return _unavailable("queued_at/verified_at columns missing", "seconds")
    late = "verified_at" if "verified_at" in cols else "updated_at"
    vals = []
    for q, v in conn.execute(
        f"select queued_at,{late} from integration_queue "
        "where status in ('PREFLIGHT_VERIFIED','INTEGRATED')"
    ):
        try:
            d = float(v) - float(q)
        except (TypeError, ValueError):
            continue
        if d >= 0:
            vals.append(d)
    return _ok(_summ(vals), "seconds", "infra",
               definition="integration_queue queued_at -> preflight verified")


def m_retries(conn, cfg, now):
    if not _exists(conn, "lease_history"):
        return _unavailable("lease_history missing", "count")
    win = cfg["windows_seconds"]["day"]
    total = retries = 0
    for tid, n in conn.execute(
        "select task_id,count(*) from lease_history where action='ACQUIRE' "
        "and ts_epoch>=? group by task_id",
        (now - win,),
    ):
        total += 1
        if n > 1:
            retries += 1
    return _ok({"tasks_leased": total, "retried_tasks": retries}, "count", "infra",
               definition="tasks with >1 lease ACQUIRE in last day")


def m_rework(conn, cfg, now):
    out = {}
    if _exists(conn, "regressions"):
        total = conn.execute("select count(*) from regressions").fetchone()[0]
        open_n = conn.execute(
            "select count(*) from regressions where status='OPEN'"
        ).fetchone()[0]
        out["regressions_open"] = open_n
        out["regressions_total"] = total
    else:
        out["regressions_open"] = None
        out["regressions_total"] = None
    if _exists(conn, "task_state_history"):
        done = conn.execute(
            "select count(distinct task_id) from task_state_history where status='DONE'"
        ).fetchone()[0]
        reworked = conn.execute(
            """select count(distinct task_id) from task_state_history t
               where t.status='READY' and exists(
                 select 1 from task_state_history d
                 where d.task_id=t.task_id and d.status='DONE'
                   and d.ts_epoch<t.ts_epoch)"""
        ).fetchone()[0]
        out["rework_rate"] = (reworked / done) if done else None
        out["done_tasks"] = done
    else:
        out["rework_rate"] = None
    status = "ok" if any(v is not None for v in out.values()) else "unavailable"
    m = {"value": out, "status": status, "unit": "ratio", "domain": "infra",
         "definition": "regressions + tasks returning to READY after DONE"}
    if status == "unavailable":
        m["reason"] = "regressions/task_state_history missing"
    return m


def m_branch_age(conn, cfg, now, repo=None, run_cmd=None):
    if not _exists(conn, "brain_task_leases"):
        return _unavailable("brain_task_leases missing", "seconds")
    cols = _columns(conn, "brain_task_leases")
    if "branch" not in cols:
        return _unavailable("branch column missing", "seconds")
    repo = repo or Path(os.environ.get(cfg.get("repo_path_env", "LOGRES_ROOT"),
                                       "/home/ubuntu/logres"))
    run = run_cmd or (lambda a: subprocess.run(
        a, capture_output=True, text=True, timeout=15))
    ages = []
    for (branch,) in conn.execute(
        "select distinct branch from brain_task_leases where branch is not null"
    ):
        r = run(["git", "-C", str(repo), "merge-base", "HEAD", str(branch)])
        if r.returncode != 0 or not r.stdout.strip():
            continue
        t = run(["git", "-C", str(repo), "show", "-s", "--format=%ct",
                 r.stdout.strip()])
        if t.returncode == 0 and t.stdout.strip().isdigit():
            age = now - int(t.stdout.strip())
            if age >= 0:
                ages.append(age)
    if not ages:
        return _unavailable("no resolvable worker branches", "seconds")
    return _ok(_summ(ages), "seconds", "infra",
               definition="now - merge-base commit time of leased worker branches")


def m_utilization(conn, cfg, now):
    if not _exists(conn, "brain_task_leases"):
        return _unavailable("brain_task_leases missing", "ratio")
    active = conn.execute(
        "select count(*) from brain_task_leases where lease_until_epoch>?",
        (now,),
    ).fetchone()[0]
    cap = int(cfg.get("worker_capacity") or 0)
    if cap <= 0:
        return _unavailable("worker_capacity not configured", "ratio")
    return _ok({"active_workers": active, "capacity": cap,
                "utilization": active / cap}, "ratio", "infra",
               definition="active leases / configured worker capacity")


def m_critical_path(conn, cfg, now):
    if not _exists(conn, "mission_objectives"):
        return _unavailable("mission_objectives missing", "ratio", "game")
    from logres_mission import mission_status  # existing Brain source
    st = mission_status(conn)
    roots = st.get("missions") or []
    return _ok({
        "progress_percent": roots[0]["progress_percent"] if roots else None,
        "leaf_counts": st.get("leaf_counts"),
        "state": roots[0]["state"] if roots else "EMPTY",
    }, "percent", "game",
        definition="mission critical-path completion from mission_status")


def m_host(conn, cfg, now, **_):
    out = {}
    try:
        for name in ("cpu", "memory", "io"):
            for line in Path(f"/proc/pressure/{name}").read_text().splitlines():
                if line.startswith("some "):
                    for part in line.split():
                        if part.startswith("avg10="):
                            out[f"psi_{name}_some_avg10"] = float(part.split("=")[1])
    except OSError:
        out["psi"] = None
    try:
        mem = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, _, rest = line.partition(":")
            if k in ("MemTotal", "MemAvailable"):
                mem[k] = int(rest.strip().split()[0])
        if mem:
            out["mem_available_ratio"] = (
                mem["MemAvailable"] / mem["MemTotal"] if mem.get("MemTotal") else None
            )
    except OSError:
        out["mem_available_ratio"] = None
    try:
        st = os.statvfs("/")
        out["disk_available_ratio"] = (
            st.f_bavail / st.f_blocks if st.f_blocks else None
        )
    except OSError:
        out["disk_available_ratio"] = None
    return _ok(out, "ratio", "host",
               definition="host PSI avg10, mem/disk availability from /proc")


def m_verifier_saturation(conn, cfg, now):
    if not _exists(conn, "integration_queue"):
        return _unavailable("integration_queue missing", "ratio")
    backlog = conn.execute(
        "select count(*) from integration_queue "
        "where status not in ('INTEGRATED','SUPERSEDED')"
    ).fetchone()[0]
    thresh = int(cfg.get("verifier_saturation_backlog") or 0)
    ratio = (backlog / thresh) if thresh > 0 else None
    return _ok({"backlog": backlog, "saturation_threshold": thresh,
                "saturation": ratio}, "ratio", "infra",
               definition="open integration_queue rows / configured backlog threshold")


def m_devin(conn, cfg, now, run_cmd=None, **_):
    timeout = int(cfg.get("devin_models_timeout_sec") or 10)
    run = run_cmd or (lambda a: subprocess.run(
        a, capture_output=True, text=True, timeout=timeout))
    try:
        r = run(["devin", "models", "list"])
    except Exception as exc:
        return _unavailable(f"devin models list failed: {type(exc).__name__}", "count")
    if r.returncode != 0:
        return _unavailable("devin models list exited nonzero", "count")
    try:
        from logres_devin import parse_models_report
        report = parse_models_report(r.stdout)
    except Exception as exc:
        return _unavailable(f"models report parse failed: {type(exc).__name__}", "count")
    variants = report.get("variants") or {}
    free = [u for u, t in variants.items() if str(t).strip().lower() == "free"]
    return _ok({"models_reported": len(variants), "free_variants": len(free)},
               "count", "infra",
               definition="devin models list availability; quota not exposed by CLI")


COLLECTORS = [
    ("verified_integrations", m_integrations),
    ("ready_to_lease_latency", m_ready_to_lease),
    ("work_latency", m_work_latency),
    ("verifier_queue_latency", m_verifier_queue),
    ("retries_recoveries", m_retries),
    ("rework_revert_regression", m_rework),
    ("worker_utilization", m_utilization),
    ("critical_path_completion", m_critical_path),
    ("verifier_saturation", m_verifier_saturation),
]

ENV_COLLECTORS = [
    ("branch_age", m_branch_age),
    ("host_resources", m_host),
    ("devin_model_quota", m_devin),
]


def collect_metrics(conn, cfg=None, now=None, repo=None, run_cmd=None) -> dict:
    cfg = cfg or DEFAULT_CONFIG
    now = float(now if now is not None else time.time())
    metrics = {}
    for name, fn in COLLECTORS:
        metrics[name] = _safe(lambda: fn(conn, cfg, now), "", "infra")
    for name, fn in ENV_COLLECTORS:
        metrics[name] = _safe(
            lambda fn=fn: fn(conn, cfg, now, repo=repo, run_cmd=run_cmd),
            "", "infra")
    unavailable = [n for n, m in metrics.items() if m.get("status") != "ok"]
    return {
        "ts": now,
        "version": cfg.get("version", 1),
        "metrics": metrics,
        "unavailable": unavailable,
    }


def metric_definitions(cfg=None) -> dict:
    defs = {}
    for name, fn in COLLECTORS + ENV_COLLECTORS:
        defs[name] = {"domain": "game" if name in (
            "verified_integrations", "critical_path_completion") else
            ("host" if name == "host_resources" else "infra")}
    return defs


def timeseries_lines(snapshot: Mapping) -> list[str]:
    """Appendable one-JSON-object-per-line output for time-series ingestion."""
    lines = []
    for name, m in sorted(snapshot["metrics"].items()):
        lines.append(json.dumps({
            "ts": snapshot["ts"],
            "metric": name,
            "domain": m.get("domain"),
            "unit": m.get("unit"),
            "status": m.get("status"),
            "value": m.get("value"),
            "reason": m.get("reason"),
        }, sort_keys=True))
    return lines


def compare_baseline(current: Mapping, baseline: Mapping | None,
                     tolerance_ratio: float = 0.05) -> dict:
    """Deterministic change detection. Returns stable/changed/no_baseline per
    comparable numeric leaf. Never produces a subjective score."""
    if not baseline:
        return {n: "no_baseline" for n in current.get("metrics", {})}
    base_metrics = baseline.get("metrics", {})
    out = {}
    for name, m in current.get("metrics", {}).items():
        bm = base_metrics.get(name)
        if not bm or bm.get("status") != "ok" or m.get("status") != "ok":
            out[name] = "no_baseline"
            continue
        diffs = _numeric_diffs(m.get("value"), bm.get("value"), tolerance_ratio)
        out[name] = "changed" if diffs else ("stable" if diffs is not None else
                                             "no_baseline")
    return out


def _numeric_diffs(cur, base, tol, prefix="") -> dict | None:
    """Return dict of changed leaf paths, or None if not comparable."""
    changed = {}
    comparable = False
    if isinstance(cur, (int, float)) and isinstance(base, (int, float)):
        denom = abs(float(base))
        delta = abs(float(cur) - float(base))
        if denom == 0:
            return {"": float(cur)} if float(cur) != 0 else {}
        return {"": delta / denom} if delta / denom > tol else {}
    if isinstance(cur, dict) and isinstance(base, dict):
        for k in cur:
            if k in base:
                sub = _numeric_diffs(cur[k], base[k], tol, prefix + k + ".")
                if sub is not None:
                    comparable = True
                    for p, v in sub.items():
                        changed[prefix + k + "." + p] = v
        return changed if comparable else None
    if isinstance(cur, list) and isinstance(base, list) and cur and base:
        return None
    return None
