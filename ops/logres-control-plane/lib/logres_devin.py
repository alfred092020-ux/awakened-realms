from __future__ import annotations

import json
import os
import re
import shlex
import signal
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from logres_patch_agent import (
    PatchAgentError,
    git_changed_paths,
    validate_paths,
)


class DevinAgentError(RuntimeError):
    pass


class LeaseLostError(DevinAgentError):
    """The Brain authoritatively reports this worker no longer owns the lease."""


PROTECTED_BRANCHES = frozenset({"main", "feat/logres-reconstruction"})
DEFAULT_MODEL = "swe-2-max"
FREE_COST_TIER = "free"
DEFAULT_PERMISSION_MODE = "smart"
PERMISSION_MODES = frozenset(
    {
        "normal",
        "auto",
        "accept-edits",
        "smart",
        "dangerous",
        "yolo",
        "bypass",
        "autonomous",
    }
)
EXECUTION_MODES = frozenset({"interactive", "unattended"})
DEFAULT_EXECUTION_MODE = "interactive"
DEVIN_NATIVE_SANDBOX = "devin-native-sandbox"
ISOLATION_ENV_VAR = "LOGRES_DEVIN_EXECUTION_ISOLATION"
ATTEMPT_REF_PREFIX = "refs/logres/attempts"
DEFAULT_RENEW_SECONDS = 300
DEFAULT_LEASE_MINUTES = 120
DEFAULT_LEASE_TTL_SECONDS = DEFAULT_LEASE_MINUTES * 60
DEFAULT_LEASE_MARGIN_SECONDS = 30
DEFAULT_TERM_GRACE_SECONDS = 15
LEASE_OK = "ok"
LEASE_LOST = "lost"
LEASE_DEADLINE = "deadline"
REDACTED = "[REDACTED]"

_KEY_VALUE_RE = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|auth(?:orization)?|client[_-]?secret"
    r"|password|secret|token)['\"]?(\s*[=:]\s*)(['\"]?)([^\s'\",}\])]{8,})"
)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")
_JWT_RE = re.compile(r"\beyJ[\w-]{6,}\.[\w-]{6,}\.[\w-]{6,}\b")
_PREFIXED_RE = re.compile(
    r"\b(?:sk|pk|pat|gh[pousr]|github_pat|xox[baprs]?|eyJ)[-_][\w.-]{8,}\b"
)
_LONG_TOKEN_RE = re.compile(r"\b[\w.~+=-]{32,}\b")
_GIT_SHA_RE = re.compile(r"[0-9a-f]{40}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_FILENAME_RE = re.compile(
    r"\.(?:cfg|conf|csv|ini|js|json|log|md|mjs|py|sh|sql|toml|ts|tsx|txt|xml|yaml|yml)$"
)
_LEASE_LOST_RE = re.compile(
    r"(?i)not lease owner|does not own|TASK_BUSY|unknown chat"
)
_ISOLATION_MARKER_RE = re.compile(r"[A-Za-z0-9._:+@/-]{1,128}")


def _redact_long(match: re.Match) -> str:
    token = match.group(0)
    if _GIT_SHA_RE.fullmatch(token) or _SHA256_RE.fullmatch(token):
        return token
    if not (re.search(r"[0-9]", token) and re.search(r"[A-Za-z]", token)):
        return token
    if _FILENAME_RE.search(token):
        return token
    return REDACTED


def redact(text: str) -> str:
    out = str(text or "")
    out = _KEY_VALUE_RE.sub(
        lambda m: m.group(1) + m.group(2) + m.group(3) + REDACTED, out
    )
    out = _BEARER_RE.sub(lambda m: "Bearer " + REDACTED, out)
    out = _JWT_RE.sub(REDACTED, out)
    out = _PREFIXED_RE.sub(REDACTED, out)
    out = _LONG_TOKEN_RE.sub(_redact_long, out)
    return out


def redact_file(src: Path, dst: Path) -> None:
    text = Path(src).read_text(encoding="utf-8", errors="replace")
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(redact(text), encoding="utf-8")


def ensure_worker_branch(branch: str) -> str:
    value = str(branch or "").strip()
    if not value:
        raise DevinAgentError("empty worker branch")
    if value.startswith("refs/heads/"):
        value = value[len("refs/heads/"):]
    if value.startswith("refs/"):
        raise DevinAgentError("refusing non-branch ref: " + value)
    if value in PROTECTED_BRANCHES:
        raise DevinAgentError("refusing protected branch: " + value)
    return value


