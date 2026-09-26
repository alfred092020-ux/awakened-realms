from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_CONFIG = {
    "confidence_threshold": 0.6,
    "material_confidence_floor": 0.6,
    "high_cost_threshold": 0.7,
    "verification_failure_threshold": 2,
    "cooldown_seconds": 600,
    "max_consultations_per_subject": 4,
    "max_consultations_per_task": 8,
    "exempt_kinds": ["low_risk_reversible", "docs_only", "mechanical_refactor"],
    "allow_low_risk_proceed": True,
    "peer_engine": {"identity": "peer-1", "engine": "deterministic-fallback"},
}

TRIGGERS = (
    "conflicting_evidence",
    "low_material_confidence",
    "architecture_policy_change",
    "ambiguous_history",
    "irreversible_high_cost",
    "repeated_verification_failure",
    "planner_implementer_disagreement",
)

_HIGH_IMPACT = ("high", "critical", "irreversible")
_SECRET_KEY = re.compile(r"(token|secret|password|passwd|api[_-]?key|credential|private[_-]?key|bearer)", re.I)
_SECRET_VAL = re.compile(r"(sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{8,}|AKIA[0-9A-Z]{8,}|eyJ[A-Za-z0-9_-]{8,})")
_MAX_STR = 2000


def utcnow():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat(timespec="seconds")


def load_config(path=None):
    cfg = dict(DEFAULT_CONFIG)
    if path is None:
        path = Path(__file__).resolve().parents[1] / "config" / "peer_consultation.json"
    try:
        data = json.loads(Path(path).read_text())
        if isinstance(data, dict):
            cfg.update(data)
    except (OSError, ValueError):
        pass
    return cfg


def ensure_schema(conn: sqlite3.Connection):
    conn.executescript(
        """
        create table if not exists peer_consultations(
          id integer primary key autoincrement,
          created_at text not null,
          dedupe_key text not null,
          task_id text,
          payload_json text not null
        );
        create index if not exists idx_peer_consultations_dedupe
          on peer_consultations(dedupe_key, created_at);
        create index if not exists idx_peer_consultations_task
          on peer_consultations(task_id, created_at);
        """
    )
    conn.commit()


def detect_triggers(request: dict, config: dict | None = None) -> list[str]:
    cfg = config or DEFAULT_CONFIG
    found = []

    evidence = request.get("evidence") or []
    verdicts = {str(e.get("supports", "")).lower() for e in evidence if isinstance(e, dict)}
    if request.get("conflicting_evidence") or ("yes" in verdicts and "no" in verdicts):
        found.append("conflicting_evidence")

    conf = request.get("confidence")
    if conf is not None and float(conf) < float(cfg["material_confidence_floor"]):
        found.append("low_material_confidence")

    kind = str(request.get("change_kind") or "").lower()
    if kind in ("architecture", "policy"):
        found.append("architecture_policy_change")

    history = request.get("historical_precedents") or []
    outcomes = {str(h.get("outcome", "")).lower() for h in history if isinstance(h, dict)}
    if request.get("ambiguous_history") or ("success" in outcomes and "failure" in outcomes):
        found.append("ambiguous_history")

    reversible = request.get("reversible", True)
    cost = float(request.get("cost", 0.0) or 0.0)
    impact = str(request.get("impact") or "").lower()
    if reversible is False or cost >= float(cfg["high_cost_threshold"]) or impact in _HIGH_IMPACT:
        found.append("irreversible_high_cost")

    failures = int(request.get("verification_failures", 0) or 0)
    if failures >= int(cfg["verification_failure_threshold"]):
        found.append("repeated_verification_failure")

    planner = request.get("planner_recommendation")
    implementer = request.get("implementer_recommendation")
    if planner is not None and implementer is not None and planner != implementer:
        found.append("planner_implementer_disagreement")

    return found


def is_exempt(request: dict, config: dict) -> bool:
    kind = str(request.get("change_kind") or "").lower()
    reasons = {str(r).lower() for r in (request.get("exempt_reasons") or [])}
    exempt_kinds = {str(k).lower() for k in config.get("exempt_kinds", [])}
    if kind and kind in exempt_kinds:
        return True
    if reasons & exempt_kinds:
        return True
    return False


