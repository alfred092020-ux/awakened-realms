from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from logres_ai_common import bounded_text, build_prompt, dedupe_key, extract_json_object, validate_result

MODEL_PREFS = ("gpt-5.6-luna", "gpt-5-mini", "gpt-4.1-mini")
MAX_OUTPUT_TOKENS = 1600
MAX_RETRY_OUTPUT_TOKENS = 2800
SYSTEM = "You are the Logres Evidence Analyst. Use only supplied evidence. Never invent original Logres behavior. Preserve provenance and use exactly one confidence label: CONFIRMED ORIGINAL, SUPPORTED INFERENCE, RECONSTRUCTED, UNRESOLVED, VERSION SENSITIVE. Later/current JP evidence is not Global 2017 truth without direct cross-check. Return JSON only with keys summary, confidence, findings, contradictions, unresolved, recommended_next_search. Keep summary under 350 characters, use at most 6 findings, keep each finding concise, and keep recommended_next_search under 300 characters."

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
    minis = sorted(m for m in available if "mini" in m.lower() and m.startswith("gpt"))
    if minis:
        return minis[-1]
    raise SystemExit("No preferred low-cost GPT model available")

def ensure_db(conn: sqlite3.Connection) -> None:
    conn.execute("create table if not exists ai_runs (id integer primary key autoincrement, dedupe_key text unique not null, artifact_sha text not null, question text not null, artifact_path text not null, task_id text, model text, status text not null, result_json text, created_at text default current_timestamp)")
    conn.commit()

def run_model(client, model: str, prompt: str) -> dict:
    def call(limit: int):
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
                        "confidence": {"type": "string", "enum": ["CONFIRMED ORIGINAL", "SUPPORTED INFERENCE", "RECONSTRUCTED", "UNRESOLVED", "VERSION SENSITIVE"]},
                        "findings": {"type": "array", "items": {"type": "string"}},
                        "contradictions": {"type": "array", "items": {"type": "string"}},
                        "unresolved": {"type": "array", "items": {"type": "string"}},
                        "recommended_next_search": {"type": "string"}
                    },
                    "required": ["summary", "confidence", "findings", "contradictions", "unresolved", "recommended_next_search"],
                    "additionalProperties": False
                }
            }},
            store=False,
        )
    response = call(MAX_OUTPUT_TOKENS)
    reason = getattr(getattr(response, "incomplete_details", None), "reason", None)
    if getattr(response, "status", "completed") == "incomplete" and reason == "max_output_tokens":
        response = call(MAX_RETRY_OUTPUT_TOKENS)
    if getattr(response, "status", "completed") == "incomplete":
        reason = getattr(getattr(response, "incomplete_details", None), "reason", "unknown")
        raise RuntimeError(f"incomplete OpenAI response: {reason}")
    return validate_result(extract_json_object(response.output_text))

def analyze_artifact(client, conn: sqlite3.Connection, path: Path, question: str, task_id: str | None = None, force: bool = False) -> dict:
    ensure_db(conn)
    raw = Path(path).read_bytes()
    artifact_sha, text, total = bounded_text(raw)
    key = dedupe_key(artifact_sha, question)
    if not force:
        row = conn.execute("select model,result_json from ai_runs where dedupe_key=? and status='PASS'", (key,)).fetchone()
        if row:
            return {"cached": True, "model": row[0], "artifact_sha": artifact_sha, "result": json.loads(row[1])}
    model = choose_model(client)
    prompt = build_prompt(str(Path(path).resolve()), artifact_sha, total, task_id, question, text)
    result = run_model(client, model, prompt)
    payload = json.dumps(result, separators=(",", ":"), ensure_ascii=False)
    conn.execute("insert into ai_runs(dedupe_key,artifact_sha,question,artifact_path,task_id,model,status,result_json) values(?,?,?,?,?,?,?,?) on conflict(dedupe_key) do update set task_id=excluded.task_id,model=excluded.model,status=excluded.status,result_json=excluded.result_json",
                 (key, artifact_sha, question, str(Path(path).resolve()), task_id, model, "PASS", payload))
    conn.commit()
    return {"cached": False, "model": model, "artifact_sha": artifact_sha, "result": result}