def ensure_isolated_worktree(worktree: Path, base_checkout: Path) -> Path:
    resolved = Path(worktree).resolve()
    if resolved == Path(base_checkout).resolve():
        raise DevinAgentError("refusing to run inside the primary checkout")
    if not resolved.is_dir():
        raise DevinAgentError("worktree missing: " + str(resolved))
    return resolved


def worktree_branch(run, worktree: Path) -> str:
    proc = run(["git", "-C", str(worktree), "branch", "--show-current"])
    if proc.returncode:
        raise DevinAgentError("unable to read worktree branch")
    return (proc.stdout or "").strip()


def lease_owned(conn, task_id: str, worker_id: str, branch: str) -> bool:
    row = conn.execute(
        "select branch from brain_task_leases where task_id=? and chat_id=?",
        (task_id, worker_id),
    ).fetchone()
    return row is not None and str(row[0] or "") == branch


def assert_worker_lease(conn, run, worktree: Path, task_id: str, worker_id: str, branch: str) -> None:
    """Revalidate lease ownership and branch before commit/finish handoff.

    A worker whose Brain lease was reclaimed, expired, or whose worktree
    drifted off the leased branch must never publish a candidate or hand
    off; it raises instead of completing stale work.
    """
    row = conn.execute(
        "select branch,lease_until_epoch from brain_task_leases "
        "where task_id=? and chat_id=?",
        (task_id, worker_id),
    ).fetchone()
    if (
        row is None
        or str(row[0] or "") != branch
        or float(row[1] or 0) <= time.time()
    ):
        raise LeaseLostError(
            "worker no longer owns the expected task lease; refusing handoff"
        )
    if worktree_branch(run, worktree) != branch:
        raise LeaseLostError(
            "worktree is no longer on the leased worker branch; refusing handoff"
        )


def changed_paths(worktree: Path) -> list[str]:
    try:
        return git_changed_paths(worktree)
    except PatchAgentError as exc:
        raise DevinAgentError(str(exc)) from exc


def ensure_scoped(paths: list[str], scopes: list[str] | tuple[str, ...]) -> None:
    try:
        validate_paths(paths, scopes)
    except PatchAgentError as exc:
        raise DevinAgentError(str(exc)) from exc


def clean_uncommitted(run, worktree: Path) -> None:
    """Reset the worktree to a clean retry state.

    Only safe to run AFTER a recovery snapshot has preserved every changed
    path under refs/logres/attempts/; callers must never use this to discard
    Devin-produced work that has not been snapshotted first.
    """
    run(["git", "-C", str(worktree), "restore", "--staged", "--worktree", "."])
    run(["git", "-C", str(worktree), "clean", "-fd"])


def _safe_ref_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value)).strip("-.")
    return cleaned or "x"


def attempt_ref_name(task_id: str, stamp: str) -> str:
    parts = [p for p in re.split(r"[/\\]+", str(task_id)) if p] or ["task"]
    safe = "/".join(_safe_ref_component(part) for part in parts)
    return f"{ATTEMPT_REF_PREFIX}/{safe}/{_safe_ref_component(stamp)}"


