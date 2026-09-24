import unittest
from pathlib import Path


CONTROL_ROOT = Path(__file__).resolve().parent.parent


class AICLIOutputContractTests(unittest.TestCase):
    def test_brain_post_does_not_pollute_machine_json_stdout(self):
        script = CONTROL_ROOT / "bin" / "logres-ai"
        text = script.read_text()
        self.assertIn(
            "subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)",
            text,
        )
        self.assertIn(
            "print(json.dumps(cli_summary(out, result_path)",
            text,
        )


if __name__ == "__main__":
    unittest.main()
