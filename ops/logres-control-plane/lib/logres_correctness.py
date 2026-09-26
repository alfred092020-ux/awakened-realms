"""Logres correctness oracle: unified four-level verification ladder.

L0  provenance/scope/evidence classification of the candidate diff.
L1  build + focused deterministic tests.
L2  historical behavior/visual/reference fidelity, required when the
    candidate touches gameplay, protocol, map, visual, battle, field,
    onboarding or historical-fidelity surfaces and applicable evidence
    exists in the existing truth systems.
L3  explicit human/user review, required only when evidence is genuinely
    ambiguous, no objective L2 oracle exists for a touched fidelity
    domain, or the candidate modifies the evaluator itself.

The oracle never invents truth: it classifies diffs deterministically
from the committed policy, consults the existing behavior-trace,
visual-truth, device-proof and exact-SHA verification stores, and emits
a machine-readable receipt. Evidence ceilings are preserved verbatim -
UNRESOLVED evidence stays UNRESOLVED, MEDIUM/LOW/version-sensitive
records are never upgraded to CONFIRMED ORIGINAL, and current-JP/later-JP
provenance can never outrank Global May 25 2017 evidence.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from logres_knowledge import CONFIDENCE_SCORE

POLICY_SCHEMA = 1
PLAN_SCHEMA = "logres-correctness-plan/1"
RECEIPT_SCHEMA = "logres-correctness-receipt/1"
RECEIPT_VERSION = 1

LEVELS = ("L0", "L1", "L2", "L3")
VERDICTS = ("PASS", "FAIL", "BLOCKED", "ERROR")
ORACLE_KINDS = {"behavior_trace", "visual_truth", "e2e", "device", "hydration"}
SHA40 = set("0123456789abcdef")

# Canonical confidence order for evidence labels found inside truth-record
# provenance payloads. First match wins; anything not listed is reported as
# UNCLASSIFIED evidence and is never upgraded.
PROVENANCE_LABEL_ORDER = (
    "UNRESOLVED",
    "VERSION SENSITIVE",
    "VERSION_SENSITIVE",
    "SUPPORTED INFERENCE",
    "SUPPORTED_INFERENCE",
    "RECONSTRUCTED",
    "MEDIUM",
    "LOW",
    "INFERENCE",
    "CONFIRMED ORIGINAL",
    "CONFIRMED_ORIGINAL",
    "CONFIRMED",
    "EVIDENCE_BACKED",
    "EVIDENCE BACKED",
    "RECOVERED_GLOBAL",
    "RECOVERED",
    "HIGH",
    "REVIEW",
)

SUPPORTED_INFERENCE_CAP = CONFIDENCE_SCORE["SUPPORTED INFERENCE"]
UNRESOLVED_SCORE = CONFIDENCE_SCORE["UNRESOLVED"]


class CorrectnessError(Exception):
    """Base error for the correctness oracle."""


class PolicyError(CorrectnessError):
    """Malformed or unusable correctness policy; always fails closed."""


class DiffError(CorrectnessError):
    """Candidate diff could not be computed deterministically."""


# ---------------------------------------------------------------------------
# Policy loading and validation (fail closed)


def _require(cond: bool, message: str) -> None:
    if not cond:
        raise PolicyError(message)


def validate_policy(policy: Any) -> dict:
    _require(isinstance(policy, dict), "correctness policy must be an object")
    _require(
        policy.get("schema") == POLICY_SCHEMA,
        f"correctness policy schema must be {POLICY_SCHEMA}",
    )
    domains = policy.get("domains")
    _require(isinstance(domains, dict) and domains, "policy.domains must be an object")
    kinds = set()
    for name, spec in domains.items():
        _require(isinstance(name, str) and name, "domain names must be non-empty")
        _require(isinstance(spec, dict), f"domain {name} spec must be an object")
        kind = spec.get("kind")
        _require(
            kind in {"fidelity", "non_fidelity", "evaluator"},
            f"domain {name} kind must be fidelity|non_fidelity|evaluator",
        )
        kinds.add(kind)
    _require("evaluator" in kinds, "policy must define an evaluator domain")

    classification = policy.get("classification")
    _require(
        isinstance(classification, list) and classification,
        "policy.classification must be a non-empty list",
    )
    for rule in classification:
        _require(isinstance(rule, dict), "classification rules must be objects")
        dom = rule.get("domain")
        _require(dom in domains, f"classification rule references unknown domain {dom!r}")
        globs = rule.get("globs")
        _require(
            isinstance(globs, list) and globs and all(isinstance(g, str) and g for g in globs),
            f"classification rule for {dom} needs non-empty globs",
        )

    unclassified = policy.get("unclassified_domain")
    _require(
        isinstance(unclassified, str) and unclassified in domains,
        "policy.unclassified_domain must reference a domain",
    )
    _require(
        domains[unclassified]["kind"] == "non_fidelity",
        "policy.unclassified_domain must be non_fidelity",
    )
    code_roots = policy.get("unclassified_code_roots", [])
    _require(
        isinstance(code_roots, list)
        and all(isinstance(r, str) and r.endswith("/") for r in code_roots),
        "policy.unclassified_code_roots must be path prefixes ending in '/'",
    )

    oracles = policy.get("l2_oracles", {})
    _require(isinstance(oracles, dict), "policy.l2_oracles must be an object")
    for domain, refs in oracles.items():
        _require(
            domain in domains and domains[domain]["kind"] == "fidelity",
            f"l2_oracles key {domain!r} must be a fidelity domain",
        )
        _require(isinstance(refs, list), f"l2_oracles[{domain}] must be a list")
        for ref in refs:
            kind, _, arg = str(ref).partition(":")
            _require(
                kind in ORACLE_KINDS and arg,
                f"malformed oracle ref {ref!r} for domain {domain}",
            )

    evaluator = domains.get("evaluator")
    if evaluator is None or domains["evaluator"].get("requires_independent_verification"):
        ev = policy.get("evaluator")
        _require(
            isinstance(ev, dict)
            and ev.get("requires_independent_verification") is True,
            "policy.evaluator.requires_independent_verification must be true "
            "while an evaluator domain exists (evaluator changes require "
            "independent verification)",
        )

    ceilings = policy.get("ceilings", {})
    _require(isinstance(ceilings, dict), "policy.ceilings must be an object")
    for key in ("confirmed_labels", "unresolved_labels", "non_global_provenance_markers"):
        _require(
            isinstance(ceilings.get(key), list),
            f"policy.ceilings.{key} must be a list",
        )
    return policy


def load_policy(path: Path | str) -> dict:
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PolicyError(f"correctness policy unreadable: {path}: {exc}") from exc
    try:
        policy = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PolicyError(f"correctness policy is not valid JSON: {path}: {exc}") from exc
    policy = validate_policy(policy)
    policy["_policy_sha256"] = hashlib.sha256(raw.encode()).hexdigest()
    return policy


def policy_sha256(policy: dict) -> str:
    if "_policy_sha256" in policy:
        return policy["_policy_sha256"]
    canonical = json.dumps(
        {k: v for k, v in policy.items() if not k.startswith("_")},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


# ---------------------------------------------------------------------------
# L0: deterministic path classification


def normalize_path(path: str) -> str:
    return str(path).strip().lstrip("./")


def match_domains(path: str, policy: dict) -> list[str]:
    """Return every domain whose globs match path (set union, deterministic)."""
    lowered = normalize_path(path).lower()
    matched = []
    for rule in policy["classification"]:
        for glob in rule["globs"]:
            if fnmatch.fnmatchcase(lowered, glob.lower()):
                matched.append(rule["domain"])
                break
    return matched


def fidelity_domains(policy: dict) -> list[str]:
    return sorted(
        name
        for name, spec in policy["domains"].items()
        if spec["kind"] == "fidelity"
    )


def classify_paths(paths: list[str], policy: dict) -> dict:
    """Deterministically classify candidate diff paths into requirements."""
    domains: dict[str, list[str]] = {}
    unclassified: list[str] = []
    for raw in sorted({normalize_path(p) for p in paths if normalize_path(p)}):
        matched = match_domains(raw, policy)
        if not matched:
            matched = [policy["unclassified_domain"]]
            if any(
                raw.startswith(root)
                for root in policy.get("unclassified_code_roots", [])
            ):
                unclassified.append(raw)
        for dom in matched:
            domains.setdefault(dom, []).append(raw)

    l2_domains = sorted(d for d in domains if policy["domains"][d]["kind"] == "fidelity")
    oracle_map = policy.get("l2_oracles", {})
    l2_oracles = {d: list(oracle_map.get(d, [])) for d in l2_domains}
    no_oracle_domains = sorted(d for d in l2_domains if not oracle_map.get(d))

    evaluator_paths = sorted(
        p for dom, ps in domains.items() if policy["domains"][dom]["kind"] == "evaluator" for p in ps
    )
    requires_independent = bool(evaluator_paths)

    required = ["L0", "L1"]
    if l2_domains:
        required.append("L2")
    l3_reasons: list[str] = []
    if requires_independent:
        l3_reasons.append(
            "candidate modifies correctness/evaluator surface; independent verification required"
        )
    for dom in no_oracle_domains:
        l3_reasons.append(f"fidelity domain {dom} has no objective L2 oracle")
    for path in unclassified:
        l3_reasons.append(f"unclassified code path {path}")
    if l3_reasons:
        required.append("L3")

    return {
        "domains": {d: sorted(ps) for d, ps in sorted(domains.items())},
        "unclassified": unclassified,
        "l2_domains": l2_domains,
        "l2_oracles": l2_oracles,
        "no_oracle_domains": no_oracle_domains,
        "evaluator_paths": evaluator_paths,
        "requires_independent_verification": requires_independent,
        "required_levels": required,
        "l3_reasons": sorted(set(l3_reasons)),
    }


# ---------------------------------------------------------------------------
# Candidate diff computation


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise DiffError(
            f"git {' '.join(args)} failed in {repo}: {(proc.stderr or proc.stdout).strip()}"
        )
    return proc.stdout


def require_sha(sha: str) -> str:
    if not isinstance(sha, str) or len(sha) != 40 or any(c not in SHA40 for c in sha):
        raise CorrectnessError("exact lowercase 40-character SHA required")
    return sha


def merge_base(repo: Path, base_ref: str, sha: str) -> str:
    out = _git(repo, "merge-base", base_ref, sha).strip()
    if len(out) != 40:
        raise DiffError(
            f"cannot determine merge base of {base_ref} and {sha} in {repo}"
        )
    return out


def changed_paths(repo: Path, sha: str, base_ref: str) -> tuple[str, list[str]]:
    """Committed diff paths between merge-base and the candidate SHA."""
    repo = Path(repo)
    base = merge_base(repo, base_ref, sha)
    out = _git(repo, "diff", "--name-only", base, sha)
    return base, sorted(p for p in out.splitlines() if p.strip())


def worktree_paths(repo: Path, base_ref: str = "HEAD") -> tuple[str, list[str]]:
    """Working-tree diff paths (fast gate): committed delta plus uncommitted."""
    repo = Path(repo)
    head = _git(repo, "rev-parse", "HEAD").strip()
    base = merge_base(repo, base_ref, head) if base_ref != "HEAD" else head
    out = _git(repo, "diff", "--name-only", base)
    staged = _git(repo, "diff", "--cached", "--name-only")
    untracked = _git(repo, "ls-files", "-o", "--exclude-standard")
    paths = {
        p.strip()
        for chunk in (out, staged, untracked)
        for p in chunk.splitlines()
        if p.strip()
    }
    return base, sorted(paths)


def build_plan(
    policy: dict,
    *,
    sha: str | None,
    ref: str | None,
    base_ref: str | None,
    merge_base_sha: str | None,
    paths: list[str],
) -> dict:
    classification = classify_paths(paths, policy)
    plan = {
        "schema": PLAN_SCHEMA,
        "policy_id": policy.get("policy_id"),
        "policy_sha256": policy_sha256(policy),
        "sha": sha,
        "ref": ref,
        "base_ref": base_ref,
        "merge_base": merge_base_sha,
        "changed_paths": sorted(paths),
        "path_count": len(paths),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    plan.update(classification)
    return plan


# ---------------------------------------------------------------------------
# Evidence ceilings (Global 2017 evidence outranks current/later JP)


def cap_confidence(label: str | None, provenance: str | None, policy: dict) -> dict:
    """Cap a claimed evidence label by provenance.

    current_jp/later_jp provenance can never exceed SUPPORTED INFERENCE for
    Global May 25 2017 target behavior, and MEDIUM/LOW/VERSION SENSITIVE/
    UNRESOLVED labels are never upgraded to CONFIRMED ORIGINAL.
    """
    normalized = str(label or "UNRESOLVED").strip().upper().replace("_", " ")
    score = CONFIDENCE_SCORE.get(normalized, UNRESOLVED_SCORE)
    markers = [
        str(m).lower()
        for m in policy.get("ceilings", {}).get("non_global_provenance_markers", [])
    ]
    prov = str(provenance or "").lower()
    capped_by_provenance = any(marker and marker in prov for marker in markers)
    if capped_by_provenance:
        score = min(score, SUPPORTED_INFERENCE_CAP)
    confirmed = score >= CONFIDENCE_SCORE["CONFIRMED ORIGINAL"]
    return {
        "label": normalized or "UNRESOLVED",
        "provenance": provenance or "",
        "score": score,
        "capped_by_non_global_provenance": capped_by_provenance,
        "confirmed_original": confirmed and not capped_by_provenance,
    }


def _canonical_provenance_label(value: str) -> str:
    upper = str(value).upper()
    for label in PROVENANCE_LABEL_ORDER:
        if label in upper:
            return label.replace("_", " ")
    return "UNCLASSIFIED"


def provenance_ceilings(source: str, check: str, payload: Any, policy: dict) -> list[dict]:
    """Extract explicit evidence ceilings from a truth record's provenance.

    Every non-confirmed aspect is preserved verbatim: UNRESOLVED stays
    UNRESOLVED, and current-JP sourced CONFIRMED labels are reported capped
    at SUPPORTED INFERENCE.
    """
    out: list[dict] = []
    if not isinstance(payload, dict):
        return out
    confirmed = {
        str(x).upper()
        for x in policy.get("ceilings", {}).get("confirmed_labels", [])
    }
    for aspect in sorted(payload):
        raw = payload[aspect]
        if not isinstance(raw, str):
            continue
        canonical = _canonical_provenance_label(raw)
        capped = cap_confidence(canonical, raw, policy)
        is_confirmed = canonical in confirmed and capped["confirmed_original"]
        if not is_confirmed:
            out.append(
                {
                    "source": source,
                    "check": check,
                    "aspect": str(aspect),
                    "raw": raw,
                    "canonical": canonical,
                    "score": capped["score"],
                    "capped_by_non_global_provenance": capped[
                        "capped_by_non_global_provenance"
                    ],
                    "blocking": False,
                }
            )
    return out


# ---------------------------------------------------------------------------
# Truth-store collection (reuses existing stores; no parallel truth)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "select 1 from sqlite_master where type='table' and name=?", (table,)
    ).fetchone()
    return row is not None


def _safe_connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def _behavior_rows(conn, sha):
    if not _table_exists(conn, "behavior_trace_checks"):
        return []
    return [
        dict(r)
        for r in conn.execute(
            """select id,sha,objective_id,checkpoint,expected_json,observed_json,
                 divergence_json,provenance_json,verdict,created_at
                 from behavior_trace_checks where sha=? order by id""",
            (sha,),
        )
    ]


def _visual_rows(conn, sha):
    if not _table_exists(conn, "visual_truth_checks"):
        return []
    return [
        dict(r)
        for r in conn.execute(
            """select id,sha,checkpoint,objective_id,reference_artifact,
                 observed_artifact,viewport_json,device_json,metrics_json,
                 verdict,created_at
                 from visual_truth_checks where sha=? order by id""",
            (sha,),
        )
    ]


def _device_rows(conn, sha):
    if not _table_exists(conn, "device_proofs"):
        return []
    return [
        dict(r)
        for r in conn.execute(
            """select id,sha,apk_sha256,checkpoint,status,artifact_path,note,
                 created_at from device_proofs where sha=? order by id""",
            (sha,),
        )
    ]


def _verification_rows(conn, sha):
    if not _table_exists(conn, "verification"):
        return []
    return [
        dict(r)
        for r in conn.execute(
            """select rowid as id,ref,sha,mode,status,duration_sec,ran_at,details
                 from verification where sha=? order by ran_at""",
            (sha,),
        )
    ]


def _row_fingerprint(kind: str, row: dict) -> str:
    key = {
        "kind": kind,
        "checkpoint": row.get("checkpoint"),
        "verdict": row.get("verdict") or row.get("status"),
        "sha": row.get("sha"),
        "created_at": row.get("created_at") or row.get("ran_at"),
        "mode": row.get("mode"),
        "artifact": row.get("observed_artifact") or row.get("artifact_path"),
        "objective": row.get("objective_id"),
    }
    return hashlib.sha256(
        json.dumps(key, sort_keys=True).encode()
    ).hexdigest()


def collect_truth(db_paths: list[Path], sha: str) -> dict:
    """Collect existing truth-store records for an exact SHA.

    Reads behavior_trace_checks, visual_truth_checks, device_proofs and
    verification from every supplied database (isolated farm DBs plus the
    canonical control DB) and dedupes records that were merged verbatim.
    """
    truth = {"behavior": [], "visual": [], "device": [], "verification": []}
    seen: set[str] = set()
    for db_path in db_paths:
        db_path = Path(db_path)
        if not db_path.is_file():
            continue
        conn = _safe_connect(db_path)
        try:
            for kind, rows in (
                ("behavior", _behavior_rows(conn, sha)),
                ("visual", _visual_rows(conn, sha)),
                ("device", _device_rows(conn, sha)),
                ("verification", _verification_rows(conn, sha)),
            ):
                for row in rows:
                    fp = _row_fingerprint(kind, row)
                    if fp in seen:
                        continue
                    seen.add(fp)
                    row["_source_db"] = str(db_path)
                    truth[kind].append(row)
        finally:
            conn.close()
    return truth


def _parse_json(raw: Any) -> Any:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if raw is not None else {}


# ---------------------------------------------------------------------------
# L1-L3 evaluation


def _lane(outcomes: dict, name: str) -> dict:
    lanes = outcomes.get("lanes")
    if not isinstance(lanes, dict):
        raise CorrectnessError("outcomes.lanes must be an object")
    lane = lanes.get(name)
    return lane if isinstance(lane, dict) else {}


def _lane_pass(lane: dict) -> bool:
    return bool(lane.get("ran")) and int(lane.get("rc", 1) or 0) == 0


def _oracle_check(
    ref: str, domain: str, outcomes: dict, truth: dict, policy: dict
) -> dict:
    """Evaluate one configured oracle ref against run outcomes + truth."""
    kind, _, arg = ref.partition(":")
    check = {"oracle": ref, "domain": domain, "kind": kind, "outcome": None}
    if kind == "e2e":
        e2e = _lane(outcomes, "e2e")
        specs = e2e.get("specs")
        if not e2e.get("ran"):
            check["outcome"] = "not_run"
            check["reason"] = "e2e lane did not execute"
        elif specs is None:
            check["outcome"] = "missing"
            check["reason"] = "e2e spec list not recorded in outcomes"
        elif arg not in specs:
            check["outcome"] = "skipped"
            check["reason"] = "spec not present at candidate SHA"
        else:
            check["outcome"] = "PASS" if _lane_pass(e2e) else "FAIL"
        return check
    if kind == "hydration":
        hyd = _lane(outcomes, "hydration")
        if not hyd.get("ran"):
            check["outcome"] = "not_run"
            check["reason"] = "hydration lane did not execute"
        else:
            check["outcome"] = "PASS" if hyd.get("rc", 0) in (0, None) else "FAIL"
        return check
    if kind == "behavior_trace":
        records = [
            r for r in truth["behavior"] if r.get("checkpoint") == arg
        ]
        if not records:
            if _lane(outcomes, "behavior").get("ran"):
                check["outcome"] = "missing"
                check["reason"] = (
                    "behavior lane ran but produced no truth record for "
                    f"checkpoint {arg}"
                )
            else:
                check["outcome"] = "not_run"
                check["reason"] = "behavior checkpoint lane did not execute"
            return check
        latest = records[-1]
        check["outcome"] = latest.get("verdict") or "FAIL"
        check["record_id"] = latest.get("id")
        check["record"] = latest
        return check
    if kind == "visual_truth":
        records = [r for r in truth["visual"] if r.get("checkpoint") == arg]
        if not records:
            if _lane(outcomes, "e2e").get("ran"):
                check["outcome"] = "missing"
                check["reason"] = (
                    f"no visual truth record for checkpoint {arg} at this SHA"
                )
            else:
                check["outcome"] = "not_run"
                check["reason"] = "e2e lane did not execute"
            return check
        latest = records[-1]
        check["outcome"] = latest.get("verdict") or "FAIL"
        check["record_id"] = latest.get("id")
        check["record"] = latest
        return check
    if kind == "device":
        records = [r for r in truth["device"] if r.get("checkpoint") == arg]
        if not records:
            check["outcome"] = "missing"
            check["reason"] = f"no device proof for checkpoint {arg} at this SHA"
            return check
        latest = records[-1]
        check["outcome"] = latest.get("status") or "FAIL"
        check["record_id"] = latest.get("id")
        check["record"] = latest
        return check
    raise CorrectnessError(f"unknown oracle kind in {ref!r}")


def _verdict_rank(tier: str | None) -> int:
    return LEVELS.index(tier) if tier in LEVELS else -1


def evaluate(
    plan: dict,
    outcomes: dict,
    truth: dict,
    policy: dict,
    *,
    attestations: list[dict] | None = None,
    run_id: str | None = None,
    now: str | None = None,
) -> dict:
    """Evaluate the four-level ladder and build an exact-SHA receipt."""
    if not isinstance(plan, dict) or plan.get("schema") != PLAN_SCHEMA:
        raise CorrectnessError("plan is missing or malformed")
    if not isinstance(outcomes, dict):
        raise CorrectnessError("outcomes must be an object")
    sha = require_sha(str(plan.get("sha") or outcomes.get("sha") or ""))
    ref = plan.get("ref") or outcomes.get("ref") or ""
    attestations = attestations or []

    l0 = {
        "ran": True,
        "verdict": "PASS",
        "detail": {
            "policy_sha256": plan.get("policy_sha256"),
            "base_ref": plan.get("base_ref"),
            "merge_base": plan.get("merge_base"),
            "path_count": plan.get("path_count"),
            "domains": plan.get("domains", {}),
            "unclassified": plan.get("unclassified", []),
        },
    }

    # -- L1: build + focused deterministic tests -----------------------------
    skips: list[dict] = []
    failures: list[str] = []
    blocks: list[str] = []
    ceilings: list[dict] = []
    evidence: list[dict] = []

    l1_checks = []
    unit = _lane(outcomes, "unit")
    l1_checks.append(
        {
            "check": "unit-tests",
            "ran": bool(unit.get("ran")),
            "outcome": "PASS" if _lane_pass(unit) else ("FAIL" if unit.get("ran") else "not_run"),
            "detail": {"path": unit.get("path"), "rc": unit.get("rc")},
        }
    )
    build = _lane(outcomes, "build")
    if not build and _lane(outcomes, "e2e").get("ran"):
        build = dict(_lane(outcomes, "e2e"))
        build["_subsumed"] = True
    l1_checks.append(
        {
            "check": "build",
            "ran": bool(build.get("ran")),
            "outcome": "PASS" if _lane_pass(build) else ("FAIL" if build.get("ran") else "not_run"),
            "detail": {
                "rc": build.get("rc"),
                "note": "build runs inside the local E2E lane" if build.get("_subsumed") else None,
            },
        }
    )
    perf = _lane(outcomes, "performance")
    perf_required = bool(perf.get("required"))
    if not perf_required and not perf.get("ran"):
        skips.append(
            {
                "check": "performance",
                "reason": "performance verification not requested for this run",
            }
        )
    else:
        l1_checks.append(
            {
                "check": "performance",
                "gating": perf_required,
                "ran": bool(perf.get("ran")),
                "outcome": "PASS" if _lane_pass(perf) else ("FAIL" if perf.get("ran") else "not_run"),
                "detail": {"rc": perf.get("rc"), "control_rc": perf.get("control_rc")},
            }
        )
    l1_verdict = (
        "PASS"
        if all(c["outcome"] == "PASS" for c in l1_checks if c.get("gating", True))
        else "FAIL"
    )
    l1 = {"ran": True, "verdict": l1_verdict, "checks": l1_checks}

    # Existing candidate gates: hydration, E2E and the behavior-checkpoint
    # lane run for every candidate and are the execution substrate for L2
    # oracles. A lane that ran and failed is a blocking failure regardless of
    # which domains the diff touched.
    gate_checks = []
    for name in ("hydration", "e2e", "behavior"):
        lane = _lane(outcomes, name)
        ran = bool(lane.get("ran"))
        rc = lane.get("rc")
        outcome = (
            "PASS" if ran and rc in (0, None) else ("FAIL" if ran else "not_run")
        )
        gate_checks.append(
            {"check": name, "ran": ran, "rc": rc, "outcome": outcome}
        )
        if outcome == "FAIL":
            failures.append(f"{name} lane failed (rc={rc})")
        elif outcome == "not_run":
            skips.append(
                {"check": f"gate:{name}", "reason": "lane did not execute"}
            )
    l1["gates"] = gate_checks

    # -- L2: fidelity oracles -------------------------------------------------
    required_domains = list(plan.get("l2_domains") or [])
    oracle_map = plan.get("l2_oracles") or {}
    l2_checks: list[dict] = []
    for domain in sorted(required_domains):
        for ref in oracle_map.get(domain, []):
            l2_checks.append(_oracle_check(ref, domain, outcomes, truth, policy))

    # -- L3 evaluation inputs -------------------------------------------------
    l3_reasons = list(plan.get("l3_reasons") or [])

    for check in l2_checks:
        outcome = check["outcome"]
        record = check.get("record")
        if outcome == "skipped":
            skips.append({"check": check["oracle"], "reason": check["reason"]})
            continue
        if outcome == "FAIL":
            failures.append(
                f"L2 oracle {check['oracle']} (domain {check['domain']}) reported FAIL"
            )
        elif outcome in {"not_run", "missing"}:
            blocks.append(
                f"required L2 oracle {check['oracle']} (domain {check['domain']}): {check['reason']}"
            )
        elif outcome == "REVIEW":
            ceilings.append(
                {
                    "source": "visual_truth",
                    "check": check["oracle"],
                    "aspect": "verdict",
                    "raw": "REVIEW",
                    "canonical": "REVIEW",
                    "score": None,
                    "capped_by_non_global_provenance": False,
                    "blocking": False,
                    "note": "structural pass; historical pixel truth remains under human review",
                }
            )
        elif outcome == "PARTIAL":
            ceilings.append(
                {
                    "source": "device",
                    "check": check["oracle"],
                    "aspect": "status",
                    "raw": "PARTIAL",
                    "canonical": "PARTIAL",
                    "score": None,
                    "capped_by_non_global_provenance": False,
                    "blocking": False,
                    "note": "device proof only partially verified",
                }
            )
        if record is not None:
            prov = _parse_json(record.get("provenance_json"))
            if not prov:
                prov = _parse_json(record.get("metrics_json")).get(
                    "structural_provenance", {}
                )
            ceilings.extend(
                provenance_ceilings(
                    check["kind"], check["oracle"], prov, policy
                )
            )

    # Additional truth evidence for this exact SHA. Only the latest record
    # per checkpoint can gate: an older FAIL superseded by a PASS at the same
    # checkpoint is history, not a current blocker.
    cited = {id(c.get("record")) for c in l2_checks if c.get("record")}
    latest_by_checkpoint: dict[tuple[str, str], dict] = {}
    for kind, key in (("behavior", "verdict"), ("visual", "verdict"), ("device", "status")):
        for record in truth[kind]:
            ck = (kind, str(record.get("checkpoint")))
            if ck not in latest_by_checkpoint or (record.get("id") or 0) > (
                latest_by_checkpoint[ck].get("id") or 0
            ):
                latest_by_checkpoint[ck] = record
    for (kind, checkpoint), record in sorted(latest_by_checkpoint.items()):
        if kind == "behavior":
            prov = _parse_json(record.get("provenance_json"))
            ceilings.extend(
                provenance_ceilings(
                    "behavior_trace",
                    f"behavior_trace:{checkpoint}",
                    prov,
                    policy,
                )
            )
            if record.get("verdict") == "FAIL" and id(record) not in cited:
                failures.append(
                    f"behavior truth record {record.get('id')} "
                    f"({checkpoint}) is FAIL at this SHA"
                )
        elif kind == "visual":
            if record.get("verdict") == "FAIL" and id(record) not in cited:
                failures.append(
                    f"visual truth record {record.get('id')} "
                    f"({checkpoint}) is FAIL at this SHA"
                )
            elif record.get("verdict") == "REVIEW" and id(record) not in cited:
                ceilings.append(
                    {
                        "source": "visual_truth",
                        "check": f"visual_truth:{checkpoint}",
                        "aspect": "verdict",
                        "raw": "REVIEW",
                        "canonical": "REVIEW",
                        "score": None,
                        "capped_by_non_global_provenance": False,
                        "blocking": False,
                        "note": "structural pass; historical pixel truth remains under human review",
                    }
                )
        elif kind == "device":
            status = record.get("status")
            if status == "FAIL":
                failures.append(
                    f"device proof {record.get('id')} ({checkpoint}) is FAIL at this SHA"
                )
            elif status == "PARTIAL" and id(record) not in cited:
                ceilings.append(
                    {
                        "source": "device",
                        "check": f"device:{checkpoint}",
                        "aspect": "status",
                        "raw": "PARTIAL",
                        "canonical": "PARTIAL",
                        "score": None,
                        "capped_by_non_global_provenance": False,
                        "blocking": False,
                    }
                )

    for kind in ("behavior", "visual", "device", "verification"):
        for record in truth[kind]:
            entry = {
                "system": kind,
                "id": record.get("id"),
                "checkpoint": record.get("checkpoint"),
                "verdict": record.get("verdict") or record.get("status"),
                "sha": record.get("sha"),
                "created_at": record.get("created_at") or record.get("ran_at"),
                "source_db": record.get("_source_db"),
            }
            if kind == "verification":
                entry["mode"] = record.get("mode")
                entry["ref"] = record.get("ref")
            evidence.append(entry)

    # Lane failures are blocking failures regardless of domain coverage.
    for c in l1_checks:
        if not c.get("gating", True):
            continue
        if c["outcome"] == "FAIL":
            failures.append(f"L1 check {c['check']} failed")
        elif c["outcome"] == "not_run":
            blocks.append(f"required L1 check {c['check']} did not run")
    merge = outcomes.get("lanes", {}).get("merge", {})
    if merge:
        for name in sorted(merge):
            if isinstance(merge[name], dict) and merge[name].get("ran") and not merge[name].get("ok"):
                failures.append(f"{name} truth merge failed closed")

    # -- L3: human review when evidence is ambiguous or evaluator changed ----
    l3_required = bool(l3_reasons)
    valid_attestation = None
    for att in attestations:
        reviewer = str(att.get("reviewer") or "").strip()
        note = str(att.get("note") or "").strip()
        if reviewer and note:
            valid_attestation = {"reviewer": reviewer, "note": note}
            break
    l3 = {
        "required": l3_required,
        "reasons": sorted(set(l3_reasons)),
        "attestation": valid_attestation,
        "verdict": (
            "PASS"
            if not l3_required
            else ("PASS" if valid_attestation else "BLOCKED")
        ),
    }
    if l3_required and not valid_attestation:
        blocks.extend(
            f"L3 review required: {reason}" for reason in l3["reasons"]
        )

    # -- verdict + tier -------------------------------------------------------
    # FAIL: a check that executed reported a failure (lane rc, oracle FAIL,
    # truth record FAIL, merge failure). BLOCKED: verification could not be
    # completed - required oracle evidence missing/not run, or L3 human
    # review still pending. Neither may be auto-promoted; both exit nonzero.
    missing_oracles = [
        c for c in l2_checks if c["outcome"] in {"not_run", "missing"}
    ]
    l2_clean = not missing_oracles and not any(
        c["outcome"] == "FAIL" for c in l2_checks
    )
    l2_attained = bool(l2_checks) or bool(
        truth["behavior"] or truth["visual"]
    )

    if failures:
        verdict = "FAIL"
    elif blocks:
        verdict = "BLOCKED"
    else:
        verdict = "PASS"

    # The same oracle (e.g. behavior_trace:playable-field-battle-reward-return)
    # can be required by several domains; report each distinct ceiling once.
    deduped_ceilings: list[dict] = []
    seen_ceilings: set[tuple] = set()
    for c in ceilings:
        key = (
            c.get("source"),
            c.get("check"),
            c.get("aspect"),
            c.get("raw"),
            c.get("canonical"),
        )
        if key in seen_ceilings:
            continue
        seen_ceilings.add(key)
        deduped_ceilings.append(c)

    if verdict == "FAIL":
        tier = "L1" if l1_verdict == "PASS" else "L0"
    elif verdict == "BLOCKED":
        if l1_verdict != "PASS":
            tier = "L0"
        elif missing_oracles:
            tier = "L1"
        elif l2_attained and l2_clean:
            tier = "L2"
        else:
            tier = "L1"
    elif l3_required and valid_attestation:
        tier = "L3"
    elif l2_attained:
        tier = "L2"
    else:
        tier = "L1"

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "receipt_version": RECEIPT_VERSION,
        "run_id": run_id,
        "sha": sha,
        "ref": ref,
        "policy_id": policy.get("policy_id"),
        "policy_sha256": policy_sha256(policy),
        "verdict": verdict,
        "tier": tier,
        "required_levels": plan.get("required_levels", ["L0", "L1"]),
        "levels": {"L0": l0, "L1": l1, "L2": {
            "required": bool(required_domains),
            "domains": required_domains,
            "ran": bool(l2_checks) or not required_domains,
            "verdict": (
                "PASS"
                if not missing_oracles and not any(c["outcome"] == "FAIL" for c in l2_checks)
                else "FAIL"
            ),
            "checks": [
                {k: v for k, v in c.items() if k != "record"} for c in l2_checks
            ],
        }, "L3": l3},
        "requires_independent_verification": bool(
            plan.get("requires_independent_verification")
        ),
        "evaluator_paths": plan.get("evaluator_paths", []),
        "evidence": evidence,
        "trace": _trace_summary(truth),
        "visual": _visual_summary(truth),
        "device": _device_summary(truth),
        "verification": _verification_summary(truth),
        "skips": skips,
        "failures": sorted(set(failures)),
        "blocking_failures": sorted(set(failures + blocks)),
        "unresolved_ceilings": deduped_ceilings,
        "outcomes": outcomes.get("lanes", {}),
        "created_at": now or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    receipt["receipt_sha256"] = hashlib.sha256(
        json.dumps(
            {k: v for k, v in receipt.items() if k != "receipt_sha256"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return receipt


def _trace_summary(truth: dict) -> dict:
    out = []
    for r in truth["behavior"]:
        div = _parse_json(r.get("divergence_json"))
        out.append(
            {
                "id": r.get("id"),
                "checkpoint": r.get("checkpoint"),
                "verdict": r.get("verdict"),
                "event_mismatches": len(div.get("event_mismatches") or []),
                "final_state_match": div.get("final_state_match"),
                "created_at": r.get("created_at"),
            }
        )
    return {"records": out, "count": len(out)}


def _visual_summary(truth: dict) -> dict:
    out = [
        {
            "id": r.get("id"),
            "checkpoint": r.get("checkpoint"),
            "verdict": r.get("verdict"),
            "reference": r.get("reference_artifact"),
            "observed": r.get("observed_artifact"),
            "created_at": r.get("created_at"),
        }
        for r in truth["visual"]
    ]
    return {"records": out, "count": len(out)}


def _device_summary(truth: dict) -> dict:
    out = [
        {
            "id": r.get("id"),
            "checkpoint": r.get("checkpoint"),
            "status": r.get("status"),
            "apk_sha256": r.get("apk_sha256"),
            "created_at": r.get("created_at"),
        }
        for r in truth["device"]
    ]
    return {"records": out, "count": len(out)}


def _verification_summary(truth: dict) -> dict:
    out = [
        {
            "ref": r.get("ref"),
            "mode": r.get("mode"),
            "status": r.get("status"),
            "ran_at": r.get("ran_at"),
            "details": r.get("details"),
        }
        for r in truth["verification"]
    ]
    return {"records": out, "count": len(out)}


# ---------------------------------------------------------------------------
# Receipt persistence (exact-SHA keyed)


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists correctness_receipts(
          id integer primary key autoincrement,
          sha text not null,
          ref text not null,
          run_id text,
          verdict text not null,
          tier text,
          receipt_json text not null,
          receipt_sha256 text not null,
          created_at text not null,
          created_epoch real not null
        );
        create index if not exists correctness_receipts_sha_idx
          on correctness_receipts(sha,id);
        """
    )
    conn.commit()


