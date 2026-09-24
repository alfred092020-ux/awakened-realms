import importlib.machinery
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
SCRIPT = TEST_DIR.parent / "bin" / "logres-autonomy"


def load_module():
    name = "test_logres_autonomy_runtime_deploy"
    loader = importlib.machinery.SourceFileLoader(name, str(SCRIPT))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class AutonomyRuntimeDeployTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def test_runtime_deploy_uses_exact_new_integration_sha(self):
        calls = []
        sha = "a" * 40

        def runner(argv, **kwargs):
            calls.append([str(x) for x in argv])
            return subprocess.CompletedProcess(argv, 0, "ok", "")

        result = self.module.run_runtime_deploy(sha, runner=runner)

        self.assertEqual(0, result.returncode)
        self.assertEqual(
            [[self.module.RUNTIME_DEPLOY, "--sha", sha]],
            calls,
        )

    def test_runtime_deploy_failure_trips_circuit_immediately(self):
        posts = []
        with tempfile.TemporaryDirectory() as td:
            self.module.STATE = Path(td) / "autonomy-state.json"
            self.module.post = lambda *args: posts.append(args)
            failed = subprocess.CompletedProcess(
                ["runtime-deploy"],
                2,
                "",
                "hash mismatch",
            )

            state = self.module.trip_on_runtime_deploy_failure(
                42,
                "b" * 40,
                failed,
            )

            self.assertTrue(state["tripped"])
            self.assertEqual(1, state["consecutive_failures"])
            self.assertIn("hash mismatch", state["last_failure"])
            self.assertEqual(1, len(posts))
            self.assertEqual("AUTONOMY_FAILURE", posts[0][0])
            self.assertEqual("CRITICAL", posts[0][1])


if __name__ == "__main__":
    unittest.main()
