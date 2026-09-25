import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_patch_agent import (
    PatchAgentError,
    apply_operations,
    bounded_file_bundle,
    git_changed_paths,
    normalize_relpath,
    path_in_scopes,
    scoped_file_index,
    validate_paths,
)


class PatchAgentTests(unittest.TestCase):
    def init_repo(self, root: Path) -> None:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(
            ["git", "-C", str(root), "config", "user.email", "test@example.invalid"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(root), "config", "user.name", "Test"],
            check=True,
        )
        (root / "src").mkdir()
        (root / "src" / "game.py").write_text("value = 1\n", encoding="utf-8")
        (root / ".github").mkdir()
        (root / ".github" / "workflow.yml").write_text("name: test\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "base"], check=True)

    def test_dot_prefixed_path_is_preserved(self):
        self.assertEqual(".github/workflow.yml", normalize_relpath(".github/workflow.yml"))
        self.assertTrue(
            path_in_scopes(
                ".github/workflow.yml",
                [".github/workflow.yml"],
            )
        )

    def test_unsafe_relative_paths_are_rejected(self):
        for value in ("../secret", "/etc/passwd", "src/../../secret"):
            with self.subTest(value=value):
                with self.assertRaises(PatchAgentError):
                    normalize_relpath(value)

    def test_scope_allows_exact_file_and_descendants(self):
        self.assertTrue(path_in_scopes("src/game.py", ["src/game.py"]))
        self.assertTrue(path_in_scopes("src/game.py", ["src"]))
        self.assertFalse(path_in_scopes("tests/game.py", ["src"]))

    def test_replace_requires_unique_text_and_stays_in_scope(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.init_repo(root)
            touched = apply_operations(
                root,
                [
                    {
                        "type": "replace",
                        "path": "src/game.py",
                        "old": "value = 1",
                        "new": "value = 2",
                    }
                ],
                ["src/game.py"],
            )
            self.assertEqual(["src/game.py"], touched)
            self.assertEqual("value = 2\n", (root / "src/game.py").read_text())
            with self.assertRaises(PatchAgentError):
                apply_operations(
                    root,
                    [
                        {
                            "type": "replace",
                            "path": "src/game.py",
                            "old": "missing",
                            "new": "x",
                        }
                    ],
                    ["src/game.py"],
                )

    def test_out_of_scope_create_is_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.init_repo(root)
            with self.assertRaises(PatchAgentError):
                apply_operations(
                    root,
                    [
                        {
                            "type": "create",
                            "path": "secret.txt",
                            "old": "",
                            "new": "nope",
                        }
                    ],
                    ["src"],
                )
            self.assertFalse((root / "secret.txt").exists())

    def test_changed_paths_and_context_are_scope_bounded(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.init_repo(root)
            (root / "src" / "game.py").write_text("value = 3\n", encoding="utf-8")
            self.assertEqual(["src/game.py"], git_changed_paths(root))
            validate_paths(git_changed_paths(root), ["src"])
            index = scoped_file_index(root, ["src"])
            self.assertEqual(["src/game.py"], [item["path"] for item in index])
            bundle = bounded_file_bundle(root, ["src/game.py"], ["src"])
            self.assertIn("value = 3", bundle)
            self.assertNotIn("workflow.yml", bundle)

    def test_empty_scopes_fail_closed(self):
        with self.assertRaises(PatchAgentError):
            validate_paths(["src/game.py"], [])


if __name__ == "__main__":
    unittest.main()

