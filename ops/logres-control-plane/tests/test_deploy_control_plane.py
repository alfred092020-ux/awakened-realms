import stat
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "logres"))

from deploy_control_plane import deploy


PRODUCTION_FILES = (
    "bin/logres-ai",
    "bin/logres-ai-router",
    "bin/logres-autonomy",
    "bin/logres-autonomy-cron",
    "bin/logres-autopilot-watch",
    "bin/logres-health-snapshot",
    "bin/logres-maintain",
    "bin/logres-blocker-router",
    "bin/logres-frontier",
    "bin/logres-goal",
    "bin/logres-impact",
    "bin/logres-preview-reaper",
    "bin/logres-research-agent",
    "bin/logres-swarm",
    "bin/logres-supervisor",
    "bin/logres-coordinator",
    "bin/logres-claims-reconcile",
    "bin/logres-copilot-router",
    "bin/logres-merge-preflight",
    "bin/logres-merge-train",
    "bin/logres-doctor",
    "bin/logres-knowledge",
    "bin/logres-lead",
    "bin/logres-optimizer",
    "bin/logres-lead-snapshot",
    "bin/logres-lead-takeover",
    "bin/logres-route-reconcile",
    "bin/logres-remote-pool",
    "bin/logres-resource-broker",
    "bin/logres-runtime-deploy",
    "bin/logres-verify-all-ref",
    "bin/logres-verify-farm",
    "lib/logres_ai_common.py",
    "lib/logres_ai_router.py",
    "lib/logres_ai_runner.py",
    "lib/logres_autonomy.py",
    "lib/logres_claims_reconcile.py",
    "lib/logres_copilot.py",
    "lib/logres_copilot_router.py",
    "lib/logres_frontier.py",
    "lib/logres_goal.py",
    "lib/logres_impact.py",
    "lib/logres_knowledge.py",
    "lib/logres_optimizer.py",
    "lib/logres_preview_reaper.py",
    "lib/logres_reconcile.py",
    "lib/logres_regression_reconcile.py",
    "lib/logres_remote_pool.py",
    "lib/logres_resource_broker.py",
    "lib/logres_route_policy.py",
    "lib/logres_route_store.py",
    "lib/logres_research_agent.py",
    "lib/logres_swarm.py",
    "lib/logres_supervisor.py",
    "config/autoflow.default.json",
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
