from pathlib import Path
import os
import sys
import tempfile
import time
import unittest

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_verify_temp import sweep_verify_temp, verify_path_in_use


class VerifyTempTests(unittest.TestCase):
    def test_active_cmdline_path_is_never_removed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proc = root / "proc"
            proc.mkdir()
            candidate = root / "verify-farm-old-test"
            candidate.mkdir()
            old = time.time() - 3600
            os.utime(candidate, (old, old))
            pid = proc / "123"
            pid.mkdir()
            (pid / "cmdline").write_bytes(
                b"python3\0" + str(candidate).encode() + b"\0"
            )
            result = sweep_verify_temp(
                [candidate],
                proc_root=proc,
                now=time.time(),
                min_age_seconds=600,
            )
            self.assertTrue(candidate.exists())
            self.assertEqual([str(candidate)], result["active"])
            self.assertEqual([], result["removed"])

    def test_stale_inactive_directory_and_file_are_removed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proc = root / "proc"
            proc.mkdir()
            directory = root / "verify-once.old"
            directory.mkdir()
            (directory / "x").write_text("x")
            file = root / "verify-farm-old.sqlite"
            file.write_text("x")
            old = time.time() - 3600
            os.utime(directory, (old, old))
            os.utime(file, (old, old))
            result = sweep_verify_temp(
                [directory, file],
                proc_root=proc,
                now=time.time(),
                min_age_seconds=600,
            )
            self.assertFalse(directory.exists())
            self.assertFalse(file.exists())
            self.assertEqual(2, len(result["removed"]))

    def test_young_paths_are_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proc = root / "proc"
            proc.mkdir()
            candidate = root / "verify-all-once.new"
            candidate.mkdir()
            result = sweep_verify_temp(
                [candidate],
                proc_root=proc,
                now=time.time(),
                min_age_seconds=600,
            )
            self.assertTrue(candidate.exists())
            self.assertEqual([str(candidate)], result["young"])

    def test_cleanup_is_bounded(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proc = root / "proc"
            proc.mkdir()
            candidates = []
            old = time.time() - 3600
            for index in range(3):
                p = root / f"verify-farm-{index}"
                p.mkdir()
                os.utime(p, (old, old))
                candidates.append(p)
            result = sweep_verify_temp(
                candidates,
                proc_root=proc,
                now=time.time(),
                min_age_seconds=600,
                max_remove=2,
            )
            self.assertEqual(2, len(result["removed"]))
            self.assertEqual(1, sum(1 for p in candidates if p.exists()))

    def test_proc_read_failure_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate = root / "verify-farm-old"
            candidate.mkdir()
            self.assertTrue(
                verify_path_in_use(candidate, root / "missing-proc")
            )


if __name__ == "__main__":
    unittest.main()
