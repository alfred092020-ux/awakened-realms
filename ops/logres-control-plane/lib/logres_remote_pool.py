from __future__ import annotations

import fcntl
import json
import os
import re
import shlex
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from logres_resource_broker import choose_remote_role


FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SAFE_SCRIPT_RE = re.compile(r"^[A-Za-z0-9:_-]+$")
SAFE_SCRIPT_PREFIXES = ("test", "verify", "build", "typecheck", "lint")
FORBIDDEN_SCRIPT_WORDS = {
    "deploy",
    "merge",
    "publish",
    "push",
    "release",
    "tag",
    "version",
}


class PoolError(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkerSpec:
    role: str
    host: str
    label: str
    max_slots: int


DEFAULT_WORKERS = {
    "heavy": WorkerSpec(
        role="heavy",
        host=os.environ.get("LOGRES_UPCLOUD_HEAVY_HOST", "209.50.63.78"),
        label="SJO heavy",
        max_slots=2,
    ),
    "light": WorkerSpec(
        role="light",
        host=os.environ.get("LOGRES_UPCLOUD_LIGHT_HOST", "194.113.74.97"),
        label="NYC light",
        max_slots=1,
    ),
}


def ensure_exact_sha(value: str) -> str:
    value = value.strip().lower()
    if not FULL_SHA_RE.fullmatch(value):
        raise PoolError("source SHA must be an immutable 40-character lowercase hex commit")
    return value


def verification_ref(sha: str) -> str:
    return f"refs/logres/verify/{ensure_exact_sha(sha)}"


def ensure_safe_npm_script(script: str) -> str:
    if not SAFE_SCRIPT_RE.fullmatch(script):
        raise PoolError("npm script contains unsupported characters")
    lowered = script.lower()
    words = set(re.split(r"[:_-]+", lowered))
    if words & FORBIDDEN_SCRIPT_WORDS:
        raise PoolError("mutating/deployment npm scripts are forbidden on remote pool workers")
    if not lowered.startswith(SAFE_SCRIPT_PREFIXES):
        raise PoolError("remote pool only accepts verification/build npm scripts")
    return script


def targets_for(role: str) -> tuple[str, ...]:
    if role == "heavy":
        return ("heavy",)
    if role == "light":
        return ("light",)
    if role == "both":
        return ("heavy", "light")
    if role == "auto":
        return ()
    raise PoolError(f"unknown pool role: {role}")


def fallback_role(role: str) -> str:
    if role == "heavy":
        return "light"
    if role == "light":
        return "heavy"
    raise PoolError("failover is only defined for one primary worker")


@contextmanager
def exclusive_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def count_worker_process_lines(lines: Iterable[str]) -> int:
    target = "scripts/logres/" + "oracle_worker.py"
    return sum(1 for line in lines if target in line)


def normalize_health(spec: WorkerSpec, payload: dict) -> dict:
    active = max(0, int(payload.get("active_workers") or 0))
    max_slots = max(1, spec.max_slots)
    return {
        "role": spec.role,
        "host": spec.host,
        "label": spec.label,
        "reachable": True,
        "hostname": str(payload.get("hostname") or ""),
        "cpu_count": int(payload.get("cpu_count") or 0),
        "memory_total_bytes": int(payload.get("memory_total_bytes") or 0),
        "memory_available_bytes": int(payload.get("memory_available_bytes") or 0),
        "disk_free_bytes": int(payload.get("disk_free_bytes") or 0),
        "node_version": str(payload.get("node_version") or ""),
        "npm_version": str(payload.get("npm_version") or ""),
        "checkout_sha": str(payload.get("checkout_sha") or ""),
        "active_workers": active,
        "max_slots": max_slots,
        "available_slots": max(0, max_slots - active),
    }


def select_auto_target(health_rows: Iterable[dict]) -> str:
    candidates = [
        row
        for row in health_rows
        if row.get("reachable") and row.get("available_slots", 0) > 0
    ]
    if not candidates:
        raise PoolError("no remote worker has available capacity")
    candidates.sort(
        key=lambda row: (
            int(row.get("active_workers") or 0)
            / max(1, int(row.get("max_slots") or 1)),
            -int(row.get("available_slots") or 0),
            -int(row.get("cpu_count") or 0),
            str(row.get("role") or ""),
        )
    )
    return str(candidates[0]["role"])


def validate_summary(summary: dict, *, expected_sha: str, expected_job_id: str) -> dict:
    if summary.get("source_sha") != expected_sha:
        raise PoolError("remote summary source SHA mismatch")
    if summary.get("job_id") != expected_job_id:
        raise PoolError("remote summary job ID mismatch")
    if summary.get("status") != "success" or int(summary.get("exit_code", 1)) != 0:
        raise PoolError(
            f"remote job failed: {summary.get('error') or summary.get('status')}"
        )
    return summary


def store_collected_result(
    artifact_root: Path,
    job: str,
    spec: WorkerSpec,
    summary: dict,
    *,
    npm_script: str | None = None,
) -> Path:
    outdir = artifact_root / job / spec.role
    outdir.mkdir(parents=True, exist_ok=True)
    normalized = {
        "schema": 1,
        "role": spec.role,
        "host": spec.host,
        "label": spec.label,
        "job_id": summary.get("job_id"),
        "source_sha": summary.get("source_sha"),
        "status": summary.get("status"),
        "exit_code": summary.get("exit_code"),
        "duration_seconds": summary.get("duration_seconds"),
        "kind": summary.get("kind"),
        "npm_script": npm_script,
        "error": summary.get("error"),
    }
    path = outdir / "pool-result.json"
    path.write_text(json.dumps(normalized, indent=2, sort_keys=True) + "\n")
    return path


Runner = Callable[..., subprocess.CompletedProcess[str]]


class RemotePool:
    def __init__(
        self,
        *,
        root: Path,
        ssh_key: Path,
        artifact_root: Path,
        workers: dict[str, WorkerSpec] | None = None,
        runner: Runner = subprocess.run,
        lock_path: Path = Path("/tmp/logres-remote-pool-sync.lock"),
    ) -> None:
        self.root = root
        self.ssh_key = ssh_key
        self.artifact_root = artifact_root
        self.workers = dict(workers or DEFAULT_WORKERS)
        self.runner = runner
        self.lock_path = lock_path

    def _run(
        self,
        argv: list[str],
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        proc = self.runner(
            argv,
            text=True,
            capture_output=True,
            check=False,
        )
        if check and proc.returncode:
            detail = (proc.stderr or proc.stdout or "").strip()
            raise PoolError(f"command failed rc={proc.returncode}: {detail}")
        return proc

    def _ssh(self, spec: WorkerSpec, command: str, *, check: bool = True):
        return self._run(
            [
                "ssh",
                "-i",
                str(self.ssh_key),
                "-o",
                "BatchMode=yes",
                f"root@{spec.host}",
                command,
            ],
            check=check,
        )

    def _scp(self, source: str, destination: str, *, check: bool = True):
        return self._run(
            [
                "scp",
                "-q",
                "-i",
                str(self.ssh_key),
                source,
                destination,
            ],
            check=check,
        )

    def verify_local_sha(self, sha: str) -> str:
        sha = ensure_exact_sha(sha)
        self._run(
            ["git", "-C", str(self.root), "cat-file", "-e", f"{sha}^{{commit}}"]
        )
        return sha

    def probe(self, role: str) -> dict:
        spec = self.workers[role]
        code = (
            "import json,os,shutil,socket,subprocess;"
            "m={};"
            "[(m.__setitem__(k,int(v.split()[0])*1024)) for k,v in "
            "[line.split(':',1) for line in open('/proc/meminfo') if ':' in line] "
            "if k in ('MemTotal','MemAvailable')];"
            "run=lambda a: subprocess.run(a,text=True,capture_output=True).stdout.strip();"
            "needle='scripts/logres/'+'oracle_worker.py';"
            "workers=run(['pgrep','-af','oracle_worker.py']).splitlines();"
            "print(json.dumps({"
            "'hostname':socket.gethostname(),"
            "'cpu_count':os.cpu_count() or 0,"
            "'memory_total_bytes':m.get('MemTotal',0),"
            "'memory_available_bytes':m.get('MemAvailable',0),"
            "'disk_free_bytes':shutil.disk_usage('/').free,"
            "'node_version':run(['node','-v']),"
            "'npm_version':run(['npm','-v']),"
            "'checkout_sha':run(['git','-C','/srv/logres/worker','rev-parse','HEAD']),"
            "'active_workers':sum(1 for line in workers if needle in line)"
            "}))"
        )
        proc = self._ssh(spec, f"python3 -c {shlex.quote(code)}", check=False)
        if proc.returncode:
            return {
                "role": spec.role,
                "host": spec.host,
                "label": spec.label,
                "reachable": False,
                "error": (proc.stderr or proc.stdout or "").strip(),
                "max_slots": spec.max_slots,
                "available_slots": 0,
            }
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise PoolError(f"invalid health payload from {role}") from exc
        return normalize_health(spec, payload)

    def health(self) -> list[dict]:
        return [self.probe(role) for role in ("heavy", "light")]

    def _sync_one(
        self,
        spec: WorkerSpec,
        bundle: Path,
        sha: str,
        verify_ref: str,
    ) -> None:
        remote_bundle = "/srv/logres/sync.bundle"
        self._scp(str(bundle), f"root@{spec.host}:{remote_bundle}")
        quoted_ref = shlex.quote(verify_ref)
        command = (
            "set -e; "
            f"git --git-dir=/srv/logres/mirror.git fetch {remote_bundle} "
            "'+refs/heads/*:refs/heads/*' '+refs/tags/*:refs/tags/*' "
            f"'+{verify_ref}:{verify_ref}'; "
            "cd /srv/logres/worker; "
            "git fetch origin feat/logres-reconstruction "
            f"{quoted_ref}:{quoted_ref} >/dev/null; "
            f"git cat-file -e {shlex.quote(sha)}^{{commit}}"
        )
        self._ssh(spec, command)

    def _cleanup_remote_verify_ref(self, spec: WorkerSpec, verify_ref: str) -> None:
        quoted_ref = shlex.quote(verify_ref)
        command = (
            "set +e; "
            f"git -C /srv/logres/worker update-ref -d {quoted_ref}; "
            f"git --git-dir=/srv/logres/mirror.git update-ref -d {quoted_ref}; "
            "exit 0"
        )
        self._ssh(spec, command, check=False)

    def cleanup_verify_ref(self, sha: str) -> None:
        verify_ref = verification_ref(sha)
        for role in ("heavy", "light"):
            self._cleanup_remote_verify_ref(self.workers[role], verify_ref)

    def sync(self, sha: str) -> str:
        sha = self.verify_local_sha(sha)
        verify_ref = verification_ref(sha)
        with exclusive_lock(self.lock_path):
            self._run(
                ["git", "-C", str(self.root), "update-ref", verify_ref, sha]
            )
            try:
                with tempfile.TemporaryDirectory(
                    prefix="logres-remote-pool-"
                ) as tmp:
                    bundle = Path(tmp) / "sync.bundle"
                    self._run(
                        [
                            "git",
                            "-C",
                            str(self.root),
                            "bundle",
                            "create",
                            str(bundle),
                            "--all",
                        ]
                    )
                    synced_roles: list[str] = []
                    try:
                        for role in ("heavy", "light"):
                            self._sync_one(
                                self.workers[role],
                                bundle,
                                sha,
                                verify_ref,
                            )
                            synced_roles.append(role)
                    except Exception:
                        for role in synced_roles:
                            self._cleanup_remote_verify_ref(
                                self.workers[role],
                                verify_ref,
                            )
                        raise
            finally:
                self._run(
                    ["git", "-C", str(self.root), "update-ref", "-d", verify_ref],
                    check=False,
                )
        return sha

    def _run_one(self, role: str, job: str, script: str, sha: str) -> dict:
        spec = self.workers[role]
        remote_id = f"{job}-{role}"
        outdir = self.artifact_root / job / role
        outdir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema": 1,
            "job_id": remote_id,
            "source_sha": sha,
            "kind": "npm",
            "npm_script": script,
            "timeout_seconds": 3600,
        }
        with tempfile.NamedTemporaryFile(
            "w",
            suffix=".json",
            delete=False,
        ) as handle:
            json.dump(manifest, handle, sort_keys=True)
            handle.write("\n")
            manifest_path = Path(handle.name)
        try:
            remote_manifest = f"/srv/logres/jobs/{remote_id}.json"
            self._scp(
                str(manifest_path),
                f"root@{spec.host}:{remote_manifest}",
            )
            command = (
                "set -e; cd /srv/logres/worker; "
                f"python3 scripts/logres/oracle_worker.py {shlex.quote(remote_manifest)} "
                "--repo-root /srv/logres/worker "
                "--archive /srv/logres/private/logres-private-cache.zip "
                "--artifact-root /srv/logres/artifacts"
            )
            proc = self._ssh(spec, command, check=False)
            remote_summary = (
                f"/srv/logres/artifacts/{remote_id}/summary.json"
            )
            local_summary = outdir / "summary.json"
            self._scp(
                f"root@{spec.host}:{remote_summary}",
                str(local_summary),
            )
            summary = json.loads(local_summary.read_text())
            try:
                validate_summary(
                    summary,
                    expected_sha=sha,
                    expected_job_id=remote_id,
                )
            except PoolError:
                detail = (proc.stderr or proc.stdout or "").strip()
                if detail and not summary.get("error"):
                    summary["error"] = detail
                raise
            result_path = store_collected_result(
                self.artifact_root,
                job,
                spec,
                summary,
                npm_script=script,
            )
            return {
                "role": role,
                "host": spec.host,
                "summary": summary,
                "summary_path": str(local_summary),
                "result_path": str(result_path),
            }
        finally:
            manifest_path.unlink(missing_ok=True)

    def run(
        self,
        role: str,
        job: str,
        script: str,
        sha: str,
        *,
        reassignable: bool = False,
        retries: int = 0,
    ) -> list[dict]:
        if not re.fullmatch(r"[A-Za-z0-9._-]+", job):
            raise PoolError("job id contains unsupported characters")
        script = ensure_safe_npm_script(script)
        sha = self.sync(sha)
        try:
            targets = targets_for(role)
            if role == "auto":
                health_rows = self.health()
                try:
                    selected = choose_remote_role(
                        health_rows,
                        self.artifact_root,
                        npm_script=script,
                    )
                except RuntimeError as exc:
                    raise PoolError(str(exc)) from exc
                targets = (selected,)

            if len(targets) > 1:
                with ThreadPoolExecutor(max_workers=len(targets)) as pool:
                    futures = [
                        pool.submit(
                            self._run_one,
                            target,
                            job,
                            script,
                            sha,
                        )
                        for target in targets
                    ]
                    return [future.result() for future in futures]

            primary = targets[0]
            attempts = [primary]
            if reassignable and retries > 0:
                attempts.extend(
                    [fallback_role(primary)] * min(1, retries)
                )
            last_error: Exception | None = None
            for target in attempts:
                try:
                    return [
                        self._run_one(
                            target,
                            job,
                            script,
                            sha,
                        )
                    ]
                except Exception as exc:
                    last_error = exc
                    if not reassignable:
                        raise
            assert last_error is not None
            raise PoolError(
                f"remote verification failed after failover: {last_error}"
            )
        finally:
            self.cleanup_verify_ref(sha)
