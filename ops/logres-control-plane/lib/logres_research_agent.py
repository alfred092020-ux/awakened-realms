from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
from pathlib import Path

from logres_ai_common import extract_json_object
from logres_ai_runner import usage_from_response
from logres_route_store import ensure_route_schema


CONFIDENCE = (
    "CONFIRMED ORIGINAL",
    "SUPPORTED INFERENCE",
    "RECONSTRUCTED",
    "UNRESOLVED",
    "VERSION SENSITIVE",
)

SYSTEM = """You are an autonomous Logres reconstruction research worker.
Your job is to satisfy the assigned work package using the supplied local evidence
and, when available, web search. Preserve provenance rigorously.

Global May 25 2017 / recovered Global client evidence outranks later/current JP.
Never promote current JP behavior, IDs, server state, endpoints, economy, maps, or
resources to historical Global truth without an independent Global cross-check.
Byte-identical Global/JP resources prove byte continuity only for those bytes.
Negative searches must be described as bounded, not proof that evidence never
existed.

Judge every acceptance criterion explicitly. Mark a criterion PASS only when the
report itself contains enough evidence to support it. It is valid to finish a task
with an EXHAUSTIVE_NEGATIVE basis when the acceptance criterion is to recover OR
bound/exhaust an evidence path. Otherwise unresolved required evidence means the
task must remain BLOCKED_EVIDENCE.

Return only the requested strict JSON object. Do not invent file paths, hashes,
citations, packet fields, protocol fields, symbols, or historical facts."""

RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "confidence": {"type": "string", "enum": list(CONFIDENCE)},
        "completion_basis": {
            "type": "string",
            "enum": [
                "PRIMARY_EVIDENCE",
                "EXHAUSTIVE_NEGATIVE",
                "SUPPORTED_SYNTHESIS",
                "INCOMPLETE",
            ],
        },
        "findings": {"type": "array", "items": {"type": "string"}},
        "provenance": {"type": "array", "items": {"type": "string"}},
        "contradictions": {"type": "array", "items": {"type": "string"}},
        "unresolved": {"type": "array", "items": {"type": "string"}},
        "acceptance_checks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion": {"type": "string"},
                    "status": {"type": "string", "enum": ["PASS", "BLOCKED"]},
                    "evidence": {"type": "string"},
                },
                "required": ["criterion", "status", "evidence"],
                "additionalProperties": False,
            },
        },
        "sources": {"type": "array", "items": {"type": "string"}},
        "deterministic_searches": {
            "type": "array",
            "items": {"type": "string"},
        },
        "recommended_next_search": {"type": "string"},
        "task_status": {
            "type": "string",
            "enum": ["DONE", "BLOCKED_EVIDENCE"],
        },
        "completion_note": {"type": "string"},
    },
    "required": [
        "summary",
        "confidence",
        "completion_basis",
        "findings",
        "provenance",
        "contradictions",
        "unresolved",
        "acceptance_checks",
        "sources",
        "deterministic_searches",
        "recommended_next_search",
        "task_status",
        "completion_note",
    ],
    "additionalProperties": False,
}


def bounded(value: str, limit: int = 50000) -> str:
    if len(value) <= limit:
        return value
    half = limit // 2
    return value[:half] + "\n...[TRUNCATED]...\n" + value[-half:]


