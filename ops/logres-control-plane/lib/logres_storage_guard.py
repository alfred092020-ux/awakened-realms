from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

GIB = 1024 ** 3
BANDS = ("warning", "high", "critical")


class StorageGuardError(RuntimeError):
    def __init__(self, message: str, *, manifest_path: str | Path):
        super().__init__(message)
        self.manifest_path = str(manifest_path)


def _resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else Path(root) / path


def _configured_inside(child: str | Path, parent: str | Path) -> bool:
    c = Path(child)
    p = Path(parent)
    return c == p or p in c.parents


def validate_policy(policy: Mapping[str, Any]) -> dict[str, Any]:
    data = json.loads(json.dumps(dict(policy)))
    thresholds = data.get("thresholds") or {}
    warning = float(thresholds.get("warning_free_gib", 0))
    high = float(thresholds.get("high_free_gib", 0))
    critical = float(thresholds.get("critical_free_gib", 0))
    if not (warning >= high >= critical > 0):
        raise ValueError("storage thresholds must satisfy warning >= high >= critical > 0")
    expected = float(data.get("expected_autonomy_min_free_disk_gib", critical))
    if abs(expected - critical) > 1e-9:
        raise ValueError("critical threshold must align with autonomy disk gate")

    protected = [Path(str(x)) for x in data.get("protected_roots", [])]
    for tier in data.get("retention_tiers", []):
        tier_root = Path(str(tier.get("root") or ""))
        if not str(tier_root) or str(tier_root) == ".":
            raise ValueError("retention tier root is required")
        if any(_configured_inside(tier_root, item) for item in protected):
            raise ValueError(f"retention tier overlaps protected root: {tier_root}")
        patterns = tier.get("patterns") or []
        if not patterns:
            raise ValueError(f"retention tier has no patterns: {tier_root}")
        ages = tier.get("min_age_hours") or {}
        for band in BANDS:
            if band not in ages or float(ages[band]) < 0:
                raise ValueError(f"retention tier missing nonnegative {band} age")
    return data


def load_policy(path: Path) -> dict[str, Any]:
    return validate_policy(json.loads(Path(path).read_text(encoding="utf-8")))


def classify_pressure(free_bytes: int, policy: Mapping[str, Any]) -> dict[str, Any]:
    thresholds = validate_policy(policy)["thresholds"]
    free_gib = max(0.0, float(free_bytes) / GIB)
    warning = float(thresholds["warning_free_gib"])
    high = float(thresholds["high_free_gib"])
    critical = float(thresholds["critical_free_gib"])
    if free_gib <= critical:
        band = "critical"
    elif free_gib <= high:
        band = "high"
    elif free_gib <= warning:
        band = "warning"
    else:
        band = "normal"
    return {
        "band": band,
        "free_bytes": int(free_bytes),
        "free_gib": free_gib,
        "allow_new_fanout": band != "critical",
        "preserve_brain_writes": True,
        "preserve_verifier_writes": True,
        "critical_free_gib": critical,
    }


def filesystem_free_bytes(path: Path) -> int:
    stat = os.statvfs(path)
    return int(stat.f_bavail * stat.f_frsize)


def _path_size(path: Path) -> int:
    try:
        if path.is_symlink() or path.is_file():
            return int(path.lstat().st_size)
        if not path.is_dir():
            return 0
    except OSError:
        return 0
    total = 0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():
                            total += entry.stat(follow_symlinks=False).st_size
                        elif entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        else:
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return int(total)


