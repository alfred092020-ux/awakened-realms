import unittest
from pathlib import Path


CONTROL_ROOT = Path(__file__).resolve().parent.parent


class AICLIOutputContractTests(unittest.TestCase):
    def test_cli_uses_secure_keyfile_fallback_for_cron_environments(self):
        script = CONTROL_ROOT / "bin" / "logres-ai"
        text = script.read_text()
        self.assertIn(
            '"/home/ubuntu/.config/logres/openai_api_key"',
            text,
        )
        self.assertIn(
            'os.environ.get("OPENAI_API_KEY", "").strip()',
            text,
        )
        self.assertIn(
            "return OpenAI(api_key=key)",
            text,
        )
        self.assertNotIn(
            "print(key)",
            text,
        )

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