def snapshot_attempt(
    run,
    worktree: Path,
    task_id: str,
    *,
    stage: str,
    stamp: str | None = None,
    env: dict | None = None,
) -> dict:
    """Preserve all changed repository state as a recovery commit.

    Captures tracked modifications, staged content, and untracked files
    (gitignore rules still apply, matching the cleanup policy) into a commit
    under refs/logres/attempts/<safe-task>/<stamp>-<stage>. The leased worker
    branch HEAD is never moved: the snapshot is built through a temporary
    index and commit-tree, leaving HEAD, the real index, and the worktree
    exactly as the agent produced them.

    The attempt ref is recovery data only; it is never a candidate SHA.
    """
    worktree = Path(worktree)
    stamp = stamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ref = attempt_ref_name(task_id, f"{stamp}-{_safe_ref_component(stage)}")
    head = run(["git", "-C", str(worktree), "rev-parse", "--verify", "HEAD"])
    if head.returncode:
        raise DevinAgentError(
            "cannot resolve HEAD for attempt snapshot: "
            + redact(((head.stderr or "") + (head.stdout or ""))[-2000:])
        )
    head_sha = (head.stdout or "").strip()
    base_env = dict(env if env is not None else os.environ)
    try:
        with tempfile.TemporaryDirectory(prefix="logres-attempt-") as td:
            git_env = dict(base_env)
            git_env["GIT_INDEX_FILE"] = str(Path(td) / "index")
            for argv in (
                ["git", "-C", str(worktree), "read-tree", "HEAD"],
                ["git", "-C", str(worktree), "add", "-A"],
            ):
                proc = run(argv, env=git_env)
                if proc.returncode:
                    raise DevinAgentError(
                        "attempt snapshot staging failed: "
                        + redact(((proc.stderr or "") + (proc.stdout or ""))[-2000:])
                    )
            tree = run(
                ["git", "-C", str(worktree), "write-tree"], env=git_env
            )
            if tree.returncode:
                raise DevinAgentError(
                    "attempt snapshot write-tree failed: "
                    + redact(((tree.stderr or "") + (tree.stdout or ""))[-2000:])
                )
            tree_sha = (tree.stdout or "").strip()
        commit = run(
            [
                "git",
                "-C",
                str(worktree),
                "-c",
                "user.name=Logres Devin Worker",
                "-c",
                "user.email=devin-worker@local.invalid",
                "commit-tree",
                tree_sha,
                "-p",
                head_sha,
                "-m",
                f"logres attempt snapshot task={task_id} stage={stage}",
            ],
            env=base_env,
        )
        if commit.returncode:
            raise DevinAgentError(
                "attempt snapshot commit-tree failed: "
                + redact(((commit.stderr or "") + (commit.stdout or ""))[-2000:])
            )
        sha = (commit.stdout or "").strip()
        refproc = run(["git", "-C", str(worktree), "update-ref", ref, sha])
        if refproc.returncode:
            raise DevinAgentError(
                "attempt snapshot update-ref failed: "
                + redact(((refproc.stderr or "") + (refproc.stdout or ""))[-2000:])
            )
    except DevinAgentError:
        raise
    except Exception as exc:
        raise DevinAgentError(
            f"attempt snapshot failed: {type(exc).__name__}: {exc}"
        ) from exc
    return {
        "ref": ref,
        "sha": sha,
        "tree": tree_sha,
        "parent_head": head_sha,
        "stage": str(stage),
        "kind": "recovery-snapshot",
    }


def preserve_failed_attempt(
    run,
    worktree: Path,
    task_id: str,
    *,
    stage: str,
    stamp: str | None = None,
    env: dict | None = None,
) -> dict:
    """Snapshot all work, then reset the worktree clean for retry.

    Ordering is structural: the snapshot must succeed before any cleanup
    runs, so failed attempts are preserved instead of discarded. If the
    snapshot fails the worktree is left dirty and the error propagates —
    unsnapshotted work is never destroyed.
    """
    attempt = snapshot_attempt(
        run, worktree, task_id, stage=stage, stamp=stamp, env=env
    )
    clean_uncommitted(run, worktree)
    return attempt


def parse_models_report(text: str) -> dict:
    try:
        data = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise DevinAgentError("devin models list did not return valid JSON") from exc
    variants: dict[str, str] = {}
    families: dict[str, list[str]] = {}
    for family in data.get("families") or []:
        uids: list[str] = []
        for variant in family.get("variants") or []:
            uid = str(variant.get("model_uid") or "")
            if not uid:
                continue
            variants[uid] = str(variant.get("cost_tier") or "")
            uids.append(uid)
        names = [family.get("slug"), family.get("family_uid")]
        names += list(family.get("aliases") or [])
        for name in names:
            name = str(name or "").strip()
            if name and name not in variants:
                families[name] = uids
    return {"variants": variants, "families": families}


