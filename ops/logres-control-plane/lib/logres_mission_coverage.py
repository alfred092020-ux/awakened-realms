from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

_CONTENT_OBJECTIVES = frozenset(
    {
        "MAP_CONTENT",
        "ACTOR_CONTENT",
        "COMBAT_CONTENT",
        "ITEM_CONTENT",
        "QUEST_CONTENT",
    }
)
_MANIFEST_NAME = "completion_manifest.json"
_MANIFEST_SCHEMA = "logres-project-completion-manifest-v2"
_HISTORICAL_TOTAL_STATUS = "UNKNOWABLE_FROM_CURRENT_EVIDENCE"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_LITERAL_KEY_RE = re.compile(r"\bkey\s*:\s*['\"]([^'\"]+)['\"]")
_SYMBOL_KEY_RE = re.compile(r"\bkey\s*:\s*([A-Z][A-Z0-9_]*)\b")
_SCHEMA_VERSION_RE = re.compile(
    r"['\"]([a-z][a-z0-9-]*-content-v\d+)['\"]\s+as\s+const"
)


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists mission_gap_scans(
          id integer primary key autoincrement,
          created_at text not null default (datetime('now')),
          payload_json text not null
        );
        """
    )
    conn.commit()


def _rows(conn: sqlite3.Connection, sql: str, args=()) -> list[dict]:
    return [dict(row) for row in conn.execute(sql, args)]


def _leaf_objectives(conn: sqlite3.Connection) -> list[dict]:
    return _rows(
        conn,
        """select o.id,o.title,o.definition_of_done
             from mission_objectives o
            where not exists(
              select 1 from mission_objectives c where c.parent_id=o.id
            )
            order by o.sort_order,o.id""",
    )


def _links(conn: sqlite3.Connection, objective_id: str) -> list[dict]:
    return _rows(
        conn,
        """select milestone_id,task_id,gate_type
             from mission_links
            where objective_id=?
            order by gate_type,milestone_id,task_id""",
        (objective_id,),
    )


def _task_refs(conn: sqlite3.Connection, links: list[dict]) -> list[dict]:
    out: list[dict] = []
    for link in links:
        task_id = link.get("task_id")
        if task_id:
            row = conn.execute(
                "select id,status,title,note from tasks where id=?",
                (task_id,),
            ).fetchone()
            if row:
                out.append(
                    {
                        "type": "task",
                        "id": row["id"],
                        "status": row["status"],
                        "title": row["title"],
                        "note": row["note"],
                    }
                )
        milestone_id = link.get("milestone_id")
        if milestone_id:
            row = conn.execute(
                """select id,status,title,definition_of_done
                     from milestones where id=?""",
                (milestone_id,),
            ).fetchone()
            if row:
                out.append(
                    {
                        "type": "milestone",
                        "id": row["id"],
                        "status": row["status"],
                        "title": row["title"],
                        "definition_of_done": row["definition_of_done"],
                    }
                )
    return out


def _classify(refs: list[dict]) -> tuple[str, str]:
    if not refs:
        return "UNCOVERED", "IMPLEMENTATION_GAP"
    statuses = {str(ref["status"]) for ref in refs}
    if statuses and all(
        status in {"DONE", "COMPLETE", "RESOLVED"} for status in statuses
    ):
        return "COMPLETE", "NONE"
    if statuses & {"ACTIVE", "READY", "IN_PROGRESS"}:
        return "IN_PROGRESS", "RUNNABLE_OR_ACTIVE"
    if statuses and all(
        status in {"BLOCKED_EVIDENCE", "WAITING_EXTERNAL"} for status in statuses
    ):
        return "WAITING_EXTERNAL", "EVIDENCE_CEILING"
    if statuses & {"BLOCKED_DEP", "BLOCKED"}:
        return "BLOCKED", "DEPENDENCY_BLOCKED"
    return "UNCOVERED", "IMPLEMENTATION_GAP"


def stable_ids_sha256(ids: list[str] | tuple[str, ...]) -> str:
    normalized = sorted(str(value) for value in ids)
    raw = json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _safe_relative_path(value: Any, *, label: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"{label} path is required")
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} path must be repository-relative")
    return path.as_posix()


def _validate_hash(value: Any, *, label: str) -> str:
    digest = str(value or "").strip().lower()
    if not _SHA256_RE.fullmatch(digest):
        raise ValueError(f"{label} must be a lowercase sha256")
    return digest


def load_completion_manifest(path: Path) -> dict:
    data = json.loads(Path(path).read_text())
    if data.get("schema") != _MANIFEST_SCHEMA:
        raise ValueError(
            f"completion manifest schema must be {_MANIFEST_SCHEMA}"
        )
    version = str(data.get("version") or "").strip()
    if not version:
        raise ValueError("completion manifest version is required")

    historical = data.get("historical_total_completeness")
    if (
        not isinstance(historical, dict)
        or historical.get("status") != _HISTORICAL_TOTAL_STATUS
        or not str(historical.get("reason") or "").strip()
    ):
        raise ValueError(
            "completion manifest must explicitly mark historical total "
            "as UNKNOWABLE_FROM_CURRENT_EVIDENCE"
        )

    categories = data.get("categories")
    if not isinstance(categories, dict) or not categories:
        raise ValueError("completion manifest categories must be non-empty")

    normalized: dict[str, dict] = {}
    by_objective: dict[str, dict] = {}

    for category_id, raw in categories.items():
        if not isinstance(raw, dict):
            raise ValueError(f"category {category_id} must be an object")
        objective_id = str(raw.get("objective_id") or "").strip()
        criterion_id = str(raw.get("criterion_id") or "").strip()
        if not objective_id or not criterion_id:
            raise ValueError(
                f"category {category_id} must declare objective_id and criterion_id"
            )

        source = raw.get("source_inventory")
        if not isinstance(source, dict):
            raise ValueError(f"category {category_id} source_inventory is required")
        source_path = _safe_relative_path(
            source.get("path"),
            label=f"{category_id} source_inventory",
        )
        schema_version = str(source.get("schema_version") or "").strip()
        if not schema_version:
            raise ValueError(
                f"category {category_id} source schema_version is required"
            )
        file_sha256 = _validate_hash(
            source.get("file_sha256"),
            label=f"{category_id} source file_sha256",
        )

        ids_raw = source.get("ids")
        if not isinstance(ids_raw, list) or not ids_raw:
            raise ValueError(
                f"category {category_id} source ids must be a non-empty list"
            )
        source_ids = [str(value or "").strip() for value in ids_raw]
        if any(not value for value in source_ids):
            raise ValueError(f"category {category_id} source ids cannot be empty")
        if source_ids != sorted(source_ids) or len(source_ids) != len(set(source_ids)):
            raise ValueError(
                f"category {category_id} source ids must be unique and sorted"
            )
        ids_sha256 = _validate_hash(
            source.get("ids_sha256"),
            label=f"{category_id} source ids_sha256",
        )
        actual_declared_ids_hash = stable_ids_sha256(source_ids)
        if ids_sha256 != actual_declared_ids_hash:
            raise ValueError(
                f"category {category_id} source ids_sha256 mismatch: "
                f"expected {ids_sha256}, computed {actual_declared_ids_hash}"
            )

        targets_raw = raw.get("targets")
        if not isinstance(targets_raw, list) or not targets_raw:
            raise ValueError(f"category {category_id} targets must be non-empty")
        target_map: dict[str, dict] = {}
        required_ids: list[str] = []
        bounded_ids: list[str] = []
        for target in targets_raw:
            if not isinstance(target, dict):
                raise ValueError(f"category {category_id} target must be an object")
            stable_id = str(target.get("stable_id") or "").strip()
            if not stable_id or stable_id in target_map:
                raise ValueError(
                    f"category {category_id} has invalid or duplicate stable_id"
                )
            disposition = str(target.get("disposition") or "").strip()
            if disposition == "required":
                if not str(target.get("provenance_class") or "").strip():
                    raise ValueError(
                        f"required target {stable_id} must declare provenance_class"
                    )
                required_ids.append(stable_id)
            elif disposition in {"ceiling", "excluded"}:
                reason = str(
                    target.get("evidence_ceiling")
                    or target.get("exclusion_reason")
                    or ""
                ).strip()
                if not reason:
                    raise ValueError(
                        f"bounded target {stable_id} must declare a reason"
                    )
                bounded_ids.append(stable_id)
            else:
                raise ValueError(
                    f"target {stable_id} has unsupported disposition "
                    f"{disposition!r}"
                )
            target_map[stable_id] = dict(target)

        if set(target_map) != set(source_ids):
            missing_targets = sorted(set(source_ids) - set(target_map))
            manifest_only = sorted(set(target_map) - set(source_ids))
            raise ValueError(
                f"category {category_id} target/source inventory mismatch: "
                f"unaccounted={missing_targets} manifest_only={manifest_only}"
            )

        ceiling = raw.get("historical_total_ceiling")
        if (
            not isinstance(ceiling, dict)
            or ceiling.get("status") != _HISTORICAL_TOTAL_STATUS
            or not str(ceiling.get("reason") or "").strip()
        ):
            raise ValueError(
                f"category {category_id} must declare historical total ceiling"
            )

        category = {
            "category_id": category_id,
            "objective_id": objective_id,
            "criterion_id": criterion_id,
            "title": str(raw.get("title") or category_id),
            "source_inventory": {
                "path": source_path,
                "schema_version": schema_version,
                "file_sha256": file_sha256,
                "ids": tuple(source_ids),
                "ids_sha256": ids_sha256,
            },
            "targets": target_map,
            "required_ids": tuple(sorted(required_ids)),
            "bounded_ids": tuple(sorted(bounded_ids)),
            "historical_total_ceiling": dict(ceiling),
        }
        normalized[category_id] = category
        if objective_id in by_objective:
            raise ValueError(
                f"duplicate content objective in completion manifest: {objective_id}"
            )
        by_objective[objective_id] = category

    missing_objectives = sorted(_CONTENT_OBJECTIVES - set(by_objective))
    if missing_objectives:
        raise ValueError(
            "completion manifest missing content objectives: "
            + ", ".join(missing_objectives)
        )

    return {
        "schema": _MANIFEST_SCHEMA,
        "version": version,
        "inventory_anchor_sha": str(data.get("inventory_anchor_sha") or ""),
        "evidence_policy": str(data.get("evidence_policy") or ""),
        "historical_total_completeness": dict(historical),
        "categories": normalized,
        "objectives": by_objective,
    }


def _resolve_repo_root(root: Path) -> Path:
    root = Path(root)
    if (root / "src" / "game" / "logres").is_dir():
        return root

    configured = os.environ.get("LOGRES_REPO")
    if configured:
        candidate = Path(configured)
        if (candidate / "src" / "game" / "logres").is_dir():
            return candidate

    candidate = root / "src" / "awakened-realms"
    if (candidate / "src" / "game" / "logres").is_dir():
        return candidate
    return root


def _resolve_manifest_path(root: Path, manifest_path: Path | None) -> Path:
    if manifest_path is not None:
        return Path(manifest_path)
    root = Path(root)
    runtime = root / "config" / _MANIFEST_NAME
    if runtime.is_file():
        return runtime
    repo = _resolve_repo_root(root)
    source = repo / "ops" / "logres-control-plane" / "config" / _MANIFEST_NAME
    return source


def _resolve_literal_symbol(repo_root: Path, symbol: str) -> str | None:
    pattern = re.compile(
        rf"(?:export\s+)?const\s+{re.escape(symbol)}\s*=\s*"
        r"['\"]([^'\"]+)['\"]",
        re.MULTILINE,
    )
    for path in sorted((repo_root / "src" / "game" / "logres").rglob("*.ts")):
        try:
            text = path.read_text()
        except OSError:
            continue
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


def _extract_source_inventory(
    repo_root: Path,
    source: dict,
) -> dict[str, Any]:
    path = repo_root / source["path"]
    if not path.is_file():
        return {
            "path": str(path),
            "exists": False,
            "file_sha256": None,
            "schema_version": None,
            "ids": [],
            "ids_sha256": stable_ids_sha256([]),
            "unresolved_key_symbols": [],
        }

    raw = path.read_bytes()
    text = raw.decode("utf-8")
    ids = list(_LITERAL_KEY_RE.findall(text))
    unresolved: list[str] = []
    for symbol in _SYMBOL_KEY_RE.findall(text):
        resolved = _resolve_literal_symbol(repo_root, symbol)
        if resolved:
            ids.append(resolved)
        else:
            unresolved.append(symbol)

    actual_ids = sorted(set(ids))
    versions = sorted(set(_SCHEMA_VERSION_RE.findall(text)))
    return {
        "path": str(path),
        "exists": True,
        "file_sha256": hashlib.sha256(raw).hexdigest(),
        "schema_version": versions[0] if len(versions) == 1 else None,
        "schema_versions_found": versions,
        "ids": actual_ids,
        "ids_sha256": stable_ids_sha256(actual_ids),
        "unresolved_key_symbols": sorted(set(unresolved)),
    }


def _category_report(repo_root: Path, category: dict) -> dict:
    source = category["source_inventory"]
    actual = _extract_source_inventory(repo_root, source)

    expected_ids = set(source["ids"])
    actual_ids = set(actual["ids"])
    target_ids = set(category["targets"])
    required_ids = set(category["required_ids"])
    bounded_ids = set(category["bounded_ids"])

    represented_ids = sorted(required_ids & actual_ids)
    bounded_present_ids = sorted(bounded_ids & actual_ids)
    missing_ids = sorted(required_ids - actual_ids)
    omitted_from_manifest_ids = sorted(actual_ids - target_ids)
    manifest_only_ids = sorted(target_ids - actual_ids)
    omitted_from_source_inventory_ids = sorted(actual_ids - expected_ids)
    missing_from_source_ids = sorted(expected_ids - actual_ids)

    file_hash_match = (
        actual["exists"] and actual["file_sha256"] == source["file_sha256"]
    )
    source_version_match = (
        actual["schema_version"] == source["schema_version"]
    )
    inventory_hash_match = actual["ids_sha256"] == source["ids_sha256"]

    complete = bool(
        actual["exists"]
        and file_hash_match
        and source_version_match
        and inventory_hash_match
        and not actual["unresolved_key_symbols"]
        and not missing_ids
        and not omitted_from_manifest_ids
        and not manifest_only_ids
        and not omitted_from_source_inventory_ids
        and not missing_from_source_ids
    )

    return {
        "category_id": category["category_id"],
        "objective_id": category["objective_id"],
        "criterion_id": category["criterion_id"],
        "title": category["title"],
        "source_path": source["path"],
        "source_exists": actual["exists"],
        "source_version_expected": source["schema_version"],
        "source_version_actual": actual["schema_version"],
        "source_version_match": source_version_match,
        "source_file_sha256_expected": source["file_sha256"],
        "source_file_sha256_actual": actual["file_sha256"],
        "source_file_hash_match": file_hash_match,
        "source_inventory_sha256_expected": source["ids_sha256"],
        "source_inventory_sha256_actual": actual["ids_sha256"],
        "source_inventory_hash_match": inventory_hash_match,
        "corpus_total": len(actual_ids),
        "required_count": len(required_ids),
        "represented_count": len(represented_ids),
        "ceiling_or_excluded_count": len(bounded_present_ids),
        "missing_count": len(missing_ids),
        "omitted_from_manifest_count": len(omitted_from_manifest_ids),
        "manifest_only_count": len(manifest_only_ids),
        "omitted_from_source_inventory_count": len(
            omitted_from_source_inventory_ids
        ),
        "missing_from_source_count": len(missing_from_source_ids),
        "represented_ids": represented_ids,
        "ceiling_or_excluded_ids": bounded_present_ids,
        "missing_ids": missing_ids,
        "omitted_from_manifest_ids": omitted_from_manifest_ids,
        "manifest_only_ids": manifest_only_ids,
        "omitted_from_source_inventory_ids": omitted_from_source_inventory_ids,
        "missing_from_source_ids": missing_from_source_ids,
        "unresolved_key_symbols": actual["unresolved_key_symbols"],
        "historical_total_ceiling": category["historical_total_ceiling"],
        "complete": complete,
    }


def completion_manifest_report(
    root: Path,
    manifest_path: Path | None = None,
) -> dict:
    root = Path(root)
    repo_root = _resolve_repo_root(root)
    resolved_manifest = _resolve_manifest_path(root, manifest_path)

    try:
        manifest = load_completion_manifest(resolved_manifest)
    except Exception as exc:
        return {
            "schema": "logres-project-completion-report-v2",
            "manifest_path": str(resolved_manifest),
            "manifest_error": f"{type(exc).__name__}: {exc}",
            "declared_scope_complete": False,
            "historical_total_complete": False,
            "historical_total_status": _HISTORICAL_TOTAL_STATUS,
            "completion_claim": "DECLARED_RECONSTRUCTION_SCOPE_ONLY",
            "categories": {},
            "by_objective": {},
        }

    categories: dict[str, dict] = {}
    by_objective: dict[str, dict] = {}
    for category_id, category in manifest["categories"].items():
        report = _category_report(repo_root, category)
        categories[category_id] = report
        by_objective[category["objective_id"]] = report

    declared_complete = all(
        report["complete"] for report in categories.values()
    )

    def total(field: str) -> int:
        return sum(int(report[field]) for report in categories.values())

    return {
        "schema": "logres-project-completion-report-v2",
        "manifest_schema": manifest["schema"],
        "manifest_version": manifest["version"],
        "manifest_path": str(resolved_manifest),
        "inventory_anchor_sha": manifest["inventory_anchor_sha"],
        "repository_root": str(repo_root),
        "completion_claim": "DECLARED_RECONSTRUCTION_SCOPE_ONLY",
        "declared_scope_complete": declared_complete,
        "historical_total_complete": False,
        "historical_total_status": manifest[
            "historical_total_completeness"
        ]["status"],
        "historical_total_reason": manifest[
            "historical_total_completeness"
        ]["reason"],
        "corpus_total": total("corpus_total"),
        "required_count": total("required_count"),
        "represented_count": total("represented_count"),
        "ceiling_or_excluded_count": total("ceiling_or_excluded_count"),
        "missing_count": total("missing_count"),
        "omitted_from_manifest_count": total("omitted_from_manifest_count"),
        "manifest_only_count": total("manifest_only_count"),
        "categories": categories,
        "by_objective": by_objective,
    }


def scan(
    conn: sqlite3.Connection,
    persist: bool = False,
    *,
    root: Path | None = None,
    manifest_path: Path | None = None,
) -> dict:
    ensure_schema(conn)
    objectives = _leaf_objectives(conn)
    content_needed = any(
        objective["id"] in _CONTENT_OBJECTIVES for objective in objectives
    )
    completion = None
    if content_needed:
        completion = completion_manifest_report(
            root
            or Path(
                os.environ.get(
                    "LOGRES_ROOT",
                    "/home/ubuntu/logres",
                )
            ),
            manifest_path=manifest_path,
        )

    gaps: list[dict] = []
    counts: dict[str, int] = {}
    content_completion: dict[str, dict] = {}

    for objective in objectives:
        links = _links(conn, objective["id"])
        refs = _task_refs(conn, links)
        state, kind = _classify(refs)
        category_report = None
        if completion is not None and objective["id"] in _CONTENT_OBJECTIVES:
            category_report = completion["by_objective"].get(objective["id"])
            if category_report is None or not category_report["complete"]:
                if state == "COMPLETE":
                    state = "UNCOVERED"
                kind = "CONTENT_CORPUS_GAP"
            if category_report is not None:
                content_completion[category_report["category_id"]] = (
                    category_report
                )

        item = {
            "objective_id": objective["id"],
            "title": objective["title"],
            "definition_of_done": objective["definition_of_done"],
            "state": state,
            "gap_kind": kind,
            "references": refs,
        }
        if category_report is not None:
            item["content_completion"] = category_report

        counts[state] = counts.get(state, 0) + 1
        if state != "COMPLETE":
            gaps.append(item)

    payload = {
        "counts": counts,
        "gaps": gaps,
        "gap_count": len(gaps),
        "content_completion": content_completion,
    }
    if completion is not None:
        payload["project_completion_scope"] = completion

    if persist:
        cur = conn.execute(
            "insert into mission_gap_scans(payload_json) values(?)",
            (json.dumps(payload, sort_keys=True),),
        )
        conn.commit()
        payload["scan_id"] = int(cur.lastrowid)
    return payload


def latest(conn: sqlite3.Connection) -> dict:
    ensure_schema(conn)
    row = conn.execute(
        """select id,created_at,payload_json
             from mission_gap_scans
            order by id desc limit 1"""
    ).fetchone()
    if not row:
        return {"available": False}
    return {
        "available": True,
        "scan_id": row[0],
        "created_at": row[1],
        "payload": json.loads(row[2]),
    }
