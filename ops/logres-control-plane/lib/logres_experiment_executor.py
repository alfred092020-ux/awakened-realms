from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from logres_governor import (
    EXECUTABLE_SHADOW_CONTRACTS,
    evaluate_experiment,
    record_outcome,
)
from logres_optimizer import score_ready_tasks
from logres_shadow_scheduler import score_candidates


AUTHORITY = "SHADOW_EXPERIMENT_EXECUTOR_NO_DISPATCH_NO_DEPLOY_NO_MERGE"

VARIANTS = (
    ("duration_light", {"duration": 0.75, "cost": 1.0, "conflict": 1.0, "evidence": 1.0, "failure": 1.0}),
    ("duration_heavy", {"duration": 1.25, "cost": 1.0, "conflict": 1.0, "evidence": 1.0, "failure": 1.0}),
    ("risk_light", {"duration": 1.0, "cost": 1.0, "conflict": 0.75, "evidence": 0.75, "failure": 0.75}),
    ("risk_heavy", {"duration": 1.0, "cost": 1.0, "conflict": 1.25, "evidence": 1.25, "failure": 1.25}),
)


@dataclass(frozen=True)
class ShadowVariantResult:
    name: str
    weights: dict[str, float]
    top5_overlap: int
    order: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "weights": dict(self.weights),
            "top5_overlap": self.top5_overlap,
            "order": list(self.order),
        }


def _experiment(conn: sqlite3.Connection, experiment_id: int) -> sqlite3.Row:
    row = conn.execute(
        "select * from governor_experiments where id=?",
        (int(experiment_id),),
    ).fetchone()
    if row is None:
        raise ValueError(f"unknown experiment: {experiment_id}")
    if row["status"] != "PROPOSED":
        raise ValueError(
            f"experiment {experiment_id} is not PROPOSED: {row['status']}"
        )
    contract = (str(row["source_kind"]), str(row["metric_name"]))
    if contract not in EXECUTABLE_SHADOW_CONTRACTS:
        raise ValueError(
            "experiment contract is not approved for executable shadow mode: "
            f"{contract[0]}/{contract[1]}"
        )
    return row


def _authoritative_ids(conn: sqlite3.Connection) -> list[str]:
    return [item.task_id for item in score_ready_tasks(conn)[:20]]


def _overlap(authoritative: list[str], candidate: list[str]) -> int:
    return len(set(authoritative[:5]) & set(candidate[:5]))


def run_shadow_experiment(
    conn: sqlite3.Connection,
    experiment_id: int,
) -> dict[str, Any]:
    row = _experiment(conn, experiment_id)
    authoritative = _authoritative_ids(conn)
    ready_before = {
        r[0]
        for r in conn.execute(
            "select id from tasks where status='READY' order by id"
        )
    }

    baseline_rows = score_candidates(conn)
    baseline_ids = [item["task_id"] for item in baseline_rows]
    baseline_overlap = _overlap(authoritative, baseline_ids)

    variants: list[ShadowVariantResult] = []
    for name, weights in VARIANTS:
        rows = score_candidates(conn, weights=weights)
        order = tuple(item["task_id"] for item in rows)
        if set(order) != ready_before:
            raise RuntimeError(
                f"shadow variant {name} changed candidate membership"
            )
        variants.append(
            ShadowVariantResult(
                name=name,
                weights=dict(weights),
                top5_overlap=_overlap(authoritative, list(order)),
                order=order,
            )
        )

    ranked = sorted(
        variants,
        key=lambda item: (-item.top5_overlap, item.name),
    )
    best = ranked[0] if ranked else None
    measured = best.top5_overlap if best is not None else baseline_overlap

    ready_after = {
        r[0]
        for r in conn.execute(
            "select id from tasks where status='READY' order by id"
        )
    }
    guardrail = ready_after != ready_before
    notes = json.dumps(
        {
            "authority": AUTHORITY,
            "authoritative": authoritative,
            "baseline": {
                "top5_overlap": baseline_overlap,
                "order": baseline_ids,
            },
            "variants": [item.to_dict() for item in variants],
            "selected_variant": best.name if best else None,
            "ready_membership_unchanged": not guardrail,
            "no_dispatch": True,
            "no_deploy": True,
            "no_merge": True,
        },
        sort_keys=True,
    )

    record_outcome(
        conn,
        int(experiment_id),
        metric_value=float(measured),
        guardrail_breached=guardrail,
        notes=notes,
    )
    evaluation = evaluate_experiment(conn, int(experiment_id))
    return {
        "experiment_id": int(experiment_id),
        "authority": AUTHORITY,
        "baseline_overlap": baseline_overlap,
        "selected_variant": best.to_dict() if best else None,
        "variants": [item.to_dict() for item in variants],
        "evaluation": evaluation,
        "effect": (
            "Recorded advisory measurement only. No task dispatch, scheduler "
            "authority change, deployment, merge, or promotion occurred."
        ),
    }


def next_shadow_experiment(conn: sqlite3.Connection) -> int | None:
    row = conn.execute(
        """select id from governor_experiments
            where status='PROPOSED'
              and source_kind='SHADOW_SCHEDULER'
              and metric_name='top5_overlap'
            order by id
            limit 1"""
    ).fetchone()
    return int(row[0]) if row else None
