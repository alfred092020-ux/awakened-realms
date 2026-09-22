#!/usr/bin/env python3
"""Run tightly-scoped Logres analysis jobs on the private Oracle worker."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
JOB_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_NPM_SCRIPTS = {"build", "test", "verify", "verify:all"}
ALLOWED_TEXT_SUFFIXES = {".csv", ".json", ".log", ".md", ".txt"}
MAX_TIMEOUT_SECONDS = 21600
MAX_RESULT_FILE_BYTES = 10 * 1024 * 1024
MAX_RESULT_TOTAL_BYTES = 50 * 1024 * 1024


class JobError(RuntimeError):
    pass


def require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise JobError(f"{field} must be a non-empty string")
    return value


def load_job(path: Path) -> dict[str, Any]:
    try:
        job = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise JobError(f"unable to read job manifest: {exc}") from exc

    if not isinstance(job, dict):
        raise JobError("job manifest must be a JSON object")
    if job.get("schema") != SCHEMA_VERSION:
        raise JobError(f"schema must be {SCHEMA_VERSION}")

    job_id = require_string(job.get("job_id"), "job_id")
    if not JOB_ID_RE.fullmatch(job_id):
        raise JobError("job_id contains unsafe characters")

    source_sha = require_string(job.get("source_sha"), "source_sha")
    if not SHA_RE.fullmatch(source_sha):
        raise JobError(
            "source_sha must be a full lowercase 40-character commit SHA"
        )

    kind = require_string(job.get("kind"), "kind")
    if kind not in {"python", "npm"}:
        raise JobError(f"unsupported job kind: {kind}")

    timeout_seconds = job.get("timeout_seconds", 3600)
    if (
        not isinstance(timeout_seconds, int)
        or isinstance(timeout_seconds, bool)
        or not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS
    ):
        raise JobError(
            f"timeout_seconds must be between 1 and {MAX_TIMEOUT_SECONDS}"
        )

    if kind == "python":
        require_string(job.get("script"), "script")
        args = job.get("args", [])
        if (
            not isinstance(args, list)
            or len(args) > 64
            or any(not isinstance(arg, str) for arg in args)
        ):
            raise JobError("args must be a list of at most 64 strings")
    else:
        npm_script = require_string(job.get("npm_script"), "npm_script")
        if npm_script not in ALLOWED_NPM_SCRIPTS:
            raise JobError(f"npm_script is not allowed: {npm_script}")

    return job


def resolve_python_script(repo_root: Path, value: str) -> Path:
    scripts_root = (repo_root / "scripts" / "logres").resolve()
    candidate = (repo_root / value).resolve()
    try:
        candidate.relative_to(scripts_root)
    except ValueError as exc:
        raise JobError("python script must stay under scripts/logres") from exc
    if candidate.suffix != ".py" or not candidate.is_file():
        raise JobError("python script must be an existing .py file")
    return candidate


def expand_args(
    args: list[str],
    archive: Path,
    output_dir: Path,
) -> list[str]:
    return [
        arg.replace("@PRIVATE_ARCHIVE@", str(archive)).replace(
            "@OUTPUT@", str(output_dir)
        )
        for arg in args
    ]


def run_command(
    command: list[str],
    cwd: Path,
    log_path: Path,
    timeout_seconds: int,
    *,
    append: bool = False,
) -> int:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        output = completed.stdout
        exit_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + "\nORACLE WORKER TIMEOUT\n"
        exit_code = 124

    with log_path.open("a" if append else "w", encoding="utf-8") as handle:
        handle.write(output)
    sys.stdout.write(output)
    sys.stdout.flush()
    return exit_code


def checkout_source(repo_root: Path, source_sha: str) -> None:
    for command in (
        ["git", "fetch", "--no-tags", "origin", source_sha],
        ["git", "checkout", "--detach", source_sha],
        ["git", "reset", "--hard", source_sha],
    ):
        subprocess.run(command, cwd=repo_root, check=True)


def validate_text_results(output_dir: Path) -> None:
    total_bytes = 0
    for path in output_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in ALLOWED_TEXT_SUFFIXES:
            raise JobError(f"result contains a non-text file: {path.name}")
        size = path.stat().st_size
        if size > MAX_RESULT_FILE_BYTES:
            raise JobError(f"result file is too large: {path.name}")
        total_bytes += size
    if total_bytes > MAX_RESULT_TOTAL_BYTES:
        raise JobError("result directory exceeds the text artifact size limit")


def write_summary(
    output_dir: Path,
    job: dict[str, Any],
    status: str,
    exit_code: int | None,
    started_at: float,
    error: str | None = None,
) -> None:
    summary = {
        "schema": SCHEMA_VERSION,
        "job_id": job.get("job_id"),
        "source_sha": job.get("source_sha"),
        "kind": job.get("kind"),
        "status": status,
        "exit_code": exit_code,
        "duration_seconds": round(time.monotonic() - started_at, 3),
        "error": error,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def execute_job(
    job: dict[str, Any],
    repo_root: Path,
    archive: Path,
    artifact_root: Path,
) -> int:
    started_at = time.monotonic()
    output_dir = artifact_root / job["job_id"]
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "run.log"
    exit_code: int | None = None

    try:
        checkout_source(repo_root, job["source_sha"])
        timeout_seconds = job.get("timeout_seconds", 3600)

        if job["kind"] == "python":
            script = resolve_python_script(repo_root, job["script"])
            command = [
                "python3",
                "-B",
                str(script),
                *expand_args(job.get("args", []), archive, output_dir),
            ]
        else:
            exit_code = run_command(
                ["npm", "ci"],
                repo_root,
                log_path,
                timeout_seconds,
            )
            if exit_code != 0:
                write_summary(
                    output_dir,
                    job,
                    "failed",
                    exit_code,
                    started_at,
                    "npm ci failed",
                )
                validate_text_results(output_dir)
                return exit_code
            command = ["npm", "run", job["npm_script"]]

        exit_code = run_command(
            command,
            repo_root,
            log_path,
            timeout_seconds,
            append=job["kind"] == "npm",
        )
        write_summary(
            output_dir,
            job,
            "success" if exit_code == 0 else "failed",
            exit_code,
            started_at,
        )
        validate_text_results(output_dir)
        return exit_code

    except (JobError, OSError, subprocess.CalledProcessError) as exc:
        error = str(exc)
        print(f"Oracle worker failed: {error}", file=sys.stderr)
        if not log_path.exists():
            log_path.write_text(error + "\n", encoding="utf-8")
        write_summary(
            output_dir,
            job,
            "failed",
            exit_code,
            started_at,
            error,
        )
        return exit_code if exit_code not in (None, 0) else 1


def self_test() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        repo = root / "repo"
        script_dir = repo / "scripts" / "logres"
        script_dir.mkdir(parents=True)
        demo = script_dir / "demo.py"
        demo.write_text("print('ok')\n", encoding="utf-8")

        manifest = root / "job.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "job_id": "self-test",
                    "source_sha": "a" * 40,
                    "kind": "python",
                    "script": "scripts/logres/demo.py",
                    "args": [
                        "@PRIVATE_ARCHIVE@",
                        "@OUTPUT@/facts.json",
                    ],
                }
            ),
            encoding="utf-8",
        )
        job = load_job(manifest)
        if resolve_python_script(repo, job["script"]) != demo.resolve():
            raise AssertionError("safe script path did not resolve")

        expanded = expand_args(
            job["args"],
            root / "private.zip",
            root / "output",
        )
        if str(root / "private.zip") not in expanded[0]:
            raise AssertionError("archive token expansion failed")
        if str(root / "output") not in expanded[1]:
            raise AssertionError("output token expansion failed")

        try:
            resolve_python_script(repo, "../escape.py")
        except JobError:
            pass
        else:
            raise AssertionError("unsafe script path was accepted")

        bad_path = root / "bad-npm.json"
        bad_path.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "job_id": "bad-npm",
                    "source_sha": "b" * 40,
                    "kind": "npm",
                    "npm_script": "publish",
                }
            ),
            encoding="utf-8",
        )
        try:
            load_job(bad_path)
        except JobError:
            pass
        else:
            raise AssertionError("unsafe npm script was accepted")

    print("Logres Oracle worker self-test: PASS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_manifest", nargs="?", type=Path)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        self_test()
        return 0

    if not all(
        (
            args.job_manifest,
            args.repo_root,
            args.archive,
            args.artifact_root,
        )
    ):
        print(
            "job_manifest, --repo-root, --archive, and --artifact-root "
            "are required",
            file=sys.stderr,
        )
        return 2

    assert args.job_manifest
    assert args.repo_root
    assert args.archive
    assert args.artifact_root

    try:
        job = load_job(args.job_manifest)
    except JobError as exc:
        print(f"Oracle worker rejected job: {exc}", file=sys.stderr)
        return 2

    return execute_job(
        job,
        args.repo_root.resolve(),
        args.archive.resolve(),
        args.artifact_root.resolve(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
