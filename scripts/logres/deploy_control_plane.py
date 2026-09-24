#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


MANIFEST: dict[str, tuple[str, int]] = {
    "bin/logres-ai": ("bin/logres-ai", 0o700),
    "bin/logres-autopilot-watch": ("bin/logres-autopilot-watch", 0o755),
    "bin/logres-doctor": ("bin/logres-doctor", 0o700),
    "bin/logres-lead": ("bin/logres-lead", 0o700),
    "lib/logres_ai_common.py": ("lib/logres_ai_common.py", 0o600),
    "lib/logres_ai_runner.py": ("lib/logres_ai_runner.py", 0o600),
}


@dataclass(frozen=True)
class Deployment:
    source: Path
    destination: Path
    mode: int


def _validate_source(source_root: Path) -> list[Deployment]:
    deployments: list[Deployment] = []
    for source_rel, (destination_rel, mode) in MANIFEST.items():
        source = source_root / source_rel
        if not source.is_file():
            raise FileNotFoundError(f"manifest source missing: {source}")
        deployments.append(
            Deployment(
                source=source,
                destination=Path(destination_rel),
                mode=mode,
            )
        )
    return deployments


def _atomic_copy(source: Path, destination: Path, mode: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = source.read_bytes()
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, mode)
        os.replace(temp_path, destination)
    finally:
        if temp_path.exists():
            temp_path.unlink()
def deploy(source_root: Path, target_root: Path, dry_run: bool = False) -> list[Deployment]:
    source_root = Path(source_root).resolve()
    target_root = Path(target_root).resolve()
    manifest = _validate_source(source_root)
    resolved = [
        Deployment(item.source, target_root / item.destination, item.mode)
        for item in manifest
    ]
    if dry_run:
        return resolved
    for item in resolved:
        _atomic_copy(item.source, item.destination, item.mode)
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy versioned Logres control-plane helpers.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    deployments = deploy(args.source, args.target, dry_run=args.dry_run)
    prefix = "DRY-RUN" if args.dry_run else "DEPLOYED"
    for item in deployments:
        print(
            f"{prefix} {item.source} -> {item.destination} "
            f"mode={oct(item.mode)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
