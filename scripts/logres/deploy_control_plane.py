#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


MANIFEST: dict[str, tuple[str, int]] = {
    "bin/logres-brain": ("bin/logres-brain", 0o755),
    "bin/logres-superbrain": ("bin/logres-superbrain", 0o755),
    "bin/logres-superbrain-maintain": ("bin/logres-superbrain-maintain", 0o755),
    "bin/logres-ai": ("bin/logres-ai", 0o700),
    "bin/logres-ai-router": ("bin/logres-ai-router", 0o755),
    "bin/logres-autonomy": ("bin/logres-autonomy", 0o755),
    "bin/logres-autonomy-cron": ("bin/logres-autonomy-cron", 0o755),
    "bin/logres-autopilot-watch": ("bin/logres-autopilot-watch", 0o755),
    "bin/logres-architecture-pressure": ("bin/logres-architecture-pressure", 0o755),
    "bin/logres-code-index": ("bin/logres-code-index", 0o755),
    "bin/logres-context-pack": ("bin/logres-context-pack", 0o755),
    "bin/logres-decision-bridge": ("bin/logres-decision-bridge", 0o755),
    "bin/logres-device-proof": ("bin/logres-device-proof", 0o755),
    "bin/logres-devin-agent": ("bin/logres-devin-agent", 0o755),
    "bin/logres-devin-isolate": ("bin/logres-devin-isolate", 0o755),
    "bin/logres-devin-sandbox-setup": ("bin/logres-devin-sandbox-setup", 0o755),
    "bin/logres-experiment-executor": ("bin/logres-experiment-executor", 0o755),
    "bin/logres-governor": ("bin/logres-governor", 0o755),
    "bin/logres-lifecycle-guard": ("bin/logres-lifecycle-guard", 0o755),
    "bin/logres-mission-contract-proposals": ("bin/logres-mission-contract-proposals", 0o755),
    "bin/logres-sync-health": ("bin/logres-sync-health", 0o755),
    "bin/logres-temporal": ("bin/logres-temporal", 0o755),
    "bin/logres-health-snapshot": ("bin/logres-health-snapshot", 0o755),
    "bin/logres-maintain": ("bin/logres-maintain", 0o755),
    "bin/logres-blocker-router": ("bin/logres-blocker-router", 0o755),
    "bin/logres-behavior-trace": ("bin/logres-behavior-trace", 0o755),
    "bin/logres-bottleneck": ("bin/logres-bottleneck", 0o755),
    "bin/logres-engine-reconcile": ("bin/logres-engine-reconcile", 0o755),
    "bin/logres-fault-injection": ("bin/logres-fault-injection", 0o755),
    "bin/logres-chaos-cert": ("bin/logres-chaos-cert", 0o755),
    "bin/logres-health-confidence": ("bin/logres-health-confidence", 0o755),
    "bin/logres-chat-memory": ("bin/logres-chat-memory", 0o755),
    "bin/logres-chat-wake": ("bin/logres-chat-wake", 0o755),
    "bin/logres-chat-watchdog": ("bin/logres-chat-watchdog", 0o755),
    "bin/logres-chat-contract": ("bin/logres-chat-contract", 0o755),
    "bin/logres-phone-local-ai": ("bin/logres-phone-local-ai", 0o755),
    "bin/logres-tool-broker": ("bin/logres-tool-broker", 0o755),
    "bin/logres-chat-start": ("bin/logres-chat-start", 0o755),
    "bin/logres-worker-start": ("bin/logres-worker-start", 0o755),
    "bin/logres-journal": ("bin/logres-journal", 0o755),
    "bin/logres-mission-coverage": ("bin/logres-mission-coverage", 0o755),
    "bin/logres-replay": ("bin/logres-replay", 0o755),
    "bin/logres-semantic-dedupe": ("bin/logres-semantic-dedupe", 0o755),
    "bin/logres-shadow-scheduler": ("bin/logres-shadow-scheduler", 0o755),
    "bin/logres-status": ("bin/logres-status", 0o755),
    "bin/logres-verify-cache": ("bin/logres-verify-cache", 0o755),
    "bin/logres-visual-compare": ("bin/logres-visual-compare", 0o755),
    "bin/logres-visual-truth": ("bin/logres-visual-truth", 0o755),
    "bin/logres-workspace-lifecycle": ("bin/logres-workspace-lifecycle", 0o755),
    "bin/logres-workspace-gc": ("bin/logres-workspace-gc", 0o755),
    "bin/logres-zero-human": ("bin/logres-zero-human", 0o755),
    "bin/logres-frontier": ("bin/logres-frontier", 0o755),
    "bin/logres-finish-task": ("bin/logres-finish-task", 0o755),
    "bin/logres-goal-contract": ("bin/logres-goal-contract", 0o755),
    "bin/logres-goal": ("bin/logres-goal", 0o755),
    "bin/logres-goal-executor": ("bin/logres-goal-executor", 0o755),
    "bin/logres-goal-certify": ("bin/logres-goal-certify", 0o755),
    "bin/logres-hardware-qa": ("bin/logres-hardware-qa", 0o755),
    "bin/logres-phone-qa": ("bin/logres-phone-qa", 0o755),
    "bin/logres-finish-loop": ("bin/logres-finish-loop", 0o755),
    "bin/logres-impact": ("bin/logres-impact", 0o755),
    "bin/logres-integration": ("bin/logres-integration", 0o755),
    "bin/logres-preview-reaper": ("bin/logres-preview-reaper", 0o755),
    "bin/logres-patch-agent": ("bin/logres-patch-agent", 0o755),
    "bin/logres-regression-capture": ("bin/logres-regression-capture", 0o755),
    "bin/logres-regression-dedupe": ("bin/logres-regression-dedupe", 0o755),
    "bin/logres-recon-loop": ("bin/logres-recon-loop", 0o755),
    "bin/logres-research-agent": ("bin/logres-research-agent", 0o755),
    "bin/logres-regression-supersede": ("bin/logres-regression-supersede", 0o755),
    "bin/logres-swarm": ("bin/logres-swarm", 0o755),
    "bin/logres-supervisor": ("bin/logres-supervisor", 0o755),
    "bin/logres-coordinator": ("bin/logres-coordinator", 0o755),
    "bin/logres-claims-reconcile": ("bin/logres-claims-reconcile", 0o755),
    "bin/logres-copilot-router": ("bin/logres-copilot-router", 0o755),
    "bin/logres-merge-preflight": ("bin/logres-merge-preflight", 0o755),
    "bin/logres-merge-train": ("bin/logres-merge-train", 0o755),
    "bin/logres-mission": ("bin/logres-mission", 0o755),
    "bin/logres-doctor": ("bin/logres-doctor", 0o700),
    "bin/logres-knowledge": ("bin/logres-knowledge", 0o755),
    "bin/logres-lead": ("bin/logres-lead", 0o700),
    "bin/logres-optimizer": ("bin/logres-optimizer", 0o755),
    "bin/logres-throughput": ("bin/logres-throughput", 0o755),
    "bin/logres-lead-snapshot": ("bin/logres-lead-snapshot", 0o755),
    "bin/logres-lead-takeover": ("bin/logres-lead-takeover", 0o755),
    "bin/logres-route-reconcile": ("bin/logres-route-reconcile", 0o755),
    "bin/logres-remote-pool": ("bin/logres-remote-pool", 0o755),
    "bin/logres-resource-broker": ("bin/logres-resource-broker", 0o755),
    "bin/logres-runtime-deploy": ("bin/logres-runtime-deploy", 0o755),
    "bin/logres-verify-all-ref": ("bin/logres-verify-all-ref", 0o755),
    "bin/logres-verify-farm": ("bin/logres-verify-farm", 0o755),
    "bin/logres-correctness": ("bin/logres-correctness", 0o755),
    "bin/logres-factory-metrics": ("bin/logres-factory-metrics", 0o755),
    "bin/logres-gate": ("bin/logres-gate", 0o755),
    "bin/logres-peer-consult": ("bin/logres-peer-consult", 0o755),
    "lib/logres_ai_common.py": ("lib/logres_ai_common.py", 0o600),
    "lib/logres_superbrain.py": ("lib/logres_superbrain.py", 0o600),
    "lib/logres_migrations.py": ("lib/logres_migrations.py", 0o600),
    "lib/logres_architecture_pressure.py": ("lib/logres_architecture_pressure.py", 0o600),
    "lib/logres_behavior_trace.py": ("lib/logres_behavior_trace.py", 0o600),
    "lib/logres_decision_bridge.py": ("lib/logres_decision_bridge.py", 0o600),
    "lib/logres_devin.py": ("lib/logres_devin.py", 0o600),
    "lib/logres_devin_isolation.py": ("lib/logres_devin_isolation.py", 0o600),
    "lib/logres_experiment_executor.py": ("lib/logres_experiment_executor.py", 0o600),
    "lib/logres_governor.py": ("lib/logres_governor.py", 0o600),
    "lib/logres_lifecycle_guard.py": ("lib/logres_lifecycle_guard.py", 0o600),
    "lib/logres_mission_contract_proposals.py": ("lib/logres_mission_contract_proposals.py", 0o600),
    "lib/logres_temporal.py": ("lib/logres_temporal.py", 0o600),
    "lib/logres_temporal_drift.py": ("lib/logres_temporal_drift.py", 0o600),
    "lib/logres_bottleneck.py": ("lib/logres_bottleneck.py", 0o600),
    "lib/logres_engine_reconcile.py": ("lib/logres_engine_reconcile.py", 0o600),
    "lib/logres_fault_injection.py": ("lib/logres_fault_injection.py", 0o600),
    "lib/logres_chaos_cert.py": ("lib/logres_chaos_cert.py", 0o600),
    "lib/logres_health_confidence.py": ("lib/logres_health_confidence.py", 0o600),
    "lib/logres_journal.py": ("lib/logres_journal.py", 0o600),
    "lib/logres_chat_wake.py": ("lib/logres_chat_wake.py", 0o600),
    "lib/logres_chat_watchdog.py": ("lib/logres_chat_watchdog.py", 0o600),
    "lib/logres_chat_contract.py": ("lib/logres_chat_contract.py", 0o600),
    "lib/logres_phone_local_ai.py": ("lib/logres_phone_local_ai.py", 0o600),
    "lib/logres_capability_broker.py": ("lib/logres_capability_broker.py", 0o600),
    "lib/logres_mission_coverage.py": ("lib/logres_mission_coverage.py", 0o600),
    "lib/logres_recon_loop.py": ("lib/logres_recon_loop.py", 0o600),
    "lib/logres_replay.py": ("lib/logres_replay.py", 0o600),
    "lib/logres_regression_supersede.py": ("lib/logres_regression_supersede.py", 0o600),
    "lib/logres_semantic_dedupe.py": ("lib/logres_semantic_dedupe.py", 0o600),
    "lib/logres_shadow_scheduler.py": ("lib/logres_shadow_scheduler.py", 0o600),
    "lib/logres_status.py": ("lib/logres_status.py", 0o600),
    "lib/logres_verify_cache.py": ("lib/logres_verify_cache.py", 0o600),
    "lib/logres_visual_compare.py": ("lib/logres_visual_compare.py", 0o600),
    "lib/logres_visual_truth.py": ("lib/logres_visual_truth.py", 0o600),
    "lib/logres_workspace_lifecycle.py": ("lib/logres_workspace_lifecycle.py", 0o600),
    "lib/logres_workspace_gc.py": ("lib/logres_workspace_gc.py", 0o600),
    "lib/logres_zero_human.py": ("lib/logres_zero_human.py", 0o600),
    "lib/logres_ai_router.py": ("lib/logres_ai_router.py", 0o600),
    "lib/logres_ai_runner.py": ("lib/logres_ai_runner.py", 0o600),
    "lib/logres_autonomy.py": ("lib/logres_autonomy.py", 0o600),
    "lib/logres_claims_reconcile.py": ("lib/logres_claims_reconcile.py", 0o600),
    "lib/logres_copilot.py": ("lib/logres_copilot.py", 0o600),
    "lib/logres_copilot_router.py": ("lib/logres_copilot_router.py", 0o600),
    "lib/logres_context_pack.py": ("lib/logres_context_pack.py", 0o600),
    "lib/logres_dependency.py": ("lib/logres_dependency.py", 0o600),
    "lib/logres_frontier.py": ("lib/logres_frontier.py", 0o600),
    "lib/logres_goal_contract.py": ("lib/logres_goal_contract.py", 0o600),
    "lib/logres_goal.py": ("lib/logres_goal.py", 0o600),
    "lib/logres_goal_executor.py": ("lib/logres_goal_executor.py", 0o600),
    "lib/logres_goal_certify.py": ("lib/logres_goal_certify.py", 0o600),
    "lib/logres_finish_loop.py": ("lib/logres_finish_loop.py", 0o600),
    "lib/logres_impact.py": ("lib/logres_impact.py", 0o600),
    "lib/logres_integration.py": ("lib/logres_integration.py", 0o600),
    "lib/logres_knowledge.py": ("lib/logres_knowledge.py", 0o600),
    "lib/logres_mission.py": ("lib/logres_mission.py", 0o600),
    "lib/logres_optimizer.py": ("lib/logres_optimizer.py", 0o600),
    "lib/logres_patch_agent.py": ("lib/logres_patch_agent.py", 0o600),
    "lib/logres_preview_reaper.py": ("lib/logres_preview_reaper.py", 0o600),
    "lib/logres_reconcile.py": ("lib/logres_reconcile.py", 0o600),
    "lib/logres_regression_reconcile.py": ("lib/logres_regression_reconcile.py", 0o600),
    "lib/logres_regression_signature.py": ("lib/logres_regression_signature.py", 0o600),
    "lib/logres_remote_pool.py": ("lib/logres_remote_pool.py", 0o600),
    "lib/logres_resource_broker.py": ("lib/logres_resource_broker.py", 0o600),
    "lib/logres_route_policy.py": ("lib/logres_route_policy.py", 0o600),
    "lib/logres_route_store.py": ("lib/logres_route_store.py", 0o600),
    "lib/logres_research_agent.py": ("lib/logres_research_agent.py", 0o600),
    "lib/logres_swarm.py": ("lib/logres_swarm.py", 0o600),
    "lib/logres_supervisor.py": ("lib/logres_supervisor.py", 0o600),
    "lib/logres_throughput.py": ("lib/logres_throughput.py", 0o600),
    "lib/logres_correctness.py": ("lib/logres_correctness.py", 0o600),
    "lib/logres_factory_metrics.py": ("lib/logres_factory_metrics.py", 0o600),
    "lib/logres_peer_consultation.py": ("lib/logres_peer_consultation.py", 0o600),
    "migrations/20260926_001_superbrain_v2.sql": ("migrations/20260926_001_superbrain_v2.sql", 0o600),
    "migrations/20260926_002_superbrain_selfheal_dispatch.sql": ("migrations/20260926_002_superbrain_selfheal_dispatch.sql", 0o600),
    "apparmor/usr.bin.bwrap.logres": ("apparmor/usr.bin.bwrap.logres", 0o600),
    "systemd/logres-devin-worker@.service": ("systemd/logres-devin-worker@.service", 0o644),
    "config/devin_isolation.json": ("config/devin_isolation.json", 0o600),
    "config/devin_workers.json": ("config/devin_workers.json", 0o600),
    "config/correctness_policy.json": ("config/correctness_policy.json", 0o600),
    "config/factory_metrics.json": ("config/factory_metrics.json", 0o600),
    "config/peer_consultation.json": ("config/peer_consultation.json", 0o600),
    "config/autoflow.default.json": ("config/autoflow.default.json", 0o600),
    "config/chat_bridge.default.json": ("config/chat_bridge.default.json", 0o600),
    "config/chat_watchdog.default.json": ("config/chat_watchdog.default.json", 0o600),
    "config/phone_local_ai.default.json": ("config/phone_local_ai.default.json", 0o600),
    "config/context_pack.json": ("config/context_pack.json", 0o600),
    "config/completion_manifest.json": ("config/completion_manifest.json", 0o600),
    "config/milestone_contracts.json": ("config/milestone_contracts.json", 0o600),
    "config/mission.default.json": ("config/mission.default.json", 0o600),
}

