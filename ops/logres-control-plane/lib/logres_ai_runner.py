from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

from logres_ai_common import bounded_text, build_prompt, dedupe_key, extract_json_object, validate_result
from logres_route_store import ensure_route_schema

MODEL_PREFS = ("gpt-5.6-luna", "gpt-5-mini", "gpt-4.1-mini")
MAX_OUTPUT_TOKENS = 1600
MAX_RETRY_OUTPUT_TOKENS = 2800
SYSTEM = "You are the Logres Evidence Analyst. Use only supplied evidence. Never invent original Logres behavior. Preserve provenance and use exactly one confidence label: CONFIRMED ORIGINAL, SUPPORTED INFERENCE, RECONSTRUCTED, UNRESOLVED, VERSION SENSITIVE. Later/current JP evidence is not Global 2017 truth without direct cross-check. Return JSON only with keys summary, confidence, findings, contradictions, unresolved, recommended_next_search. Keep summary under 350 characters, use at most 6 findings, keep each finding concise, and keep recommended_next_search under 300 characters."


@dataclass(frozen=True)
class UsageRecord:
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    estimated_cost_usd: float | None

    def to_dict(self) -> dict:
        return asdict(self)


def choose_model(client) -> str:
    forced = os.getenv("LOGRES_AI_MODEL", "").strip()
    available = {m.id for m in client.models.list().data}
    if forced:
        if forced not in available:
            raise SystemExit(f"LOGRES_AI_MODEL unavailable: {forced}")
        return forced
    for candidate in MODEL_PREFS:
        if candidate in available:
            return candidate
    minis = sorted(
        m for m in available if "mini" in m.lower() and m.startswith("gpt")
    )
    if minis:
        return minis[-1]
    raise SystemExit("No preferred low-cost GPT model available")


def ensure_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """create table if not exists ai_runs (
             id integer primary key autoincrement,
             dedupe_key text unique not null,
             artifact_sha text not null,
             question text not null,
             artifact_path text not null,
             task_id text,
             model text,
             status text not null,
             result_json text,
             created_at text default current_timestamp
           )"""
    )
    ensure_route_schema(conn)
    conn.commit()


def usage_from_response(
    response,
    model: str,
    rate_config: dict | None,
) -> UsageRecord:
    usage = getattr(response, "usage", None)
    if usage is None:
        return UsageRecord(0, 0, 0, 0, None)

    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    input_details = getattr(usage, "input_tokens_details", None)
    output_details = getattr(usage, "output_tokens_details", None)
    cached_input_tokens = int(
        getattr(input_details, "cached_tokens", 0) or 0
    )
    reasoning_tokens = int(
        getattr(output_details, "reasoning_tokens", 0) or 0
    )

    estimated = None
    rates = (rate_config or {}).get(model)
    if rates is not None:
        uncached = max(0, input_tokens - cached_input_tokens)
        input_rate = float(rates["input"])
        cached_rate = float(rates.get("cached_input", input_rate))
        output_rate = float(rates["output"])
        estimated = (
            uncached * input_rate
            + cached_input_tokens * cached_rate
            + output_tokens * output_rate
        ) / 1_000_000.0

    return UsageRecord(
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
        estimated_cost_usd=estimated,
    )


def budget_state(
    conn: sqlite3.Connection,
    config: dict,
    priority: int,
    model: str,
) -> str:
    del priority
    openai_config = config.get("openai", {})
    rates = openai_config.get("model_rates_per_million", {})
    if model not in rates:
        return "UNKNOWN"
    budget = float(openai_config.get("budget_usd", 0) or 0)
    if budget <= 0:
        return "CLOSED"

    rows = conn.execute(
        "select estimated_cost_usd from api_usage order by id"
    ).fetchall()
    if any(row[0] is None for row in rows):
        return "UNKNOWN"
    spent = sum(float(row[0] or 0) for row in rows)
    ratio = spent / budget
    if ratio >= 1.0:
        return "CLOSED"

    reserve_fraction = float(openai_config.get("reserve_fraction", 0.20))
    throttle_fraction = float(openai_config.get("throttle_fraction", 0.75))
    if ratio >= 1.0 - reserve_fraction:
        return "RESERVED"
    if ratio >= throttle_fraction:
        return "THROTTLED"
    return "OPEN"


def automatic_api_allowed(state: str, priority: int) -> bool:
    if state == "OPEN":
        return True
    if state in {"THROTTLED", "RESERVED"}:
        return priority == 0
    return False


class IncompleteModelResponse(RuntimeError):
    def __init__(self, reason: str, responses: list):
        super().__init__(f"incomplete OpenAI response: {reason}")
        self.reason = reason
        self.responses = responses
def _call_model(client, model: str, prompt: str, limit: int):
    return client.responses.create(
        model=model,
        instructions=SYSTEM,
        input=prompt,
        max_output_tokens=limit,
        reasoning={"effort": "none"},
        text={"format": {
            "type": "json_schema",
            "name": "logres_evidence_analysis",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "confidence": {
                        "type": "string",
                        "enum": [
                            "CONFIRMED ORIGINAL",
                            "SUPPORTED INFERENCE",
                            "RECONSTRUCTED",
                            "UNRESOLVED",
                            "VERSION SENSITIVE",
                        ],
                    },
                    "findings": {"type": "array", "items": {"type": "string"}},
                    "contradictions": {"type": "array", "items": {"type": "string"}},
                    "unresolved": {"type": "array", "items": {"type": "string"}},
                    "recommended_next_search": {"type": "string"},
                },
                "required": [
                    "summary",
                    "confidence",
                    "findings",
                    "contradictions",
                    "unresolved",
                    "recommended_next_search",
                ],
                "additionalProperties": False,
            },
        }},
        store=False,
    )


