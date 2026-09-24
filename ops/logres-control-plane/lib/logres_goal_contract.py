from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


SCHEMA = "logres-milestone-contract-v1"
SUPPORTED_CHECKS = {
    "task_state",
    "verification",
    "artifact",
    "dependency_state",
    "evidence_state",
    "external_manual",
}
PASS_TASK_STATES = {"DONE", "RESOLVED"}
TERMINAL_TASK_STATES = {"DONE", "RESOLVED", "SUPERSEDED", "CANCELLED"}


@dataclass(frozen=True)
class CriterionResult:
    criterion_id: str
    description: str
    weight: float
    status: str
    passed: bool
    reason: str
    check_type: str
    task_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContractResult:
    milestone_id: str
    title: str
    definition_of_done: str
    contract_fingerprint: str
    integration_sha: str
    progress_percent: float
    passed_weight: float
    total_weight: float
    state: str
    criteria: tuple[CriterionResult, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["criteria"] = [item.to_dict() for item in self.criteria]
        data["unmet_criterion_ids"] = [
            item.criterion_id for item in self.criteria if not item.passed
        ]
        data["by_status"] = {}
        for item in self.criteria:
            data["by_status"].setdefault(item.status, []).append(item.criterion_id)
        return data


def load_contracts(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    validate_contracts(payload)
    return payload


def canonical_fingerprint(value: Any) -> str:
    blob = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def validate_contracts(payload: dict[str, Any]) -> None:
    if payload.get("schema") != SCHEMA:
        raise ValueError(f"unsupported contract schema: {payload.get('schema')!r}")
    milestones = payload.get("milestones")
    if not isinstance(milestones, dict) or not milestones:
        raise ValueError("milestones must be a non-empty object")

    for milestone_id, milestone in milestones.items():
        if not isinstance(milestone, dict):
            raise ValueError(f"{milestone_id}: milestone must be an object")
        criteria = milestone.get("criteria")
        if not isinstance(criteria, list) or not criteria:
            raise ValueError(f"{milestone_id}: criteria must be a non-empty list")
        seen: set[str] = set()
        total = 0.0
        for item in criteria:
            if not isinstance(item, dict):
                raise ValueError(f"{milestone_id}: criterion must be an object")
            criterion_id = str(item.get("id") or "").strip()
            if not criterion_id:
                raise ValueError(f"{milestone_id}: criterion id is required")
            if criterion_id in seen:
                raise ValueError(f"{milestone_id}: duplicate criterion id {criterion_id}")
            seen.add(criterion_id)
            weight = float(item.get("weight", 0))
            if weight <= 0:
                raise ValueError(
                    f"{milestone_id}/{criterion_id}: weight must be positive"
                )
            total += weight
            check = item.get("check")
            if not isinstance(check, dict):
                raise ValueError(
                    f"{milestone_id}/{criterion_id}: check must be an object"
                )
            check_type = check.get("type")
            if check_type not in SUPPORTED_CHECKS:
                raise ValueError(
                    f"{milestone_id}/{criterion_id}: unsupported check {check_type!r}"
                )
            template = item.get("task_template")
            if template is not None:
                _validate_task_template(milestone_id, criterion_id, template)
        if total <= 0:
            raise ValueError(f"{milestone_id}: total weight must be positive")


def _validate_task_template(
    milestone_id: str,
    criterion_id: str,
    template: Any,
) -> None:
    if not isinstance(template, dict):
        raise ValueError(
            f"{milestone_id}/{criterion_id}: task_template must be an object"
        )
    required = {"title", "work_type", "priority", "scopes", "acceptance"}
    missing = sorted(key for key in required if key not in template)
    if missing:
        raise ValueError(
            f"{milestone_id}/{criterion_id}: task_template missing {','.join(missing)}"
        )
    if not isinstance(template.get("scopes"), list) or not template["scopes"]:
        raise ValueError(
            f"{milestone_id}/{criterion_id}: task_template scopes required"
        )
    if not isinstance(template.get("acceptance"), list) or not template["acceptance"]:
        raise ValueError(
            f"{milestone_id}/{criterion_id}: task_template acceptance required"
        )


def _task_status(conn: sqlite3.Connection, task_id: str) -> str | None:
    row = conn.execute("select status from tasks where id=?", (task_id,)).fetchone()
    return str(row[0]) if row else None


def _task_result(
    criterion: dict[str, Any],
    *,
    status: str | None,
    pass_statuses: set[str],
    evidence_mode: bool = False,
) -> tuple[str, bool, str]:
    if status is None:
        return "BLOCKED_DEP", False, "referenced task does not exist"
    if status in pass_statuses:
        return "PASS", True, f"task status={status}"
    if status == "READY":
        return "EXECUTABLE", False, "referenced task is ready"
    if status == "ACTIVE":
        return "ACTIVE", False, "referenced task is active"
    if status == "BLOCKED_EVIDENCE":
        return "BLOCKED_EVIDENCE", False, "referenced task is evidence-blocked"
    if status == "BLOCKED_DEP":
        return "BLOCKED_DEP", False, "referenced task is dependency-blocked"
    if evidence_mode and status in {"SUPERSEDED", "CANCELLED"}:
        return "BLOCKED_EVIDENCE", False, f"evidence task is terminal: {status}"
    return "BLOCKED_DEP", False, f"task status={status} is not accepted"


def _evaluate_task_state(
    conn: sqlite3.Connection,
    criterion: dict[str, Any],
) -> tuple[str, bool, str, str | None]:
    check = criterion["check"]
    task_id = str(check["task_id"])
    pass_statuses = set(check.get("pass_statuses") or PASS_TASK_STATES)
    status = _task_status(conn, task_id)
    result = _task_result(
        criterion,
        status=status,
        pass_statuses=pass_statuses,
    )
    return (*result, task_id)


def _evaluate_verification(
    conn: sqlite3.Connection,
    criterion: dict[str, Any],
    integration_sha: str,
) -> tuple[str, bool, str, str | None]:
    check = criterion["check"]
    mode = str(check.get("mode") or "full-e2e")
    wanted = str(check.get("status") or "PASS")
    row = conn.execute(
        """select status,ran_at,details
             from verification
            where sha=? and mode=?
            order by ran_at desc
            limit 1""",
        (integration_sha, mode),
    ).fetchone()
    if not row:
        return (
            "BLOCKED_DEP",
            False,
            f"no {mode} verification exists for current integration SHA",
            None,
        )
    status = str(row[0])
    if status == wanted:
        return (
            "PASS",
            True,
            f"{mode}={status} for current integration SHA",
            None,
        )
    return (
        "BLOCKED_DEP",
        False,
        f"{mode}={status}; required {wanted}",
        None,
    )


def _evaluate_artifact(
    criterion: dict[str, Any],
    root: Path,
) -> tuple[str, bool, str, str | None]:
    check = criterion["check"]
    relative = Path(str(check["path"]))
    path = relative if relative.is_absolute() else root / relative
    if not path.is_file():
        status = "EXECUTABLE" if criterion.get("task_template") else "BLOCKED_DEP"
        return status, False, f"artifact missing: {path}", None
    expected = check.get("sha256")
    if expected:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            status = "EXECUTABLE" if criterion.get("task_template") else "BLOCKED_DEP"
            return (
                status,
                False,
                f"artifact hash mismatch: expected {expected}, got {actual}",
                None,
            )
    return "PASS", True, f"artifact present: {path}", None


def _evaluate_dependency_state(
    conn: sqlite3.Connection,
    criterion: dict[str, Any],
) -> tuple[str, bool, str, str | None]:
    task_id = str(criterion["check"]["task_id"])
    rows = list(
        conn.execute(
            """select d.depends_on,d.kind,t.status
                 from task_dependencies d
                 left join tasks t on t.id=d.depends_on
                where d.task_id=?
                order by d.depends_on""",
            (task_id,),
        )
    )
    unresolved = [
        (str(row[0]), str(row[1]), str(row[2] or "MISSING"))
        for row in rows
        if str(row[2] or "MISSING") not in PASS_TASK_STATES
    ]
    if not unresolved:
        return "PASS", True, "all task dependencies are satisfied", task_id
    if any(status == "BLOCKED_EVIDENCE" for _dep, _kind, status in unresolved):
        return (
            "BLOCKED_EVIDENCE",
            False,
            "dependency evidence ceiling: "
            + ", ".join(f"{dep}={status}" for dep, _kind, status in unresolved),
            task_id,
        )
    return (
        "BLOCKED_DEP",
        False,
        "unsatisfied dependencies: "
        + ", ".join(f"{dep}={status}" for dep, _kind, status in unresolved),
        task_id,
    )


def _evaluate_evidence_state(
    conn: sqlite3.Connection,
    criterion: dict[str, Any],
) -> tuple[str, bool, str, str | None]:
    check = criterion["check"]
    task_id = str(check["task_id"])
    pass_statuses = set(check.get("pass_statuses") or PASS_TASK_STATES)
    status = _task_status(conn, task_id)
    result = _task_result(
        criterion,
        status=status,
        pass_statuses=pass_statuses,
        evidence_mode=True,
    )
    return (*result, task_id)


def _evaluate_external_manual(
    conn: sqlite3.Connection,
    criterion: dict[str, Any],
) -> tuple[str, bool, str, str | None]:
    check = criterion["check"]
    task_id = str(check.get("task_id") or "") or None
    if not task_id:
        return "BLOCKED_EXTERNAL", False, "manual external gate is unresolved", None
    pass_statuses = set(check.get("pass_statuses") or PASS_TASK_STATES)
    status = _task_status(conn, task_id)
    if status in pass_statuses:
        return "PASS", True, f"external/manual task status={status}", task_id
    return (
        "BLOCKED_EXTERNAL",
        False,
        f"external/manual task status={status or 'MISSING'}",
        task_id,
    )


def evaluate_criterion(
    conn: sqlite3.Connection,
    criterion: dict[str, Any],
    *,
    integration_sha: str,
    root: Path,
) -> CriterionResult:
    check_type = str(criterion["check"]["type"])
    if check_type == "task_state":
        result = _evaluate_task_state(conn, criterion)
    elif check_type == "verification":
        result = _evaluate_verification(conn, criterion, integration_sha)
    elif check_type == "artifact":
        result = _evaluate_artifact(criterion, root)
    elif check_type == "dependency_state":
        result = _evaluate_dependency_state(conn, criterion)
    elif check_type == "evidence_state":
        result = _evaluate_evidence_state(conn, criterion)
    elif check_type == "external_manual":
        result = _evaluate_external_manual(conn, criterion)
    else:
        raise ValueError(f"unsupported criterion check: {check_type}")

    status, passed, reason, task_id = result
    if (
        not passed
        and status in {"BLOCKED_DEP", "BLOCKED_EVIDENCE"}
        and criterion.get("task_template")
    ):
        status = "EXECUTABLE"

    return CriterionResult(
        criterion_id=str(criterion["id"]),
        description=str(criterion.get("description") or ""),
        weight=float(criterion["weight"]),
        status=status,
        passed=bool(passed),
        reason=str(reason),
        check_type=check_type,
        task_id=task_id,
    )


def _overall_state(criteria: list[CriterionResult]) -> str:
    if criteria and all(item.passed for item in criteria):
        return "COMPLETE"
    statuses = {item.status for item in criteria if not item.passed}
    if "EXECUTABLE" in statuses:
        return "RUNNABLE"
    if "ACTIVE" in statuses:
        return "WAIT_ACTIVE"
    if "BLOCKED_EXTERNAL" in statuses:
        return "BLOCKED_EXTERNAL"
    if "BLOCKED_EVIDENCE" in statuses:
        return "BLOCKED_EVIDENCE"
    return "BLOCKED_DEP"


def evaluate_milestone(
    conn: sqlite3.Connection,
    contracts: dict[str, Any],
    milestone_id: str,
    *,
    integration_sha: str,
    root: Path,
) -> ContractResult:
    validate_contracts(contracts)
    milestone = contracts["milestones"].get(milestone_id)
    if milestone is None:
        raise ValueError(f"unknown milestone contract: {milestone_id}")
    criteria = [
        evaluate_criterion(
            conn,
            item,
            integration_sha=integration_sha,
            root=root,
        )
        for item in milestone["criteria"]
    ]
    total = sum(item.weight for item in criteria)
    passed = sum(item.weight for item in criteria if item.passed)
    progress = 100.0 if total <= 0 else round(100.0 * passed / total, 2)
    fingerprint = canonical_fingerprint(milestone)
    return ContractResult(
        milestone_id=milestone_id,
        title=str(milestone.get("title") or milestone_id),
        definition_of_done=str(milestone.get("definition_of_done") or ""),
        contract_fingerprint=fingerprint,
        integration_sha=integration_sha,
        progress_percent=progress,
        passed_weight=passed,
        total_weight=total,
        state=_overall_state(criteria),
        criteria=tuple(criteria),
    )