def _inside(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath([str(path.resolve(strict=False)), str(root.resolve(strict=False))]) == str(root.resolve(strict=False))
    except (OSError, ValueError):
        return False


def _protected_root(path: Path, root: Path, policy: Mapping[str, Any]) -> bool:
    for value in policy.get("protected_roots", []):
        protected = _resolve(root, value)
        if _inside(path, protected):
            return True
    return False


def inventory_storage(root: Path, policy: Mapping[str, Any]) -> dict[str, Any]:
    root = Path(root)
    checked = validate_policy(policy)
    rows = []
    for spec in checked.get("inventory_roots", []):
        path = _resolve(root, spec["path"])
        rows.append(
            {
                "name": str(spec["name"]),
                "kind": str(spec.get("kind") or "other"),
                "path": str(path),
                "bytes": _path_size(path),
                "exists": path.exists(),
                "protected": _protected_root(path, root, checked),
            }
        )
    rows.sort(key=lambda item: (-int(item["bytes"]), item["name"]))
    return {"roots": rows, "total_bytes": sum(int(row["bytes"]) for row in rows)}


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {str(row[1]) for row in conn.execute(f"pragma table_info({table})")}
    except sqlite3.OperationalError:
        return set()


def _add_path(target: set[str], value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        return
    text = value.strip()
    if not text.startswith("/"):
        return
    target.add(str(Path(text).resolve(strict=False)))


def _walk_json_paths(target: set[str], value: Any) -> None:
    if isinstance(value, str):
        _add_path(target, value)
    elif isinstance(value, list):
        for item in value:
            _walk_json_paths(target, item)
    elif isinstance(value, dict):
        for item in value.values():
            _walk_json_paths(target, item)


def _quote_identifier(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _collect_reference_value(target: set[str], value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        _walk_json_paths(target, value)
        return
    text = value.strip()
    if not text:
        return
    _add_path(target, text)
    if text[:1] in {"{", "["}:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return
        _walk_json_paths(target, parsed)


def collect_protected_paths(conn: sqlite3.Connection) -> set[str]:
    """Return every absolute file reference discoverable from Brain schema.

    This intentionally discovers path-bearing columns rather than maintaining a
    hand-written table list, so new evidence/receipt tables fail safe without a
    storage-guard code change. Relative repository paths and hashes are ignored.
    """
    protected: set[str] = set()
    try:
        tables = [
            str(row[0])
            for row in conn.execute(
                "select name from sqlite_master "
                "where type='table' and name not like 'sqlite_%'"
            )
        ]
    except sqlite3.OperationalError:
        return protected

    tokens = ("path", "log", "artifact", "file", "receipt")
    for table in tables:
        columns = _table_columns(conn, table)
        for column in columns:
            if not any(token in column.casefold() for token in tokens):
                continue
            table_q = _quote_identifier(table)
            column_q = _quote_identifier(column)
            try:
                rows = conn.execute(
                    f"select {column_q} from {table_q} "
                    f"where {column_q} is not null"
                )
            except sqlite3.OperationalError:
                continue
            for row in rows:
                _collect_reference_value(protected, row[0])
    return protected


def _is_referenced(candidate: Path, protected_paths: Iterable[str]) -> bool:
    c = candidate.resolve(strict=False)
    for raw in protected_paths:
        p = Path(raw).resolve(strict=False)
        if c == p or c in p.parents or p in c.parents:
            return True
    return False


def plan_cleanup(
    root: Path,
    policy: Mapping[str, Any],
    band: str,
    *,
    now_epoch: float | None = None,
    protected_paths: Iterable[str] = (),
) -> dict[str, Any]:
    checked = validate_policy(policy)
    now = float(now_epoch if now_epoch is not None else __import__("time").time())
    if band == "normal":
        return {"band": band, "candidates": [], "skipped": [], "candidate_bytes": 0}
    if band not in BANDS:
        raise ValueError(f"unknown storage pressure band: {band}")
    max_actions = max(1, int(checked.get("max_actions_per_run", 200) or 200))
    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for tier in checked.get("retention_tiers", []):
        tier_root = _resolve(Path(root), tier["root"])
        if not tier_root.is_dir():
            continue
        age_limit = float(tier["min_age_hours"][band])
        for pattern in tier.get("patterns", []):
            for candidate in tier_root.glob(str(pattern)):
                key = str(candidate.resolve(strict=False))
                if key in seen or candidate.resolve(strict=False) == tier_root.resolve(strict=False):
                    continue
                seen.add(key)
                if not _inside(candidate, tier_root):
                    skipped.append({"path": str(candidate), "tier": tier["name"], "reason": "OUTSIDE_RETENTION_ROOT"})
                    continue
                try:
                    stat = candidate.lstat()
                except OSError:
                    continue
                age_hours = max(0.0, (now - stat.st_mtime) / 3600.0)
                item = {
                    "path": str(candidate),
                    "tier": str(tier["name"]),
                    "retention_root": str(tier_root),
                    "age_hours": age_hours,
                    "min_age_hours": age_limit,
                    "bytes": _path_size(candidate),
                    "mtime_ns": int(stat.st_mtime_ns),
                }
                if age_hours < age_limit:
                    skipped.append({**item, "reason": "FRESH"})
                    continue
                if _is_referenced(candidate, protected_paths):
                    skipped.append({**item, "reason": "REFERENCED_EVIDENCE"})
                    continue
                candidates.append({**item, "reason": "RETENTION_EXPIRED"})
    candidates.sort(key=lambda item: (-int(item["bytes"]), item["path"]))
    selected = candidates[:max_actions]
    for item in candidates[max_actions:]:
        skipped.append({**item, "reason": "RUN_LIMIT"})
    return {
        "band": band,
        "candidates": selected,
        "skipped": skipped,
        "candidate_bytes": sum(int(item["bytes"]) for item in selected),
    }


def _apply_cleanup(plan: Mapping[str, Any]) -> dict[str, Any]:
    actions = []
    removed_bytes = 0
    for item in plan.get("candidates", []):
        path = Path(str(item["path"]))
        retention_root = Path(str(item["retention_root"]))
        action = dict(item)
        if not _inside(path, retention_root) or path.resolve(strict=False) == retention_root.resolve(strict=False):
            action.update(status="SKIPPED", apply_reason="SAFETY_REVALIDATION_FAILED")
            actions.append(action)
            continue
        try:
            stat = path.lstat()
        except OSError:
            action.update(status="SKIPPED", apply_reason="MISSING_AT_APPLY")
            actions.append(action)
            continue
        if int(stat.st_mtime_ns) != int(item.get("mtime_ns", -1)):
            action.update(status="SKIPPED", apply_reason="CHANGED_SINCE_PLAN")
            actions.append(action)
            continue
        try:
            if path.is_symlink() or path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
            else:
                action.update(status="SKIPPED", apply_reason="UNSUPPORTED_FILE_TYPE")
                actions.append(action)
                continue
        except OSError as exc:
            action.update(status="FAILED", apply_reason=f"{type(exc).__name__}: {exc}")
            actions.append(action)
            continue
        removed_bytes += int(item.get("bytes", 0) or 0)
        action.update(status="REMOVED", apply_reason="RETENTION_EXPIRED")
        actions.append(action)
    return {
        "attempted": len(actions),
        "removed": sum(1 for item in actions if item["status"] == "REMOVED"),
        "removed_bytes": removed_bytes,
        "actions": actions,
    }


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sync_brownout(config_path: Path, state_path: Path, *, critical: bool) -> dict[str, Any]:
    config_path = Path(config_path)
    state_path = Path(state_path)
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            state = {}
    except (OSError, json.JSONDecodeError):
        state = {}

    if critical:
        if not config_path.is_file():
            return {"active": False, "changed": False, "restored": False, "restore_reason": "CONFIG_MISSING"}
        config = json.loads(config_path.read_text(encoding="utf-8"))
        swarm = config.setdefault("swarm", {})
        prior = bool(state.get("prior_swarm_enabled", swarm.get("enabled", False))) if state.get("active") else bool(swarm.get("enabled", False))
        swarm["enabled"] = False
        _atomic_json(config_path, config)
        mutated_hash = _sha256(config_path)
        new_state = {
            "active": True,
            "prior_swarm_enabled": prior,
            "mutated_config_sha256": mutated_hash,
            "reason": "CRITICAL_DISK_PRESSURE",
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        _atomic_json(state_path, new_state)
        return {**new_state, "changed": True, "restored": False, "restore_reason": None}

    if not state.get("active"):
        return {"active": False, "changed": False, "restored": False, "restore_reason": "NOT_ACTIVE"}
    if not config_path.is_file():
        return {**state, "active": True, "changed": False, "restored": False, "restore_reason": "CONFIG_MISSING"}
    current_hash = _sha256(config_path)
    if current_hash != str(state.get("mutated_config_sha256") or ""):
        state["restore_reason"] = "CONFIG_CHANGED"
        state["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _atomic_json(state_path, state)
        return {**state, "active": True, "changed": False, "restored": False, "restore_reason": "CONFIG_CHANGED"}
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config.setdefault("swarm", {})["enabled"] = bool(state.get("prior_swarm_enabled", False))
    _atomic_json(config_path, config)
    state.update(
        {
            "active": False,
            "restored_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "restore_reason": "PRESSURE_RECOVERED",
        }
    )
    _atomic_json(state_path, state)
    return {**state, "changed": True, "restored": True}


def fanout_guard(
    root: Path,
    policy: Mapping[str, Any],
    config_path: Path,
    state_path: Path | None = None,
    *,
    apply_brownout: bool = True,
    free_bytes_fn: Callable[[Path], int] = filesystem_free_bytes,
) -> dict[str, Any]:
    """Lightweight pressure gate used by the minute-by-minute fan-out path."""
    root = Path(root)
    checked = validate_policy(policy)
    free_bytes = int(free_bytes_fn(root))
    pressure = classify_pressure(free_bytes, checked)
    configured_state = state_path or _resolve(
        root,
        (checked.get("brownout") or {}).get(
            "state_path",
            "control/storage-pressure.json",
        ),
    )
    if apply_brownout:
        brownout = sync_brownout(
            Path(config_path),
            Path(configured_state),
            critical=pressure["band"] == "critical",
        )
    else:
        brownout = {
            "active": pressure["band"] == "critical",
            "changed": False,
            "restored": False,
            "restore_reason": "DRY_RUN",
        }
    return {**pressure, "brownout": brownout}


def run_existing_gc(
    root: Path,
    policy: Mapping[str, Any],
    *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> list[dict[str, Any]]:
    cfg = validate_policy(policy).get("workspace_gc", {})
    if not bool(cfg.get("enabled", True)):
        return []
    root = Path(root)
    commands = [
        [str(root / "bin/logres-workspace-gc"), "apply", "--limit", str(int(cfg.get("workspace_limit", 25)))],
        [str(root / "bin/logres-worktree-gc"), "--apply", "--age-hours", str(int(cfg.get("worktree_age_hours", 24)))],
        [str(root / "bin/logres-preview-reaper"), "--apply", "--age-hours", str(int(cfg.get("preview_age_hours", 2)))],
    ]
    outcomes = []
    for command in commands:
        result = runner(command, text=True, capture_output=True, check=False)
        outcome = {
            "command": command,
            "returncode": int(result.returncode),
            "stdout": str(result.stdout or "")[-4000:],
            "stderr": str(result.stderr or "")[-2000:],
        }
        outcomes.append(outcome)
        if result.returncode:
            break
    return outcomes


def _manifest_path(root: Path, policy: Mapping[str, Any]) -> Path:
    audit_root = _resolve(root, policy.get("audit_root", "artifacts/storage-guard"))
    audit_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return audit_root / f"storage-guard-{stamp}.json"


def _write_manifest(
    path: Path,
    payload: Mapping[str, Any],
    *,
    writer: Callable[[Path, Mapping[str, Any]], None] = _atomic_json,
) -> Path:
    writer(Path(path), payload)
    return Path(path)


def _failed_manifest(
    manifest: Path,
    payload: dict[str, Any],
    *,
    status: str,
    error: Exception | str,
    writer: Callable[[Path, Mapping[str, Any]], None],
) -> None:
    payload["status"] = status
    payload["error"] = (
        error if isinstance(error, str)
        else f"{type(error).__name__}: {error}"
    )
    payload["failed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _write_manifest(manifest, payload, writer=writer)


def apply_guard(
    root: Path,
    conn: sqlite3.Connection,
    policy: Mapping[str, Any],
    *,
    now_epoch: float | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    free_bytes_fn: Callable[[Path], int] = filesystem_free_bytes,
    manifest_writer: Callable[[Path, Mapping[str, Any]], None] = _atomic_json,
) -> dict[str, Any]:
    root = Path(root)
    checked = validate_policy(policy)
    before_inventory = inventory_storage(root, checked)
    before_free = int(free_bytes_fn(root))
    initial_pressure = classify_pressure(before_free, checked)
    protected = collect_protected_paths(conn)
    initial_plan = plan_cleanup(
        root,
        checked,
        initial_pressure["band"],
        now_epoch=now_epoch,
        protected_paths=protected,
    )
    brownout_cfg = checked.get("brownout", {})
    config_path = _resolve(root, brownout_cfg.get("autoflow_config", "control/autoflow.json"))
    state_path = _resolve(root, brownout_cfg.get("state_path", "control/storage-pressure.json"))
    manifest = _manifest_path(root, checked)
    payload: dict[str, Any] = {
        "schema": "logres-storage-guard-run/1",
        "status": "PREPARED",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "root": str(root),
        "initial_pressure": initial_pressure,
        "before_free_bytes": before_free,
        "inventory_before": before_inventory,
        "protected_reference_count": len(protected),
        "initial_cleanup_plan": initial_plan,
        "delegated_cleanup": [],
        "direct_cleanup": None,
        "brownout_before": None,
        "brownout_after": None,
        "safety": {
            "brain_writes_preserved": True,
            "verifier_writes_preserved": True,
            "protected_roots": list(checked.get("protected_roots", [])),
            "direct_worktree_deletion": False,
            "workspace_gc_delegated": True,
            "audit_manifest_precedes_destructive_actions": True,
        },
    }
    # Fail before any mutation if the audit trail cannot be established.
    _write_manifest(manifest, payload, writer=manifest_writer)

    try:
        brownout_before = sync_brownout(
            config_path,
            state_path,
            critical=initial_pressure["band"] == "critical",
        )
    except Exception as exc:
        _failed_manifest(
            manifest,
            payload,
            status="FAILED_BROWNOUT",
            error=exc,
            writer=manifest_writer,
        )
        raise StorageGuardError(
            f"storage brownout failed: {type(exc).__name__}: {exc}",
            manifest_path=manifest,
        ) from exc
    payload["brownout_before"] = brownout_before
    _write_manifest(manifest, payload, writer=manifest_writer)

    delegated = run_existing_gc(root, checked, runner=runner)
    payload["delegated_cleanup"] = delegated
    failed_delegated = next(
        (item for item in delegated if int(item.get("returncode", 0)) != 0),
        None,
    )
    if failed_delegated is not None:
        _failed_manifest(
            manifest,
            payload,
            status="FAILED_DELEGATED_GC",
            error=(
                "delegated cleanup failed rc="
                f"{failed_delegated['returncode']} command="
                + " ".join(str(x) for x in failed_delegated.get("command", []))
            ),
            writer=manifest_writer,
        )
        raise StorageGuardError(
            "delegated cleanup failed; direct cleanup aborted",
            manifest_path=manifest,
        )
    _write_manifest(manifest, payload, writer=manifest_writer)

    after_gc_free = int(free_bytes_fn(root))
    cleanup_pressure = classify_pressure(after_gc_free, checked)
    plan = plan_cleanup(
        root,
        checked,
        cleanup_pressure["band"],
        now_epoch=now_epoch,
        protected_paths=protected,
    )
    direct = _apply_cleanup(plan)
    final_free = int(free_bytes_fn(root))
    final_pressure = classify_pressure(final_free, checked)
    try:
        brownout_after = sync_brownout(
            config_path,
            state_path,
            critical=final_pressure["band"] == "critical",
        )
    except Exception as exc:
        payload.update(
            cleanup_pressure=cleanup_pressure,
            cleanup_plan=plan,
            direct_cleanup=direct,
        )
        _failed_manifest(
            manifest,
            payload,
            status="FAILED_BROWNOUT",
            error=exc,
            writer=manifest_writer,
        )
        raise StorageGuardError(
            f"storage brownout finalization failed: {type(exc).__name__}: {exc}",
            manifest_path=manifest,
        ) from exc

    after_inventory = inventory_storage(root, checked)
    payload.update(
        status="COMPLETE",
        cleanup_pressure=cleanup_pressure,
        final_pressure=final_pressure,
        after_gc_free_bytes=after_gc_free,
        after_free_bytes=final_free,
        filesystem_reclaimed_bytes=max(0, final_free - before_free),
        inventory_after=after_inventory,
        cleanup_plan=plan,
        direct_cleanup=direct,
        brownout_after=brownout_after,
        completed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    _write_manifest(manifest, payload, writer=manifest_writer)
    payload["manifest_path"] = str(manifest)
    return payload

