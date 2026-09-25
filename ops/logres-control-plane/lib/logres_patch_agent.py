from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath


class PatchAgentError(RuntimeError):
    pass


def normalize_relpath(value: str) -> str:
    value = str(value or "").replace("\\", "/").strip()
    pure = PurePosixPath(value)
    if not value or pure.is_absolute() or ".." in pure.parts:
        raise PatchAgentError(f"unsafe relative path: {value!r}")
    normalized = pure.as_posix()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if not normalized:
        raise PatchAgentError("empty relative path")
    return normalized


def path_in_scopes(path: str, scopes: list[str] | tuple[str, ...]) -> bool:
    candidate = normalize_relpath(path)
    for raw in scopes:
        scope = normalize_relpath(raw).rstrip("/")
        if candidate == scope or candidate.startswith(scope + "/"):
            return True
    return False


def validate_paths(paths: list[str], scopes: list[str] | tuple[str, ...]) -> None:
    if not scopes:
        raise PatchAgentError("implementation task has no declared file scopes")
    bad = sorted({normalize_relpath(path) for path in paths if not path_in_scopes(path, scopes)})
    if bad:
        raise PatchAgentError("changed paths outside declared scopes: " + ", ".join(bad))


def git_changed_paths(worktree: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(worktree), "status", "--porcelain=v1", "-z"],
        text=False,
        capture_output=True,
        check=False,
    )
    if proc.returncode:
        raise PatchAgentError((proc.stderr or b"git status failed").decode(errors="replace"))
    entries = [item for item in proc.stdout.split(b"\0") if item]
    paths: list[str] = []
    i = 0
    while i < len(entries):
        entry = entries[i].decode(errors="replace")
        if len(entry) < 4:
            i += 1
            continue
        status = entry[:2]
        path = entry[3:]
        paths.append(normalize_relpath(path))
        if "R" in status or "C" in status:
            if i + 1 >= len(entries):
                raise PatchAgentError("malformed rename/copy status")
            original = entries[i + 1].decode(errors="replace")
            paths.append(normalize_relpath(original))
            i += 1
        i += 1
    return sorted(set(paths))


def scoped_file_index(
    worktree: Path,
    scopes: list[str] | tuple[str, ...],
    *,
    limit: int = 500,
) -> list[dict]:
    if not scopes:
        return []
    proc = subprocess.run(
        ["git", "-C", str(worktree), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if proc.returncode:
        raise PatchAgentError((proc.stderr or b"git ls-files failed").decode(errors="replace"))
    rows: list[dict] = []
    for raw in proc.stdout.split(b"\0"):
        if not raw:
            continue
        rel = normalize_relpath(raw.decode(errors="replace"))
        if not path_in_scopes(rel, scopes):
            continue
        full = worktree / rel
        try:
            size = full.stat().st_size
        except OSError:
            size = -1
        rows.append({"path": rel, "size": size})
    rows.sort(key=lambda item: (item["size"] < 0, item["size"], item["path"]))
    return rows[: max(1, int(limit))]


def bounded_file_bundle(
    worktree: Path,
    paths: list[str],
    scopes: list[str] | tuple[str, ...],
    *,
    total_chars: int = 120_000,
    per_file_chars: int = 30_000,
) -> str:
    validate_paths(paths, scopes)
    chunks: list[str] = []
    used = 0
    for rel in paths:
        rel = normalize_relpath(rel)
        full = worktree / rel
        if not full.is_file():
            raise PatchAgentError(f"selected context path is not a file: {rel}")
        text = full.read_text(encoding="utf-8", errors="replace")
        clipped = text[:per_file_chars]
        marker = f"\n===== FILE {rel} ({len(text)} chars) =====\n"
        room = total_chars - used - len(marker)
        if room <= 0:
            break
        clipped = clipped[:room]
        chunks.append(marker + clipped)
        used += len(marker) + len(clipped)
        if used >= total_chars:
            break
    return "".join(chunks)


def apply_operations(
    worktree: Path,
    operations: list[dict],
    scopes: list[str] | tuple[str, ...],
    *,
    max_operations: int = 40,
    max_write_chars: int = 300_000,
) -> list[str]:
    if not operations:
        return []
    if len(operations) > max_operations:
        raise PatchAgentError(f"too many edit operations: {len(operations)}")
    paths = [normalize_relpath(op.get("path", "")) for op in operations]
    validate_paths(paths, scopes)
    total = sum(len(str(op.get("new", ""))) for op in operations)
    if total > max_write_chars:
        raise PatchAgentError(f"edit payload too large: {total} chars")

    touched: list[str] = []
    for op, rel in zip(operations, paths):
        kind = str(op.get("type") or "").lower()
        full = worktree / rel
        if kind == "replace":
            if not full.is_file():
                raise PatchAgentError(f"replace target missing: {rel}")
            old = str(op.get("old") or "")
            new = str(op.get("new") or "")
            if not old:
                raise PatchAgentError(f"replace old text is empty: {rel}")
            text = full.read_text(encoding="utf-8", errors="strict")
            count = text.count(old)
            if count != 1:
                raise PatchAgentError(
                    f"replace text must match exactly once in {rel}; matched {count}"
                )
            full.write_text(text.replace(old, new, 1), encoding="utf-8")
        elif kind == "create":
            if full.exists():
                raise PatchAgentError(f"create target already exists: {rel}")
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(str(op.get("new") or ""), encoding="utf-8")
        elif kind == "delete":
            if not full.is_file():
                raise PatchAgentError(f"delete target missing or not a file: {rel}")
            full.unlink()
        else:
            raise PatchAgentError(f"unsupported edit type {kind!r} for {rel}")
        touched.append(rel)
    return sorted(set(touched))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.{os.urandom(4).hex()}.tmp")
    try:
        temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp, path)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def task_keywords(text: str) -> list[str]:
    stop = {
        "task", "worker", "branch", "status", "acceptance", "criteria", "logres",
        "implementation", "current", "should", "must", "with", "from", "this",
        "that", "into", "only", "verify", "verification", "scope", "scopes",
    }
    words = re.findall(r"[A-Za-z0-9_]{4,}", text.lower())
    out: list[str] = []
    for word in words:
        if word in stop or word.isdigit() or word in out:
            continue
        out.append(word)
        if len(out) >= 40:
            break
    return out


def rank_index(index: list[dict], packet: str, limit: int = 250) -> list[dict]:
    keywords = task_keywords(packet)
    ranked = []
    for item in index:
        path = str(item["path"]).lower()
        score = sum(1 for word in keywords if word in path)
        ranked.append((score, item))
    ranked.sort(key=lambda row: (-row[0], row[1].get("size", 0), row[1]["path"]))
    return [item for _, item in ranked[: max(1, int(limit))]]

