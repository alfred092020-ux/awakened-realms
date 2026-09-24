from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from logres_goal_contract import evaluate_milestone, resolve_device_proof
from logres_mission_coverage import completion_manifest_report


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists milestone_certificates(
          id integer primary key autoincrement,
          milestone_id text not null,
          integration_sha text not null,
          contract_fingerprint text not null,
          status text not null,
          artifact_path text not null,
          artifact_sha256 text not null,
          created_at text not null
        );
        create index if not exists milestone_certificates_idx
          on milestone_certificates(milestone_id,id);
        """
    )
    conn.commit()


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "select 1 from sqlite_master where type='table' and name=?",
        (name,),
    ).fetchone() is not None


def _artifact_hashes(
    contracts: dict[str, Any],
    milestone_id: str,
    root: Path,
) -> list[dict[str, str | None]]:
    out: list[dict[str, str | None]] = []
    milestone = contracts["milestones"][milestone_id]
    for criterion in milestone["criteria"]:
        check = criterion["check"]
        if check.get("type") != "artifact":
            continue
        raw = Path(str(check["path"]))
        path = raw if raw.is_absolute() else root / raw
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        out.append(
            {
                "criterion_id": str(criterion["id"]),
                "path": str(path),
                "sha256": digest,
            }
        )
    return out


def _device_proof_rows(
    conn: sqlite3.Connection,
    contracts: dict[str, Any],
    milestone_id: str,
    *,
    integration_sha: str,
    root: Path,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    milestone = contracts["milestones"][milestone_id]
    for criterion in milestone["criteria"]:
        check = criterion["check"]
        if check.get("type") != "device_proof":
            continue
        evidence, _reason = resolve_device_proof(
            conn,
            check,
            integration_sha=integration_sha,
            root=root,
        )
        if evidence is None:
            continue
        out.append(
            {
                "criterion_id": str(criterion["id"]),
                **evidence,
            }
        )
    return out


def _verification_rows(conn: sqlite3.Connection, integration_sha: str) -> list[dict]:
    if not _table_exists(conn, "verification"):
        return []
    return [
        {
            "ref": str(row[0]),
            "sha": str(row[1] or ""),
            "mode": str(row[2] or ""),
            "status": str(row[3] or ""),
            "duration_sec": row[4],
            "ran_at": str(row[5] or ""),
            "details": str(row[6] or ""),
        }
        for row in conn.execute(
            """select ref,sha,mode,status,duration_sec,ran_at,details
                 from verification
                where sha=?
                order by mode,ran_at,ref""",
            (integration_sha,),
        )
    ]


def _open_regression_count(conn: sqlite3.Connection) -> int:
    if not _table_exists(conn, "regressions"):
        return 0
    return int(
        conn.execute(
            "select count(*) from regressions where status='OPEN'"
        ).fetchone()[0]
    )


def build_certificate(
    conn: sqlite3.Connection,
    contracts: dict[str, Any],
    milestone_id: str,
    *,
    integration_sha: str,
    root: Path,
    timestamp: str | None = None,
) -> dict:
    result = evaluate_milestone(
        conn,
        contracts,
        milestone_id,
        integration_sha=integration_sha,
        root=root,
    ).to_dict()
    open_regressions = _open_regression_count(conn)
    content_scope_report = None
    content_scope_valid = True
    if milestone_id == "CONTENT-0.5":
        content_scope_report = completion_manifest_report(root)
        content_scope_valid = bool(
            content_scope_report.get("declared_scope_complete", False)
        )

    valid = (
        result["state"] == "COMPLETE"
        and not result["unmet_criterion_ids"]
        and open_regressions == 0
        and len(integration_sha) == 40
        and content_scope_valid
    )
    return {
        "schema": "logres-milestone-certificate-v1",
        "milestone_id": milestone_id,
        "contract_fingerprint": result["contract_fingerprint"],
        "integration_sha": integration_sha,
        "criterion_results": result["criteria"],
        "required_artifact_hashes": _artifact_hashes(
            contracts, milestone_id, root
        ),
        "verification_rows": _verification_rows(conn, integration_sha),
        "device_proof_rows": _device_proof_rows(
            conn,
            contracts,
            milestone_id,
            integration_sha=integration_sha,
            root=root,
        ),
        "open_regression_count": open_regressions,
        "project_completion_scope": content_scope_report,
        "completion_claim": (
            "DECLARED_RECONSTRUCTION_SCOPE_ONLY"
            if milestone_id == "CONTENT-0.5"
            else None
        ),
        "historical_total_complete": (
            False if milestone_id == "CONTENT-0.5" else None
        ),
        "timestamp": timestamp or now(),
        "status": "PASS" if valid else "FAIL",
        "valid": valid,
        "state": result["state"],
        "unmet_criterion_ids": result["unmet_criterion_ids"],
    }


def write_certificate(
    conn: sqlite3.Connection,
    certificate: dict,
    *,
    artifact_dir: Path,
) -> dict:
    ensure_schema(conn)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    stamp = (
        certificate["timestamp"]
        .replace(":", "")
        .replace("-", "")
        .replace("+00:00", "Z")
    )
    path = artifact_dir / (
        f"{certificate['milestone_id']}-{stamp}-"
        f"{certificate['integration_sha'][:12]}.json"
    )
    if path.exists():
        raise FileExistsError(f"certificate artifact already exists: {path}")
    raw = json.dumps(certificate, sort_keys=True, indent=2) + "\n"
    path.write_text(raw)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    cur = conn.execute(
        """insert into milestone_certificates(
             milestone_id,integration_sha,contract_fingerprint,status,
             artifact_path,artifact_sha256,created_at
           ) values(?,?,?,?,?,?,?)""",
        (
            certificate["milestone_id"],
            certificate["integration_sha"],
            certificate["contract_fingerprint"],
            certificate["status"],
            str(path),
            digest,
            certificate["timestamp"],
        ),
    )
    conn.commit()
    return {
        "certificate_id": int(cur.lastrowid),
        "artifact_path": str(path),
        "artifact_sha256": digest,
        "status": certificate["status"],
        "valid": bool(certificate["valid"]),
    }


def apply_milestone_completion(
    conn: sqlite3.Connection,
    certificate: dict,
) -> bool:
    ensure_schema(conn)
    if not certificate.get("valid") or certificate.get("status") != "PASS":
        return False
    row = conn.execute(
        """select id,status,contract_fingerprint,integration_sha
             from milestone_certificates
            where milestone_id=?
            order by id desc limit 1""",
        (certificate["milestone_id"],),
    ).fetchone()
    if (
        row is None
        or str(row[1]) != "PASS"
        or str(row[2]) != certificate["contract_fingerprint"]
        or str(row[3]) != certificate["integration_sha"]
    ):
        return False
    conn.execute(
        """update milestones
              set status='DONE',updated_at=?
            where id=?""",
        (now(), certificate["milestone_id"]),
    )
    conn.commit()
    return True


def current_certificate_valid(
    conn: sqlite3.Connection,
    contracts: dict[str, Any],
    milestone_id: str,
    *,
    integration_sha: str,
    root: Path,
) -> bool:
    ensure_schema(conn)
    current = build_certificate(
        conn,
        contracts,
        milestone_id,
        integration_sha=integration_sha,
        root=root,
        timestamp="CURRENT_EVALUATION",
    )
    if not current["valid"]:
        return False
    row = conn.execute(
        """select contract_fingerprint,integration_sha,status
             from milestone_certificates
            where milestone_id=?
            order by id desc limit 1""",
        (milestone_id,),
    ).fetchone()
    return bool(
        row
        and str(row[0]) == current["contract_fingerprint"]
        and str(row[1]) == integration_sha
        and str(row[2]) == "PASS"
    )
