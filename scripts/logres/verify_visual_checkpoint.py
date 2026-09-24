#!/usr/bin/env python3
"""Structural visual gate for Logres reconstruction checkpoints.

This is intentionally not a historical pixel-perfect baseline. It rejects
catastrophic render failures while preserving provenance distinctions for
visual details that remain unresolved.
"""
from __future__ import annotations
import argparse
import json
import math
import os
import struct
import subprocess
import sys
import zlib
from collections import Counter
from pathlib import Path

PROFILES = {
    "title": {
        "max_dark_ratio": 0.96,
        "min_quantized_colors": 32,
        "min_active_bbox_ratio": 0.30,
        "min_luma_stddev": 8.0,
        "provenance": {
            "assets": "RECOVERED_GLOBAL",
            "layout": "SUPPORTED_INFERENCE_CURRENT_JP_LAYOUT",
            "animation": "UNRESOLVED_GLOBAL_LFLA",
        },
    },
    "field": {
        "max_dark_ratio": 0.94,
        "min_quantized_colors": 64,
        "min_active_bbox_ratio": 0.45,
        "min_luma_stddev": 10.0,
        "provenance": {
            "map_binding": "CONFIRMED_CURRENT_JP_002_000_00001",
            "global_application": "SUPPORTED_INFERENCE",
            "spawn": "RECONSTRUCTED",
        },
    },
    "battle": {
        "max_dark_ratio": 0.985,
        "min_quantized_colors": 16,
        "min_active_bbox_ratio": 0.20,
        "min_luma_stddev": 5.0,
        "provenance": {
            "presentation": "RECONSTRUCTED",
            "ui_assets": "EVIDENCE_BACKED_RECOVERED",
            "historical_scene_composition": "UNRESOLVED",
        },
    },
}

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _truth_enabled() -> bool:
    return os.environ.get("LOGRES_RECORD_VISUAL_TRUTH", "").lower() in {
        "1",
        "true",
        "yes",
    }


def _truth_required() -> bool:
    return os.environ.get("LOGRES_REQUIRE_VISUAL_TRUTH_RECORD", "").lower() in {
        "1",
        "true",
        "yes",
    }


def _truth_timeout_seconds() -> float:
    raw = os.environ.get("LOGRES_VISUAL_TRUTH_TIMEOUT_SECONDS", "8")
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(
            "LOGRES_VISUAL_TRUTH_TIMEOUT_SECONDS must be numeric"
        ) from exc
    if value <= 0 or value > 30:
        raise ValueError(
            "LOGRES_VISUAL_TRUTH_TIMEOUT_SECONDS must be > 0 and <= 30"
        )
    return value


def record_visual_truth(checkpoint: str, image: Path, result: dict) -> dict:
    if not _truth_enabled():
        return {"recorded": False, "reason": "DISABLED"}

    sha = os.environ.get("LOGRES_VERIFY_SHA", "")
    truth_bin = os.environ.get(
        "LOGRES_VISUAL_TRUTH_BIN",
        "/home/ubuntu/logres/bin/logres-visual-truth",
    )
    if len(sha) != 40 or any(ch not in "0123456789abcdef" for ch in sha):
        message = "canonical visual truth recording requires exact lowercase SHA"
        if _truth_required():
            raise RuntimeError(message)
        return {"recorded": False, "reason": "INVALID_SHA", "error": message}
    if not Path(truth_bin).is_file():
        message = f"visual truth recorder missing: {truth_bin}"
        if _truth_required():
            raise RuntimeError(message)
        return {"recorded": False, "reason": "RECORDER_MISSING", "error": message}

    verdict = "REVIEW" if result.get("pass") else "FAIL"
    metrics = dict(result.get("metrics") or {})
    metrics["structural_provenance"] = result.get("provenance") or {}
    metrics["structural_failures"] = result.get("failures") or []
    viewport = {
        "width": metrics.get("width"),
        "height": metrics.get("height"),
        "source": "playwright-canvas",
    }
    recorder_env = os.environ.copy()
    recorder_env.setdefault(
        "LOGRES_VISUAL_TRUTH_DB_TIMEOUT_SECONDS",
        "0.25",
    )
    try:
        completed = subprocess.run(
            [
                truth_bin,
                "record",
                sha,
                checkpoint,
                str(image),
                verdict,
                "--viewport",
                json.dumps(viewport, sort_keys=True),
                "--device",
                json.dumps(
                    {
                        "runner": "canonical-playwright",
                        "gate": "structural",
                    },
                    sort_keys=True,
                ),
                "--metrics",
                json.dumps(metrics, sort_keys=True),
            ],
            text=True,
            capture_output=True,
            check=False,
            timeout=_truth_timeout_seconds(),
            env=recorder_env,
        )
    except subprocess.TimeoutExpired as exc:
        message = (
            f"visual truth recording timed out after "
            f"{_truth_timeout_seconds():g}s"
        )
        if _truth_required():
            raise RuntimeError(message) from exc
        return {
            "recorded": False,
            "reason": "RECORDER_TIMEOUT",
            "error": message,
        }
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "recording failed").strip()
        if _truth_required():
            raise RuntimeError(f"visual truth recording failed: {message}")
        lowered = message.lower()
        reason = (
            "RECORDER_CONTENTION"
            if "database is locked" in lowered
            or "database table is locked" in lowered
            else "RECORDER_FAILED"
        )
        return {
            "recorded": False,
            "reason": reason,
            "error": message,
        }
    try:
        payload = json.loads(completed.stdout)
    except Exception:
        payload = {"raw": completed.stdout.strip()}
    return {
        "recorded": True,
        "verdict": verdict,
        "record": payload,
    }


def paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def decode_png(path: Path):
    data = path.read_bytes()
    if not data.startswith(PNG_SIG):
        raise ValueError("not-png")
    pos = len(PNG_SIG)
    width = height = bit_depth = color_type = None
    payload = bytearray()
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            payload.extend(body)
        elif kind == b"IEND":
            break
    if not width or not height or bit_depth != 8 or color_type not in (0, 2, 4, 6):
        raise ValueError(f"unsupported-png:{width}x{height}:depth={bit_depth}:type={color_type}")
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[color_type]
    raw = zlib.decompress(bytes(payload))
    stride = width * channels
    rows = []
    cursor = 0
    previous = bytearray(stride)
    for _ in range(height):
        f = raw[cursor]
        cursor += 1
        scan = bytearray(raw[cursor:cursor + stride])
        cursor += stride
        for i in range(stride):
            left = scan[i - channels] if i >= channels else 0
            up = previous[i]
            upper_left = previous[i - channels] if i >= channels else 0
            if f == 1:
                scan[i] = (scan[i] + left) & 255
            elif f == 2:
                scan[i] = (scan[i] + up) & 255
            elif f == 3:
                scan[i] = (scan[i] + ((left + up) >> 1)) & 255
            elif f == 4:
                scan[i] = (scan[i] + paeth(left, up, upper_left)) & 255
            elif f != 0:
                raise ValueError(f"unsupported-png-filter:{f}")
        rows.append(bytes(scan))
        previous = scan

    pixels = []
    for row in rows:
        for x in range(width):
            p = x * channels
            if color_type == 0:
                v = row[p]
                pixels.append((v, v, v))
            elif color_type == 2:
                pixels.append((row[p], row[p + 1], row[p + 2]))
            elif color_type == 4:
                v = row[p]
                pixels.append((v, v, v))
            else:
                pixels.append((row[p], row[p + 1], row[p + 2]))
    return width, height, pixels


