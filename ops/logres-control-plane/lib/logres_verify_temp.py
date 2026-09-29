#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import shutil
import time
from typing import Iterable


def verify_path_in_use(path: Path, proc_root: Path = Path("/proc")) -> bool:
    needle = str(path)
    try:
        entries = list(proc_root.iterdir())
    except OSError:
        return True
    for proc in entries:
        if not proc.name.isdigit():
            continue
        try:
            cwd = os.readlink(proc / "cwd")
        except OSError:
            cwd = ""
        try:
            cmd = (proc / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                errors="replace"
            )
        except OSError:
            cmd = ""
        if cwd == needle or cwd.startswith(needle + "/") or needle in cmd:
            return True
    return False


def candidate_paths(
    tmp_root: Path = Path("/home/ubuntu/logres/tmp"),
    shm_root: Path = Path("/dev/shm/logres"),
) -> list[Path]:
    paths = list(tmp_root.glob("verify-once.*"))
    paths += list(tmp_root.glob("verify-all-once.*"))
    paths += list(shm_root.glob("verify-farm-*"))
    return sorted(set(paths), key=lambda p: str(p))


def sweep_verify_temp(
    candidates: Iterable[Path],
    *,
    proc_root: Path = Path("/proc"),
    now: float | None = None,
    min_age_seconds: float = 600.0,
    max_remove: int = 128,
) -> dict:
    now = time.time() if now is None else float(now)
    max_remove = max(0, int(max_remove))
    removed: list[str] = []
    active: list[str] = []
    young: list[str] = []
    errors: list[str] = []

    for path in sorted(set(candidates), key=lambda p: str(p)):
        if len(removed) >= max_remove:
            break
        try:
            st = path.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            errors.append(f"{path}: {exc}")
            continue
        age = max(0.0, now - st.st_mtime)
        if age < min_age_seconds:
            young.append(str(path))
            continue
        if verify_path_in_use(path, proc_root):
            active.append(str(path))
            continue
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
            removed.append(str(path))
        except FileNotFoundError:
            continue
        except OSError as exc:
            errors.append(f"{path}: {exc}")

    return {
        "removed": removed,
        "active": active,
        "young": young,
        "errors": errors,
        "limit": max_remove,
    }
