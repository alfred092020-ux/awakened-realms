from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from logres_goal_contract import (
    canonical_fingerprint,
    evaluate_milestone,
    load_contracts,
)
from logres_semantic_dedupe import canonical, norm_text


GENERATION_SCHEMA = """
create table if not exists goal_executor_generations(
  milestone_id text not null,
  criterion_id text not null,
  contract_fingerprint text not null,
  template_fingerprint text not null,
  task_id text not null,
  created_at text not null,
  primary key(milestone_id,criterion_id,contract_fingerprint)
);
create unique index if not exists goal_executor_task_uq
  on goal_executor_generations(task_id);
"""
ELIGIBLE_CHECK_TYPES = {"task_state", "artifact"}
BLOCKED_TASK_STATES = {"BLOCKED_DEP", "BLOCKED_EVIDENCE"}
EQUIVALENT_TASK_STATES = {
    "READY",
    "ACTIVE",
    "DONE",
    "RESOLVED",
    "BLOCKED_DEP",
    "BLOCKED_EVIDENCE",
}
REQUIRED_TEMPLATE_FIELDS = {
    "title",
    "lane",
    "work_type",
    "priority",
    "expected_minutes",
    "concurrency_key",
    "evidence_policy",
    "scopes",
    "acceptance",
    "dependencies",
}


@dataclass(frozen=True)
class ExecutionCandidate:
    milestone_id: str
    criterion_id: str
    contract_fingerprint: str
    template_fingerprint: str
    task_id: str
    template: dict[str, Any]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "milestone_id": self.milestone_id,
            "criterion_id": self.criterion_id,
            "contract_fingerprint": self.contract_fingerprint,
            "template_fingerprint": self.template_fingerprint,
            "task_id": self.task_id,
            "template": self.template,
            "reason": self.reason,
        }


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(GENERATION_SCHEMA)
    conn.commit()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").upper()
    return token[:36] or "CRITERION"


def deterministic_task_id(
    milestone_id: str,
    criterion_id: str,
    contract_fingerprint: str,
) -> str:
    return (
        f"GOAL-{_slug(milestone_id)}-{_slug(criterion_id)}-"
        f"{contract_fingerprint[:10].upper()}"
    )


def _string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"task_template {field} must be a list")
    result = [str(item).strip() for item in value]
    if any(not item for item in result):
        raise ValueError(f"task_template {field} contains an empty value")
    return result