def select_model(
    report: dict,
    requested: str | None,
    *,
    allow_paid: bool = False,
) -> str:
    name = str(requested or "").strip() or DEFAULT_MODEL
    variants = report.get("variants") or {}
    families = report.get("families") or {}
    if name in variants:
        tier = variants[name]
        if tier.strip().lower() == FREE_COST_TIER or allow_paid:
            return name
        raise DevinAgentError(
            f"model {name} is paid (cost_tier={tier or 'unknown'}); "
            "explicit paid opt-in is required"
        )
    if name in families:
        tiers = {
            variants[uid]
            for uid in families[name]
            if uid in variants
        }
        if not tiers:
            raise DevinAgentError(
                f"model {name} is not reported by devin models list"
            )
        if all(tier.strip().lower() == FREE_COST_TIER for tier in tiers):
            return name
        if allow_paid:
            return name
        raise DevinAgentError(
            f"model family {name} includes paid variants; "
            "explicit paid opt-in is required"
        )
    raise DevinAgentError(
        f"model {name} is not reported by devin models list"
    )


def resolve_execution_isolation(
    *,
    execution_mode: str = DEFAULT_EXECUTION_MODE,
    sandbox: bool = False,
    isolation: str | None = None,
) -> dict:
    """Fail-closed execution-isolation contract for command construction.

    The Devin permission mode (including smart) is only a prompt policy: it
    is NOT proof the run is safe to leave unattended, and the CLI allow/deny
    permission config is defense-in-depth, not an OS boundary. Production
    unattended execution therefore requires an OS isolation contract: either
    the Devin native sandbox (--sandbox, which itself fails closed when the
    platform cannot enforce it) or an external isolation marker naming the
    OS/systemd/container boundary that the control-plane launcher provides.

    Interactive mode stays permissive for compatibility: it is attended, so
    the operator is the isolation boundary.
    """
    mode = str(execution_mode or DEFAULT_EXECUTION_MODE).strip().lower()
    if mode not in EXECUTION_MODES:
        raise DevinAgentError("unsupported execution mode: " + mode)
    marker = str(isolation or "").strip()
    if marker and not _ISOLATION_MARKER_RE.fullmatch(marker):
        raise DevinAgentError("invalid isolation marker: " + marker)
    if mode == "unattended" and not (sandbox or marker):
        raise DevinAgentError(
            "unattended execution requires an OS isolation contract: enable "
            "the Devin native sandbox (--sandbox) or supply an external "
            "isolation marker (--isolation, LOGRES_DEVIN_ISOLATION, or "
            "devin.isolation config) from the OS launcher"
        )
    return {
        "mode": mode,
        "sandbox": bool(sandbox),
        "isolation": marker or (DEVIN_NATIVE_SANDBOX if sandbox else None),
        "unattended": mode == "unattended",
    }


def build_devin_argv(
    *,
    prompt_file: Path,
    devin_bin: str = "devin",
    model: str = DEFAULT_MODEL,
    permission_mode: str = DEFAULT_PERMISSION_MODE,
    export_path: Path | None = None,
    extra: list[str] | tuple[str, ...] = (),
    sandbox: bool = False,
    execution_mode: str = DEFAULT_EXECUTION_MODE,
    isolation: str | None = None,
) -> list[str]:
    mode = str(permission_mode or DEFAULT_PERMISSION_MODE).strip().lower()
    if mode not in PERMISSION_MODES:
        raise DevinAgentError("unsupported permission mode: " + mode)
    resolve_execution_isolation(
        execution_mode=execution_mode, sandbox=sandbox, isolation=isolation
    )
    if mode == "autonomous" and not sandbox:
        raise DevinAgentError("autonomous permission mode requires --sandbox")
    argv = [
        str(devin_bin),
        "-p",
        "--model",
        str(model),
        "--permission-mode",
        mode,
        "--prompt-file",
        str(prompt_file),
        "--respect-workspace-trust",
        "false",
    ]
    if sandbox:
        argv.append("--sandbox")
    if export_path is not None:
        argv += ["--export", str(export_path)]
    argv += [str(item) for item in extra]
    return argv


def parse_verify_specs(values, default: list[str]) -> list[list[str]]:
    specs: list[list[str]] = []
    for raw in values or []:
        args = shlex.split(str(raw))
        if args:
            specs.append(args)
    return specs or [list(default)]


