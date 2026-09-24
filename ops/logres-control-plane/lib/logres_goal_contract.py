from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from logres_dependency import integration_prerequisite_satisfied


SCHEMA = "logres-milestone-contract-v1"
SUPPORTED_CHECKS = {
    "task_state",
    "verification",
    "artifact",
    "dependency_state",
    "evidence_state",
    "external_manual",
    "device_proof",
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
            if (
                check_type == "task_state"
                and "integration_required" in check
                and not isinstance(check["integration_required"], bool)
            ):
                raise ValueError(
                    f"{milestone_id}/{criterion_id}: "
                    "integration_required must be boolean"
                )
            if check_type == "device_proof":
                checkpoint = str(check.get("checkpoint") or "").strip()
                if not checkpoint:
                    raise ValueError(
                        f"{milestone_id}/{criterion_id}: "
                        "device_proof checkpoint is required"
                    )
                wanted_status = str(check.get("status") or "PASS").strip()
                if not wanted_status:
                    raise ValueError(
                        f"{milestone_id}/{criterion_id}: "
                        "device_proof status must be non-empty"
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


def _git_ancestor_checker(
    root: Path,
) -> Callable[[str, str], bool]:
    repositories = (
        root / "src" / "awakened-realms",
        root,
    )
    repo = next(
        (
            candidate
            for candidate in repositories
            if (candidate / ".git").exists()
        ),
        None,
    )

    def check(
        ancestor: str,
        descendant: str,
    ) -> bool:
        if ancestor == descendant:
            return True
        if repo is None:
            return False
        try:
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "merge-base",
                    "--is-ancestor",
                    ancestor,
                    descendant,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0

    return check


def _integration_carrier_task_ids(
    conn: sqlite3.Connection,
    task_id: str,
) -> tuple[str, ...]:
    try:
        rows = conn.execute(
            """select depends_on
                 from task_dependencies
                where task_id=?
                  and kind='integration_carrier'
                order by depends_on""",
            (task_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        return ()
    return tuple(
        str(row[0])
        for row in rows
        if str(row[0] or "").strip()
    )


def _evaluate_task_state(
    conn: sqlite3.Connection,
    criterion: dict[str, Any],
    *,
    integration_sha: str,
    root: Path,
    ancestor_checker: Callable[[str, str], bool] | None = None,
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
    result_status, passed, reason = result
    if passed and bool(check.get("integration_required", False)):
        checker = ancestor_checker or _git_ancestor_checker(root)
        proof_task_ids = [
            task_id,
            *_integration_carrier_task_ids(
                conn,
                task_id,
            ),
        ]
        integrated_via = next(
            (
                proof_task_id
                for proof_task_id in proof_task_ids
                if integration_prerequisite_satisfied(
                    conn,
                    proof_task_id,
                    integration_head=integration_sha,
                    ancestor_checker=checker,
                )
            ),
            None,
        )
        if integrated_via is None:
            return (
                "BLOCKED_DEP",
                False,
                f"task status={status} but canonical integration ancestry is not satisfied",
                task_id,
            )
        return (
            "PASS",
            True,
            (
                f"task status={status} and canonical integration ancestry "
                f"is satisfied via {integrated_via}"
            ),
            task_id,
        )
    return result_status, passed, reason, task_id


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


def _table_exists(
    conn: sqlite3.Connection,
    name: str,
) -> bool:
    return (
        conn.execute(
            "select 1 from sqlite_master where type='table' and name=?",
            (name,),
        ).fetchone()
        is not None
    )


def resolve_device_proof(
    conn: sqlite3.Connection,
    check: dict[str, Any],
    *,
    integration_sha: str,
    root: Path,
) -> tuple[dict[str, Any] | None, str]:
    checkpoint = str(check.get("checkpoint") or "").strip()
    wanted_status = str(check.get("status") or "PASS").strip()

    if not checkpoint:
        return None, "device proof checkpoint is missing"
    if not _table_exists(conn, "device_proofs"):
        return None, "device_proofs table does not exist"

    row = conn.execute(
        """select id,sha,apk_sha256,checkpoint,status,artifact_path,
                  note,created_at,created_epoch
             from device_proofs
            where sha=? and checkpoint=?
            order by created_epoch desc,id desc
            limit 1""",
        (integration_sha, checkpoint),
    ).fetchone()

    if row is None:
        return (
            None,
            "no device proof exists for exact current integration SHA "
            f"{integration_sha} checkpoint={checkpoint}",
        )

    status = str(row[4] or "")
    if status != wanted_status:
        return (
            None,
            f"current-SHA device proof status={status or 'MISSING'}; "
            f"required {wanted_status}",
        )

    raw_artifact = str(row[5] or "").strip()
    if not raw_artifact:
        return None, "current-SHA device proof has no artifact_path"

    raw_path = Path(raw_artifact)
    artifact_path = raw_path if raw_path.is_absolute() else root / raw_path
    if not artifact_path.is_file():
        return None, f"device proof artifact missing: {artifact_path}"

    try:
        payload = json.loads(artifact_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"device proof artifact is unreadable JSON: {exc}"
    if not isinstance(payload, dict):
        return None, "device proof artifact must be a JSON object"

    embedded_sha = str(
        payload.get("canonical_sha")
        or payload.get("git_sha")
        or ""
    ).strip()
    if not embedded_sha:
        return None, "device proof artifact does not declare canonical_sha/git_sha"
    if embedded_sha != integration_sha:
        return (
            None,
            "device proof artifact SHA mismatch: "
            f"artifact={embedded_sha} current={integration_sha}",
        )

    artifact_checkpoint = str(payload.get("checkpoint") or "").strip()
    if artifact_checkpoint and artifact_checkpoint != checkpoint:
        return (
            None,
            "device proof artifact checkpoint mismatch: "
            f"artifact={artifact_checkpoint} required={checkpoint}",
        )

    row_apk_sha = str(row[2] or "").strip() or None
    artifact_apk_sha = None
    raw_apk = payload.get("apk")
    if isinstance(raw_apk, dict):
        artifact_apk_sha = str(raw_apk.get("sha256") or "").strip() or None
    if artifact_apk_sha is None:
        artifact_apk_sha = str(payload.get("apk_sha256") or "").strip() or None

    if (
        row_apk_sha is not None
        and artifact_apk_sha is not None
        and row_apk_sha != artifact_apk_sha
    ):
        return (
            None,
            "device proof APK SHA mismatch between DB row and artifact",
        )

    artifact_sha256 = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    evidence = {
        "id": int(row[0]),
        "sha": str(row[1]),
        "apk_sha256": row_apk_sha,
        "checkpoint": str(row[3]),
        "status": status,
        "artifact_path": str(artifact_path),
        "artifact_sha256": artifact_sha256,
        "artifact_embedded_sha": embedded_sha,
        "artifact_checkpoint": artifact_checkpoint or None,
        "artifact_apk_sha256": artifact_apk_sha,
        "note": str(row[6] or ""),
        "created_at": str(row[7] or ""),
        "created_epoch": float(row[8]),
    }
    return evidence, (
        f"device proof id={evidence['id']} status={status} "
        f"sha={integration_sha} checkpoint={checkpoint} "
        f"artifact_sha256={artifact_sha256}"
    )


def _evaluate_device_proof(
    conn: sqlite3.Connection,
    criterion: dict[str, Any],
    *,
    integration_sha: str,
    root: Path,
) -> tuple[str, bool, str, str | None]:
    evidence, reason = resolve_device_proof(
        conn,
        criterion["check"],
        integration_sha=integration_sha,
        root=root,
    )
    if evidence is None:
        return "BLOCKED_EXTERNAL", False, reason, None
    return "PASS", True, reason, None


def evaluate_criterion(
    conn: sqlite3.Connection,
    criterion: dict[str, Any],
    *,
    integration_sha: str,
    root: Path,
    ancestor_checker: Callable[[str, str], bool] | None = None,
) -> CriterionResult:
    check_type = str(criterion["check"]["type"])
    if check_type == "task_state":
        result = _evaluate_task_state(
            conn,
            criterion,
            integration_sha=integration_sha,
            root=root,
            ancestor_checker=ancestor_checker,
        )
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
    elif check_type == "device_proof":
        result = _evaluate_device_proof(
            conn,
            criterion,
            integration_sha=integration_sha,
            root=root,
        )
    else:
        raise ValueError(f"unsupported criterion check: {check_type}")

    status, passed, reason, task_id = result
    terminal_waiting_for_integration = (
        check_type == "task_state"
        and bool(criterion["check"].get("integration_required", False))
        and _task_status(conn, str(criterion["check"]["task_id"]))
        in set(criterion["check"].get("pass_statuses") or PASS_TASK_STATES)
        and not passed
    )
    if (
        not passed
        and status in {"BLOCKED_DEP", "BLOCKED_EVIDENCE"}
        and criterion.get("task_template")
        and not terminal_waiting_for_integration
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
    ancestor_checker: Callable[[str, str], bool] | None = None,
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
            ancestor_checker=ancestor_checker,
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