def record_receipt(conn: sqlite3.Connection, receipt: dict) -> int:
    ensure_schema(conn)
    sha = require_sha(str(receipt.get("sha") or ""))
    verdict = str(receipt.get("verdict") or "")
    if verdict not in VERDICTS:
        raise CorrectnessError(f"invalid receipt verdict {verdict!r}")
    tier = receipt.get("tier")
    if tier is not None and tier not in LEVELS:
        raise CorrectnessError(f"invalid receipt tier {tier!r}")
    stamp = receipt.get("created_at") or datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )
    epoch = datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
    cur = conn.execute(
        """insert into correctness_receipts(
             sha,ref,run_id,verdict,tier,receipt_json,receipt_sha256,
             created_at,created_epoch
           ) values(?,?,?,?,?,?,?,?,?)""",
        (
            sha,
            str(receipt.get("ref") or ""),
            receipt.get("run_id"),
            verdict,
            tier,
            json.dumps(receipt, sort_keys=True),
            str(receipt.get("receipt_sha256") or ""),
            stamp,
            epoch,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def latest_receipt(conn: sqlite3.Connection, sha: str | None = None):
    ensure_schema(conn)
    if sha:
        row = conn.execute(
            """select id,sha,ref,run_id,verdict,tier,receipt_json,receipt_sha256,
                 created_at from correctness_receipts where sha=?
                 order by id desc limit 1""",
            (sha,),
        ).fetchone()
        return None if not row else _receipt_row(row)
    rows = conn.execute(
        """select r.id,r.sha,r.ref,r.run_id,r.verdict,r.tier,r.receipt_json,
             r.receipt_sha256,r.created_at
             from correctness_receipts r
             join (select sha,max(id) id from correctness_receipts group by sha) x
               on x.id=r.id order by r.sha"""
    )
    return [_receipt_row(r) for r in rows]


def _receipt_row(r) -> dict:
    return {
        "id": r[0],
        "sha": r[1],
        "ref": r[2],
        "run_id": r[3],
        "verdict": r[4],
        "tier": r[5],
        "receipt": json.loads(r[6]),
        "receipt_sha256": r[7],
        "created_at": r[8],
    }
