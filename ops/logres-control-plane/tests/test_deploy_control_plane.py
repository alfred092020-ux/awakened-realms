import stat
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "logres"))

from deploy_control_plane import (
    MANIFEST,
    REPO_BOUND_TOOL_EXCLUSIONS,
    deploy,
)


PRODUCTION_FILES = (
    "bin/logres-ai",
    "bin/logres-ai-router",
    "bin/logres-autonomy",
    "bin/logres-autonomy-cron",
    "bin/logres-autopilot-watch",
    "bin/logres-architecture-pressure",
    "bin/logres-code-index",
    "bin/logres-decision-bridge",
    "bin/logres-experiment-executor",
    "bin/logres-governor",
    "bin/logres-lifecycle-guard",
    "bin/logres-mission-contract-proposals",
    "bin/logres-sync-health",
    "bin/logres-temporal",
    "bin/logres-health-snapshot",
    "bin/logres-maintain",
    "bin/logres-blocker-router",
    "bin/logres-behavior-trace",
    "bin/logres-bottleneck",
    "bin/logres-engine-reconcile",
    "bin/logres-fault-injection",
    "bin/logres-chaos-cert",
    "bin/logres-health-confidence",
    "bin/logres-journal",
    "bin/logres-mission-coverage",
    "bin/logres-replay",
    "bin/logres-semantic-dedupe",
    "bin/logres-shadow-scheduler",
    "bin/logres-status",
    "bin/logres-verify-cache",
    "bin/logres-visual-compare",
    "bin/logres-visual-truth",
    "bin/logres-workspace-lifecycle",
    "bin/logres-workspace-gc",
    "bin/logres-zero-human",
    "bin/logres-frontier",
    "bin/logres-finish-task",
    "bin/logres-goal-contract",
    "bin/logres-goal",
    "bin/logres-goal-executor",
    "bin/logres-goal-certify",
    "bin/logres-hardware-qa",
    "bin/logres-finish-loop",
    "bin/logres-impact",
    "bin/logres-preview-reaper",
    "bin/logres-regression-capture",
    "bin/logres-regression-dedupe",
    "bin/logres-recon-loop",
    "bin/logres-research-agent",
    "bin/logres-regression-supersede",
    "bin/logres-swarm",
    "bin/logres-supervisor",
    "bin/logres-coordinator",
    "bin/logres-claims-reconcile",
    "bin/logres-copilot-router",
    "bin/logres-merge-preflight",
    "bin/logres-merge-train",
    "bin/logres-mission",
    "bin/logres-doctor",
    "bin/logres-knowledge",
    "bin/logres-lead",
    "bin/logres-optimizer",
    "bin/logres-throughput",
    "bin/logres-lead-snapshot",
    "bin/logres-lead-takeover",
    "bin/logres-route-reconcile",
    "bin/logres-remote-pool",
    "bin/logres-resource-broker",
    "bin/logres-runtime-deploy",
    "bin/logres-verify-all-ref",
    "bin/logres-verify-farm",
    "lib/logres_ai_common.py",
    "lib/logres_architecture_pressure.py",
    "lib/logres_behavior_trace.py",
    "lib/logres_decision_bridge.py",
    "lib/logres_experiment_executor.py",
    "lib/logres_governor.py",
    "lib/logres_lifecycle_guard.py",
    "lib/logres_mission_contract_proposals.py",
    "lib/logres_temporal.py",
    "lib/logres_temporal_drift.py",
    "lib/logres_bottleneck.py",
    "lib/logres_engine_reconcile.py",
    "lib/logres_fault_injection.py",
    "lib/logres_chaos_cert.py",
    "lib/logres_health_confidence.py",
    "lib/logres_journal.py",
    "lib/logres_mission_coverage.py",
    "lib/logres_recon_loop.py",
    "lib/logres_replay.py",
    "lib/logres_regression_supersede.py",
    "lib/logres_semantic_dedupe.py",
    "lib/logres_shadow_scheduler.py",
    "lib/logres_status.py",
    "lib/logres_verify_cache.py",
    "lib/logres_visual_compare.py",
    "lib/logres_visual_truth.py",
    "lib/logres_workspace_lifecycle.py",
    "lib/logres_workspace_gc.py",
    "lib/logres_zero_human.py",
    "lib/logres_ai_router.py",
    "lib/logres_ai_runner.py",
    "lib/logres_autonomy.py",
    "lib/logres_claims_reconcile.py",
    "lib/logres_copilot.py",
    "lib/logres_copilot_router.py",
    "lib/logres_dependency.py",
    "lib/logres_frontier.py",
    "lib/logres_goal_contract.py",
    "lib/logres_goal.py",
    "lib/logres_goal_executor.py",
    "lib/logres_goal_certify.py",
    "lib/logres_finish_loop.py",
    "lib/logres_impact.py",
    "lib/logres_knowledge.py",
    "lib/logres_mission.py",
    "lib/logres_optimizer.py",
    "lib/logres_preview_reaper.py",
    "lib/logres_reconcile.py",
    "lib/logres_regression_reconcile.py",
    "lib/logres_regression_signature.py",
    "lib/logres_remote_pool.py",
    "lib/logres_resource_broker.py",
    "lib/logres_route_policy.py",
    "lib/logres_route_store.py",
    "lib/logres_research_agent.py",
    "lib/logres_swarm.py",
    "lib/logres_supervisor.py",
    "lib/logres_throughput.py",
    "config/autoflow.default.json",
    "config/milestone_contracts.json",
    "config/mission.default.json",
)


