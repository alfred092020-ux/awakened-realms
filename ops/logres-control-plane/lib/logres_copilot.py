from __future__ import annotations

import json
import re
import subprocess
import tempfile
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
