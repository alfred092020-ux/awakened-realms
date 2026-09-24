from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


SCHEMA = """
create table if not exists recon_loop_repairs(
  divergence_fingerprint text primary key,
  packet_id text not null,
  synthesis_sha256 text not null,
  baseline_differential_sha256 text not null,
  baseline_trace_sha256 text not null,
  repair_task_id text not null unique,
  status text not null,
  created_at text not null,
  updated_at text not null,
  verified_differential_sha256 text,
  verified_trace_sha256 text,
  note text not null default ''
);
"""
PROVENANCE = "ZENITH_CERTIFICATE_FIRST_SELF_CORRECTING_RECON_LOOP"
REPAIR_PREFIX = "RECON-REPAIR-"
FORBIDDEN_TASK_PREFIXES = ("AUTO-RE", "UNBLOCK")
TERMINAL_TASK_STATES = {"DONE", "RESOLVED", "INTEGRATED"}
PATCH_STATUS = "BOUNDED_PATCH_REQUIRED"
ZERO_STATUS = "ZERO_DELTA_ALREADY_SATISFIED"
EXTERNAL_STATUSES = {
    "BLOCKED_EVIDENCE",
    "BLOCKED_EXTERNAL_CEILING",
    "REJECTED_INSUFFICIENT_EVIDENCE",
}
STRONG_HASH = re.compile(r"^[0-9a-f]{64}$")


class ReconLoopError(RuntimeError):
    pass


