from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path


class TemporalQueryError(ValueError):
    pass


def _safe_artifact_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.is_file() or p.stat().st_size > 8_000_000:
        return {}
    try:
        payload = json.loads(p.read_text(errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _normalize_record(row: sqlite3.Row) -> dict:
    payload = _safe_artifact_json(row["artifact_path"])
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    provenance = payload.get("provenance") or result.get("provenance") or "UNSPECIFIED"
    version = (
        payload.get("version")
        or result.get("version")
        or payload.get("version_scope")
        or result.get("version_scope")
        or "unknown"
    )
    entity = payload.get("entity") or result.get("entity") or row["subject"]
    change_class = (
        payload.get("change_class")
        or result.get("change_class")
        or payload.get("change")
        or "unknown"
    )
    fact = payload.get("fact") or result.get("fact") or row["summary"]
    evidence_grade = payload.get("evidence_grade") or row["confidence"]
    source_hashes = []
    if row["artifact_sha256"]:
        source_hashes.append(str(row["artifact_sha256"]))
    listed_hashes = payload.get("source_hashes") or result.get("source_hashes")
    if isinstance(listed_hashes, list):
        source_hashes.extend(str(item) for item in listed_hashes if str(item).strip())
    if not source_hashes and row["artifact_path"]:
        source_hashes.append(hashlib.sha256(str(row["artifact_path"]).encode()).hexdigest())

    return {
        "discovery_id": row["id"],
        "task_id": row["task_id"],
        "entity": str(entity),
        "version": str(version),
        "change_class": str(change_class),
        "evidence_grade": str(evidence_grade),
        "fact": str(fact),
        "provenance": str(provenance),
        "source_hashes": list(dict.fromkeys(source_hashes)),
        "interval": {
            "start": payload.get("interval_start") or result.get("interval_start") or str(version),
            "end": payload.get("interval_end") or result.get("interval_end") or str(version),
            "uncertain": bool(payload.get("interval_uncertain") or result.get("interval_uncertain") or False),
            "unknown_reason": payload.get("unknown_interval_reason")
            or result.get("unknown_interval_reason")
            or "",
        },
        "historical_predicate": bool(
            payload.get("historical_predicate") or result.get("historical_predicate") or False
        ),
    }


def _is_current_jp(record: dict) -> bool:
    joined = f"{record['version']} {record['provenance']}".upper()
    return "CURRENT_JP" in joined or record["version"].lower() == "jp-current"


def query_temporal_lattice(
    conn: sqlite3.Connection,
    *,
    entity: str,
    version: str | None = None,
    change_class: str | None = None,
    evidence_grade: str | None = None,
) -> dict:
    try:
        rows = list(
            conn.execute(
                """select id,task_id,confidence,subject,summary,artifact_path,artifact_sha256
                     from brain_discoveries
                    where status != 'DISMISSED'"""
            )
        )
    except sqlite3.OperationalError as exc:
        raise TemporalQueryError("brain_discoveries table is required for temporal queries") from exc

    records = [_normalize_record(row) for row in rows]
    entity_records = [r for r in records if r["entity"].lower() == entity.lower()]

    filtered = entity_records
    if version:
        filtered = [r for r in filtered if r["version"].lower() == version.lower()]
    if change_class:
        filtered = [r for r in filtered if r["change_class"].lower() == change_class.lower()]
    if evidence_grade:
        filtered = [r for r in filtered if r["evidence_grade"].lower() == evidence_grade.lower()]

    historical_request = bool(version) and version.lower() not in {"current_jp", "jp-current", "jp"}
    if historical_request:
        has_current_jp = any(_is_current_jp(item) for item in entity_records)
        has_historical_predicate = any(item["historical_predicate"] for item in filtered)
        if has_current_jp and (not filtered or not has_historical_predicate):
            raise TemporalQueryError(
                "BLOCKED_EVIDENCE: refusing to backfill unknown historical interval from current JP evidence without a historical predicate"
            )

    interval_uncertainty = []
    for item in filtered:
        interval = item["interval"]
        if interval["uncertain"] or interval["unknown_reason"]:
            interval_uncertainty.append(
                {
                    "entity": item["entity"],
                    "version": item["version"],
                    "start": interval["start"],
                    "end": interval["end"],
                    "unknown_reason": interval["unknown_reason"] or "UNKNOWN_INTERVAL",
                }
            )

    return {
        "query": {
            "entity": entity,
            "version": version,
            "change_class": change_class,
            "evidence_grade": evidence_grade,
        },
        "facts": filtered,
        "interval_uncertainty": interval_uncertainty,
    }
