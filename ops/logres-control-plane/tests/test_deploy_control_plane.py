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
    "bin/logres-coordinator",
    "bin/logres-copilot-router",
    "bin/logres-merge-preflight",
    "bin/logres-merge-train",
    "bin/logres-doctor",
    "bin/logres-lead",
    "bin/logres-lead-snapshot",
    "bin/logres-lead-takeover",
    "bin/logres-route-reconcile",
    "bin/logres-verify-all-ref",
    "lib/logres_ai_common.py",
    "lib/logres_ai_router.py",
    "lib/logres_ai_runner.py",
    "lib/logres_autonomy.py",
    "lib/logres_copilot.py",
    "lib/logres_copilot_router.py",
    "lib/logres_reconcile.py",
    "lib/logres_route_policy.py",
    "lib/logres_route_store.py",
    "config/autoflow.default.json",
)


def make_source(root: Path) -> Path:
    source = root / "source"
    for relative in PRODUCTION_FILES:
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative == "bin/logres-ai":
            path.write_text("#!/bin/sh\necho ai\n")
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
            self.assertFalse((target / "secret.txt").exists())
            self.assertTrue(
                all("openai_api_key" not in str(item.destination) for item in deployed)
            )

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
