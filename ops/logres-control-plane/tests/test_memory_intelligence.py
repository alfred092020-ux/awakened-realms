import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CONTROL_ROOT = Path(__file__).resolve().parents[1]
LIB = CONTROL_ROOT / "lib"
sys.path.insert(0, str(LIB))

from logres_journal import append_chat_message, ensure_schema as ensure_journal, open_chat
from logres_memory_intelligence import (
    build_context_packet,
    distill_message,
    ensure_schema,
    mark_truth,
    relevant_facts,
)

CHAT_MEMORY = CONTROL_ROOT / "bin" / "logres-chat-memory"


class MemoryIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(":memory:")
        self.c.row_factory = sqlite3.Row
        ensure_journal(self.c)
        ensure_schema(self.c)
        self.c.executescript(
            """
            create table tasks(
              id text primary key,title text,status text,priority integer,
              lane text,note text,owner text
            );
            create table task_scopes(
              task_id text not null,path_prefix text not null,
              primary key(task_id,path_prefix)
            );
            create table task_dependencies(
              task_id text,depends_on text,kind text,rationale text
            );
            create table integration_queue(
              task_id text,sha text,branch text,status text,
              verification_mode text,updated_at text
            );
            create table knowledge_nodes(
              node_id text primary key,kind text,label text,provenance text,
              confidence real,artifact_path text,artifact_sha text,
              metadata_json text,updated_at text
            );
            create table knowledge_edges(
              src text,dst text,relation text,confidence real,
              task_id text,metadata_json text,updated_at text,
              primary key(src,dst,relation)
            );
            """
        )
        self.c.execute(
            "insert into tasks values(?,?,?,?,?,?,?)",
            (
                "BATTLE-RENDER-001",
                "Reconstruct authentic battle renderer",
                "ACTIVE",
                0,
                "battle",
                "Use APK evidence before visual guesses",
                "memory",
            ),
        )
        self.c.execute(
            "insert into task_scopes values(?,?)",
            ("BATTLE-RENDER-001", "src/game/battle"),
        )
        self.c.execute(
            "insert into task_dependencies values(?,?,?,?)",
            ("BATTLE-RENDER-001", "APK-EVIDENCE-001", "hard", "needs formulas"),
        )
        self.c.execute(
            "insert into integration_queue values(?,?,?,?,?,?)",
            (
                "BATTLE-RENDER-001",
                "a" * 40,
                "worker/battle",
                "READY_FOR_PREFLIGHT",
                "fast",
                "2026-09-25T00:00:00Z",
            ),
        )
        self.c.commit()

    def tearDown(self):
        self.c.close()

    def _message(self, role, content, metadata=None):
        open_chat(
            self.c,
            chat_id="battle",
            session_id="battle-session",
            archive_root=Path(tempfile.gettempdir()) / "memory-intelligence-tests",
        )
        return append_chat_message(
            self.c,
            session_id="battle-session",
            role=role,
            content=content,
            metadata=metadata or {},
            source_path="test",
        )

    def test_distill_is_idempotent_and_preserves_provenance_without_auto_truth(self):
        msg = self._message(
            "assistant",
            "BATTLE-RENDER-001 failed because the old timing path desynced. "
            "We decided to use APK evidence before changing animation timing.",
            {"task_id": "BATTLE-RENDER-001"},
        )
        first = distill_message(self.c, msg["id"])
        second = distill_message(self.c, msg["id"])

        self.assertGreaterEqual(first["inserted"], 1)
        self.assertEqual(0, second["inserted"])
        rows = self.c.execute(
            "select * from memory_facts where message_id=? order by id",
            (msg["id"],),
        ).fetchall()
        self.assertTrue(rows)
        self.assertTrue(all(r["truth_status"] in ("CLAIM", "SUPPORTED") for r in rows))
        self.assertTrue(all(r["task_id"] == "BATTLE-RENDER-001" for r in rows))
        self.assertTrue(all(r["session_id"] == "battle-session" for r in rows))
        self.assertTrue(all(r["ordinal"] == 1 for r in rows))

    def test_tool_summary_is_supported_but_not_verified_until_marked(self):
        msg = self._message(
            "tool-summary",
            "BATTLE-RENDER-001 full E2E PASS at exact SHA abcdef1234567890.",
            {"task_id": "BATTLE-RENDER-001"},
        )
        result = distill_message(self.c, msg["id"])
        fact = result["facts"][0]
        self.assertEqual("SUPPORTED", fact["truth_status"])
        marked = mark_truth(self.c, fact["id"], "VERIFIED", confidence=1.0)
        self.assertEqual("VERIFIED", marked["truth_status"])
        self.assertEqual(1.0, marked["confidence"])

    def test_relevant_context_is_bounded_and_task_ranked(self):
        for idx in range(30):
            msg = self._message(
                "assistant",
                f"BATTLE-RENDER-001 discovery {idx}: battle animation evidence indicates timing {idx}.",
                {"task_id": "BATTLE-RENDER-001"},
            )
            distill_message(self.c, msg["id"])
        other = self._message(
            "assistant",
            "MAP-OTHER-001 discovery: unrelated terrain evidence.",
            {"task_id": "MAP-OTHER-001"},
        )
        distill_message(self.c, other["id"])

        facts = relevant_facts(self.c, "BATTLE-RENDER-001", limit=7)
        self.assertLessEqual(len(facts), 7)
        self.assertTrue(all(f["task_id"] == "BATTLE-RENDER-001" for f in facts))

        packet = build_context_packet(
            self.c,
            "BATTLE-RENDER-001",
            fact_limit=6,
            knowledge_limit=4,
            transcript_limit=3,
        )
        self.assertEqual("BATTLE-RENDER-001", packet["task"]["id"])
        self.assertEqual(["src/game/battle"], packet["scopes"])
        self.assertEqual("APK-EVIDENCE-001", packet["dependencies"][0]["depends_on"])
        self.assertLessEqual(len(packet["structured_memory"]), 6)
        self.assertLessEqual(len(packet["transcript_excerpts"]), 3)
        self.assertTrue(
            all(
                "unrelated terrain" not in x["content"]
                for x in packet["transcript_excerpts"]
            )
        )

    def test_chat_memory_cli_auto_distills_append(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            env = os.environ.copy()
            env["LOGRES_ROOT"] = str(root)
            env["LOGRES_CONTROL_DB"] = str(root / "control.sqlite")
            env["LOGRES_CHAT_STATE_ROOT"] = str(root / "state")
            subprocess.run(
                [str(CHAT_MEMORY), "ensure", "memory", "--session", "auto-distill"],
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            result = subprocess.run(
                [
                    str(CHAT_MEMORY),
                    "append",
                    "memory",
                    "assistant",
                    "--text",
                    "MEMORY-INTELLIGENCE-001 completed structured memory test.",
                    "--metadata",
                    '{"task_id":"MEMORY-INTELLIGENCE-001"}',
                ],
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(result.stdout)
            self.assertIn("distill", payload)
            self.assertGreaterEqual(payload["distill"]["inserted"], 1)

            c = sqlite3.connect(env["LOGRES_CONTROL_DB"])
            try:
                row = c.execute(
                    "select task_id,truth_status from memory_facts limit 1"
                ).fetchone()
            finally:
                c.close()
            self.assertEqual("MEMORY-INTELLIGENCE-001", row[0])
            self.assertIn(row[1], ("CLAIM", "SUPPORTED"))


if __name__ == "__main__":
    unittest.main()