@dataclass(frozen=True)
class RepairPlan:
    status: str
    reason: str
    fingerprint: str
    packet_id: str
    repair_task_id: str | None
    scopes: tuple[str, ...]
    acceptance: tuple[str, ...]
    synthesis_sha256: str
    baseline_differential_sha256: str
    baseline_trace_sha256: str
    evidence_hashes: tuple[str, ...]
    rollback_predicates: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "provenance": PROVENANCE,
            "status": self.status,
            "reason": self.reason,
            "fingerprint": self.fingerprint,
            "packet_id": self.packet_id,
            "repair_task_id": self.repair_task_id,
            "scopes": list(self.scopes),
            "acceptance": list(self.acceptance),
            "synthesis_sha256": self.synthesis_sha256,
            "baseline_differential_sha256": self.baseline_differential_sha256,
            "baseline_trace_sha256": self.baseline_trace_sha256,
            "evidence_hashes": list(self.evidence_hashes),
            "rollback_predicates": list(self.rollback_predicates),
            "automation": {
                "writes_game_code": False,
                "commits": False,
                "merges": False,
                "deploys": False,
                "modifies_main": False,
                "creates_research_children": False,
                "creates_unblock_children": False,
            },
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ReconLoopError(f"cannot load JSON artifact {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReconLoopError(f"artifact must contain a JSON object: {path}")
    return value


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def _declared_artifact_hash(
    evidence: dict[str, Any],
    key: str,
) -> str:
    raw = evidence.get(key)
    if not isinstance(raw, dict):
        raise ReconLoopError(f"synthesis missing evidence.{key}")
    expected = str(raw.get("sha256") or "")
    if not STRONG_HASH.fullmatch(expected):
        raise ReconLoopError(f"evidence.{key}.sha256 is invalid")
    return expected


def _artifact_binding(
    evidence: dict[str, Any],
    key: str,
) -> tuple[Path, str]:
    raw = evidence.get(key)
    if not isinstance(raw, dict):
        raise ReconLoopError(f"synthesis missing evidence.{key}")
    path = Path(str(raw.get("path") or ""))
    expected = str(raw.get("sha256") or "")
    if not path.is_file():
        raise ReconLoopError(f"evidence artifact missing: {path}")
    if not STRONG_HASH.fullmatch(expected):
        raise ReconLoopError(f"evidence.{key}.sha256 is invalid")
    actual = sha256_file(path)
    if actual != expected:
        raise ReconLoopError(
            f"evidence hash drift for {key}: expected={expected} actual={actual}"
        )
    return path, expected


def _safe_scope(scope: str) -> bool:
    p = Path(scope)
    return (
        bool(scope)
        and not p.is_absolute()
        and ".." not in p.parts
        and scope != "main"
        and not scope.startswith(".git/")
    )


def _verify_repo_hashes(
    synthesis: dict[str, Any],
    repo: Path,
) -> list[str]:
    errors: list[str] = []
    evidence = synthesis.get("evidence") or {}
    source_hashes = evidence.get("current_scope_source_hashes") or {}
    if not isinstance(source_hashes, dict):
        return ["current_scope_source_hashes must be an object"]
    for rel, expected in sorted(source_hashes.items()):
        rel = str(rel)
        expected = str(expected)
        if not _safe_scope(rel):
            errors.append(f"unsafe current source scope: {rel}")
            continue
        path = repo / rel
        if not path.is_file():
            errors.append(f"current source missing: {rel}")
            continue
        actual = sha256_file(path)
        if actual != expected:
            errors.append(
                f"source hash drift: {rel} expected={expected} actual={actual}"
            )

    tests = evidence.get("targeted_tests") or []
    if not isinstance(tests, list):
        errors.append("targeted_tests must be a list")
        return errors
    for row in tests:
        if not isinstance(row, dict):
            errors.append("targeted_tests contains a non-object")
            continue
        rel = str(row.get("path") or "")
        expected = str(row.get("sha256") or "")
        if not _safe_scope(rel):
            errors.append(f"unsafe targeted test scope: {rel}")
            continue
        path = repo / rel
        if not path.is_file():
            errors.append(f"targeted test missing: {rel}")
            continue
        actual = sha256_file(path)
        if actual != expected:
            errors.append(
                f"targeted test hash drift: {rel} expected={expected} actual={actual}"
            )
    return errors


def _truth_has_relevant_same_authority_tie(
    synthesis: dict[str, Any],
    truth: dict[str, Any],
) -> bool:
    predicates = synthesis.get("predicates") or {}
    if predicates.get("same_authority_contradiction_tie") is True:
        return True

    evidence_ids = set()
    packet = synthesis.get("packet") or {}
    for key in ("evidence_ids", "truth_claim_ids", "fact_ids"):
        values = packet.get(key) or synthesis.get(key) or []
        if isinstance(values, list):
            evidence_ids.update(str(value) for value in values if value)

    if not evidence_ids:
        return False

    stack: list[Any] = [truth]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            status = str(item.get("status") or "")
            if status == "UNRESOLVED_SAME_AUTHORITY_TIE":
                blob = canonical_json(item)
                if any(token in blob for token in evidence_ids):
                    return True
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return False


def _fingerprint(
    synthesis: dict[str, Any],
    synthesis_sha: str,
    certified_diff_sha: str,
) -> str:
    packet = synthesis.get("packet") or {}
    core = {
        "packet_id": packet.get("id"),
        "classification": packet.get("classification"),
        "scope": sorted(str(x) for x in packet.get("scope", [])),
        "acceptance": sorted(str(x) for x in packet.get("acceptance", [])),
        "certified_differential_sha256": certified_diff_sha,
        "synthesis_sha256": synthesis_sha,
    }
    return hashlib.sha256(canonical_json(core).encode()).hexdigest()


def _history_row(
    conn: sqlite3.Connection,
    fingerprint: str,
) -> sqlite3.Row | None:
    try:
        return conn.execute(
            "select * from recon_loop_repairs where divergence_fingerprint=?",
            (fingerprint,),
        ).fetchone()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc).lower():
            return None
        raise