def dedupe_key(request: dict, triggers: list[str]) -> str:
    question = str(request.get("question") or "")
    subject = str(request.get("subject") or request.get("task_id") or "")
    raw = f"{subject}|{','.join(sorted(triggers))}|{question}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def default_peer_pass(request: dict, triggers: list[str], config: dict) -> dict:
    """Deterministic fallback peer pass when no external engine is available."""
    peer = config.get("peer_engine", {})
    hypotheses = []
    for t in triggers:
        hypotheses.append({"hypothesis": f"{t} may invalidate the plan", "source": "peer"})
    planner = request.get("planner_recommendation")
    implementer = request.get("implementer_recommendation")
    if "planner_implementer_disagreement" in triggers:
        recommendation = implementer if implementer is not None else planner
        rationale = "peer defers to implementer absent contrary evidence"
    else:
        recommendation = planner if planner is not None else "proceed_with_caution"
        rationale = "no contradictory internal evidence found"
    return {
        "peer_identity": peer.get("identity", "peer-1"),
        "peer_engine": peer.get("engine", "deterministic-fallback"),
        "hypotheses": hypotheses,
        "recommendation": recommendation,
        "rationale": rationale,
    }


def default_evidence_pass(request: dict) -> dict:
    """Evaluate supplied evidence/test results deterministically.

    Evidence refs: list of {"ref": ..., "supports": "yes"|"no", "kind": "test"|"evidence"}.
    Returns resolved=True when evidence agrees on a direction.
    """
    evidence = request.get("evidence") or []
    refs = []
    yes = no = 0
    for e in evidence:
        if not isinstance(e, dict):
            continue
        refs.append(str(e.get("ref") or e.get("kind") or "evidence"))
        s = str(e.get("supports", "")).lower()
        if s in ("yes", "pass", "true", "supports"):
            yes += 1
        elif s in ("no", "fail", "false", "contradicts"):
            no += 1
    resolved = bool(evidence) and (yes == 0 or no == 0)
    verdict = "support" if yes > no else "contradict" if no > yes else None
    return {"resolved": resolved, "verdict": verdict, "refs": refs, "yes": yes, "no": no}


def _sanitize(value, depth=0):
    if depth > 6:
        return "[redacted:depth]"
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if _SECRET_KEY.search(str(k)):
                out[str(k)] = "[redacted]"
            else:
                out[str(k)] = _sanitize(v, depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        return [_sanitize(v, depth + 1) for v in value[:64]]
    if isinstance(value, str):
        if _SECRET_VAL.search(value):
            return "[redacted]"
        return value[:_MAX_STR]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:_MAX_STR]


def build_provenance(request, triggers, peer, evidence_pass, decision, confidence, status):
    return _sanitize(
        {
            "trigger": sorted(triggers),
            "question": request.get("question"),
            "hypotheses": (peer or {}).get("hypotheses", []),
            "peer_identity": (peer or {}).get("peer_identity"),
            "peer_engine": (peer or {}).get("peer_engine"),
            "recommendation_summary": (peer or {}).get("recommendation"),
            "evidence_refs": (evidence_pass or {}).get("refs", []),
            "decision": decision,
            "confidence": confidence,
            "status": status,
        }
    )


def _recent(conn, key, cooldown_seconds):
    cutoff = _iso(utcnow() - timedelta(seconds=int(cooldown_seconds)))
    row = conn.execute(
        "select payload_json from peer_consultations where dedupe_key=? and created_at>=? "
        "order by id desc limit 1",
        (key, cutoff),
    ).fetchone()
    if row:
        return json.loads(row[0])
    return None


def _count_for_task(conn, task_id):
    if not task_id:
        return 0
    row = conn.execute(
        "select count(*) from peer_consultations where task_id=?", (str(task_id),)
    ).fetchone()
    return int(row[0])