# These helpers intentionally execute from the repository because they import
# scripts/logres modules using repository-relative paths. Deploying them into
# /home/ubuntu/logres/bin would silently resolve the wrong repository root.
REPO_BOUND_TOOL_EXCLUSIONS = {
    "bin/logres-reconstruct",
    "bin/logres-truth",
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


def _runtime_surface_files(source_root: Path) -> set[str]:
    files: set[str] = set()
    bin_root = source_root / "bin"
    if bin_root.is_dir():
        files.update(
            f"bin/{path.name}"
            for path in bin_root.iterdir()
            if path.is_file() and path.name.startswith("logres-")
        )
    lib_root = source_root / "lib"
    if lib_root.is_dir():
        files.update(
            f"lib/{path.name}"
            for path in lib_root.iterdir()
            if (
                path.is_file()
                and path.name.startswith("logres_")
                and path.suffix == ".py"
            )
        )
    return files


def _validate_runtime_surface_coverage(source_root: Path) -> None:
    runtime_files = _runtime_surface_files(source_root)
    allowed = set(MANIFEST) | REPO_BOUND_TOOL_EXCLUSIONS
    missing = sorted(runtime_files - allowed)
    if missing:
        raise ValueError(
            "deployment manifest missing runtime-safe control-plane files: "
            + ", ".join(missing)
        )


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
    _validate_runtime_surface_coverage(source_root)
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
