"""Deterministic cold-start context packs for Logres AI workers.

Builds a self-contained, engine-neutral task contract from the Brain control
SQLite database plus locally indexed/search evidence. The same canonical pack
is produced for Devin, ChatGPT, research workers, and future engines; the
text rendering is generated from the identical structure.

Evidence larger than the configured inline ceiling stays content-addressed
(path + sha256 + byte count) so prompts never carry unbounded blobs.
Credential-shaped strings are redacted from every emitted field.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

SCHEMA = "logres.context-pack/v1"
ENGINE_NEUTRAL = "engine-neutral"

# Ranking classes, lowest number emitted first / dropped last.
RANK_CRITICAL = 0
RANK_HIGH = 1
RANK_MEDIUM = 2
RANK_LOW = 3
RANK_BACKGROUND = 4

RESOLVED_TASK_STATES = {"DONE", "RESOLVED", "INTEGRATED"}

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(sk|pk|key|token|secret|password|passwd|api[_-]?key)"
               r"[A-Za-z0-9_-]*\s*[:=]\s*['\"]?[A-Za-z0-9_./+\-]{12,}"),
    re.compile(r"\b(ghp|gho|ghu|ghs|ghr|github_pat|sk-ant|sk-proj|sk-)"
               r"[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9_./+\-]{20,}"),
]
REDACTED = "[REDACTED]"

DEFAULT_CONFIG = {
    "max_bytes": 24000,
    "max_tokens": 6000,
    "token_bytes": 4,
    "evidence_inline_bytes": 2048,
    "evidence_max_items": 24,
    "decisions_max_items": 12,
    "underspecified_phrases": [
        "continue previous work",
        "continue the previous",
        "as before",
        "same as last time",
        "keep going",
        "resume where",
        "pick up where",
        "carry on",
    ],
    "authority_rank": {
        "GLOBAL_ORIGINAL": 0,
        "GIT_EXACT_SHA": 1,
        "IMPLEMENTATION_VERIFIED": 2,
        "CONFIRMED": 3,
        "HIGH": 4,
        "MEDIUM": 5,
        "LOW": 6,
        "SPECULATION_OR_UNRESOLVED": 7,
        "UNRESOLVED": 8,
        "EVIDENCE_CONFLICT": 8,
    },
    "confidence_rank": {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "UNKNOWN": 3},
}


class UnderspecifiedTaskError(ValueError):
    """The task relies on prior context that Brain/local indexes cannot resolve."""


class TaskNotFoundError(ValueError):
    pass


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _read_evidence_bytes(path: str) -> bytes | None:
    try:
        return Path(path).read_bytes()
    except (OSError, ValueError):
        return None


def _redact(value, counter):
    if isinstance(value, str):
        out = value
        for pat in SECRET_PATTERNS:
            out, n = pat.subn(REDACTED, out)
            counter[0] += n
        return out
    if isinstance(value, list):
        return [_redact(v, counter) for v in value]
    if isinstance(value, dict):
        return {k: _redact(v, counter) for k, v in value.items()}
    return value


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "select 1 from sqlite_master where type='table' and name=?", (name,)
    ).fetchone()
    return row is not None


def _q(conn: sqlite3.Connection, sql: str, args=()) -> list[sqlite3.Row]:
    try:
        return conn.execute(sql, args).fetchall()
    except sqlite3.OperationalError:
        return []


def _norm_confidence(value) -> str:
    v = str(value or "UNKNOWN").upper()
    return v if v in {"HIGH", "MEDIUM", "LOW"} else "UNKNOWN"


def _norm_status(value) -> str:
    v = str(value or "").upper()
    if v in {"UNRESOLVED", "EVIDENCE_CONFLICT"}:
        return v
    return "INDEXED"


def normalize_evidence(item: dict, inline_ceiling: int) -> dict:
    """Canonicalize one evidence item; content-address large content."""
    snippet = item.get("snippet") or ""
    path = item.get("path") or ""
    content_bytes = item.get("bytes")
    sha = item.get("sha256")
    if content_bytes is None and path:
        data = _read_evidence_bytes(path)
        if data is not None:
            content_bytes = len(data)
            sha = sha or _sha256_bytes(data)
    if content_bytes is None:
        content_bytes = len(snippet.encode("utf-8"))
    if not sha and snippet:
        sha = _sha256_text(snippet)
    entry = {
        "id": item.get("id") or (sha[:16] if sha else _sha256_text(path or snippet)[:16]),
        "source": str(item.get("source") or "local"),
        "path": path,
        "sha256": sha,
        "bytes": int(content_bytes),
        "confidence": _norm_confidence(item.get("confidence")),
        "authority": str(item.get("authority") or "UNRESOLVED").upper(),
        "status": _norm_status(item.get("status")),
        "relevance": float(item.get("relevance") or 0.0),
        "content_addressed": content_bytes > inline_ceiling,
    }
    if entry["content_addressed"]:
        entry["ref"] = f"{path}#sha256:{sha}" if path else f"sha256:{sha}"
    else:
        entry["snippet"] = snippet
    return entry


def _evidence_sort_key(entry: dict, cfg: dict) -> tuple:
    auth = cfg["authority_rank"].get(
        entry["authority"], len(cfg["authority_rank"])
    )
    conf = cfg["confidence_rank"].get(entry["confidence"], 9)
    return (
        auth,
        conf,
        -entry["relevance"],
        entry["source"],
        entry["path"],
        entry["id"],
    )


def _detect_underspecified(title: str, note: str, cfg: dict) -> str | None:
    text = f"{title}\n{note}".lower()
    for phrase in cfg["underspecified_phrases"]:
        if phrase in text:
            return phrase
    return None


def build_pack(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    config: dict | None = None,
    evidence: list[dict] | None = None,
    integration_sha: str | None = None,
    integration_branch: str = "feat/logres-reconstruction",
    interfaces: list[str] | None = None,
    blockers: list[str] | None = None,
    expected_output: dict | None = None,
    verification: list[str] | None = None,
) -> dict:
    """Build the canonical, deterministic, engine-neutral context pack."""
    cfg = dict(DEFAULT_CONFIG)
    if config:
        cfg.update(config)
        merged = dict(DEFAULT_CONFIG["authority_rank"])
        merged.update(config.get("authority_rank", {}))
        cfg["authority_rank"] = merged

    conn.row_factory = sqlite3.Row
    task = _q(conn, "select * from tasks where id=?", (task_id,))
    if not task:
        raise TaskNotFoundError(f"task not found in Brain index: {task_id}")
    task = dict(task[0])

    acceptance = [
        r["criterion"]
        for r in _q(
            conn,
            "select criterion from task_acceptance where task_id=? "
            "order by ordinal, criterion",
            (task_id,),
        )
    ]
    scopes = [
        r["path_prefix"]
        for r in _q(
            conn,
            "select path_prefix from task_scopes where task_id=? "
            "order by path_prefix",
            (task_id,),
        )
    ]

    phrase = _detect_underspecified(
        str(task.get("title") or ""), str(task.get("note") or ""), cfg
    )
    if phrase and (not acceptance or not scopes):
        raise UnderspecifiedTaskError(
            f"task {task_id} is under-specified: phrase {phrase!r} and "
            "Brain context cannot resolve acceptance criteria and scopes"
        )

    deps = []
    for r in _q(
        conn,
        "select d.depends_on, d.kind, d.rationale, t.status "
        "from task_dependencies d left join tasks t on t.id=d.depends_on "
        "where d.task_id=? order by d.depends_on",
        (task_id,),
    ):
        status = r["status"] or "UNKNOWN"
        deps.append({
            "task_id": r["depends_on"],
            "kind": r["kind"],
            "rationale": r["rationale"] or "",
            "status": status,
            "satisfied": status in RESOLVED_TASK_STATES,
        })

    claims_own = []
    conflicts = []
    for r in _q(conn, "select * from claims order by path_prefix"):
        row = {
            "path_prefix": r["path_prefix"],
            "task_id": r["task_id"],
            "owner": r["owner"],
            "branch": r["branch"],
        }
        if r["task_id"] == task_id:
            claims_own.append(row)
        elif scopes and any(
            r["path_prefix"].startswith(s) or s.startswith(r["path_prefix"])
            for s in scopes
        ):
            conflicts.append(row)

    recovery = None
    rows = _q(
        conn,
        "select * from task_recovery where task_id=? order by id desc limit 1",
        (task_id,),
    )
    if rows:
        r = rows[0]
        recovery = {
            "status": r["status"],
            "branch": r["branch"],
            "worktree": r["worktree"],
            "manifest_path": r["manifest_path"],
            "created_at": r["created_at"],
            "note": r["note"] or "",
        }

    decisions = []
    for r in _q(
        conn,
        "select id, ts, author, scope, subject, decision, status "
        "from brain_decisions where task_id=? order by id",
        (task_id,),
    ):
        decisions.append({
            "id": r["id"],
            "ts": r["ts"],
            "author": r["author"],
            "scope": r["scope"],
            "subject": r["subject"],
            "decision": r["decision"],
            "status": r["status"],
        })

    ev = [
        normalize_evidence(e, cfg["evidence_inline_bytes"])
        for e in (evidence or [])
    ]
    ev.sort(key=lambda e: _evidence_sort_key(e, cfg))
    ev = ev[: cfg["evidence_max_items"]]
    ceilings = sorted({e["status"] for e in ev} - {"INDEXED"})

    pack = {
        "schema": SCHEMA,
        "engine": ENGINE_NEUTRAL,
        "task_id": task_id,
        "objective": {
            "title": task.get("title") or "",
            "priority": task.get("priority"),
            "lane": task.get("lane"),
            "status": task.get("status"),
            "note": task.get("note") or "",
        },
        "integration": {
            "target_branch": integration_branch,
            "integration_sha": integration_sha,
            "worker_branch": task.get("branch"),
            "owner": task.get("owner"),
        },
        "acceptance_criteria": acceptance,
        "scopes": scopes,
        "dependencies": deps,
        "recovery": recovery,
        "decisions": decisions[: cfg["decisions_max_items"]],
        "blockers": sorted(blockers or []),
        "claims": {"own": claims_own, "conflicts": conflicts},
        "evidence": ev,
        "evidence_ceilings": ceilings,
        "interfaces": sorted(set(interfaces or [])),
        "expected_output": expected_output or {},
        "verification": list(verification or []),
        "underspecified_marker": phrase,
    }
    counter = [0]
    pack = _redact(pack, counter)
    pack["redactions"] = counter[0]
    pack["budget"] = _apply_budget(pack, cfg)
    return pack


def _serialized(pack: dict) -> bytes:
    return json.dumps(pack, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _apply_budget(pack: dict, cfg: dict) -> dict:
    """Drop lowest-priority optional material until the pack fits the budget.

    Critical sections (objective, acceptance, scopes, dependencies, blockers,
    claims, evidence refs/ceilings) always survive; snippets and background
    material are truncated first, in deterministic order.
    """
    max_bytes = int(cfg["max_bytes"])
    dropped = []

    def fits() -> bool:
        probe = {k: v for k, v in pack.items() if k != "budget"}
        return len(_serialized(probe)) <= max_bytes

    # 1. inline snippets (refs/hashes stay)
    for e in pack["evidence"]:
        if fits():
            break
        if "snippet" in e:
            del e["snippet"]
            e["content_addressed"] = True
            e["ref"] = (
                f"{e['path']}#sha256:{e['sha256']}"
                if e["path"] else f"sha256:{e['sha256']}"
            )
            if "evidence_snippets" not in dropped:
                dropped.append("evidence_snippets")
    # 2. decisions tail, then interfaces tail
    for key in ("decisions", "interfaces"):
        while pack[key] and not fits():
            pack[key].pop()
            if key not in dropped:
                dropped.append(key)
    # 3. non-critical deps rationale
    for d in pack["dependencies"]:
        if fits():
            break
        if d.get("rationale"):
            d["rationale"] = ""
            if "dependency_rationale" not in dropped:
                dropped.append("dependency_rationale")

    size = len(_serialized({k: v for k, v in pack.items() if k != "budget"}))
    return {
        "max_bytes": max_bytes,
        "max_tokens": int(cfg["max_tokens"]),
        "bytes": size,
        "tokens": size // int(cfg["token_bytes"]),
        "truncated": bool(dropped),
        "dropped": dropped,
        "fits": size <= max_bytes,
    }


def canonical_json(pack: dict) -> str:
    """Engine-neutral machine-readable form; identical for every engine."""
    return json.dumps(pack, indent=2, sort_keys=True)


def render_text(pack: dict) -> str:
    """Concise human/LLM rendering generated from the canonical structure."""
    L = []
    o = pack["objective"]
    i = pack["integration"]
    L.append(f"CONTEXT PACK {pack['schema']} :: {pack['task_id']}")
    L.append(f"Objective: {o['title']} (P{o['priority']} lane={o['lane']} "
             f"status={o['status']})")
    if o.get("note"):
        L.append(f"Note: {o['note']}")
    L.append(f"Integration: {i['target_branch']} @ {i['integration_sha']}")
    L.append(f"Worker branch: {i['worker_branch']} owner={i['owner']}")
    L.append("Scopes:")
    for s in pack["scopes"]:
        L.append(f"  - {s}")
    L.append("Acceptance criteria:")
    for n, c in enumerate(pack["acceptance_criteria"], 1):
        L.append(f"  {n}. {c}")
    if pack["dependencies"]:
        L.append("Dependencies:")
        for d in pack["dependencies"]:
            state = "SATISFIED" if d["satisfied"] else d["status"]
            L.append(f"  - {d['task_id']} [{d['kind']}] {state} {d['rationale']}")
    if pack["recovery"]:
        r = pack["recovery"]
        L.append(f"Recovery: status={r['status']} branch={r['branch']} "
                 f"manifest={r['manifest_path']}")
    if pack["blockers"]:
        L.append("Blockers:")
        for b in pack["blockers"]:
            L.append(f"  - {b}")
    if pack["claims"]["conflicts"]:
        L.append("CLAIM CONFLICTS (refuse overlapping work):")
        for c in pack["claims"]["conflicts"]:
            L.append(f"  - {c['path_prefix']} held by {c['task_id']}"
                     f"/{c['owner']} on {c['branch']}")
    if pack["evidence_ceilings"]:
        L.append("Evidence ceilings: " + ", ".join(pack["evidence_ceilings"]))
    if pack["evidence"]:
        L.append("Evidence:")
        for e in pack["evidence"]:
            ref = e.get("ref") or e["path"] or e["id"]
            L.append(f"  - [{e['authority']}/{e['confidence']}"
                     f"/{e['status']}] {e['source']} {ref}")
            if e.get("snippet"):
                snip = " ".join(e["snippet"].split())[:200]
                L.append(f"      {snip}")
    if pack["interfaces"]:
        L.append("Related interfaces/dependency files:")
        for f in pack["interfaces"]:
            L.append(f"  - {f}")
    if pack["decisions"]:
        L.append("Decisions:")
        for d in pack["decisions"]:
            L.append(f"  - [{d['status']}] {d['subject']}: {d['decision']}")
    if pack["expected_output"]:
        L.append("Expected output: "
                 + json.dumps(pack["expected_output"], sort_keys=True))
    if pack["verification"]:
        L.append("Verification:")
        for v in pack["verification"]:
            L.append(f"  - {v}")
    b = pack.get("budget", {})
    if b.get("truncated"):
        L.append(f"Budget: truncated; dropped {', '.join(b['dropped'])}")
    if pack.get("redactions"):
        L.append(f"Redactions applied: {pack['redactions']}")
    return "\n".join(L)