def record(conn, key, task_id, payload):
    ensure_schema(conn)
    cur = conn.execute(
        "insert into peer_consultations(created_at,dedupe_key,task_id,payload_json) values(?,?,?,?)",
        (_iso(utcnow()), key, str(task_id) if task_id else None, json.dumps(payload, sort_keys=True)),
    )
    conn.commit()
    return int(cur.lastrowid)


def history(conn, limit=50):
    ensure_schema(conn)
    rows = conn.execute(
        "select id,created_at,dedupe_key,task_id,payload_json from peer_consultations "
        "order by id desc limit ?",
        (int(limit),),
    ).fetchall()
    return [
        {
            "id": r[0],
            "created_at": r[1],
            "dedupe_key": r[2],
            "task_id": r[3],
            "payload": json.loads(r[4]),
        }
        for r in rows
    ]


def consult(
    conn: sqlite3.Connection,
    request: dict,
    config: dict | None = None,
    peer_pass=None,
    evidence_pass=None,
) -> dict:
    """Run the peer consultation protocol for one request.

    Protocol: one independent peer pass -> one evidence/test pass -> decide /
    bounded experiment / user escalation. Evidence and tests beat AI authority.
    High-impact unresolved uncertainty fails closed; low-risk reversible
    actions may proceed when policy allows.
    """
    cfg = config or DEFAULT_CONFIG
    request = dict(request or {})
    peer_pass = peer_pass or default_peer_pass
    evidence_pass = evidence_pass or default_evidence_pass

    triggers = detect_triggers(request, cfg)
    key = dedupe_key(request, triggers or ["none"])
    task_id = request.get("task_id")

    if is_exempt(request, cfg):
        payload = build_provenance(request, [], None, None, "proceed", "high", "EXEMPT")
        record(conn, key, task_id, payload)
        return {"decision": "proceed", "status": "EXEMPT", "dedupe_key": key, "triggers": [], "provenance": payload}

    if not triggers:
        payload = build_provenance(request, [], None, None, "proceed", "high", "NO_TRIGGER")
        return {"decision": "proceed", "status": "NO_TRIGGER", "dedupe_key": key, "triggers": [], "provenance": payload}

    prior = _recent(conn, key, cfg["cooldown_seconds"])
    if prior is not None:
        return {
            "decision": prior.get("decision"),
            "status": "DEDUPED",
            "dedupe_key": key,
            "triggers": triggers,
            "provenance": prior,
        }

    used = _count_for_task(conn, task_id)
    if used >= int(cfg["max_consultations_per_task"]):
        payload = build_provenance(request, triggers, None, None, "escalate", "unresolved", "BUDGET_EXHAUSTED")
        return {
            "decision": "escalate",
            "status": "BUDGET_EXHAUSTED",
            "dedupe_key": key,
            "triggers": triggers,
            "provenance": payload,
        }

    peer = peer_pass(request, triggers, cfg)
    ev = evidence_pass(request)

    impact = str(request.get("impact") or "").lower()
    reversible = request.get("reversible", True)
    high_impact = impact in _HIGH_IMPACT or reversible is False

    if ev.get("resolved"):
        verdict = ev.get("verdict")
        if verdict == "support":
            decision, confidence, status = "decide", "confirmed_by_evidence", "RESOLVED"
        else:
            decision, confidence, status = "decide", "contradicted_by_evidence", "RESOLVED"
    elif ev.get("refs") and not ev.get("resolved"):
        decision, confidence, status = "bounded_experiment", "unresolved", "BOUNDED_EXPERIMENT"
        if high_impact:
            decision, status = "escalate", "ESCALATED"
    elif high_impact:
        decision, confidence, status = "escalate", "unresolved", "FAIL_CLOSED"
    elif cfg.get("allow_low_risk_proceed", True):
        decision, confidence, status = "proceed", "low_risk", "PROCEED_LOW_RISK"
    else:
        decision, confidence, status = "bounded_experiment", "unresolved", "BOUNDED_EXPERIMENT"

    payload = build_provenance(request, triggers, peer, ev, decision, confidence, status)
    record(conn, key, task_id, payload)
    return {
        "decision": decision,
        "status": status,
        "dedupe_key": key,
        "triggers": triggers,
        "provenance": payload,
    }