def plan(
    conn: sqlite3.Connection,
    *,
    synthesis_path: Path,
    repo: Path,
) -> RepairPlan:
    # Planning is deliberately read-only. A busy canonical control DB must not
    # prevent a certificate/hash decision, and schema creation belongs only to
    # write commands such as issue/reconcile/history.
    synthesis_sha = sha256_file(synthesis_path)
    synthesis = load_json(synthesis_path)
    evidence = synthesis.get("evidence") or {}
    if not isinstance(evidence, dict):
        raise ReconLoopError("synthesis evidence must be an object")

    # Duplicate suppression is stronger than mutable verification-artifact
    # freshness. Identify the immutable repair fingerprint from the synthesis
    # bytes plus the declared certified-differential hash before opening any
    # current differential/trace/truth artifacts. This guarantees that a
    # previously issued repair can never be re-issued merely because later
    # verification evidence changed.
    certified_declared_sha = _declared_artifact_hash(
        evidence,
        "certified_differential",
    )

    packet = synthesis.get("packet") or {}
    if not isinstance(packet, dict):
        raise ReconLoopError("synthesis packet must be an object")
    packet_id = str(packet.get("id") or "").strip()
    if not packet_id:
        raise ReconLoopError("synthesis packet id is required")

    fingerprint = _fingerprint(
        synthesis,
        synthesis_sha,
        certified_declared_sha,
    )
    repair_task_id = f"{REPAIR_PREFIX}{fingerprint[:12].upper()}"

    rollback = synthesis.get("rollback_predicate") or {}
    rollback_predicates = tuple(
        str(x)
        for x in rollback.get("invalidate_synthesis_if_any", [])
        if str(x).strip()
    )

    existing = _history_row(conn, fingerprint)
    if existing:
        duplicate_hashes = tuple(
            sorted(
                {
                    synthesis_sha,
                    certified_declared_sha,
                    str(existing["baseline_differential_sha256"]),
                    str(existing["baseline_trace_sha256"]),
                }
            )
        )
        return RepairPlan(
            status="ALREADY_ISSUED",
            reason=(
                "This certified divergence fingerprint already has repair task "
                f"{existing['repair_task_id']} status={existing['status']}; "
                "the loop will not issue a second repair."
            ),
            fingerprint=fingerprint,
            packet_id=packet_id,
            repair_task_id=str(existing["repair_task_id"]),
            scopes=(),
            acceptance=(),
            synthesis_sha256=synthesis_sha,
            baseline_differential_sha256=str(
                existing["baseline_differential_sha256"]
            ),
            baseline_trace_sha256=str(existing["baseline_trace_sha256"]),
            evidence_hashes=duplicate_hashes,
            rollback_predicates=rollback_predicates,
        )

    # First-time repair planning remains fail-closed: every referenced artifact
    # must exist and match the synthesis-declared hash before a repair can be
    # proposed.
    certified_path, certified_sha = _artifact_binding(
        evidence,
        "certified_differential",
    )
    current_path, current_sha = _artifact_binding(
        evidence,
        "current_differential",
    )
    truth_path, truth_sha = _artifact_binding(evidence, "truth_kernel")
    consistency_path, consistency_sha = _artifact_binding(
        evidence,
        "consistency_certificate",
    )
    trace_path, trace_sha = _artifact_binding(
        evidence,
        "trace_certificate",
    )

    certified = load_json(certified_path)
    current = load_json(current_path)
    truth = load_json(truth_path)
    consistency = load_json(consistency_path)
    trace = load_json(trace_path)

    evidence_hashes = tuple(
        sorted(
            {
                synthesis_sha,
                certified_sha,
                current_sha,
                truth_sha,
                consistency_sha,
                trace_sha,
            }
        )
    )

    errors = _verify_repo_hashes(synthesis, repo)
    if errors:
        return RepairPlan(
            status="STOP_EVIDENCE_HASH_DRIFT",
            reason="; ".join(errors),
            fingerprint=fingerprint,
            packet_id=packet_id,
            repair_task_id=None,
            scopes=(),
            acceptance=(),
            synthesis_sha256=synthesis_sha,
            baseline_differential_sha256=current_sha,
            baseline_trace_sha256=trace_sha,
            evidence_hashes=evidence_hashes,
            rollback_predicates=rollback_predicates,
        )

    if _truth_has_relevant_same_authority_tie(synthesis, truth):
        return RepairPlan(
            status="STOP_SAME_AUTHORITY_CONTRADICTION_TIE",
            reason=(
                "A same-authority contradiction tie touches this synthesis "
                "evidence; automatic repair planning is forbidden."
            ),
            fingerprint=fingerprint,
            packet_id=packet_id,
            repair_task_id=None,
            scopes=(),
            acceptance=(),
            synthesis_sha256=synthesis_sha,
            baseline_differential_sha256=current_sha,
            baseline_trace_sha256=trace_sha,
            evidence_hashes=evidence_hashes,
            rollback_predicates=rollback_predicates,
        )

    if (
        consistency.get("status") != "PASS"
        or (consistency.get("invariant_counts") or {}).get("failed") != 0
    ):
        return RepairPlan(
            status="STOP_CONSISTENCY_FAILURE",
            reason="Consistency certificate is not PASS with zero failed invariants.",
            fingerprint=fingerprint,
            packet_id=packet_id,
            repair_task_id=None,
            scopes=(),
            acceptance=(),
            synthesis_sha256=synthesis_sha,
            baseline_differential_sha256=current_sha,
            baseline_trace_sha256=trace_sha,
            evidence_hashes=evidence_hashes,
            rollback_predicates=rollback_predicates,
        )

    if trace.get("offline_only") is not True:
        return RepairPlan(
            status="STOP_TRACE_CERTIFICATE_POLICY",
            reason="Trace certificate is not an offline-only bounded certificate.",
            fingerprint=fingerprint,
            packet_id=packet_id,
            repair_task_id=None,
            scopes=(),
            acceptance=(),
            synthesis_sha256=synthesis_sha,
            baseline_differential_sha256=current_sha,
            baseline_trace_sha256=trace_sha,
            evidence_hashes=evidence_hashes,
            rollback_predicates=rollback_predicates,
        )

    status = str(synthesis.get("status") or "")
    predicates = synthesis.get("predicates") or {}
    if status == ZERO_STATUS:
        return RepairPlan(
            status="NO_REPAIR_REQUIRED",
            reason=(
                "Minimal synthesis proves the certified implementation gap is "
                "already absent from the fresh differential; zero files is the "
                "smallest evidence-sufficient delta."
            ),
            fingerprint=fingerprint,
            packet_id=packet_id,
            repair_task_id=None,
            scopes=(),
            acceptance=tuple(str(x) for x in packet.get("acceptance", [])),
            synthesis_sha256=synthesis_sha,
            baseline_differential_sha256=current_sha,
            baseline_trace_sha256=trace_sha,
            evidence_hashes=evidence_hashes,
            rollback_predicates=rollback_predicates,
        )

    if status in EXTERNAL_STATUSES:
        return RepairPlan(
            status="STOP_EXTERNAL_EVIDENCE_CEILING",
            reason=(
                "Minimal synthesis is evidence-blocked; the loop will not "
                "convert an external ceiling into an implementation task."
            ),
            fingerprint=fingerprint,
            packet_id=packet_id,
            repair_task_id=None,
            scopes=(),
            acceptance=(),
            synthesis_sha256=synthesis_sha,
            baseline_differential_sha256=current_sha,
            baseline_trace_sha256=trace_sha,
            evidence_hashes=evidence_hashes,
            rollback_predicates=rollback_predicates,
        )

    if status != PATCH_STATUS:
        return RepairPlan(
            status="STOP_UNSUPPORTED_SYNTHESIS_STATUS",
            reason=f"Unsupported synthesis status: {status or 'missing'}",
            fingerprint=fingerprint,
            packet_id=packet_id,
            repair_task_id=None,
            scopes=(),
            acceptance=(),
            synthesis_sha256=synthesis_sha,
            baseline_differential_sha256=current_sha,
            baseline_trace_sha256=trace_sha,
            evidence_hashes=evidence_hashes,
            rollback_predicates=rollback_predicates,
        )

    if predicates.get("active_gap_exists") is not True:
        return RepairPlan(
            status="STOP_SYNTHESIS_CONTRADICTION",
            reason="BOUNDED_PATCH_REQUIRED without active_gap_exists=true.",
            fingerprint=fingerprint,
            packet_id=packet_id,
            repair_task_id=None,
            scopes=(),
            acceptance=(),
            synthesis_sha256=synthesis_sha,
            baseline_differential_sha256=current_sha,
            baseline_trace_sha256=trace_sha,
            evidence_hashes=evidence_hashes,
            rollback_predicates=rollback_predicates,
        )

    delta = synthesis.get("delta") or {}
    requested = tuple(
        sorted(str(x) for x in delta.get("files_to_modify", []))
    )
    packet_scope = tuple(
        sorted(str(x) for x in packet.get("scope", []))
    )
    if (
        not requested
        or any(not _safe_scope(x) for x in requested)
        or not set(requested).issubset(set(packet_scope))
    ):
        return RepairPlan(
            status="STOP_SCOPE_VIOLATION",
            reason=(
                "Synthesis repair scope is empty, unsafe, or expands beyond "
                "the certified packet scope."
            ),
            fingerprint=fingerprint,
            packet_id=packet_id,
            repair_task_id=None,
            scopes=(),
            acceptance=(),
            synthesis_sha256=synthesis_sha,
            baseline_differential_sha256=current_sha,
            baseline_trace_sha256=trace_sha,
            evidence_hashes=evidence_hashes,
            rollback_predicates=rollback_predicates,
        )

    acceptance = tuple(
        [
            *(str(x) for x in packet.get("acceptance", [])),
            (
                "After implementation, regenerate the differential emulator "
                "and require this certified divergence fingerprint to be absent."
            ),
            (
                "After implementation, regenerate a fresh offline trace "
                "certificate; unchanged pre-repair certificates do not close "
                "the repair."
            ),
            (
                "Do not create AUTO-RE/UNBLOCK research children, merge, deploy, "
                "or modify main."
            ),
        ]
    )

    return RepairPlan(
        status="REPAIR_READY",
        reason=(
            "Certified implementation divergence remains active and all "
            "certificate/hash/scope gates pass."
        ),
        fingerprint=fingerprint,
        packet_id=packet_id,
        repair_task_id=repair_task_id,
        scopes=requested,
        acceptance=acceptance,
        synthesis_sha256=synthesis_sha,
        baseline_differential_sha256=current_sha,
        baseline_trace_sha256=trace_sha,
        evidence_hashes=evidence_hashes,
        rollback_predicates=rollback_predicates,
    )


