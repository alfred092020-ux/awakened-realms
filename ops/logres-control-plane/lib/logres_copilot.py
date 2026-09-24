from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


INTEGRATION_BRANCH = "feat/logres-reconstruction"
DEFAULT_REPO = "alfred092020-ux/awakened-realms"


class PolicyError(RuntimeError):
    pass


@dataclass(frozen=True)
class CopilotPacket:
    task_id: str
    title: str
    base_sha: str
    evidence_summary: str
    allowed_files: tuple[str, ...]
    forbidden_files: tuple[str, ...]
    acceptance: tuple[str, ...]
    tests: tuple[str, ...]


@dataclass(frozen=True)
class AssignmentResult:
    issue_number: int
    payload: dict


@dataclass(frozen=True)
class CopilotJobRecord:
    id: int
    route_job_id: int
    task_id: str
    issue_number: int | None
    pr_number: int | None
    branch: str | None
    base_sha: str
    candidate_sha: str | None
    state: str
    last_error: str | None


def _instructions(packet: CopilotPacket) -> str:
    allowed = "\n".join(f"- {x}" for x in packet.allowed_files) or "- none"
    forbidden = "\n".join(f"- {x}" for x in packet.forbidden_files) or "- none"
    tests = "\n".join(f"- {x}" for x in packet.tests) or "- none"
    return (
        "Never modify main. Work only from feat/logres-reconstruction on an isolated "
        "copilot/* branch. Do not commit directly to feat/logres-reconstruction. "
        "Do not self-merge. Open a draft PR targeting feat/logres-reconstruction. "
        "If historical behavior is unresolved, stop and report BLOCKED_EVIDENCE.\n\n"
        f"Task: {packet.task_id}\nBase SHA: {packet.base_sha}\n"
        f"Allowed files/scopes:\n{allowed}\nForbidden files/scopes:\n{forbidden}\n"
        f"Required tests:\n{tests}"
    )
def build_issue_body(packet: CopilotPacket) -> str:
    allowed = "\n".join(f"- {x}" for x in packet.allowed_files) or "- none"
    forbidden = "\n".join(f"- {x}" for x in packet.forbidden_files) or "- none"
    acceptance = "\n".join(f"- {x}" for x in packet.acceptance) or "- none"
    tests = "\n".join(f"- {x}" for x in packet.tests) or "- none"
    return f"""Task ID: {packet.task_id}
Base integration SHA: {packet.base_sha}

Evidence:
{packet.evidence_summary}

Allowed files/scopes:
{allowed}

Forbidden files/scopes:
{forbidden}

Acceptance criteria:
{acceptance}

Required tests:
{tests}

Definition of DONE:
- Acceptance criteria satisfied.
- Required tests pass.
- No forbidden files touched.
- Open a draft PR against feat/logres-reconstruction.
- Do not merge the PR.
- If historical behavior is unresolved, stop and report BLOCKED_EVIDENCE.
"""


def build_assignment(packet: CopilotPacket, base_branch: str) -> dict:
    if base_branch != INTEGRATION_BRANCH:
        raise PolicyError(
            f"Copilot base branch must be {INTEGRATION_BRANCH}, got {base_branch}"
        )
    return {
        "assignees": ["copilot-swe-agent[bot]"],
        "agent_assignment": {
            "target_repo": DEFAULT_REPO,
            "base_branch": INTEGRATION_BRANCH,
            "custom_instructions": _instructions(packet),
        },
    }
def assign_copilot(
    repo: str,
    issue_number: int,
    base_branch: str,
    instructions: str,
    gh_runner,
) -> AssignmentResult:
    if base_branch != INTEGRATION_BRANCH:
        raise PolicyError(
            f"Copilot base branch must be {INTEGRATION_BRANCH}, got {base_branch}"
        )
    payload = {
        "assignees": ["copilot-swe-agent[bot]"],
        "agent_assignment": {
            "target_repo": repo,
            "base_branch": INTEGRATION_BRANCH,
            "custom_instructions": instructions,
        },
    }
    gh_runner.assign_copilot(repo, issue_number, payload)
    return AssignmentResult(issue_number=issue_number, payload=payload)


