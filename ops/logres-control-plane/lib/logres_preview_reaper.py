from __future__ import annotations

import os
import re
import signal
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


VITE_PREVIEW_RE = re.compile(
    r"(?:^|\s)node\s+(?P<root>/[^\s]+?)/node_modules/\.bin/vite\s+preview(?:\s|$)"
)


@dataclass(frozen=True)
class PreviewProcess:
    pid: int
    age_seconds: float
    rss_bytes: int
    command: str
    worktree_path: str


@dataclass(frozen=True)
class WorktreeState:
    path: str
    branch: str
    dirty_count: int
    merged_into_integration: bool


@dataclass(frozen=True)
class ReaperDecision:
    eligible: bool
    reason: str


def preview_worktree_from_command(command: str) -> str | None:
    match = VITE_PREVIEW_RE.search(command)
    return match.group("root") if match else None


def decide_preview(
    process: PreviewProcess,
    worktree: WorktreeState | None,
    active_branches: set[str],
    *,
    min_age_seconds: float,
) -> ReaperDecision:
    if worktree is None:
        return ReaperDecision(False, "unknown-worktree")
    if process.worktree_path != worktree.path:
        return ReaperDecision(False, "path-mismatch")
    if process.age_seconds < min_age_seconds:
        return ReaperDecision(False, "young")
    if worktree.dirty_count != 0:
        return ReaperDecision(False, "dirty")
    if not worktree.merged_into_integration:
        return ReaperDecision(False, "unmerged")
    if worktree.branch in active_branches:
        return ReaperDecision(False, "active")
    return ReaperDecision(True, "eligible")


def active_branches(conn: sqlite3.Connection, now_epoch: float) -> set[str]:
    branches = {
        str(row[0])
        for row in conn.execute(
            "select branch from brain_task_leases "
            "where branch is not null and lease_until_epoch>?",
            (now_epoch,),
        )
        if row[0]
    }
    branches |= {
        str(row[0])
        for row in conn.execute(
            "select distinct branch from claims where branch is not null"
        )
        if row[0]
    }
    return branches


def load_worktrees(conn: sqlite3.Connection) -> dict[str, WorktreeState]:
    rows = conn.execute(
        "select path,branch,dirty_count,merged_into_integration from worktrees"
    )
    return {
        str(row[0]): WorktreeState(
            path=str(row[0]),
            branch=str(row[1] or ""),
            dirty_count=int(row[2] or 0),
            merged_into_integration=bool(row[3]),
        )
        for row in rows
    }


def _read_cmdline(proc_dir: Path) -> str:
    return (
        (proc_dir / "cmdline")
        .read_bytes()
        .replace(b"\0", b" ")
        .decode(errors="replace")
        .strip()
    )


def _process_age_seconds(proc_dir: Path, uptime: float, ticks: int) -> float:
    fields = (proc_dir / "stat").read_text().split()
    start_ticks = int(fields[21])
    return max(0.0, uptime - (start_ticks / ticks))


def _process_rss_bytes(proc_dir: Path, page_size: int) -> int:
    fields = (proc_dir / "stat").read_text().split()
    return max(0, int(fields[23])) * page_size


def discover_previews(
    proc_root: Path = Path("/proc"),
) -> list[PreviewProcess]:
    uptime = float((proc_root / "uptime").read_text().split()[0])
    ticks = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
    page_size = os.sysconf("SC_PAGE_SIZE")
    found: list[PreviewProcess] = []
    for proc_dir in proc_root.iterdir():
        if not proc_dir.name.isdigit():
            continue
        try:
            command = _read_cmdline(proc_dir)
            worktree = preview_worktree_from_command(command)
            if not worktree:
                continue
            found.append(
                PreviewProcess(
                    pid=int(proc_dir.name),
                    age_seconds=_process_age_seconds(proc_dir, uptime, ticks),
                    rss_bytes=_process_rss_bytes(proc_dir, page_size),
                    command=command,
                    worktree_path=worktree,
                )
            )
        except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError):
            continue
    return found


