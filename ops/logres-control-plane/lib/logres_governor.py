from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


AUTHORITY = "ADVISORY_EXPERIMENT_ONLY_NO_SCHEDULER_DEPLOY_MERGE"

EXECUTABLE_SHADOW_CONTRACTS = {
    ("SHADOW_SCHEDULER", "top5_overlap"),
}


def shadow_executable_proposals(
    proposals: Iterable["ExperimentProposal"],
) -> list["ExperimentProposal"]:
    return [
        proposal
        for proposal in proposals
        if (proposal.source_kind, proposal.metric_name)
        in EXECUTABLE_SHADOW_CONTRACTS
    ]
VALID_DIRECTIONS = {"higher", "lower"}


@dataclass(frozen=True)
class ExperimentProposal:
    source_kind: str
    hypothesis: str
    metric_name: str
    direction: str
    baseline_value: float
    success_target: float
    rollback_threshold: float
    rollback_condition: str
    max_scope: str
    proposed_action: str
    source: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "authority": AUTHORITY,
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists governor_experiments(
          id integer primary key autoincrement,
          created_at text not null,
          source_kind text not null,
          source_json text not null,
          hypothesis text not null,
          metric_name text not null,
          direction text not null,
          baseline_value real not null,
          success_target real not null,
          rollback_threshold real not null,
          rollback_condition text not null,
          max_scope text not null,
          proposed_action text not null,
          status text not null default 'PROPOSED',
          recommendation text,
          authority text not null,
          fingerprint text not null unique
        );
        create table if not exists governor_outcomes(
          id integer primary key autoincrement,
          experiment_id integer not null,
          recorded_at text not null,
          metric_value real not null,
          guardrail_breached integer not null default 0,
          notes text not null default '',
          foreign key(experiment_id) references governor_experiments(id)
        );
        create index if not exists idx_governor_experiments_status
          on governor_experiments(status,created_at);
        create index if not exists idx_governor_outcomes_experiment
          on governor_outcomes(experiment_id,id);
        """
    )
    conn.commit()


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if math.isfinite(number) else float(default)


def _first_failed_throughput_metric(throughput: Mapping[str, Any]) -> dict | None:
    summary = throughput.get("summary") if isinstance(throughput, Mapping) else None
    if not isinstance(summary, Mapping):
        return None
    recent = summary.get("recent")
    if not isinstance(recent, Mapping):
        return None

    for window_name in ("20m", "60m"):
        window = recent.get(window_name)
        if not isinstance(window, Mapping):
            continue
        metrics = window.get("metrics")
        if not isinstance(metrics, Mapping):
            continue
        for name in sorted(metrics):
            details = metrics[name]
            if not isinstance(details, Mapping):
                continue
            if details.get("slo_status") != "FAIL":
                continue
            p95 = details.get("p95_seconds")
            target = details.get("target_seconds")
            if p95 is None or target is None:
                continue
            return {
                "window": window_name,
                "metric": name,
                "p95": _finite(p95),
                "target": _finite(target),
                "samples": int(details.get("samples") or 0),
            }
    return None


def _health_pass_fraction(health: Iterable[Mapping[str, Any]]) -> tuple[float, int]:
    rows = list(health or [])
    if not rows:
        return 1.0, 0
    passing = sum(1 for row in rows if str(row.get("status") or "").upper() == "PASS")
    return passing / len(rows), len(rows)


def _top_bottleneck(bottleneck: Mapping[str, Any]) -> dict | None:
    ranked = bottleneck.get("ranked") if isinstance(bottleneck, Mapping) else None
    if not isinstance(ranked, list) or not ranked:
        return None
    row = ranked[0]
    return dict(row) if isinstance(row, Mapping) else None


def _shadow_overlap(shadow: Mapping[str, Any]) -> tuple[int, int]:
    if not isinstance(shadow, Mapping):
        return 5, 0
    overlap = int(shadow.get("top5_overlap") or 0)
    candidates = shadow.get("shadow")
    count = len(candidates) if isinstance(candidates, list) else 0
    return overlap, count


def _proposal_key(proposal: ExperimentProposal) -> str:
    payload = {
        "source_kind": proposal.source_kind,
        "metric_name": proposal.metric_name,
        "direction": proposal.direction,
        "baseline": round(proposal.baseline_value, 3),
        "target": round(proposal.success_target, 3),
        "action": proposal.proposed_action,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def propose_experiments(observations: Mapping[str, Any]) -> list[ExperimentProposal]:
    proposals: list[ExperimentProposal] = []

    throughput = observations.get("throughput") or {}
    failed = _first_failed_throughput_metric(throughput)
    if failed and failed["samples"] > 0:
        baseline = max(0.001, failed["p95"])
        target = max(0.0, failed["target"])
        proposals.append(
            ExperimentProposal(
                source_kind="THROUGHPUT_SLO",
                hypothesis=(
                    f"A bounded scheduling or placement change can reduce "
                    f"{failed['metric']} p95 without weakening verification."
                ),
                metric_name=f"{failed['metric']}_p95_seconds",
                direction="lower",
                baseline_value=baseline,
                success_target=target,
                rollback_threshold=baseline * 1.10,
                rollback_condition=(
                    "Reject immediately if the measured p95 exceeds baseline by "
                    "10%, an open regression appears, or any verification gate is "
                    "weakened."
                ),
                max_scope=(
                    "One shadow/dry-run scheduling parameter or one exact-SHA "
                    "candidate over a single 20-minute observation window."
                ),
                proposed_action=(
                    "Test one bounded scheduling/placement variant in shadow or "
                    "verification-only mode; do not change merge authority."
                ),
                source=failed,
            )
        )

    bottleneck = observations.get("bottleneck") or {}
    top = _top_bottleneck(bottleneck)
    if top and _finite(top.get("severity")) >= 0.40:
        kind = str(top.get("kind") or "UNKNOWN")
        metrics = dict(top.get("metrics") or {})
        if kind in {"INTEGRATION", "VERIFICATION"}:
            backlog = max(
                1.0,
                _finite(metrics.get("integration_backlog"), 1.0),
            )
            proposals.append(
                ExperimentProposal(
                    source_kind=f"BOTTLENECK_{kind}",
                    hypothesis=(
                        "A single bounded integration-flow optimization can "
                        "reduce queue pressure while preserving exact-SHA gates."
                    ),
                    metric_name="integration_backlog",
                    direction="lower",
                    baseline_value=backlog,
                    success_target=max(0.0, backlog - 1.0),
                    rollback_threshold=backlog + 1.0,
                    rollback_condition=(
                        "Reject if integration backlog grows above baseline by "
                        "one, verification failures increase, or exact-SHA "
                        "single-flight guarantees change."
                    ),
                    max_scope=(
                        "One integration-flow parameter, one preflight batch, "
                        "no authority changes."
                    ),
                    proposed_action=(
                        "Run one measured integration-flow experiment using "
                        "existing verification gates and immutable candidates."
                    ),
                    source=top,
                )
            )
        elif kind == "DEPENDENCY":
            blocked = max(
                1.0,
                _finite(metrics.get("blocked_dep"), 1.0),
            )
            proposals.append(
                ExperimentProposal(
                    source_kind="BOTTLENECK_DEPENDENCY",
                    hypothesis=(
                        "A bounded dependency-proof reconciliation can reduce "
                        "false dependency blocking without bypassing ancestry."
                    ),
                    metric_name="blocked_dependency_tasks",
                    direction="lower",
                    baseline_value=blocked,
                    success_target=max(0.0, blocked - 1.0),
                    rollback_threshold=blocked + 1.0,
                    rollback_condition=(
                        "Reject if any dependency is marked satisfied without "
                        "canonical ancestry or an applied exact preflight result."
                    ),
                    max_scope=(
                        "One dependency predicate and its focused test fixture; "
                        "no queue-history rewrite."
                    ),
                    proposed_action=(
                        "Evaluate one dependency-proof rule in tests/shadow mode "
                        "before any authoritative use."
                    ),
                    source=top,
                )
            )
        elif kind == "RESOURCE":
            proposals.append(
                ExperimentProposal(
                    source_kind="BOTTLENECK_RESOURCE",
                    hypothesis=(
                        "Moving one safe verification workload to an available "
                        "remote lane can relieve local resource pressure."
                    ),
                    metric_name="recent_overload",
                    direction="lower",
                    baseline_value=1.0,
                    success_target=0.0,
                    rollback_threshold=1.0,
                    rollback_condition=(
                        "Reject on remote verification failure, private-data "
                        "exposure, or any transfer of deploy/merge authority."
                    ),
                    max_scope=(
                        "One exact-SHA verification-only workload with automatic "
                        "local fallback."
                    ),
                    proposed_action=(
                        "Run one resource-broker placement canary; retain local "
                        "authoritative E2E and merge control."
                    ),
                    source=top,
                )
            )

    zero_human = observations.get("zero_human") or {}
    if isinstance(zero_human, Mapping) and not bool(
        zero_human.get("can_continue_without_human", True)
    ):
        reasons = zero_human.get("stop_reasons") or []
        reason_codes = sorted(
            str(row.get("code"))
            for row in reasons
            if isinstance(row, Mapping) and row.get("code")
        )
        proposals.append(
            ExperimentProposal(
                source_kind="ZERO_HUMAN_STOP",
                hypothesis=(
                    "One bounded control-plane diagnostic can remove an "
                    "automation-only stop without inventing evidence or scope."
                ),
                metric_name="can_continue_without_human",
                direction="higher",
                baseline_value=0.0,
                success_target=1.0,
                rollback_threshold=0.0,
                rollback_condition=(
                    "Reject if continuation requires fabricated evidence, "
                    "authority expansion, recursive research, or bypassing a "
                    "human/account/physical-device requirement."
                ),
                max_scope=(
                    "One dry-run diagnostic or one explicit unmet contract "
                    "criterion; no automatic task fan-out."
                ),
                proposed_action=(
                    "Test the highest-confidence stop-reason remedy in dry-run "
                    "mode and measure whether runnable work returns."
                ),
                source={"reason_codes": reason_codes},
            )
        )

    health = observations.get("health") or []
    fraction, health_count = _health_pass_fraction(health)
    if health_count and fraction < 1.0:
        unhealthy = [
            {
                "subsystem": row.get("subsystem"),
                "status": row.get("status"),
                "confidence": row.get("confidence"),
            }
            for row in health
            if str(row.get("status") or "").upper() != "PASS"
        ]
        proposals.append(
            ExperimentProposal(
                source_kind="HEALTH_CONFIDENCE",
                hypothesis=(
                    "A bounded refresh/retry adjustment can increase credible "
                    "healthy-subsystem coverage without masking failures."
                ),
                metric_name="healthy_subsystem_fraction",
                direction="higher",
                baseline_value=fraction,
                success_target=min(1.0, fraction + max(0.10, 1.0 / health_count)),
                rollback_threshold=max(0.0, fraction - 0.10),
                rollback_condition=(
                    "Reject if a credible FAIL is hidden, confidence is forged, "
                    "or healthy-subsystem fraction drops by 0.10."
                ),
                max_scope=(
                    "One subsystem refresh/retry policy and one bounded health "
                    "observation window."
                ),
                proposed_action=(
                    "Test one health refresh/retry policy in a sandbox or "
                    "non-authoritative canary and preserve raw observations."
                ),
                source={"unhealthy": unhealthy, "subsystem_count": health_count},
            )
        )

    shadow = observations.get("shadow_scheduler") or {}
    overlap, candidate_count = _shadow_overlap(shadow)
    if candidate_count >= 2 and overlap < min(5, candidate_count):
        proposals.append(
            ExperimentProposal(
                source_kind="SHADOW_SCHEDULER",
                hypothesis=(
                    "One scoring-weight variant can improve agreement with "
                    "authoritative scheduling while preserving shadow-only status."
                ),
                metric_name="top5_overlap",
                direction="higher",
                baseline_value=float(overlap),
                success_target=float(min(5, overlap + 1)),
                rollback_threshold=float(max(0, overlap - 1)),
                rollback_condition=(
                    "Reject if top-5 overlap decreases, dispatch authority is "
                    "invoked, or the experiment changes authoritative ordering."
                ),
                max_scope=(
                    "Five shadow ranking decisions using one scoring-weight "
                    "change; zero dispatches."
                ),
                proposed_action=(
                    "Replay one alternate scoring-weight set against the same "
                    "READY task snapshot and compare top-5 overlap."
                ),
                source={
                    "top5_overlap": overlap,
                    "candidate_count": candidate_count,
                },
            )
        )

    deduped: dict[str, ExperimentProposal] = {}
    for proposal in proposals:
        deduped[_proposal_key(proposal)] = proposal
    return sorted(
        deduped.values(),
        key=lambda p: (p.source_kind, p.metric_name, p.hypothesis),
    )


def persist_proposals(
    conn: sqlite3.Connection,
    proposals: Iterable[ExperimentProposal],
) -> list[dict[str, Any]]:
    ensure_schema(conn)
    rows: list[dict[str, Any]] = []
    now = _now()
    for proposal in proposals:
        if proposal.direction not in VALID_DIRECTIONS:
            raise ValueError(f"invalid experiment direction: {proposal.direction}")
        fingerprint = _proposal_key(proposal)
        conn.execute(
            """
            insert or ignore into governor_experiments(
              created_at,source_kind,source_json,hypothesis,metric_name,direction,
              baseline_value,success_target,rollback_threshold,
              rollback_condition,max_scope,proposed_action,status,recommendation,
              authority,fingerprint
            ) values(?,?,?,?,?,?,?,?,?,?,?,?, 'PROPOSED',null,?,?)
            """,
            (
                now,
                proposal.source_kind,
                json.dumps(proposal.source, sort_keys=True),
                proposal.hypothesis,
                proposal.metric_name,
                proposal.direction,
                float(proposal.baseline_value),
                float(proposal.success_target),
                float(proposal.rollback_threshold),
                proposal.rollback_condition,
                proposal.max_scope,
                proposal.proposed_action,
                AUTHORITY,
                fingerprint,
            ),
        )
        row = conn.execute(
            "select * from governor_experiments where fingerprint=?",
            (fingerprint,),
        ).fetchone()
        rows.append(experiment_row(row))
    conn.commit()
    return rows


def experiment_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    item = dict(row)
    source_raw = item.pop("source_json", "{}")
    try:
        item["source"] = json.loads(source_raw)
    except json.JSONDecodeError:
        item["source"] = {}
    return item


def list_experiments(
    conn: sqlite3.Connection,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    ensure_schema(conn)
    rows = conn.execute(
        """
        select * from governor_experiments
        order by id desc
        limit ?
        """,
        (max(1, int(limit)),),
    )
    return [experiment_row(row) for row in rows]


def record_outcome(
    conn: sqlite3.Connection,
    experiment_id: int,
    *,
    metric_value: float,
    guardrail_breached: bool = False,
    notes: str = "",
) -> dict[str, Any]:
    ensure_schema(conn)
    experiment = conn.execute(
        "select * from governor_experiments where id=?",
        (int(experiment_id),),
    ).fetchone()
    if experiment is None:
        raise ValueError(f"unknown experiment: {experiment_id}")
    if experiment["status"] == "EVALUATED":
        raise ValueError("evaluated experiment is immutable")

    value = _finite(metric_value)
    conn.execute(
        """
        insert into governor_outcomes(
          experiment_id,recorded_at,metric_value,guardrail_breached,notes
        ) values(?,?,?,?,?)
        """,
        (
            int(experiment_id),
            _now(),
            value,
            1 if guardrail_breached else 0,
            str(notes or ""),
        ),
    )
    conn.execute(
        "update governor_experiments set status='MEASURED' where id=?",
        (int(experiment_id),),
    )
    conn.commit()
    return {
        "experiment_id": int(experiment_id),
        "metric_value": value,
        "guardrail_breached": bool(guardrail_breached),
        "status": "MEASURED",
        "authority": AUTHORITY,
    }


def evaluate_experiment(
    conn: sqlite3.Connection,
    experiment_id: int,
) -> dict[str, Any]:
    ensure_schema(conn)
    experiment = conn.execute(
        "select * from governor_experiments where id=?",
        (int(experiment_id),),
    ).fetchone()
    if experiment is None:
        raise ValueError(f"unknown experiment: {experiment_id}")

    outcome = conn.execute(
        """
        select * from governor_outcomes
        where experiment_id=?
        order by id desc
        limit 1
        """,
        (int(experiment_id),),
    ).fetchone()
    if outcome is None:
        raise ValueError("experiment has no recorded outcome")

    measured = float(outcome["metric_value"])
    direction = str(experiment["direction"])
    target = float(experiment["success_target"])
    rollback = float(experiment["rollback_threshold"])
    guardrail = bool(outcome["guardrail_breached"])

    if direction == "lower":
        success = measured <= target
        rollback_hit = measured >= rollback
    elif direction == "higher":
        success = measured >= target
        rollback_hit = measured <= rollback
    else:
        raise ValueError(f"invalid experiment direction: {direction}")

    recommendation = "KEEP" if success and not guardrail and not rollback_hit else "REJECT"
    conn.execute(
        """
        update governor_experiments
        set status='EVALUATED',recommendation=?
        where id=?
        """,
        (recommendation, int(experiment_id)),
    )
    conn.commit()
    return {
        "experiment_id": int(experiment_id),
        "metric_name": experiment["metric_name"],
        "baseline_value": float(experiment["baseline_value"]),
        "success_target": target,
        "rollback_threshold": rollback,
        "measured_value": measured,
        "guardrail_breached": guardrail,
        "rollback_hit": rollback_hit,
        "recommendation": recommendation,
        "authority": AUTHORITY,
        "effect": (
            "Recommendation only. The governor cannot deploy, merge, change "
            "scheduler authority, dispatch work, or auto-promote itself."
        ),
    }
