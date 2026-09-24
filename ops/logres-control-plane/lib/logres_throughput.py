from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Mapping


METRIC_SLOS_SECONDS: dict[str, float] = {
    "ready_to_lease": 60.0,
    "lease_to_done": 1800.0,
    "done_to_queue_ready": 30.0,
    "queue_ready_to_preflight_verified": 120.0,
    "preflight_verified_to_integrated": 30.0,
    "done_to_integrated": 300.0,
}

WINDOWS_SECONDS: dict[str, int] = {
    "20m": 20 * 60,
    "60m": 60 * 60,
}


def percentile(values: Iterable[float], quantile: float) -> float | None:
    items = sorted(float(value) for value in values)
    if not items:
        return None
    if quantile <= 0:
        return items[0]
    if quantile >= 1:
        return items[-1]
    index = max(0, math.ceil(quantile * len(items)) - 1)
    return items[index]


def summarize_values(values: Iterable[float]) -> dict:
    items = [float(value) for value in values]
    return {
        "samples": len(items),
        "median_seconds": statistics.median(items) if items else None,
        "p95_seconds": percentile(items, 0.95),
    }


def summarize_window(
    samples: Iterable[tuple[float, float]],
    *,
    now_epoch: float,
    window_seconds: int,
) -> dict:
    cutoff = float(now_epoch) - int(window_seconds)
    values = [
        float(duration)
        for completed_epoch, duration in samples
        if cutoff <= float(completed_epoch) <= float(now_epoch)
    ]
    result = summarize_values(values)
    result["window_seconds"] = int(window_seconds)
    return result


def metric_slo_status(summary: Mapping[str, object], target_seconds: float) -> str:
    sample_count = int(summary.get("samples") or 0)
    p95 = summary.get("p95_seconds")
    if sample_count <= 0 or p95 is None:
        return "NO_DATA"
    return "PASS" if float(p95) <= float(target_seconds) else "FAIL"


def summarize_recent(
    samples_by_metric: Mapping[str, Iterable[tuple[float, float]]],
    *,
    now_epoch: float,
    windows: Mapping[str, int] = WINDOWS_SECONDS,
    slos: Mapping[str, float] = METRIC_SLOS_SECONDS,
) -> dict:
    result: dict[str, dict] = {}
    for window_name, window_seconds in windows.items():
        metrics: dict[str, dict] = {}
        statuses: list[str] = []
        for metric, samples in samples_by_metric.items():
            summary = summarize_window(
                samples,
                now_epoch=now_epoch,
                window_seconds=window_seconds,
            )
            target = slos.get(metric)
            status = (
                metric_slo_status(summary, target)
                if target is not None
                else "NO_TARGET"
            )
            summary["target_seconds"] = target
            summary["slo_status"] = status
            metrics[metric] = summary
            if status in {"PASS", "FAIL"}:
                statuses.append(status)
        overall = "NO_DATA"
        if "FAIL" in statuses:
            overall = "FAIL"
        elif "PASS" in statuses:
            overall = "PASS"
        result[window_name] = {
            "window_seconds": int(window_seconds),
            "status": overall,
            "metrics": metrics,
        }
    return result