def coordinator_argv(
    plan: RepairPlan,
    coordinator: str,
) -> list[str]:
    if plan.status != "REPAIR_READY" or not plan.repair_task_id:
        raise ReconLoopError("only REPAIR_READY plans may create repair tasks")
    if plan.repair_task_id.startswith(FORBIDDEN_TASK_PREFIXES):
        raise ReconLoopError("recursive research/unblock repair id is forbidden")

    evidence_policy = (
        "Certificate-first repair only. Evidence hashes="
        + ",".join(plan.evidence_hashes)
        + ". Do not infer retired-server behavior. "
        "No autonomous merge/deploy/main mutation."
    )
    argv = [
        coordinator,
        "add-task",
        plan.repair_task_id,
        "0",
        "reconstruction-repair",
        f"Repair certified reconstruction divergence {plan.packet_id}",
        "--milestone",
        "ZENITH formally certified reconstruction",
        "--work-type",
        "implementation",
        "--concurrency-key",
        f"recon-repair:{plan.fingerprint[:16]}",
        "--minutes",
        "90",
        "--evidence-policy",
        evidence_policy,
    ]
    for criterion in plan.acceptance:
        argv.extend(["--accept", criterion])
    for scope in plan.scopes:
        argv.extend(["--scope", scope])
    return argv