def validate_execution_template(template: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(template, dict):
        raise ValueError("task_template must be an object")
    missing = sorted(REQUIRED_TEMPLATE_FIELDS - set(template))
    if missing:
        raise ValueError(
            "task_template missing executor fields: " + ",".join(missing)
        )

    priority = int(template["priority"])
    minutes = int(template["expected_minutes"])
    if not 0 <= priority <= 9:
        raise ValueError("task_template priority must be 0..9")
    if not 5 <= minutes <= 240:
        raise ValueError("task_template expected_minutes must be 5..240")

    required_strings = (
        "title",
        "lane",
        "work_type",
        "concurrency_key",
        "evidence_policy",
    )
    normalized: dict[str, Any] = {}
    for field in required_strings:
        value = str(template[field]).strip()
        if not value:
            raise ValueError(f"task_template {field} is required")
        normalized[field] = value

    scopes = _string_list(template["scopes"], "scopes")
    acceptance = _string_list(template["acceptance"], "acceptance")
    if not scopes:
        raise ValueError("task_template scopes must not be empty")
    if not acceptance:
        raise ValueError("task_template acceptance must not be empty")

    dependencies = template["dependencies"]
    if not isinstance(dependencies, dict):
        raise ValueError("task_template dependencies must be an object")
    hard = _string_list(dependencies.get("hard", []), "dependencies.hard")
    integration = _string_list(
        dependencies.get("integration", []),
        "dependencies.integration",
    )
    if set(hard) & set(integration):
        raise ValueError(
            "task_template dependency cannot be both hard and integration"
        )

    normalized.update(
        {
            "priority": priority,
            "expected_minutes": minutes,
            "scopes": scopes,
            "acceptance": acceptance,
            "dependencies": {
                "hard": hard,
                "integration": integration,
            },
        }
    )
    return normalized


def _semantic_sha(template: dict[str, Any]) -> str:
    deps = [
        *template["dependencies"]["hard"],
        *template["dependencies"]["integration"],
    ]
    semantic = {
        "lane": norm_text(template["lane"]),
        "work_type": norm_text(template["work_type"]),
        "title": norm_text(template["title"]),
        "acceptance": sorted(norm_text(x) for x in template["acceptance"]),
        "scopes": sorted(norm_text(x) for x in template["scopes"]),
        "dependencies": sorted(norm_text(x) for x in deps),
        "failure_signature": "",
        "evidence_predicate": norm_text(template["evidence_policy"]),
    }
    raw = json.dumps(semantic, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def equivalent_task(
    conn: sqlite3.Connection,
    template: dict[str, Any],
) -> str | None:
    wanted = _semantic_sha(template)
    placeholders = ",".join("?" for _ in EQUIVALENT_TASK_STATES)
    rows = conn.execute(
        f"select id from tasks where status in ({placeholders}) order by id",
        tuple(sorted(EQUIVALENT_TASK_STATES)),
    ).fetchall()
    for row in rows:
        try:
            if canonical(conn, str(row[0]))["semantic_sha"] == wanted:
                return str(row[0])
        except (sqlite3.Error, ValueError):
            continue
    return None


def _criterion_is_safe(
    conn: sqlite3.Connection,
    raw: dict[str, Any],
    result: dict[str, Any],
) -> tuple[bool, str]:
    check = raw.get("check") or {}
    check_type = str(check.get("type") or "")
    if check_type not in ELIGIBLE_CHECK_TYPES:
        return False, f"check type {check_type or 'missing'} is not executable"
    if result.get("status") != "EXECUTABLE":
        return False, f"criterion status={result.get('status')}"

    if check_type == "task_state":
        task_id = str(check.get("task_id") or "")
        if task_id:
            row = conn.execute(
                "select status from tasks where id=?",
                (task_id,),
            ).fetchone()
            if row and str(row[0] or "") in BLOCKED_TASK_STATES:
                return False, f"referenced task is {row[0]}"
            if row:
                return False, f"referenced task already exists with status={row[0]}"
    return True, str(result.get("reason") or "explicit executable criterion")


def _generation_row(
    conn: sqlite3.Connection,
    milestone_id: str,
    criterion_id: str,
    contract_fingerprint: str,
) -> sqlite3.Row | None:
    return conn.execute(
        """select *
             from goal_executor_generations
            where milestone_id=?
              and criterion_id=?
              and contract_fingerprint=?""",
        (milestone_id, criterion_id, contract_fingerprint),
    ).fetchone()


def plan_one(
    conn: sqlite3.Connection,
    contracts: dict[str, Any],
    milestone_id: str,
    *,
    integration_sha: str,
    root: Path,
) -> dict[str, Any]:
    ensure_schema(conn)
    result = evaluate_milestone(
        conn,
        contracts,
        milestone_id,
        integration_sha=integration_sha,
        root=root,
    ).to_dict()
    milestone = contracts["milestones"][milestone_id]
    by_id = {item["criterion_id"]: item for item in result["criteria"]}

    skipped: list[dict[str, str]] = []
    for raw in milestone["criteria"]:
        criterion_id = str(raw["id"])
        template_raw = raw.get("task_template")
        if template_raw is None:
            continue
        criterion_result = by_id[criterion_id]
        safe, reason = _criterion_is_safe(conn, raw, criterion_result)
        if not safe:
            skipped.append({"criterion_id": criterion_id, "reason": reason})
            continue

        try:
            template = validate_execution_template(template_raw)
        except (TypeError, ValueError) as exc:
            skipped.append(
                {
                    "criterion_id": criterion_id,
                    "reason": f"template not execution-ready: {exc}",
                }
            )
            continue
        contract_fp = result["contract_fingerprint"]
        template_fp = canonical_fingerprint(template)
        check = raw.get("check") or {}
        if str(check.get("type") or "") == "task_state":
            task_id = str(check.get("task_id") or "").strip()
            if not task_id:
                skipped.append(
                    {
                        "criterion_id": criterion_id,
                        "reason": "task_state criterion requires explicit task_id",
                    }
                )
                continue
        else:
            task_id = deterministic_task_id(
                milestone_id,
                criterion_id,
                contract_fp,
            )
        generated = _generation_row(
            conn,
            milestone_id,
            criterion_id,
            contract_fp,
        )
        if generated:
            skipped.append(
                {
                    "criterion_id": criterion_id,
                    "reason": f"already generated as {generated['task_id']}",
                }
            )
            continue

        existing = conn.execute(
            "select status from tasks where id=?",
            (task_id,),
        ).fetchone()
        if existing:
            skipped.append(
                {
                    "criterion_id": criterion_id,
                    "reason": f"generated task id already exists: {task_id}",
                }
            )
            continue

        equivalent = equivalent_task(conn, template)
        if equivalent:
            skipped.append(
                {
                    "criterion_id": criterion_id,
                    "reason": f"equivalent task already exists: {equivalent}",
                }
            )
            continue

        candidate = ExecutionCandidate(
            milestone_id=milestone_id,
            criterion_id=criterion_id,
            contract_fingerprint=contract_fp,
            template_fingerprint=template_fp,
            task_id=task_id,
            template=template,
            reason=str(criterion_result.get("reason") or ""),
        )
        return {
            "milestone": result,
            "candidate": candidate.to_dict(),
            "skipped": skipped,
        }

    return {
        "milestone": result,
        "candidate": None,
        "skipped": skipped,
    }


def record_generation(
    conn: sqlite3.Connection,
    candidate: dict[str, Any],
) -> None:
    conn.execute(
        """insert or ignore into goal_executor_generations(
             milestone_id,criterion_id,contract_fingerprint,
             template_fingerprint,task_id,created_at
           ) values(?,?,?,?,?,?)""",
        (
            candidate["milestone_id"],
            candidate["criterion_id"],
            candidate["contract_fingerprint"],
            candidate["template_fingerprint"],
            candidate["task_id"],
            utc_now(),
        ),
    )
    conn.commit()


def coordinator_argv(
    candidate: dict[str, Any],
    coordinator: str,
) -> list[str]:
    template = candidate["template"]
    argv = [
        coordinator,
        "add-task",
        candidate["task_id"],
        str(template["priority"]),
        template["lane"],
        template["title"],
        "--milestone",
        candidate["milestone_id"],
        "--work-type",
        template["work_type"],
        "--concurrency-key",
        template["concurrency_key"],
        "--minutes",
        str(template["expected_minutes"]),
        "--evidence-policy",
        template["evidence_policy"],
    ]
    for dep in template["dependencies"]["hard"]:
        argv.extend(["--depends", dep])
    for dep in template["dependencies"]["integration"]:
        argv.extend(["--depends-integrated", dep])
    for criterion in template["acceptance"]:
        argv.extend(["--accept", criterion])
    for scope in template["scopes"]:
        argv.extend(["--scope", scope])
    return argv


def apply_one(
    conn: sqlite3.Connection,
    contracts: dict[str, Any],
    milestone_id: str,
    *,
    integration_sha: str,
    root: Path,
    coordinator: str,
    runner: Callable[..., Any],
) -> dict[str, Any]:
    plan = plan_one(
        conn,
        contracts,
        milestone_id,
        integration_sha=integration_sha,
        root=root,
    )
    candidate = plan["candidate"]
    if candidate is None:
        return {**plan, "created": False, "task_id": None}

    process = runner(
        coordinator_argv(candidate, coordinator),
        text=True,
        capture_output=True,
        check=False,
    )
    row = conn.execute(
        "select status from tasks where id=?",
        (candidate["task_id"],),
    ).fetchone()
    if not row:
        raise RuntimeError(
            "goal executor task creation failed: "
            + ((process.stderr or process.stdout or "").strip())
        )
    actual = canonical(conn, candidate["task_id"])["semantic_sha"]
    expected = _semantic_sha(candidate["template"])
    if actual != expected:
        raise RuntimeError(
            "goal executor deterministic task id collision: "
            f"{candidate['task_id']}"
        )
    if int(process.returncode) != 0:
        # The only accepted nonzero outcome is a race where equivalent work
        # landed under the deterministic task id before provenance recording.
        pass

    record_generation(conn, candidate)
    return {
        **plan,
        "created": True,
        "task_id": candidate["task_id"],
    }


def load_and_plan(
    conn: sqlite3.Connection,
    config_path: Path,
    milestone_id: str,
    *,
    integration_sha: str,
    root: Path,
) -> dict[str, Any]:
    return plan_one(
        conn,
        load_contracts(config_path),
        milestone_id,
        integration_sha=integration_sha,
        root=root,
    )
