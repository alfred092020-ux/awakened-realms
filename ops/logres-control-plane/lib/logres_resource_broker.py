from __future__ import annotations

import json
import math
import os
import sqlite3
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class LaneScore:
    lane: str
    eligible: bool
    score: float
    reliability: float
    median_seconds: float | None
    available_slots: int | None
    rationale: tuple[str, ...]

    def to_dict(self) -> dict:
        value = asdict(self)
        value["rationale"] = list(self.rationale)
        return value


@dataclass(frozen=True)
class PlacementPlan:
    workload: str
    selected_lane: str
    lanes: tuple[LaneScore, ...]
    policy: str

    def to_dict(self) -> dict:
        return {
            "workload": self.workload,
            "selected_lane": self.selected_lane,
            "policy": self.policy,
            "lanes": [lane.to_dict() for lane in self.lanes],
        }


def _read_json(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def remote_observations(
    artifact_root: Path,
    *,
    npm_script: str | None = None,
    limit_per_role: int = 30,
) -> dict[str, list[dict]]:
    observations: dict[str, list[dict]] = {"heavy": [], "light": []}
    if not artifact_root.is_dir():
        return observations

    paths = sorted(
        artifact_root.glob("*/*/pool-result.json"),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )
    for path in paths:
        payload = _read_json(path)
        if not payload:
            continue
        role = str(payload.get("role") or "")
        if role not in observations:
            continue
        script = payload.get("npm_script")
        if npm_script and script and script != npm_script:
            continue
        if npm_script and not script:
            # Legacy records do not carry the script. Use them only as a weak
            # role-level prior, tagged so scoring can discount them.
            payload = {**payload, "_legacy_script_unknown": True}
        if len(observations[role]) < limit_per_role:
            observations[role].append(payload)
    return observations


def summarize_remote_history(
    rows: Iterable[dict],
    *,
    script_specific: bool = True,
) -> dict:
    rows = list(rows)
    if not rows:
        return {
            "count": 0,
            "success_rate": 0.75,
            "median_seconds": None,
            "specific_count": 0,
        }

    specific = [
        row
        for row in rows
        if not row.get("_legacy_script_unknown")
    ]
    basis = specific if script_specific and specific else rows
    successes = [
        row
        for row in basis
        if row.get("status") == "success"
        and int(row.get("exit_code", 1) or 0) == 0
    ]
    durations = [
        float(row["duration_seconds"])
        for row in successes
        if isinstance(row.get("duration_seconds"), (int, float))
        and float(row["duration_seconds"]) > 0
    ]
    return {
        "count": len(basis),
        "specific_count": len(specific),
        "success_rate": (
            len(successes) / len(basis)
            if basis
            else 0.75
        ),
        "median_seconds": statistics.median(durations) if durations else None,
    }


def score_remote_lanes(
    health_rows: Iterable[dict],
    artifact_root: Path,
    *,
    npm_script: str,
) -> list[LaneScore]:
    history = remote_observations(
        artifact_root,
        npm_script=npm_script,
    )
    lanes: list[LaneScore] = []
    for health in health_rows:
        role = str(health.get("role") or "")
        if role not in {"heavy", "light"}:
            continue
        reachable = bool(health.get("reachable"))
        slots = max(0, int(health.get("available_slots") or 0))
        max_slots = max(1, int(health.get("max_slots") or 1))
        cpu = max(1, int(health.get("cpu_count") or 1))
        available_mem = max(0, int(health.get("memory_available_bytes") or 0))
        hist = summarize_remote_history(history.get(role, []))

        reliability = float(hist["success_rate"])
        median = hist["median_seconds"]
        eligible = reachable and slots > 0
        if not eligible:
            score = -1e9
        else:
            occupancy = 1.0 - slots / max_slots
            capacity_bonus = (slots / max_slots) * 22.0
            cpu_bonus = min(16.0, math.log2(cpu + 1) * 4.0)
            memory_bonus = min(
                8.0,
                available_mem / (1024**3) * 0.5,
            )
            reliability_bonus = reliability * 40.0
            speed_bonus = (
                min(25.0, 250.0 / max(1.0, float(median)))
                if median is not None
                else 8.0
            )
            score = (
                capacity_bonus
                + cpu_bonus
                + memory_bonus
                + reliability_bonus
                + speed_bonus
                - occupancy * 15.0
            )

        rationale = [
            f"reachable={reachable}",
            f"slots={slots}/{max_slots}",
            f"cpu={cpu}",
            f"reliability={reliability:.2f}",
            (
                f"median={float(median):.1f}s"
                if median is not None
                else "median=unknown"
            ),
            f"history={hist['count']}",
        ]
        lanes.append(
            LaneScore(
                lane=f"remote-{role}",
                eligible=eligible,
                score=round(score, 4),
                reliability=round(reliability, 4),
                median_seconds=(
                    round(float(median), 3)
                    if median is not None
                    else None
                ),
                available_slots=slots,
                rationale=tuple(rationale),
            )
        )

    lanes.sort(key=lambda lane: (-lane.score, lane.lane))
    return lanes


def choose_remote_role(
    health_rows: Iterable[dict],
    artifact_root: Path,
    *,
    npm_script: str,
) -> str:
    lanes = score_remote_lanes(
        health_rows,
        artifact_root,
        npm_script=npm_script,
    )
    for lane in lanes:
        if lane.eligible:
            return lane.lane.removeprefix("remote-")
    raise RuntimeError("no eligible remote verification worker")


def _local_capacity() -> tuple[int, float]:
    cpus = max(1, os.cpu_count() or 1)
    try:
        load = os.getloadavg()[0]
    except OSError:
        load = 0.0
    free_ratio = max(0.0, 1.0 - load / cpus)
    return cpus, free_ratio


def plan_workload(
    *,
    workload: str,
    health_rows: Iterable[dict] = (),
    artifact_root: Path = Path("/nonexistent"),
    npm_script: str = "test",
    sensitivity: str = "normal",
    openai_allowed: bool = True,
    copilot_allowed: bool = True,
) -> PlacementPlan:
    workload = str(workload).lower()
    sensitivity = str(sensitivity).lower()
    lanes: list[LaneScore] = []
    cpus, local_free = _local_capacity()

    local_score = 45.0 + local_free * 20.0 + min(10.0, cpus / 2)
    if workload in {"verification", "test", "build"}:
        local_score -= 8.0
    lanes.append(
        LaneScore(
            "local",
            True,
            round(local_score, 4),
            1.0,
            None,
            None,
            (
                f"cpu={cpus}",
                f"free_ratio={local_free:.2f}",
                "private-capable",
            ),
        )
    )

    if sensitivity not in {"local_only", "private_only"} and workload in {
        "verification",
        "test",
        "build",
    }:
        lanes.extend(
            score_remote_lanes(
                health_rows,
                artifact_root,
                npm_script=npm_script,
            )
        )

    if workload in {"research", "evidence", "analysis"}:
        eligible = (
            openai_allowed
            and sensitivity not in {"local_only", "private_only"}
        )
        lanes.append(
            LaneScore(
                "openai",
                eligible,
                88.0 if eligible else -1e9,
                0.75,
                None,
                None,
                (
                    "bounded-reasoning",
                    "budget-gated",
                    f"sensitivity={sensitivity}",
                ),
            )
        )

    if workload in {"implementation", "regression", "code"}:
        eligible = (
            copilot_allowed
            and sensitivity not in {"local_only", "private_only"}
        )
        lanes.append(
            LaneScore(
                "copilot",
                eligible,
                86.0 if eligible else -1e9,
                0.75,
                None,
                None,
                (
                    "implementation-specialist",
                    "scope-gated",
                    f"sensitivity={sensitivity}",
                ),
            )
        )

    eligible_lanes = [lane for lane in lanes if lane.eligible]
    selected = max(
        eligible_lanes,
        key=lambda lane: (lane.score, lane.lane),
    )
    return PlacementPlan(
        workload=workload,
        selected_lane=selected.lane,
        lanes=tuple(
            sorted(
                lanes,
                key=lambda lane: (-lane.score, lane.lane),
            )
        ),
        policy=(
            "private/local authority preserved; remote lanes are exact-SHA "
            "verification only; AI/code lanes remain budget/scope gated"
        ),
    )


def infer_task_workload(
    conn: sqlite3.Connection,
    task_id: str,
) -> tuple[str, str]:
    row = conn.execute(
        """select coalesce(m.work_type,'implementation'),
                  coalesce(m.evidence_policy,'')
             from tasks t
             left join task_metadata m on m.task_id=t.id
            where t.id=?""",
        (task_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"unknown task: {task_id}")
    work_type = str(row[0] or "implementation").lower()
    evidence = str(row[1] or "").lower()
    sensitivity = (
        "local_only"
        if any(
            token in evidence
            for token in (
                "private",
                "local-only",
                "local only",
                "secret",
            )
        )
        else "normal"
    )
    return work_type, sensitivity