class SubprocessGitHubRunner:
    def create_issue(self, repo: str, title: str, body: str) -> int:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write(body)
            body_path = Path(handle.name)
        try:
            result = subprocess.run(
                [
                    "gh", "issue", "create",
                    "--repo", repo,
                    "--title", title,
                    "--body-file", str(body_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            body_path.unlink(missing_ok=True)

        output = result.stdout.strip()
        match = re.search(r"/issues/(\d+)(?:\s*)$", output)
        if not match:
            raise RuntimeError(f"could not parse issue number from gh output: {output!r}")
        return int(match.group(1))
    def list_prs(self, repo: str) -> list[dict]:
        result = subprocess.run(
            [
                "gh", "pr", "list",
                "--repo", repo,
                "--state", "open",
                "--json", "number,headRefName,headRefOid,baseRefName,isDraft,body,changedFiles",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout or "[]")

    def search_issue(self, task_id: str, repo: str = DEFAULT_REPO) -> dict | None:
        result = subprocess.run(
            [
                "gh", "issue", "list",
                "--repo", repo,
                "--state", "open",
                "--search", f"{task_id} in:title",
                "--limit", "20",
                "--json", "number,title,body,state",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        rows = json.loads(result.stdout or "[]")
        title_token = f"[Copilot] {task_id}:"
        body_token = f"Task ID: {task_id}"
        matches = [
            row
            for row in rows
            if title_token in str(row.get("title") or "")
            or body_token in str(row.get("body") or "")
        ]
        return matches[0] if len(matches) == 1 else None

    def assign_copilot(self, repo: str, issue_number: int, payload: dict) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            json.dump(payload, handle)
            payload_path = Path(handle.name)
        try:
            subprocess.run(
                [
                    "gh", "api",
                    "--method", "POST",
                    "-H", "Accept: application/vnd.github+json",
                    "-H", "X-GitHub-Api-Version: 2022-11-28",
                    f"/repos/{repo}/issues/{issue_number}/assignees",
                    "--input", str(payload_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            payload_path.unlink(missing_ok=True)


class SubprocessCommandRunner:
    repo_root = "/home/ubuntu/logres/src/awakened-realms"
    bin_root = "/home/ubuntu/logres/bin"

    @staticmethod
    def _run(argv: list[str], **kwargs):
        return subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            **kwargs,
        )

    def prepare_ref(self, branch: str) -> str:
        if not branch.startswith("copilot/"):
            raise PolicyError(f"refusing non-Copilot branch: {branch!r}")
        remote_ref = f"origin/{branch}"
        fetch_lock = open("/tmp/logres-git-fetch.lock", "a+")
        try:
            fcntl.flock(fetch_lock.fileno(), fcntl.LOCK_EX)
            result = self._run([
                "git",
                "-C",
                self.repo_root,
                "fetch",
                "origin",
                f"+refs/heads/{branch}:refs/remotes/origin/{branch}",
            ])
        finally:
            fcntl.flock(fetch_lock.fileno(), fcntl.LOCK_UN)
            fetch_lock.close()
        if result.returncode != 0:
            raise RuntimeError(
                f"failed to fetch Copilot branch {branch}: {result.stderr.strip()}"
            )
        # Integration safety compares both the logical local branch and the
        # authoritative origin/<branch> ref to the immutable queued SHA.
        # Copilot branches originate remotely, so materialize/update a local
        # mirror at the fetched remote SHA before verification/queueing.
        mirror = self._run([
            "git", "-C", self.repo_root,
            "update-ref", f"refs/heads/{branch}", f"refs/remotes/origin/{branch}",
        ])
        if mirror.returncode != 0:
            raise RuntimeError(
                f"failed to materialize local Copilot ref {branch}: {mirror.stderr.strip()}"
            )
        return remote_ref

    def resolve_sha(self, ref: str) -> str:
        result = self._run([
            "git",
            "-C",
            self.repo_root,
            "rev-parse",
            ref,
        ])
        if result.returncode != 0:
            raise RuntimeError(
                f"failed to resolve Copilot ref {ref}: {result.stderr.strip()}"
            )
        sha = result.stdout.strip().lower()
        if re.fullmatch(r"[0-9a-f]{40}", sha) is None:
            raise RuntimeError(f"invalid SHA resolved for {ref}: {sha!r}")
        return sha

    def scope_check(self, task_id: str, branch: str) -> int:
        return int(
            self._run([
                f"{self.bin_root}/logres-scope-check",
                task_id,
                branch,
            ]).returncode
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @contextmanager
    def verification_worktree(self, ref: str):
        repo = Path(self.repo_root)
        temp_root = Path("/home/ubuntu/logres/tmp")
        temp_root.mkdir(parents=True, exist_ok=True)
        worktree = Path(tempfile.mkdtemp(prefix="copilot-fast.", dir=temp_root))
        worktree.rmdir()

        added = self._run([
            "git", "-C", str(repo),
            "worktree", "add", "--detach", str(worktree), ref,
        ])
        if added.returncode != 0:
            raise RuntimeError(
                f"failed to create verification worktree for {ref}: {added.stderr.strip()}"
            )

        try:
            base_lock = repo / "package-lock.json"
            ref_lock = worktree / "package-lock.json"
            base_modules = repo / "node_modules"
            target_modules = worktree / "node_modules"
            if (
                base_lock.is_file()
                and ref_lock.is_file()
                and self._sha256(base_lock) == self._sha256(ref_lock)
                and base_modules.is_dir()
            ):
                os.symlink(base_modules, target_modules, target_is_directory=True)
            else:
                install = self._run(
                    ["npm", "ci", "--prefer-offline", "--no-audit", "--no-fund"],
                    cwd=worktree,
                )
                if install.returncode != 0:
                    raise RuntimeError(
                        f"npm ci failed in verification worktree: {install.stderr.strip()}"
                    )
            yield worktree
        finally:
            self._run([
                "git", "-C", str(repo),
                "worktree", "remove", "--force", str(worktree),
            ])

    def fast_gate(self, branch: str) -> int:
        with self.verification_worktree(branch) as worktree:
            return int(
                self._run(
                    [
                        f"{self.bin_root}/logres-gate",
                        "fast",
                        branch,
                    ],
                    cwd=worktree,
                ).returncode
            )

    def coordinator_reconcile(
        self,
        conn,
        task_id: str,
        branch: str,
        sha: str,
    ) -> int:
        del conn, task_id, branch, sha
        return int(
            self._run([
                f"{self.bin_root}/logres-coordinator",
                "reconcile",
            ]).returncode
        )

    def capture_regression(self, task_id: str, branch: str, sha: str) -> None:
        self._run([
            f"{self.bin_root}/logres-regression-capture",
            "--kind",
            "copilot-fast-gate",
            "--ref",
            branch,
            "--sha",
            sha,
            "--summary",
            f"Copilot candidate fast gate failed for {task_id}",
        ])

    def post_scope_conflict(self, task_id: str, branch: str, sha: str) -> None:
        self._run([
            f"{self.bin_root}/logres-brain",
            "post",
            "copilot",
            "ALL",
            "CONFLICT",
            "HIGH",
            f"Copilot scope violation: {task_id}",
            "--body",
            f"branch={branch} sha={sha}; candidate failed existing scope policy.",
            "--task",
            task_id,
            "--dedupe",
            f"copilot-scope:{task_id}:{sha}",
        ])