def color_distance(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def checkerboard_score(width, height, pixels):
    step = max(4, min(width, height) // 90)
    grid = []
    for y in range(step // 2, height, step):
        grid.append([pixels[y * width + x] for x in range(step // 2, width, step)])
    matches = total = 0
    for y in range(len(grid) - 1):
        for x in range(len(grid[y]) - 1):
            a, b = grid[y][x], grid[y][x + 1]
            c, d = grid[y + 1][x], grid[y + 1][x + 1]
            total += 1
            if color_distance(a, d) < 36 and color_distance(b, c) < 36 and color_distance(a, b) > 240:
                matches += 1
    return matches / total if total else 0.0


def analyze(width, height, pixels):
    total = len(pixels)
    dark = missing = 0
    quantized = Counter()
    lum_sum = lum_sq_sum = 0.0
    min_x, min_y, max_x, max_y = width, height, -1, -1
    for i, (r, g, b) in enumerate(pixels):
        mx = max(r, g, b)
        if mx <= 24:
            dark += 1
        else:
            x, y = i % width, i // width
            min_x, min_y = min(min_x, x), min(min_y, y)
            max_x, max_y = max(max_x, x), max(max_y, y)
        if (g >= 200 and r <= 80 and b <= 80) or (r >= 200 and b >= 200 and g <= 80):
            missing += 1
        quantized[(r >> 4, g >> 4, b >> 4)] += 1
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
        lum_sum += lum
        lum_sq_sum += lum * lum
    mean = lum_sum / total
    variance = max(0.0, lum_sq_sum / total - mean * mean)
    bbox_ratio = 0.0
    if max_x >= min_x and max_y >= min_y:
        bbox_ratio = ((max_x - min_x + 1) * (max_y - min_y + 1)) / total
    top_two = sum(n for _, n in quantized.most_common(2)) / total
    return {
        "width": width,
        "height": height,
        "dark_ratio": dark / total,
        "missing_marker_ratio": missing / total,
        "quantized_colors": len(quantized),
        "active_bbox_ratio": bbox_ratio,
        "luma_stddev": math.sqrt(variance),
        "top_two_color_ratio": top_two,
        "checkerboard_score": checkerboard_score(width, height, pixels),
    }


def assess(checkpoint, metrics):
    profile = PROFILES[checkpoint]
    failures = []
    if metrics["width"] != 720 or metrics["height"] != 1280:
        failures.append("checkpoint must be deterministic 720x1280")
    if metrics["dark_ratio"] > profile["max_dark_ratio"]:
        failures.append("screen is catastrophically dark/black")
    if metrics["quantized_colors"] < profile["min_quantized_colors"]:
        failures.append("palette collapsed below checkpoint minimum")
    if metrics["active_bbox_ratio"] < profile["min_active_bbox_ratio"]:
        failures.append("visible composition occupies too little of the frame")
    if metrics["luma_stddev"] < profile["min_luma_stddev"]:
        failures.append("frame has insufficient luminance structure")
    if metrics["checkerboard_score"] > 0.20:
        failures.append("checkerboard-like render failure detected")
    if metrics["top_two_color_ratio"] > 0.985:
        failures.append("frame collapsed to two dominant colors")
    if metrics["dark_ratio"] > 0.97 and metrics["missing_marker_ratio"] > 0.00005:
        failures.append("dark frame contains Phaser-style missing-texture colors")
    return failures


def result_for(checkpoint, width, height, pixels):
    metrics = analyze(width, height, pixels)
    failures = assess(checkpoint, metrics)
    return {
        "checkpoint": checkpoint,
        "pass": not failures,
        "metrics": metrics,
        "provenance": PROFILES[checkpoint]["provenance"],
        "failures": failures,
    }


def synthetic(kind):
    width, height = 720, 1280
    pixels = []
    for y in range(height):
        for x in range(width):
            if kind == "healthy":
                pixels.append(((x * 5 + y) % 256, (y * 3 + 40) % 256, (x + y * 2) % 256))
            elif kind == "black":
                pixels.append((0, 0, 0))
            elif kind == "missing":
                green = (40 <= x < 72 and 300 <= y < 332) or (330 <= x < 362 and 1040 <= y < 1072)
                pixels.append((0, 255, 0) if green else (0, 0, 0))
            else:
                cell = ((x // 16) + (y // 16)) & 1
                pixels.append((255, 0, 255) if cell else (0, 0, 0))
    return width, height, pixels


def self_test():
    cases = {}
    for kind in ("healthy", "black", "missing", "checker"):
        width, height, pixels = synthetic(kind)
        result = result_for("title", width, height, pixels)
        expected = kind == "healthy"
        cases[kind] = {"pass": result["pass"], "expected": expected, "failures": result["failures"]}
    ok = all(item["pass"] == item["expected"] for item in cases.values())
    payload = {"pass": ok, "cases": cases, "profiles": PROFILES}
    print(json.dumps(payload, sort_keys=True))
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", choices=sorted(PROFILES))
    parser.add_argument("--image", type=Path)
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.describe:
        print(json.dumps({"profiles": PROFILES}, sort_keys=True))
        return 0
    if args.self_test:
        return self_test()
    if not args.checkpoint or not args.image:
        parser.error("--checkpoint and --image are required unless --describe/--self-test is used")
    width, height, pixels = decode_png(args.image)
    result = result_for(args.checkpoint, width, height, pixels)
    result["truth_record"] = record_visual_truth(
        args.checkpoint,
        args.image,
        result,
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