def _run_model_with_responses(client, model: str, prompt: str) -> tuple[dict, list]:
    responses = [_call_model(client, model, prompt, MAX_OUTPUT_TOKENS)]
    response = responses[-1]
    reason = getattr(
        getattr(response, "incomplete_details", None),
        "reason",
        None,
    )
    if (
        getattr(response, "status", "completed") == "incomplete"
        and reason == "max_output_tokens"
    ):
        responses.append(
            _call_model(client, model, prompt, MAX_RETRY_OUTPUT_TOKENS)
        )
        response = responses[-1]

    if getattr(response, "status", "completed") == "incomplete":
        reason = getattr(
            getattr(response, "incomplete_details", None),
            "reason",
            "unknown",
        )
        raise IncompleteModelResponse(reason, responses)

    result = validate_result(extract_json_object(response.output_text))
    return result, responses


def run_model(client, model: str, prompt: str) -> dict:
    result, _responses = _run_model_with_responses(client, model, prompt)
    return result


def _record_usage(
    conn: sqlite3.Connection,
    response,
    *,
    model: str,
    rate_config: dict | None,
    route_job_id: int | None,
    ai_run_id: int | None,
    task_id: str | None,
    artifact_sha: str,
    status: str,
) -> UsageRecord:
    usage = usage_from_response(response, model, rate_config)
    conn.execute(
        """insert into api_usage(
             route_job_id,ai_run_id,task_id,artifact_sha,model,input_tokens,
             cached_input_tokens,output_tokens,reasoning_tokens,
             estimated_cost_usd,status,created_at
           ) values(?,?,?,?,?,?,?,?,?,?,?,datetime('now'))""",
        (
            route_job_id,
            ai_run_id,
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
    return usage


def analyze_artifact(
    client,
    conn: sqlite3.Connection,
    path: Path,
    question: str,
    task_id: str | None = None,
    force: bool = False,
    route_job_id: int | None = None,
    rate_config: dict | None = None,
) -> dict:
    ensure_db(conn)
    raw = Path(path).read_bytes()
    artifact_sha, text, total = bounded_text(raw)
    key = dedupe_key(artifact_sha, question)

    if not force:
        row = conn.execute(
            """select id,model,result_json
                 from ai_runs where dedupe_key=? and status='PASS'""",
            (key,),
        ).fetchone()
        if row:
            return {
                "cached": True,
                "model": row[1],
                "artifact_sha": artifact_sha,
                "result": json.loads(row[2]),
                "usage": None,
                "ai_run_id": int(row[0]),
            }

    model = choose_model(client)
    prompt = build_prompt(
        str(Path(path).resolve()),
        artifact_sha,
        total,
        task_id,
        question,
        text,
    )

    try:
        result, responses = _run_model_with_responses(client, model, prompt)
    except IncompleteModelResponse as exc:
        for response in exc.responses:
            _record_usage(
                conn,
                response,
                model=model,
                rate_config=rate_config,
                route_job_id=route_job_id,
                ai_run_id=None,
                task_id=task_id,
                artifact_sha=artifact_sha,
                status="FAIL",
            )
        conn.commit()
        raise

    payload = json.dumps(result, separators=(",", ":"), ensure_ascii=False)
    conn.execute(
        """insert into ai_runs(
             dedupe_key,artifact_sha,question,artifact_path,task_id,model,status,result_json
           ) values(?,?,?,?,?,?,?,?)
           on conflict(dedupe_key) do update set
             task_id=excluded.task_id,
             model=excluded.model,
             status=excluded.status,
             result_json=excluded.result_json""",
        (
            key,
            artifact_sha,
            question,
            str(Path(path).resolve()),
            task_id,
            model,
            "PASS",
            payload,
        ),
    )
    ai_run_id = int(
        conn.execute(
            "select id from ai_runs where dedupe_key=?",
            (key,),
        ).fetchone()[0]
    )

    usage_records: list[UsageRecord] = []
    for index, response in enumerate(responses):
        status = "PASS" if index == len(responses) - 1 else "INCOMPLETE_RETRY"
        usage_records.append(
            _record_usage(
                conn,
                response,
                model=model,
                rate_config=rate_config,
                route_job_id=route_job_id,
                ai_run_id=ai_run_id,
                task_id=task_id,
                artifact_sha=artifact_sha,
                status=status,
            )
        )
    conn.commit()

    return {
        "cached": False,
        "model": model,
        "artifact_sha": artifact_sha,
        "result": result,
        "usage": usage_records[-1].to_dict(),
        "ai_run_id": ai_run_id,
    }


def cli_summary(out: dict, result_path: Path) -> dict:
    return {
        "cached": out["cached"],
        "model": out["model"],
        "result_path": str(result_path),
        "confidence": out["result"]["confidence"],
        "summary": out["result"]["summary"],
        "usage": out.get("usage"),
    }
