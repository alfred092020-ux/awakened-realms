from __future__ import annotations

import os
import sqlite3
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping


TERMINAL_TASK_STATES = {
    "DONE",
    "RESOLVED",
    "SUPERSEDED",
    "CANCELLED",
    "BLOCKED_EVIDENCE",
}
INTEGRATED_QUEUE_STATES = {"INTEGRATED", "SUPERSEDED"}
PROTECTED_BRANCHES = {"main", "feat/logres-reconstruction"}
POLICY = "REMOVE_WORKTREE_ONLY_BRANCH_AND_COMMIT_PRESERVED"


@dataclass(frozen=True)
class Eligibility:
    eligible: bool
    reason: str


def _inside(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath(
            [str(path.resolve()), str(root.resolve())]
        ) == str(root.resolve())
    except (OSError, ValueError):
        return False


def eligibility(
    record: Mapping[str, object],
    *,
    work_root: Path,
) -> Eligibility:
    path_raw = record.get("path")
    branch = str(record.get("branch") or "")
    status = str(record.get("task_status") or "")

    if not path_raw:
        return Eligibility(False, "MISSING_PATH")
    path = Path(str(path_raw))

    if not _inside(path, work_root):
        return Eligibility(False, "OUTSIDE_MANAGED_WORK_ROOT")
    if path.resolve() == work_root.resolve():
        return Eligibility(False, "WORK_ROOT_ITSELF")
    if bool(record.get("protected")) or branch in PROTECTED_BRANCHES:
        return Eligibility(False, "PROTECTED")
    if not branch:
        return Eligibility(False, "DETACHED_OR_BRANCHLESS")
    if bool(record.get("active_lease")) or status == "ACTIVE":
        return Eligibility(False, "ACTIVE")
    if bool(record.get("dirty")):
        return Eligibility(False, "DIRTY")
    if status not in TERMINAL_TASK_STATES:
        return Eligibility(False, "TASK_NOT_TERMINAL")
    if not bool(record.get("integrated")):
        return Eligibility(False, "NOT_INTEGRATED")
    return Eligibility(True, "ARCHIVE_CANDIDATE")


def plan_records(
    records: Iterable[Mapping[str, object]],
    *,
    work_root: Path,
    limit: int = 25,
) -> dict:
    bounded = max(1, min(100, int(limit)))
    eligible_rows = []
    skipped = []
    for record in records:
        check = eligibility(record, work_root=work_root)
        item = dict(record)
        item["eligibility"] = asdict(check)
        if check.eligible:
            eligible_rows.append(item)
        else:
            skipped.append(item)

    eligible_rows.sort(
        key=lambda row: (
            str(row.get("task_id") or ""),
            str(row.get("branch") or ""),
            str(row.get("path") or ""),
        )
    )
    selected = eligible_rows[:bounded]
    return {
        "policy": POLICY,
        "limit": bounded,
        "selected": selected,
        "eligible_total": len(eligible_rows),
        "skipped_total": len(skipped),
        "skipped": skipped,
    }


def db_revalidate(
    conn: sqlite3.Connection,
    record: Mapping[str, object],
) -> Eligibility:
    task_id = str(record.get("task_id") or "")
    if not task_id:
        return Eligibility(False, "MISSING_TASK")

    task = conn.execute(
        "select status from tasks where id=?",
        (task_id,),
    ).fetchone()
    if task is None:
        return Eligibility(False, "TASK_MISSING")
    status = str(task[0] or "")
    if status not in TERMINAL_TASK_STATES:
        return Eligibility(False, f"TASK_STATE_{status or 'UNKNOWN'}")

    lease = conn.execute(
        "select 1 from brain_task_leases where task_id=? limit 1",
        (task_id,),
    ).fetchone()
    if lease:
        return Eligibility(False, "LEASE_APPEARED")

    integrated = conn.execute(
        """
        select 1 from integration_queue
        where task_id=? and status in ('INTEGRATED','SUPERSEDED')
        limit 1
        """,
        (task_id,),
    ).fetchone()
    if not integrated:
        return Eligibility(False, "INTEGRATION_PROOF_MISSING")
    return Eligibility(True, "DB_REVALIDATED")


def _run(
    argv: list[str],
    *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> subprocess.CompletedProcess:
    return runner(
        argv,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _branch_sha(
    repo: Path,
    branch: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> str | None:
    result = _run(
        [
            "git",
            "-C",
            str(repo),
            "rev-parse",
            "--verify",
            f"refs/heads/{branch}",
        ],
        runner=runner,
    )
    if result.returncode:
        return None
    value = (result.stdout or "").strip()
    return value if len(value) == 40 else None


def _registered_worktree(
    repo: Path,
    path: Path,
    branch: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> bool:
    result = _run(
        ["git", "-C", str(repo), "worktree", "list", "--porcelain"],
        runner=runner,
    )
    if result.returncode:
        return False
    current_path = None
    current_branch = None
    records = []
    for line in (result.stdout or "").splitlines() + [""]:
        if not line:
            if current_path:
                records.append((current_path, current_branch))
            current_path = None
            current_branch = None
        elif line.startswith("worktree "):
            current_path = line.split(" ", 1)[1]
        elif line.startswith("branch refs/heads/"):
            current_branch = line[len("branch refs/heads/") :]
    target = str(path.resolve())
    return any(
        str(Path(item_path).resolve()) == target and item_branch == branch
        for item_path, item_branch in records
    )


def live_revalidate(
    repo: Path,
    record: Mapping[str, object],
    *,
    work_root: Path,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> tuple[Eligibility, str | None]:
    check = eligibility(record, work_root=work_root)
    if not check.eligible:
        return check, None

    path = Path(str(record["path"]))
    branch = str(record["branch"])

    if not path.is_dir():
        return Eligibility(False, "WORKTREE_PATH_MISSING"), None
    if path.is_symlink():
        return Eligibility(False, "SYMLINK_WORKTREE_REJECTED"), None
    if not _registered_worktree(repo, path, branch, runner=runner):
        return Eligibility(False, "WORKTREE_REGISTRATION_CHANGED"), None

    status = _run(
        ["git", "-C", str(path), "status", "--porcelain"],
        runner=runner,
    )
    if status.returncode:
        return Eligibility(False, "STATUS_PROBE_FAILED"), None
    if (status.stdout or "").strip():
        return Eligibility(False, "DIRTY_AT_APPLY"), None

    branch_sha = _branch_sha(repo, branch, runner=runner)
    if not branch_sha:
        return Eligibility(False, "LOCAL_BRANCH_REF_MISSING"), None
    return Eligibility(True, "LIVE_REVALIDATED"), branch_sha


def remove_one(
    conn: sqlite3.Connection,
    repo: Path,
    record: Mapping[str, object],
    *,
    work_root: Path,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict:
    db_check = db_revalidate(conn, record)
    if not db_check.eligible:
        return {
            "removed": False,
            "reason": db_check.reason,
            "path": record.get("path"),
            "branch": record.get("branch"),
            "task_id": record.get("task_id"),
        }

    live_check, branch_sha = live_revalidate(
        repo,
        record,
        work_root=work_root,
        runner=runner,
    )
    if not live_check.eligible:
        return {
            "removed": False,
            "reason": live_check.reason,
            "path": record.get("path"),
            "branch": record.get("branch"),
            "task_id": record.get("task_id"),
        }

    path = Path(str(record["path"]))
    branch = str(record["branch"])
    result = _run(
        ["git", "-C", str(repo), "worktree", "remove", str(path)],
        runner=runner,
    )
    if result.returncode:
        return {
            "removed": False,
            "reason": "GIT_WORKTREE_REMOVE_FAILED",
            "detail": (result.stderr or result.stdout or "")[-1000:],
            "path": str(path),
            "branch": branch,
            "task_id": record.get("task_id"),
            "preserved_sha": branch_sha,
        }

    after_sha = _branch_sha(repo, branch, runner=runner)
    preserved = after_sha == branch_sha and after_sha is not None
    return {
        "removed": True,
        "reason": "REMOVED_WORKTREE_ONLY",
        "path": str(path),
        "branch": branch,
        "task_id": record.get("task_id"),
        "preserved_sha": branch_sha,
        "branch_preserved": preserved,
        "after_sha": after_sha,
    }


def apply_plan(
    conn: sqlite3.Connection,
    repo: Path,
    records: Iterable[Mapping[str, object]],
    *,
    work_root: Path,
    limit: int = 25,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict:
    plan = plan_records(records, work_root=work_root, limit=limit)
    results = []
    for record in plan["selected"]:
        results.append(
            remove_one(
                conn,
                repo,
                record,
                work_root=work_root,
                runner=runner,
            )
        )

    _run(
        ["git", "-C", str(repo), "worktree", "prune"],
        runner=runner,
    )

    removed = [row for row in results if row.get("removed")]
    failed = [row for row in results if not row.get("removed")]
    preserved_failures = [
        row
        for row in removed
        if not row.get("branch_preserved")
    ]
    return {
        "policy": POLICY,
        "requested_limit": plan["limit"],
        "eligible_total": plan["eligible_total"],
        "attempted": len(results),
        "removed": len(removed),
        "failed_or_skipped": len(failed),
        "branch_preservation_failures": len(preserved_failures),
        "results": results,
        "safety": {
            "force_remove": False,
            "delete_local_branch": False,
            "delete_remote_branch": False,
            "delete_commit": False,
            "requires_terminal_task": True,
            "requires_integration_proof": True,
            "requires_no_lease": True,
            "requires_clean_worktree": True,
            "managed_root_only": str(work_root),
        },
    }
