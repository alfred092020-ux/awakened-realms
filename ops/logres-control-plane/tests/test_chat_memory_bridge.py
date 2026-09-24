import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

CONTROL_ROOT = Path(__file__).resolve().parents[1]
CHAT_MEMORY = CONTROL_ROOT / "bin" / "logres-chat-memory"
CHAT_START = CONTROL_ROOT / "bin" / "logres-chat-start"


def run_json(args, env):
    result = subprocess.run(
        [str(args[0]), *args[1:]],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


class ChatMemoryBridgeTests(unittest.TestCase):
    def test_session_resume_rotation_and_live_append(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            env = os.environ.copy()
            env["LOGRES_ROOT"] = str(root)
            env["LOGRES_CONTROL_DB"] = str(root / "control" / "control.sqlite")
            env["LOGRES_CHAT_STATE_ROOT"] = str(root / "control" / "chat-runtime")

            first = run_json(
                [CHAT_MEMORY, "ensure", "finder", "--title", "Finder"],
                env,
            )
            resumed = run_json(
                [CHAT_MEMORY, "ensure", "finder"],
                env,
            )
            self.assertEqual(first["session_id"], resumed["session_id"])
            self.assertTrue(resumed["resumed"])

            user = run_json(
                [
                    CHAT_MEMORY,
                    "append",
                    "finder",
                    "user",
                    "--text",
                    "first user turn",
                    "--external-id",
                    "turn-1-user",
                ],
                env,
            )
            assistant = run_json(
                [
                    CHAT_MEMORY,
                    "append",
                    "finder",
                    "assistant",
                    "--text",
                    "first assistant turn",
                    "--external-id",
                    "turn-1-assistant",
                ],
                env,
            )
            duplicate = run_json(
                [
                    CHAT_MEMORY,
                    "append",
                    "finder",
                    "assistant",
                    "--text",
                    "first assistant turn",
                    "--external-id",
                    "turn-1-assistant",
                ],
                env,
            )
            self.assertEqual(1, user["ordinal"])
            self.assertEqual(2, assistant["ordinal"])
            self.assertFalse(duplicate["inserted"])

            rotated = run_json(
                [CHAT_MEMORY, "new", "finder", "--title", "Fresh Finder"],
                env,
            )
            self.assertNotEqual(first["session_id"], rotated["session_id"])
            current = run_json([CHAT_MEMORY, "current", "finder"], env)
            self.assertEqual(rotated["session_id"], current["session_id"])

            old_archive = Path(first["archive_path"])
            self.assertTrue(old_archive.is_file())
            self.assertEqual(2, len(old_archive.read_text().splitlines()))
            state_path = Path(rotated["state_path"])
            self.assertEqual(0o600, state_path.stat().st_mode & 0o777)

    def test_chat_start_auto_joins_then_resumes_and_rotates_memory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bin_root = root / "bin"
            bin_root.mkdir(parents=True)
            log_path = root / "brain.log"

            brain = bin_root / "logres-brain"
            brain.write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' \"$*\" >> \"$LOGRES_TEST_LOG\"\n"
                "exit 0\n"
            )
            brain.chmod(0o755)

            for name in ("logres-sync-health", "logres-coordinator", "logres-nexus"):
                stub = bin_root / name
                stub.write_text("#!/bin/sh\nexit 0\n")
                stub.chmod(0o755)

            os.symlink(CHAT_MEMORY, bin_root / "logres-chat-memory")

            env = os.environ.copy()
            env["LOGRES_ROOT"] = str(root)
            env["LOGRES_CONTROL_DB"] = str(root / "control" / "control.sqlite")
            env["LOGRES_CHAT_STATE_ROOT"] = str(root / "control" / "chat-runtime")
            env["LOGRES_TEST_LOG"] = str(log_path)

            def start(*extra):
                result = subprocess.run(
                    [
                        str(CHAT_START),
                        "new-worker",
                        "--name",
                        "New Worker",
                        *extra,
                    ],
                    env=env,
                    text=True,
                    capture_output=True,
                    check=True,
                )
                line = next(
                    x for x in result.stdout.splitlines()
                    if x.startswith("CHAT_MEMORY_SESSION=")
                )
                return line.split("=", 1)[1]

            first = start()
            second = start()
            third = start("--new-session")

            self.assertEqual(first, second)
            self.assertNotEqual(first, third)

            calls = log_path.read_text().splitlines()
            self.assertGreaterEqual(len(calls), 6)
            self.assertEqual("join new-worker --name New Worker", calls[0])
            self.assertEqual("catchup new-worker --limit 20", calls[1])
            self.assertEqual("join new-worker --name New Worker", calls[2])
            self.assertEqual("catchup new-worker --limit 20", calls[3])


if __name__ == "__main__":
    unittest.main()
