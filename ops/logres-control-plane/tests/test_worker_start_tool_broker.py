import json
import os
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

CONTROL_ROOT = Path(__file__).resolve().parents[1]
WORKER_START = CONTROL_ROOT / "bin" / "logres-worker-start"


def write_exec(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


class WorkerStartToolBrokerTests(unittest.TestCase):
    def make_env(self, root: Path, *, broker_success: bool) -> tuple[dict, Path]:
        (root / "bin").mkdir(parents=True)
        (root / "control" / "packets").mkdir(parents=True)
        (root / "work").mkdir(parents=True)
        base = root / "src" / "awakened-realms"
        base.mkdir(parents=True)

        subprocess.run(["git", "init", "-q", str(base)], check=True)
        subprocess.run(["git", "-C", str(base), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(base), "config", "user.name", "Test"], check=True)
        (base / "README.md").write_text("fixture\n")
        subprocess.run(["git", "-C", str(base), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(base), "commit", "-qm", "fixture"], check=True)

        db = root / "control" / "control.sqlite"
        c = sqlite3.connect(db)
        c.executescript(
            """
            create table tasks(id text primary key,status text,owner text,branch text);
            create table brain_task_leases(task_id text,chat_id text);
            create table claims(task_id text,owner text);
            create table task_scopes(task_id text,path_prefix text);
            insert into tasks values('TASK-001','READY','','');
            """
        )
        c.commit()
        c.close()

        write_exec(root / "bin" / "logres-chat-start", "#!/bin/sh\nexit 0\n")
        write_exec(
            root / "bin" / "logres-brain",
            "#!/bin/sh\n"
            "case \"$1\" in lease|renew|release|heartbeat) exit 0;; esac\n"
            "exit 0\n",
        )
        write_exec(root / "bin" / "logres-control", "#!/bin/sh\nexit 0\n")
        write_exec(
            root / "bin" / "logres-worker-packet",
            "#!/bin/sh\n"
            "echo 'TASK PACKET'\n"
            "echo \"task=$1 branch=$2 chat=$3\"\n",
        )
        if broker_success:
            payload = {
                "use_tool": True,
                "ready": [
                    {
                        "capability": {
                            "capability_id": "github",
                            "provider": "GitHub",
                        },
                        "score": 9.5,
                    }
                ],
                "needs_connection_check": [
                    {
                        "capability": {
                            "capability_id": "figma",
                            "provider": "Figma",
                        },
                        "score": 4.0,
                    }
                ],
            }
            write_exec(
                root / "bin" / "logres-tool-broker",
                "#!/bin/sh\ncat <<'JSON'\n"
                + json.dumps(payload)
                + "\nJSON\n",
            )
        else:
            write_exec(root / "bin" / "logres-tool-broker", "#!/bin/sh\nexit 2\n")

        script = root / "bin" / "logres-worker-start"
        script.write_text(
            WORKER_START.read_text().replace("/home/ubuntu/logres", str(root)),
            encoding="utf-8",
        )
        script.chmod(0o755)
        return os.environ.copy(), script

    def test_successful_broker_injects_packet_and_preserves_worker_ready(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            env, script = self.make_env(root, broker_success=True)
            result = subprocess.run(
                [str(script), "worker", "TASK-001"],
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertIn("WORKER_READY", result.stdout)
            self.assertIn("tool_routing=ready", result.stdout)
            tool_line = next(
                line for line in result.stdout.splitlines()
                if line.startswith("tool_recommendations=")
            )
            tool_path = Path(tool_line.split("=", 1)[1])
            self.assertTrue(tool_path.is_file())
            self.assertEqual(0o600, tool_path.stat().st_mode & 0o777)

            packet = root / "control" / "packets" / "TASK-001-worker.txt"
            text = packet.read_text()
            self.assertIn("=== TOOL CAPABILITY ROUTING ===", text)
            self.assertIn("github (GitHub score=9.5)", text)
            self.assertIn("figma (Figma score=4.0)", text)
            self.assertIn("Do not force tool use", text)

    def test_broker_failure_is_fail_open_and_worker_still_ready(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            env, script = self.make_env(root, broker_success=False)
            result = subprocess.run(
                [str(script), "worker", "TASK-001"],
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertIn("WORKER_READY", result.stdout)
            self.assertIn("tool_routing=failed-open", result.stdout)
            self.assertNotIn("tool_recommendations=", result.stdout)
            packet = root / "control" / "packets" / "TASK-001-worker.txt"
            self.assertNotIn("TOOL CAPABILITY ROUTING", packet.read_text())


if __name__ == "__main__":
    unittest.main()