def make_source(root: Path) -> Path:
    source = root / "source"
    for relative in PRODUCTION_FILES:
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative == "bin/logres-ai":
            path.write_text("#!/bin/sh\necho ai\n")
        elif relative.endswith(".py"):
            path.write_text(f"# fixture {relative}\n")
        elif relative.startswith("bin/"):
            path.write_text(f"#!/bin/sh\n# fixture {relative}\n")
        else:
            path.write_text(relative + "\n")
    (source / "secret.txt").write_text("must-not-deploy\n")
    return source


class DeployControlPlaneTests(unittest.TestCase):
    def test_deploy_copies_complete_production_manifest_and_preserves_modes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = make_source(root)
            target = root / "target"

            deployed = deploy(source, target, dry_run=False)

            self.assertEqual(set(PRODUCTION_FILES), {
                str(item.destination.relative_to(target)) for item in deployed
            })
            self.assertEqual(
                "#!/bin/sh\necho ai\n",
                (target / "bin" / "logres-ai").read_text(),
            )
            self.assertTrue((target / "lib" / "logres_reconcile.py").is_file())
            self.assertTrue(
                (target / "lib" / "logres_claims_reconcile.py").is_file()
            )
            self.assertTrue(
                (target / "lib" / "logres_regression_reconcile.py").is_file()
            )
            self.assertTrue(
                (target / "bin" / "logres-claims-reconcile").is_file()
            )
            self.assertTrue(
                (target / "bin" / "logres-health-snapshot").is_file()
            )
            self.assertTrue(
                (target / "bin" / "logres-maintain").is_file()
            )
            self.assertTrue((target / "config" / "autoflow.default.json").is_file())
            self.assertTrue((target / "config" / "mission.default.json").is_file())
            self.assertTrue((target / "bin" / "logres-mission").is_file())
            self.assertEqual(
                0o700,
                stat.S_IMODE((target / "bin" / "logres-ai").stat().st_mode),
            )
            self.assertEqual(
                0o755,
                stat.S_IMODE(
                    (target / "bin" / "logres-route-reconcile").stat().st_mode
                ),
            )
            self.assertEqual(
                0o755,
                stat.S_IMODE(
                    (target / "bin" / "logres-blocker-router").stat().st_mode
                ),
            )
            self.assertEqual(
                0o755,
                stat.S_IMODE(
                    (target / "bin" / "logres-preview-reaper").stat().st_mode
                ),
            )
            self.assertEqual(
                0o600,
                stat.S_IMODE(
                    (target / "lib" / "logres_preview_reaper.py").stat().st_mode
                ),
            )
            self.assertFalse((target / "secret.txt").exists())
            self.assertTrue(
                all("openai_api_key" not in str(item.destination) for item in deployed)
            )

    def test_repository_manifest_is_closed_over_local_python_imports(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "target"
            deployed = deploy(
                REPO_ROOT / "ops" / "logres-control-plane",
                target,
                dry_run=True,
            )
            destinations = {
                str(item.destination.relative_to(target)) for item in deployed
            }
            self.assertIn("lib/logres_regression_reconcile.py", destinations)

    def test_repository_runtime_surface_is_manifested_or_explicitly_repo_bound(self):
        control_root = REPO_ROOT / "ops" / "logres-control-plane"
        runtime_files = {
            f"bin/{path.name}"
            for path in (control_root / "bin").iterdir()
            if path.is_file() and path.name.startswith("logres-")
        }
        runtime_files.update(
            f"lib/{path.name}"
            for path in (control_root / "lib").iterdir()
            if (
                path.is_file()
                and path.name.startswith("logres_")
                and path.suffix == ".py"
            )
        )
        manifested_runtime = {
            item
            for item in MANIFEST
            if item.startswith("bin/") or item.startswith("lib/")
        }

        self.assertEqual(
            runtime_files - REPO_BOUND_TOOL_EXCLUSIONS,
            manifested_runtime,
        )
        self.assertEqual(
            {
                "bin/logres-reconstruct",
                "bin/logres-truth",
            },
            REPO_BOUND_TOOL_EXCLUSIONS,
        )
        self.assertTrue(
            all(
                (control_root / item).is_file()
                for item in REPO_BOUND_TOOL_EXCLUSIONS
            )
        )

    def test_missing_local_python_import_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = make_source(root)
            coordinator = source / "bin" / "logres-coordinator"
            coordinator.write_text(
                "#!/usr/bin/env python3\n"
                "from logres_hidden_dependency import helper\n"
            )
            hidden = source / "lib" / "logres_hidden_dependency.py"
            hidden.write_text("helper = object()\n")

            with self.assertRaisesRegex(
                ValueError,
                "deployment manifest missing local imports",
            ):
                deploy(source, root / "target", dry_run=True)

    def test_dry_run_makes_no_changes_and_lists_complete_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = make_source(root)
            target = root / "target"

            deployed = deploy(source, target, dry_run=True)

            self.assertEqual(len(PRODUCTION_FILES), len(deployed))
            self.assertEqual(set(PRODUCTION_FILES), {
                str(item.destination.relative_to(target)) for item in deployed
            })
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