def build_prompt(
    *,
    task_id: str,
    worker_id: str,
    branch: str,
    packet: str,
    scopes: list[str] | tuple[str, ...],
    verify_commands: list[list[str]],
) -> str:
    scope_block = "\n".join(f"- {scope}" for scope in scopes) or "- (none)"
    verify_block = "\n".join(
        f"- {shlex.join([str(a) for a in argv])}" for argv in verify_commands
    )
    return f"""You are a bounded Logres worker running inside an isolated git worktree
that the Logres Brain already leased to worker {worker_id}.

TASK: {task_id}
WORKER: {worker_id}
BRANCH: {branch}

HARD RULES:
- Stay on branch {branch}. Never checkout, switch, merge, rebase,
  cherry-pick, push, or run git commit. Leave edits uncommitted in the
  worktree; the harness verifies, commits, and hands off after you exit.
- Never touch the protected branches main or feat/logres-reconstruction,
  and never integrate into them.
- Modify or create files only inside the declared scopes below.
- Never read, print, or modify credentials, tokens, dotenv files, SSH
  keys, or Devin/Windsurf/OpenAI configuration or secrets.
- Implement only what the task packet requires. Do not invent Logres
  behavior that the packet or repository does not support.
- Do not weaken or delete tests to hide a defect.

DECLARED SCOPES:
{scope_block}

After you exit, the harness will:
1. confirm every changed path stays inside the declared scopes,
2. run focused verification:
{verify_block}
3. commit the scoped changes and run the Logres finish handoff.
On failure your work is never discarded: the harness snapshots all changed
state (including untracked files) into a recovery commit under
refs/logres/attempts/{task_id}/ before any cleanup, records the attempt ref
and failure stage in the job artifact, then returns the task to READY.
If the Brain lease is lost while you run, the harness stops you immediately;
a retry can then start clean while your preserved work stays recoverable.

TASK PACKET:
{packet}
"""


def run_verification(run, worktree: Path, commands: list[list[str]]) -> list[dict]:
    results: list[dict] = []
    for argv in commands:
        proc = run([str(a) for a in argv], cwd=worktree)
        results.append(
            {
                "argv": [str(a) for a in argv],
                "rc": int(proc.returncode),
                "tail": redact(((proc.stdout or "") + (proc.stderr or ""))[-12000:]),
            }
        )
        if proc.returncode:
            break
    return results


def commit_scoped_changes(run, worktree: Path, task_id: str, changed: list[str]) -> str:
    add = run(["git", "-C", str(worktree), "add", "-A", "--", *changed])
    if add.returncode:
        raise DevinAgentError(
            "git add failed: " + redact((add.stderr or add.stdout or "")[-2000:])
        )
    commit = run(
        [
            "git",
            "-C",
            str(worktree),
            "-c",
            "user.name=Logres Devin Worker",
            "-c",
            "user.email=devin-worker@local.invalid",
            "commit",
            "-m",
            f"worker: {task_id} devin implementation",
        ]
    )
    if commit.returncode:
        raise DevinAgentError(
            "git commit failed: " + redact((commit.stderr or commit.stdout or "")[-2000:])
        )
    sha = run(["git", "-C", str(worktree), "rev-parse", "HEAD"])
    if sha.returncode:
        raise DevinAgentError("git rev-parse failed after commit")
    return (sha.stdout or "").strip()


def make_lease_renewer(run, brain_bin: str, worker: str, task: str, minutes: int, *, timeout: float = 60):
    """Build a renew callable that classifies Brain failures.

    rc==3 is the Brain's RuntimeError exit (semantic refusals such as "not
    lease owner"), and messages like "does not own"/"TASK_BUSY"/"unknown
    chat" also mean the lease/identity is invalid: all raise LeaseLostError
    (authoritative). Everything else is a transient renewal error.
    """

    def renew() -> None:
        proc = run(
            [
                str(brain_bin),
                "renew",
                str(worker),
                str(task),
                "--minutes",
                str(int(minutes)),
            ],
            timeout=timeout,
        )
        if proc.returncode:
            tail = redact(
                ((proc.stderr or "") + (proc.stdout or "")).strip()[-800:]
            )
            if int(proc.returncode) == 3 or _LEASE_LOST_RE.search(tail):
                raise LeaseLostError(
                    "brain reports lease lost: " + (tail or "not lease owner")
                )
            raise DevinAgentError(
                "brain lease renewal failed: " + (tail or f"rc={proc.returncode}")
            )

    return renew


def _killpg(pid: int, sig: int) -> None:
    os.killpg(int(pid), sig)