def scan(
    conn: sqlite3.Connection,
    *,
    min_age_seconds: float,
    proc_root: Path = Path("/proc"),
    now_epoch: float | None = None,
) -> list[tuple[PreviewProcess, WorktreeState | None, ReaperDecision]]:
    now_epoch = time.time() if now_epoch is None else now_epoch
    active = active_branches(conn, now_epoch)
    worktrees = load_worktrees(conn)
    return [
        (
            process,
            worktrees.get(process.worktree_path),
            decide_preview(
                process,
                worktrees.get(process.worktree_path),
                active,
                min_age_seconds=min_age_seconds,
            ),
        )
        for process in discover_previews(proc_root)
    ]


def git_worktree_safe(
    worktree_path: str,
    integration_repo: Path,
    *,
    runner=subprocess.run,
) -> bool:
    status = runner(
        ["git", "-C", worktree_path, "status", "--porcelain"],
        text=True,
        capture_output=True,
        check=False,
    )
    if status.returncode != 0 or status.stdout.strip():
        return False
    head = runner(
        ["git", "-C", worktree_path, "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    if head.returncode != 0:
        return False
    ancestor = runner(
        [
            "git",
            "-C",
            str(integration_repo),
            "merge-base",
            "--is-ancestor",
            head.stdout.strip(),
            "feat/logres-reconstruction",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    return ancestor.returncode == 0


def current_candidate_safe(
    process: PreviewProcess,
    db_path: Path,
    integration_repo: Path,
    *,
    min_age_seconds: float,
    now_epoch: float | None = None,
) -> bool:
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma busy_timeout=30000")
    try:
        now_epoch = time.time() if now_epoch is None else now_epoch
        row = conn.execute(
            "select path,branch,dirty_count,merged_into_integration "
            "from worktrees where path=?",
            (process.worktree_path,),
        ).fetchone()
        state = None
        if row is not None:
            state = WorktreeState(
                path=str(row["path"]),
                branch=str(row["branch"] or ""),
                dirty_count=int(row["dirty_count"] or 0),
                merged_into_integration=bool(row["merged_into_integration"]),
            )
        decision = decide_preview(
            process,
            state,
            active_branches(conn, now_epoch),
            min_age_seconds=min_age_seconds,
        )
    finally:
        conn.close()
    return decision.eligible and git_worktree_safe(
        process.worktree_path,
        integration_repo,
    )


def process_still_matches(
    process: PreviewProcess,
    proc_root: Path = Path("/proc"),
) -> bool:
    proc_dir = proc_root / str(process.pid)
    try:
        command = _read_cmdline(proc_dir)
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return False
    return (
        command == process.command
        and preview_worktree_from_command(command) == process.worktree_path
    )


def reap(
    candidates: list[PreviewProcess],
    *,
    proc_root: Path = Path("/proc"),
    term_wait_seconds: float = 1.0,
    eligible_fn: Callable[[PreviewProcess], bool] | None = None,
    kill_fn=os.kill,
    sleep_fn=time.sleep,
) -> dict:
    term_sent: list[PreviewProcess] = []
    for process in candidates:
        if eligible_fn is not None and not eligible_fn(process):
            continue
        if not process_still_matches(process, proc_root):
            continue
        try:
            kill_fn(process.pid, signal.SIGTERM)
            term_sent.append(process)
        except ProcessLookupError:
            continue

    if term_sent and term_wait_seconds > 0:
        sleep_fn(term_wait_seconds)

    killed = 0
    survived = 0
    for process in term_sent:
        if eligible_fn is not None and not eligible_fn(process):
            continue
        if not process_still_matches(process, proc_root):
            continue
        survived += 1
        try:
            kill_fn(process.pid, signal.SIGKILL)
            killed += 1
        except ProcessLookupError:
            pass

    return {
        "eligible": len(candidates),
        "term_sent": len(term_sent),
        "survived_term": survived,
        "kill_sent": killed,
        "rss_bytes": sum(process.rss_bytes for process in candidates),
    }