def safe_run(argv: list[str], timeout: int = 25, limit: int = 12000) -> str:
    try:
        proc = subprocess.run(
            argv,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"$ {' '.join(argv)}\nERROR: {exc}"
    out = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
    return f"$ {' '.join(argv)}\nrc={proc.returncode}\n{bounded(out, limit)}"


def task_context(conn: sqlite3.Connection, task_id: str) -> dict:
    conn.row_factory = sqlite3.Row
    task = conn.execute(
        "select * from tasks where id=?",
        (task_id,),
    ).fetchone()
    if task is None:
        raise ValueError(f"unknown task: {task_id}")
    meta = conn.execute(
        "select * from task_metadata where task_id=?",
        (task_id,),
    ).fetchone()
    acceptance = [
        row[0]
        for row in conn.execute(
            "select criterion from task_acceptance where task_id=? order by ordinal",
            (task_id,),
        )
    ]
    deps = [
        dict(row)
        for row in conn.execute(
            """select d.depends_on,d.kind,d.rationale,t.status,t.title
                 from task_dependencies d
                 left join tasks t on t.id=d.depends_on
                where d.task_id=?
                order by d.kind,d.depends_on""",
            (task_id,),
        )
    ]
    return {
        "task": dict(task),
        "metadata": dict(meta) if meta is not None else {},
        "acceptance": acceptance,
        "dependencies": deps,
    }


def _search_terms(context: dict) -> list[str]:
    text = " ".join(
        [
            str(context["task"].get("title") or ""),
            str(context["task"].get("note") or ""),
            " ".join(context.get("acceptance") or []),
        ]
    )
    preferred = []
    patterns = [
        r"\bS_[A-Z0-9_]{4,}\b",
        r"\b[A-Z][A-Za-z]+Entry\b",
        r"\b(?:Millennium Tree|MultiID|GmCl|GMCL|HostEntry|MicroBin)\b",
        r"\b\d{3}_\d{3}_\d{5}\b",
    ]
    for pattern in patterns:
        preferred.extend(re.findall(pattern, text))
    words = re.findall(r"[A-Za-z][A-Za-z0-9_]{4,}", text)
    stop = {
        "Global", "using", "exact", "recover", "evidence", "current",
        "original", "without", "through", "build", "analysis", "research",
        "task", "Logres",
    }
    preferred.extend(word for word in words if word not in stop)
    result = []
    seen = set()
    for term in preferred:
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(term)
        if len(result) >= 6:
            break
    return result


def collect_local_bundle(
    root: Path,
    conn: sqlite3.Connection,
    task_id: str,
    worker_id: str,
    branch: str,
) -> tuple[dict, str]:
    context = task_context(conn, task_id)
    commands: list[tuple[str, list[str]]] = []
    packet = safe_run(
        [
            str(root / "bin/logres-worker-packet"),
            task_id,
            branch,
            worker_id,
        ],
        timeout=30,
        limit=30000,
    )
    pieces = ["=== WORKER PACKET ===\n" + packet]

    title = str(context["task"].get("title") or "")
    for term in _search_terms(context):
        argv = [str(root / "bin/logres-lead"), "find", term, "12"]
        commands.append((f"find:{term}", argv))
        pieces.append(f"\n=== LOCAL SEARCH {term} ===\n" + safe_run(argv))
        if re.search(r"protocol|gmcl|opcode|packet", title, re.I) or term.startswith("S_"):
            argv = [str(root / "bin/logres-protocol"), term]
            commands.append((f"protocol:{term}", argv))
            pieces.append(f"\n=== PROTOCOL {term} ===\n" + safe_run(argv))
        if re.search(r"native|function|state machine|crypto|symbol", title, re.I):
            argv = [str(root / "bin/logres-ghidra-find"), term]
            commands.append((f"native:{term}", argv))
            pieces.append(f"\n=== NATIVE {term} ===\n" + safe_run(argv))

    sha = safe_run(
        ["git", "-C", str(root / "src/awakened-realms"), "rev-parse", "HEAD"],
        timeout=10,
        limit=1000,
    )
    pieces.append("\n=== CANONICAL INTEGRATION ===\n" + sha)
    bundle = bounded("\n".join(pieces), 70000)
    context["deterministic_commands"] = [name for name, _ in commands]
    return context, bundle


def build_prompt(context: dict, bundle: str) -> str:
    task = context["task"]
    meta = context["metadata"]
    acceptance = context["acceptance"]
    return f"""TASK_ID: {task['id']}
TITLE: {task.get('title','')}
CURRENT_STATUS: {task.get('status','')}
TASK_NOTE: {task.get('note','')}
WORK_TYPE: {meta.get('work_type','research')}
EVIDENCE_POLICY: {meta.get('evidence_policy','')}
EXPECTED_MINUTES: {meta.get('expected_minutes',60)}

ACCEPTANCE_CRITERIA:
{json.dumps(acceptance, ensure_ascii=False, indent=2)}

DEPENDENCIES:
{json.dumps(context['dependencies'], ensure_ascii=False, indent=2)}

LOCAL_DETERMINISTIC_EVIDENCE:
{bundle}

Research the exact task. Prefer local recovered evidence. Use web search only to
resolve gaps that genuinely require public historical/external material. When
web search is used, include the most useful source URLs in sources. Do not merely
repeat the packet: synthesize the acceptance decision and preserve evidence
ceilings. If the task asks for implementation/code, do not pretend research
completed it; return BLOCKED_EVIDENCE or INCOMPLETE instead.
"""


def _web_sources(response) -> list[str]:
    found: list[str] = []
    for item in getattr(response, "output", []) or []:
        action = getattr(item, "action", None)
        for source in getattr(action, "sources", []) or []:
            url = getattr(source, "url", None)
            if url:
                found.append(str(url))
        for content in getattr(item, "content", []) or []:
            for annotation in getattr(content, "annotations", []) or []:
                url = getattr(annotation, "url", None)
                if not url:
                    citation = getattr(annotation, "url_citation", None)
                    url = getattr(citation, "url", None) if citation else None
                if url:
                    found.append(str(url))
    result = []
    seen = set()
    for url in found:
        if url in seen:
            continue
        seen.add(url)
        result.append(url)
    return result


def run_research(
    client,
    *,
    model: str,
    prompt: str,
    web_search: bool,
    max_output_tokens: int = 6000,
):
    tools = []
    if web_search:
        tools.append(
            {
                "type": "web_search",
                "search_context_size": "medium",
            }
        )
    response = client.responses.create(
        model=model,
        instructions=SYSTEM,
        input=prompt,
        tools=tools,
        reasoning={"effort": "medium"},
        max_output_tokens=max_output_tokens,
        text={
            "format": {
                "type": "json_schema",
                "name": "logres_autonomous_research",
                "strict": True,
                "schema": RESULT_SCHEMA,
            }
        },
        store=False,
    )
    parsed = extract_json_object(response.output_text)
    result = parsed if isinstance(parsed, dict) else json.loads(parsed)
    sources = list(result.get("sources") or [])
    sources.extend(_web_sources(response))
    result["sources"] = list(dict.fromkeys(sources))
    return result, response


def can_complete(result: dict, acceptance_count: int) -> bool:
    checks = result.get("acceptance_checks") or []
    if result.get("task_status") != "DONE":
        return False
    if result.get("completion_basis") == "INCOMPLETE":
        return False
    if acceptance_count and len(checks) < acceptance_count:
        return False
    return bool(checks or acceptance_count == 0) and all(
        check.get("status") == "PASS" for check in checks
    )


def brain_confidence(label: str) -> str:
    return {
        "CONFIRMED ORIGINAL": "CONFIRMED",
        "SUPPORTED INFERENCE": "INFERENCE",
        "RECONSTRUCTED": "MEDIUM",
        "UNRESOLVED": "LOW",
        "VERSION SENSITIVE": "VERSION_SENSITIVE",
    }.get(label, "LOW")


def artifact_payload(
    context: dict,
    result: dict,
    *,
    task_id: str,
    worker_id: str,
    model: str,
    local_bundle_sha256: str,
) -> dict:
    return {
        "task_id": task_id,
        "worker_id": worker_id,
        "engine": "openai-responses-web-research",
        "model": model,
        "evidence_policy": context["metadata"].get("evidence_policy", ""),
        "acceptance": context["acceptance"],
        "local_bundle_sha256": local_bundle_sha256,
        "result": result,
    }


def write_artifact(
    root: Path,
    task_id: str,
    payload: dict,
) -> tuple[Path, str]:
    out_dir = root / "artifacts/swarm-research"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time_stamp()
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", task_id)
    path = out_dir / f"{safe}-{stamp}.json"
    raw = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    path.write_bytes(raw)
    return path, hashlib.sha256(raw).hexdigest()


def time_stamp() -> str:
    import datetime
    return datetime.datetime.now(
        datetime.timezone.utc
    ).strftime("%Y%m%dT%H%M%SZ")


def record_usage(
    conn: sqlite3.Connection,
    response,
    *,
    model: str,
    rate_config: dict,
    task_id: str,
    artifact_sha: str,
    status: str = "PASS",
) -> dict:
    ensure_route_schema(conn)
    usage = usage_from_response(response, model, rate_config)
    conn.execute(
        """insert into api_usage(
             route_job_id,ai_run_id,task_id,artifact_sha,model,
             input_tokens,cached_input_tokens,output_tokens,reasoning_tokens,
             estimated_cost_usd,status,created_at
           ) values(null,null,?,?,?,?,?,?,?,?,?,datetime('now'))""",
        (
            task_id,
            artifact_sha,
            model,
            usage.input_tokens,
            usage.cached_input_tokens,
            usage.output_tokens,
            usage.reasoning_tokens,
            usage.estimated_cost_usd,
            status,
        ),
    )
    conn.commit()
    return usage.to_dict()
