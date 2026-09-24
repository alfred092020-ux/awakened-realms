import stat
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "logres"))

from deploy_control_plane import deploy


class DeployControlPlaneTests(unittest.TestCase):
    def test_deploy_copies_only_manifested_files_and_preserves_modes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source"
            target = root / "target"
            (source / "bin").mkdir(parents=True)
            (source / "lib").mkdir()
            files = {
                "bin/logres-ai": "#!/bin/sh\necho ai\n",
                "bin/logres-autopilot-watch": "#!/bin/sh\necho watch\n",
                "bin/logres-doctor": "#!/bin/sh\necho doctor\n",
                "bin/logres-lead": "#!/bin/sh\necho lead\n",
                "lib/logres_ai_common.py": "VALUE = 'common'\n",
                "lib/logres_ai_runner.py": "VALUE = 'runner'\n",
            }
            for relative, content in files.items():
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            (source / "secret.txt").write_text("must-not-deploy\n")

            deployed = deploy(source, target, dry_run=False)

            self.assertEqual(
                "#!/bin/sh\necho ai\n",
                (target / "bin" / "logres-ai").read_text(),
            )
            self.assertTrue((target / "lib" / "logres_ai_runner.py").is_file())
            self.assertEqual(
                0o700,
                stat.S_IMODE((target / "bin" / "logres-ai").stat().st_mode),
            )
            self.assertFalse((target / "secret.txt").exists())
            self.assertTrue(
                all("openai_api_key" not in str(item.destination) for item in deployed)
            )

    def test_dry_run_makes_no_changes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source"
            target = root / "target"
            for relative in (
                "bin/logres-ai",
                "bin/logres-autopilot-watch",
                "bin/logres-doctor",
                "bin/logres-lead",
                "lib/logres_ai_common.py",
                "lib/logres_ai_runner.py",
            ):
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(relative + "\n")

            deployed = deploy(source, target, dry_run=True)

            self.assertEqual(6, len(deployed))
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