def terminate_process_group(
    proc,
    *,
    grace_seconds: float = DEFAULT_TERM_GRACE_SECONDS,
    signal_group=None,
) -> int | None:
    """SIGTERM the child's whole process group, bounded grace, then SIGKILL.

    The child is spawned with start_new_session so its pgid equals its pid.
    Any signal failure falls back to proc.terminate()/kill() so a runaway
    child is still stopped even when group signalling is unavailable.
    """
    sig = signal_group or _killpg
    try:
        sig(proc.pid, signal.SIGTERM)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass
    try:
        return int(proc.wait(timeout=max(0.05, float(grace_seconds))))
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        return None
    try:
        sig(proc.pid, signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    try:
        return int(proc.wait(timeout=5.0))
    except Exception:
        return None


def run_child_with_lease(
    argv: list[str],
    *,
    log_path: Path,
    renew,
    cwd: Path | None = None,
    env: dict | None = None,
    renew_seconds: float = DEFAULT_RENEW_SECONDS,
    lease_ttl_seconds: float = DEFAULT_LEASE_TTL_SECONDS,
    lease_margin_seconds: float | None = None,
    term_grace_seconds: float = DEFAULT_TERM_GRACE_SECONDS,
    popen=subprocess.Popen,
    signal_group=None,
    clock=time.monotonic,
) -> dict:
    """Run the Devin child while renewing the Brain lease.

    Tracks the time of the last successful renewal. An authoritative
    ownership loss (LeaseLostError) terminates the child's process group
    immediately. Transient renewal errors are retried but the run is
    terminated once elapsed time since the last successful renewal crosses
    the lease deadline (ttl - margin), i.e. before the Brain TTL can expire
    and hand the task to another worker. Returns structured lease status.
    """
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(log_path, "ab", buffering=0)
    try:
        proc = popen(
            [str(a) for a in argv],
            cwd=str(cwd) if cwd else None,
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    except BaseException:
        handle.close()
        raise
    ttl = max(1.0, float(lease_ttl_seconds))
    margin = (
        float(lease_margin_seconds)
        if lease_margin_seconds is not None
        else float(DEFAULT_LEASE_MARGIN_SECONDS)
    )
    margin = max(0.0, min(margin, ttl * 0.5))
    deadline_seconds = ttl - margin
    renewals = 0
    renew_failures = 0
    last_ok = clock()
    lease_status = LEASE_OK
    lease_detail = None
    rc = None
    terminated = False

    def beat() -> str | None:
        nonlocal renewals, renew_failures, last_ok, lease_status, lease_detail
        try:
            renew()
            renewals += 1
            last_ok = clock()
            return None
        except LeaseLostError as exc:
            lease_status = LEASE_LOST
            lease_detail = redact(str(exc))[:800]
            return lease_status
        except Exception as exc:
            renew_failures += 1
            lease_detail = redact(f"{type(exc).__name__}: {exc}")[:800]
            if clock() - last_ok >= deadline_seconds:
                lease_status = LEASE_DEADLINE
                return lease_status
            return None

    stop = beat()
    try:
        while stop is None:
            try:
                rc = proc.wait(timeout=max(1.0, float(renew_seconds)))
                break
            except subprocess.TimeoutExpired:
                stop = beat()
    except BaseException:
        terminated = True
        terminate_process_group(
            proc,
            grace_seconds=term_grace_seconds,
            signal_group=signal_group,
        )
        raise
    finally:
        handle.close()
    if stop is not None:
        terminated = True
        rc = terminate_process_group(
            proc,
            grace_seconds=term_grace_seconds,
            signal_group=signal_group,
        )
    return {
        "rc": int(rc) if rc is not None else -1,
        "pid": int(proc.pid),
        "renewals": renewals,
        "renew_failures": renew_failures,
        "terminated": terminated,
        "lease": {
            "status": lease_status,
            "detail": lease_detail,
            "renewals": renewals,
            "renew_failures": renew_failures,
            "seconds_since_renewal": round(max(0.0, clock() - last_ok), 3),
            "deadline_seconds": round(deadline_seconds, 3),
            "ttl_seconds": round(ttl, 3),
        },
    }


def devin_models_report(run, devin_bin: str) -> dict:
    proc = run([str(devin_bin), "models", "list", "--format", "json"], timeout=120)
    if proc.returncode:
        raise DevinAgentError("devin models list failed")
    return parse_models_report(proc.stdout or "")


def env_flag(environ, name: str) -> bool:
    return str(environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}