def issue(
    conn: sqlite3.Connection,
    *,
    synthesis_path: Path,
    repo: Path,
    coordinator: str,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    ensure_schema(conn)
    repair = plan(
        conn,
        synthesis_path=synthesis_path,
        repo=repo,
    )
    if repair.status != "REPAIR_READY":
        return {
            "created": False,
            "plan": repair.to_dict(),
        }

    process = runner(
        coordinator_argv(repair, coordinator),
        text=True,
        capture_output=True,
        check=False,
    )
    row = conn.execute(
        "select status,lane from tasks where id=?",
        (repair.repair_task_id,),
    ).fetchone()
    if row is None:
        raise ReconLoopError(
            "bounded repair task creation failed: "
            + ((process.stderr or process.stdout or "").strip())
        )
    if str(row[1]) == "research" or str(repair.repair_task_id).startswith(
        FORBIDDEN_TASK_PREFIXES
    ):
        raise ReconLoopError("repair task violated recursion guard")

    now = utc_now()
    conn.execute(
        """
        insert into recon_loop_repairs(
          divergence_fingerprint,packet_id,synthesis_sha256,
          baseline_differential_sha256,baseline_trace_sha256,
          repair_task_id,status,created_at,updated_at,note
        ) values(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            repair.fingerprint,
            repair.packet_id,
            repair.synthesis_sha256,
            repair.baseline_differential_sha256,
            repair.baseline_trace_sha256,
            repair.repair_task_id,
            "ISSUED",
            now,
            now,
            "Bounded implementation repair issued; Lead retains integration authority.",
        ),
    )
    conn.commit()
    return {
        "created": True,
        "task_id": repair.repair_task_id,
        "plan": repair.to_dict(),
        "coordinator_returncode": int(process.returncode),
    }


def _active_bug_ids(differential: dict[str, Any]) -> list[str]:
    return sorted(
        str(row.get("id") or "")
        for row in differential.get("divergences", [])
        if isinstance(row, dict)
        and row.get("classification") == "IMPLEMENTATION_BUG"
        and str(row.get("id") or "")
    )


def _packet_ids(differential: dict[str, Any]) -> list[str]:
    return sorted(
        str(row.get("id") or "")
        for row in differential.get("implementation_packets", [])
        if isinstance(row, dict) and str(row.get("id") or "")
    )


def reconcile_one(
    conn: sqlite3.Connection,
    fingerprint: str,
    *,
    current_differential: Path,
    trace_certificate: Path,
) -> dict[str, Any]:
    ensure_schema(conn)
    row = _history_row(conn, fingerprint)
    if row is None:
        raise ReconLoopError(f"unknown repair fingerprint: {fingerprint}")

    task = conn.execute(
        "select status from tasks where id=?",
        (row["repair_task_id"],),
    ).fetchone()
    task_status = str(task[0]) if task else "MISSING"
    if task_status not in TERMINAL_TASK_STATES:
        return {
            "fingerprint": fingerprint,
            "repair_task_id": row["repair_task_id"],
            "status": "REPAIR_IN_PROGRESS",
            "task_status": task_status,
        }

    if not current_differential.is_file() or not trace_certificate.is_file():
        return {
            "fingerprint": fingerprint,
            "repair_task_id": row["repair_task_id"],
            "status": "AWAITING_FRESH_VERIFICATION",
            "reason": "Fresh differential and trace certificate are required.",
        }

    diff_sha = sha256_file(current_differential)
    trace_sha = sha256_file(trace_certificate)
    if (
        diff_sha == row["baseline_differential_sha256"]
        or trace_sha == row["baseline_trace_sha256"]
    ):
        conn.execute(
            """
            update recon_loop_repairs
               set status='AWAITING_REVERIFICATION',
                   updated_at=?,
                   note=?
             where divergence_fingerprint=?
            """,
            (
                utc_now(),
                "Repair task is terminal but differential/trace evidence is not both fresh.",
                fingerprint,
            ),
        )
        conn.commit()
        return {
            "fingerprint": fingerprint,
            "repair_task_id": row["repair_task_id"],
            "status": "AWAITING_FRESH_VERIFICATION",
            "differential_fresh": (
                diff_sha != row["baseline_differential_sha256"]
            ),
            "trace_fresh": trace_sha != row["baseline_trace_sha256"],
        }

    differential = load_json(current_differential)
    trace = load_json(trace_certificate)
    bugs = _active_bug_ids(differential)
    packets = _packet_ids(differential)
    packet_still_present = str(row["packet_id"]) in packets
    trace_valid = trace.get("offline_only") is True

    if not bugs and not packet_still_present and trace_valid:
        status = "VERIFIED_CLOSED"
        note = (
            "Fresh differential contains no IMPLEMENTATION_BUG/matching packet "
            "and fresh trace certificate is offline-only."
        )
    else:
        status = "REPAIR_EXHAUSTED_SAME_FINGERPRINT"
        note = (
            "Fresh verification did not close the certified divergence. "
            "The same fingerprint will not generate another repair; new "
            "evidence or human/Lead review is required."
        )

    conn.execute(
        """
        update recon_loop_repairs
           set status=?,
               verified_differential_sha256=?,
               verified_trace_sha256=?,
               updated_at=?,
               note=?
         where divergence_fingerprint=?
        """,
        (
            status,
            diff_sha,
            trace_sha,
            utc_now(),
            note,
            fingerprint,
        ),
    )
    conn.commit()
    return {
        "fingerprint": fingerprint,
        "repair_task_id": row["repair_task_id"],
        "status": status,
        "task_status": task_status,
        "active_implementation_bug_ids": bugs,
        "active_implementation_packet_ids": packets,
        "trace_offline_only": trace_valid,
        "differential_sha256": diff_sha,
        "trace_sha256": trace_sha,
        "note": note,
        "automatic_repair_reissued": False,
        "automatic_merge": False,
        "automatic_deploy": False,
    }


def history(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    ensure_schema(conn)
    conn.row_factory = sqlite3.Row
    return [
        dict(row)
        for row in conn.execute(
            """
            select *
              from recon_loop_repairs
             order by created_at,divergence_fingerprint
            """
        )
    ]
