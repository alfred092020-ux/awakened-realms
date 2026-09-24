#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

SCHEMA = "logres-android-release-candidate-v1"
CHECKPOINT_SCHEMA = "logres-android-checkpoint-v1"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ReleaseCandidateError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_file_hash(path_value: str, expected: str, label: str) -> Path:
    path = Path(path_value)
    if not path.is_file():
        raise ReleaseCandidateError(f"{label} unavailable: {path}")
    actual = sha256_file(path)
    if actual != expected:
        raise ReleaseCandidateError(
            f"{label} hash mismatch: expected={expected} actual={actual}"
        )
    return path


def git_head(repo: Path) -> str:
    value = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "feat/logres-reconstruction^{commit}"],
        text=True,
    ).strip()
    if not SHA_RE.fullmatch(value):
        raise ReleaseCandidateError(f"invalid integration SHA from Git: {value}")
    return value


def _milestones_before_release(conn: sqlite3.Connection) -> list[str]:
    row = conn.execute(
        "select sort_order from milestones where id='RELEASE-1.0'"
    ).fetchone()
    if row is None:
        raise ReleaseCandidateError("RELEASE-1.0 milestone missing")
    return [
        str(r[0])
        for r in conn.execute(
            """select id from milestones
                 where sort_order < ?
                 order by sort_order,id""",
            (int(row[0]),),
        )
    ]


def verify_candidate(
    manifest_path: Path,
    *,
    repo: Path,
    control_db: Path,
    require_current: bool = True,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema") != SCHEMA:
        raise ReleaseCandidateError("unsupported release candidate schema")

    source = manifest.get("source") or {}
    sha = str(source.get("sha") or "")
    if not SHA_RE.fullmatch(sha):
        raise ReleaseCandidateError("release candidate requires exact lowercase SHA")

    current = git_head(repo)
    if require_current and sha != current:
        raise ReleaseCandidateError(
            f"release candidate SHA is stale: candidate={sha} current={current}"
        )

    checkpoint_ref = manifest.get("checkpoint_manifest") or {}
    checkpoint_path = require_file_hash(
        str(checkpoint_ref.get("path") or ""),
        str(checkpoint_ref.get("sha256") or ""),
        "checkpoint manifest",
    )
    checkpoint = json.loads(checkpoint_path.read_text())
    if checkpoint.get("schema") != CHECKPOINT_SCHEMA:
        raise ReleaseCandidateError("unsupported checkpoint manifest schema")
    if checkpoint.get("source", {}).get("sha") != sha:
        raise ReleaseCandidateError("checkpoint manifest source SHA mismatch")
    if checkpoint.get("verification", {}).get("status") != "PASS":
        raise ReleaseCandidateError("checkpoint manifest is not full-e2e PASS")

    apk_ref = manifest.get("apk") or {}
    apk_path = require_file_hash(
        str(apk_ref.get("path") or ""),
        str(apk_ref.get("sha256") or ""),
        "release APK",
    )
    checkpoint_apk = checkpoint.get("apk") or {}
    if checkpoint_apk.get("sha256") != apk_ref.get("sha256"):
        raise ReleaseCandidateError("checkpoint/release APK SHA mismatch")
    if not checkpoint_apk.get("signature_verified"):
        raise ReleaseCandidateError("checkpoint does not attest APK signature verification")
    if int(apk_ref.get("bytes") or -1) != apk_path.stat().st_size:
        raise ReleaseCandidateError("release APK byte count mismatch")

    connection = sqlite3.connect(control_db)
    connection.row_factory = sqlite3.Row
    try:
        required = _milestones_before_release(connection)
        prerequisites = manifest.get("milestone_certificates")
        if not isinstance(prerequisites, list):
            raise ReleaseCandidateError("milestone certificate list missing")
        by_id = {
            str(row.get("milestone_id")): row
            for row in prerequisites
            if isinstance(row, dict)
        }
        if set(by_id) != set(required):
            missing = sorted(set(required) - set(by_id))
            extra = sorted(set(by_id) - set(required))
            raise ReleaseCandidateError(
                f"milestone certificate set mismatch: missing={missing} extra={extra}"
            )

        for milestone_id in required:
            status = connection.execute(
                "select status from milestones where id=?",
                (milestone_id,),
            ).fetchone()
            if status is None or str(status[0]) != "DONE":
                raise ReleaseCandidateError(
                    f"prerequisite milestone is not DONE: {milestone_id}"
                )

            cert = by_id[milestone_id]
            artifact_path = require_file_hash(
                str(cert.get("artifact_path") or ""),
                str(cert.get("artifact_sha256") or ""),
                f"{milestone_id} certificate",
            )
            payload = json.loads(artifact_path.read_text())
            if payload.get("milestone_id") != milestone_id:
                raise ReleaseCandidateError(
                    f"certificate milestone mismatch: {milestone_id}"
                )
            if payload.get("status") != "PASS" or payload.get("valid") is not True:
                raise ReleaseCandidateError(
                    f"certificate is not valid PASS: {milestone_id}"
                )

            row = connection.execute(
                """select id,integration_sha,contract_fingerprint,status,
                          artifact_path,artifact_sha256
                     from milestone_certificates
                    where id=? and milestone_id=?""",
                (int(cert.get("certificate_id") or 0), milestone_id),
            ).fetchone()
            if row is None:
                raise ReleaseCandidateError(
                    f"certificate row missing from control DB: {milestone_id}"
                )
            if str(row["status"]) != "PASS":
                raise ReleaseCandidateError(
                    f"control DB certificate is not PASS: {milestone_id}"
                )
            for key in (
                "integration_sha",
                "contract_fingerprint",
                "artifact_path",
                "artifact_sha256",
            ):
                if str(cert.get(key) or "") != str(row[key] or ""):
                    raise ReleaseCandidateError(
                        f"certificate provenance mismatch {milestone_id}: {key}"
                    )

        verification = connection.execute(
            """select ref,ran_at,details
                 from verification
                where sha=? and mode='full-e2e' and status='PASS'
                order by ran_at desc limit 1""",
            (sha,),
        ).fetchone()
        if verification is None:
            raise ReleaseCandidateError(
                f"no full-e2e PASS recorded for release SHA {sha}"
            )
    finally:
        connection.close()

    declared_verification = manifest.get("verification") or {}
    if declared_verification.get("status") != "PASS":
        raise ReleaseCandidateError("release manifest verification is not PASS")
    if declared_verification.get("mode") != "full-e2e":
        raise ReleaseCandidateError("release manifest verification mode is not full-e2e")

    return {
        "status": "PASS",
        "schema": SCHEMA,
        "sha": sha,
        "current_integration_sha": current,
        "apk_path": str(apk_path),
        "apk_sha256": apk_ref["sha256"],
        "checkpoint_manifest": str(checkpoint_path),
        "prerequisite_milestones": required,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path("/home/ubuntu/logres/src/awakened-realms"),
    )
    parser.add_argument(
        "--control-db",
        type=Path,
        default=Path("/home/ubuntu/logres/control/control.sqlite"),
    )
    parser.add_argument("--allow-noncurrent", action="store_true")
    args = parser.parse_args()

    try:
        result = verify_candidate(
            args.manifest,
            repo=args.repo,
            control_db=args.control_db,
            require_current=not args.allow_noncurrent,
        )
    except (
        ReleaseCandidateError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        sqlite3.Error,
        subprocess.CalledProcessError,
    ) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True))
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
