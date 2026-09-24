from __future__ import annotations

import hashlib
import json

CONFIDENCE_LABELS = {
    "CONFIRMED ORIGINAL",
    "SUPPORTED INFERENCE",
    "RECONSTRUCTED",
    "UNRESOLVED",
    "VERSION SENSITIVE",
}

def bounded_text(raw: bytes, limit: int = 80000):
    sha = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8", "replace")
    total = len(text)
    if total <= limit:
        return sha, text, total
    half = limit // 2
    marker = "\n\n[TRUNCATED BY LOGRES-AI]\n\n"
    return sha, text[:half] + marker + text[-half:], total

def extract_json_object(text: str):
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("response did not contain a JSON object")
    obj = json.loads(text[start:end + 1])
    if not isinstance(obj, dict):
        raise ValueError("response JSON must be an object")
    return obj

def dedupe_key(artifact_sha: str, question: str) -> str:
    qsha = hashlib.sha256(question.encode("utf-8")).hexdigest()
    return hashlib.sha256(f"{artifact_sha}:{qsha}".encode("ascii")).hexdigest()

def valid_confidence(value: str) -> bool:
    return value in CONFIDENCE_LABELS

REQUIRED_RESULT_KEYS = {
    "summary",
    "confidence",
    "findings",
    "contradictions",
    "unresolved",
    "recommended_next_search",
}

def build_prompt(path: str, artifact_sha: str, original_chars: int, task_id: str | None, question: str, content: str) -> str:
    return (
        f"Artifact: {path}\n"
        f"SHA256: {artifact_sha}\n"
        f"Original characters: {original_chars}\n"
        f"Task: {task_id or '-'}\n"
        f"Question: {question}\n\n"
        f"ARTIFACT CONTENT:\n{content}"
    )

def validate_result(result: dict) -> dict:
    if not isinstance(result, dict):
        raise ValueError("result must be a JSON object")
    missing = REQUIRED_RESULT_KEYS - set(result)
    if missing:
        raise ValueError(f"missing result keys: {sorted(missing)}")
    if not valid_confidence(result.get("confidence", "")):
        raise ValueError("invalid confidence label")
    return result

def build_prompt(path: str, artifact_sha: str, original_chars: int, task_id: str | None, question: str, content: str) -> str:
    return (
        f"Artifact: {path}\n"
        f"SHA256: {artifact_sha}\n"
        f"Original characters: {original_chars}\n"
        f"Task: {task_id or '-'}\n"
        f"Question: {question}\n\n"
        f"ARTIFACT CONTENT:\n{content}"
    )

def validate_result(obj: dict) -> dict:
    required = {"summary", "confidence", "findings", "contradictions", "unresolved", "recommended_next_search"}
    missing = required.difference(obj)
    if missing:
        raise ValueError(f"missing result keys: {sorted(missing)}")
    if not valid_confidence(obj.get("confidence")):
        raise ValueError(f"invalid confidence: {obj.get('confidence')}")
    for key in ("findings", "contradictions", "unresolved"):
        if not isinstance(obj[key], list):
            raise ValueError(f"{key} must be a list")
    return obj
