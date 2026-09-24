#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


MANIFEST: dict[str, tuple[str, int]] = {
    "bin/logres-ai": ("bin/logres-ai", 0o700),
    "bin/logres-ai-router": ("bin/logres-ai-router", 0o755),
    "bin/logres-autonomy": ("bin/logres-autonomy", 0o755),
    "bin/logres-autonomy-cron": ("bin/logres-autonomy-cron", 0o755),
    "bin/logres-autopilot-watch": ("bin/logres-autopilot-watch", 0o755),
    "bin/logres-blocker-router": ("bin/logres-blocker-router", 0o755),
    "bin/logres-frontier": ("bin/logres-frontier", 0o755),
    "bin/logres-impact": ("bin/logres-impact", 0o755),
    "bin/logres-preview-reaper": ("bin/logres-preview-reaper", 0o755),
    "bin/logres-research-agent": ("bin/logres-research-agent", 0o755),
    "bin/logres-swarm": ("bin/logres-swarm", 0o755),
    "bin/logres-supervisor": ("bin/logres-supervisor", 0o755),
    "bin/logres-coordinator": ("bin/logres-coordinator", 0o755),
    "bin/logres-claims-reconcile": ("bin/logres-claims-reconcile", 0o755),
    "bin/logres-copilot-router": ("bin/logres-copilot-router", 0o755),
    "bin/logres-merge-preflight": ("bin/logres-merge-preflight", 0o755),
    "bin/logres-merge-train": ("bin/logres-merge-train", 0o755),
    "bin/logres-doctor": ("bin/logres-doctor", 0o700),
    "bin/logres-knowledge": ("bin/logres-knowledge", 0o755),
    "bin/logres-lead": ("bin/logres-lead", 0o700),
    "bin/logres-optimizer": ("bin/logres-optimizer", 0o755),
    "bin/logres-lead-snapshot": ("bin/logres-lead-snapshot", 0o755),
    "bin/logres-lead-takeover": ("bin/logres-lead-takeover", 0o755),
    "bin/logres-route-reconcile": ("bin/logres-route-reconcile", 0o755),
    "bin/logres-remote-pool": ("bin/logres-remote-pool", 0o755),
    "bin/logres-resource-broker": ("bin/logres-resource-broker", 0o755),
    "bin/logres-runtime-deploy": ("bin/logres-runtime-deploy", 0o755),
    "bin/logres-verify-all-ref": ("bin/logres-verify-all-ref", 0o755),
    "bin/logres-verify-farm": ("bin/logres-verify-farm", 0o755),
    "lib/logres_ai_common.py": ("lib/logres_ai_common.py", 0o600),
    "lib/logres_ai_router.py": ("lib/logres_ai_router.py", 0o600),
    "lib/logres_ai_runner.py": ("lib/logres_ai_runner.py", 0o600),
    "lib/logres_autonomy.py": ("lib/logres_autonomy.py", 0o600),
    "lib/logres_claims_reconcile.py": ("lib/logres_claims_reconcile.py", 0o600),
    "lib/logres_copilot.py": ("lib/logres_copilot.py", 0o600),
    "lib/logres_copilot_router.py": ("lib/logres_copilot_router.py", 0o600),
    "lib/logres_frontier.py": ("lib/logres_frontier.py", 0o600),
    "lib/logres_impact.py": ("lib/logres_impact.py", 0o600),
    "lib/logres_knowledge.py": ("lib/logres_knowledge.py", 0o600),
    "lib/logres_optimizer.py": ("lib/logres_optimizer.py", 0o600),
    "lib/logres_preview_reaper.py": ("lib/logres_preview_reaper.py", 0o600),
    "lib/logres_reconcile.py": ("lib/logres_reconcile.py", 0o600),
    "lib/logres_regression_reconcile.py": ("lib/logres_regression_reconcile.py", 0o600),
    "lib/logres_remote_pool.py": ("lib/logres_remote_pool.py", 0o600),
    "lib/logres_resource_broker.py": ("lib/logres_resource_broker.py", 0o600),
    "lib/logres_route_policy.py": ("lib/logres_route_policy.py", 0o600),
    "lib/logres_route_store.py": ("lib/logres_route_store.py", 0o600),
    "lib/logres_research_agent.py": ("lib/logres_research_agent.py", 0o600),
    "lib/logres_swarm.py": ("lib/logres_swarm.py", 0o600),
    "lib/logres_supervisor.py": ("lib/logres_supervisor.py", 0o600),
    "config/autoflow.default.json": ("config/autoflow.default.json", 0o600),
}


@dataclass(frozen=True)
class Deployment:
    source: Path
    destination: Path
    mode: int


def _is_python_source(path: Path) -> bool:
    if path.suffix == ".py":
        return True
    try:
        first = path.read_text(errors="replace").splitlines()[0]
    except (OSError, IndexError):
        return False
    return "python" in first.lower()


def _local_logres_imports(path: Path) -> set[str]:
    if not _is_python_source(path):
        return set()
    try:
        tree = ast.parse(path.read_text())
    except (OSError, SyntaxError) as exc:
        raise ValueError(f"invalid Python source in deployment manifest: {path}: {exc}") from exc
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name.split(".", 1)[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module.split(".", 1)[0]]
        else:
            continue
        modules.update(name for name in names if name.startswith("logres_"))
    return modules


def _validate_import_closure(source_root: Path) -> None:
    manifest_sources = set(MANIFEST)
    missing: dict[str, list[str]] = {}
    for source_rel in MANIFEST:
        source = source_root / source_rel
        if not source.is_file():
            continue
        for module in _local_logres_imports(source):
            local_rel = f"lib/{module}.py"
            if not (source_root / local_rel).is_file():
                continue
            if local_rel not in manifest_sources:
                missing.setdefault(local_rel, []).append(source_rel)
    if missing:
        details = ", ".join(
            f"{module} imported by {','.join(sorted(importers))}"
            for module, importers in sorted(missing.items())
        )
        raise ValueError(f"deployment manifest missing local imports: {details}")


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
    _validate_import_closure(source_root)
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
