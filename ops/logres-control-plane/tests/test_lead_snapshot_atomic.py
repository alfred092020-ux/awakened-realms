import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
SCRIPT = TEST_DIR.parent / "bin" / "logres-lead-snapshot"

COMMANDS = (
    "logres-code-index",
    "logres-control",
    "logres-lead-json",
    "logres-worktree-audit",
    "logres-branch-sweep",
    "logres-branch-archaeology",
    "logres-integration-review",
    "logres-coordinator",
    "logres-throughput",
    "logres-merge-train",
    "logres-merge-preflight",
    "logres-integration-pager",
)

OUTPUTS = (
    "LEAD_SNAPSHOT.txt",
    "LEAD_SNAPSHOT.json",
    "WORKTREE_AUDIT.txt",
    "BRANCH_SWEEP.txt",
    "BRANCH_ARCHAEOLOGY.txt",
    "INTEGRATION_REVIEW.txt",
    "COORDINATION_PLAN.txt",
    "WORK_WAVE.txt",
    "THROUGHPUT.txt",
    "THROUGHPUT.json",
    "MERGE_TRAIN.txt",
    "MERGE_PREFLIGHT.txt",
)


def install_fake_bins(root: Path, *, failing: str | None = None) -> None:
    bindir = root / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    for name in COMMANDS:
        target = bindir / name
        if name == failing:
            body = textwrap.dedent(
                """\
                #!/usr/bin/env bash
                printf 'partial-output\n'
                exit 7
                """
            )
        else:
            body = textwrap.dedent(
                f"""\
                #!/usr/bin/env bash
                set -euo pipefail
                sleep "${{FAKE_SLEEP:-0.02}}"
                printf '{name}:%s:%s\n' "${{RUN_ID:-x}}" "$*"
                """
            )
        target.write_text(body)
        target.chmod(0o755)


def snapshot_env(root: Path, run_id: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "LOGRES_ROOT": str(root),
            "RUN_ID": run_id,
            "LOGRES_MAINTENANCE_LANE_LOCK": str(root / f"{run_id}.lane.lock"),
            "LOGRES_LEAD_SNAPSHOT_LOCK": str(root / f"{run_id}.snapshot.lock"),
            "FAKE_SLEEP": "0.03",
        }
    )
    return env


def temp_outputs(root: Path) -> list[Path]:
    control = root / "control"
    return sorted(
        p
        for p in control.iterdir()
        if ".tmp." in p.name or p.name.endswith(".tmp")
    )


class LeadSnapshotAtomicTests(unittest.TestCase):
    def test_concurrent_publishers_use_unique_atomic_temps(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "control").mkdir()
            (root / "index").mkdir()
            install_fake_bins(root)

            first = subprocess.Popen(
                [str(SCRIPT)],
                env=snapshot_env(root, "first"),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            second = subprocess.Popen(
                [str(SCRIPT)],
                env=snapshot_env(root, "second"),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            out1, err1 = first.communicate(timeout=20)
            out2, err2 = second.communicate(timeout=20)

            self.assertEqual(0, first.returncode, err1 or out1)
            self.assertEqual(0, second.returncode, err2 or out2)
            self.assertNotIn("cannot stat", err1 + err2)
            for name in OUTPUTS:
                self.assertTrue((root / "control" / name).is_file(), name)
            self.assertEqual([], temp_outputs(root))

    def test_failed_producer_cleans_temp_and_preserves_existing_target(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "control").mkdir()
            (root / "index").mkdir()
            install_fake_bins(root, failing="logres-lead-json")
            target = root / "control" / "LEAD_SNAPSHOT.json"
            target.write_text("previous\n")

            result = subprocess.run(
                [str(SCRIPT)],
                env=snapshot_env(root, "failure"),
                text=True,
                capture_output=True,
                timeout=20,
                check=False,
            )

            self.assertEqual(7, result.returncode)
            self.assertEqual("previous\n", target.read_text())
            self.assertEqual([], temp_outputs(root))

    def test_no_fixed_publication_tmp_names_remain(self):
        text = SCRIPT.read_text()
        for name in OUTPUTS:
            self.assertNotIn(f"{name}.tmp", text)
        self.assertIn('mktemp "$dir/.${base}.tmp.XXXXXX"', text)


if __name__ == "__main__":
    unittest.main()
