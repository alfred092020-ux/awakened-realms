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
    distill_pending,
    ensure_schema,
    mark_truth,
    relevant_facts,
)

CHAT_MEMORY = CONTROL_ROOT / "bin" / "logres-chat-memory"
CONTEXT_PACK = CONTROL_ROOT / "bin" / "logres-context-pack"


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

    def test_tool_summary_stays_supported_and_generic_mark_cannot_verify(self):
        msg = self._message(
            "tool-summary",
            "BATTLE-RENDER-001 full E2E PASS at exact SHA abcdef1234567890.",
            {"task_id": "BATTLE-RENDER-001"},
        )
        result = distill_message(self.c, msg["id"])
        fact = result["facts"][0]
        self.assertEqual("SUPPORTED", fact["truth_status"])
        with self.assertRaisesRegex(ValueError, "cannot promote.*VERIFIED"):
            mark_truth(self.c, fact["id"], "VERIFIED", confidence=1.0)
        with self.assertRaisesRegex(ValueError, "cannot promote.*SUPPORTED"):
            mark_truth(self.c, fact["id"], "SUPPORTED", confidence=0.8)
        with self.assertRaisesRegex(ValueError, "confidence.*0.*1"):
            mark_truth(self.c, fact["id"], "CLAIM", confidence=1.1)
        with self.assertRaisesRegex(ValueError, "confidence.*0.*1"):
            mark_truth(self.c, fact["id"], "CLAIM", confidence=-0.1)
        with self.assertRaisesRegex(ValueError, "cannot increase confidence"):
            mark_truth(self.c, fact["id"], "CLAIM", confidence=0.9)
        marked = mark_truth(self.c, fact["id"], "CLAIM", confidence=0.5)
        self.assertEqual("CLAIM", marked["truth_status"])
        self.assertEqual(0.5, marked["confidence"])

    def test_pending_distillation_requires_session_and_bounded_limit(self):
        with self.assertRaisesRegex(ValueError, "session_id is required"):
            distill_pending(self.c)
        with self.assertRaisesRegex(ValueError, "limit must be between 1 and 500"):
            distill_pending(self.c, session_id="battle-session", limit=0)
        with self.assertRaisesRegex(ValueError, "limit must be between 1 and 500"):
            distill_pending(self.c, session_id="battle-session", limit=501)

    def test_pending_distillation_is_session_scoped(self):
        battle = self._message(
            "assistant",
            "BATTLE-RENDER-001 discovery: scoped pending memory.",
            {"task_id": "BATTLE-RENDER-001"},
        )
        open_chat(
            self.c,
            chat_id="other",
            session_id="other-session",
            archive_root=Path(tempfile.gettempdir()) / "memory-intelligence-tests",
        )
        other = append_chat_message(
            self.c,
            session_id="other-session",
            role="assistant",
            content="MAP-OTHER-001 discovery: unrelated pending memory.",
            metadata={"task_id": "MAP-OTHER-001"},
            source_path="test",
        )
        result = distill_pending(self.c, session_id="battle-session", limit=10)
        self.assertEqual(1, result["processed_messages"])
        self.assertIsNotNone(
            self.c.execute("select 1 from memory_facts where message_id=?", (battle["id"],)).fetchone()
        )
        self.assertIsNone(
            self.c.execute("select 1 from memory_facts where message_id=?", (other["id"],)).fetchone()
        )

    def test_source_sha_requires_exact_full_git_sha(self):
        short = self._message(
            "tool-summary",
            "BATTLE-RENDER-001 PASS at exact SHA abcdef1234567890.",
            {"task_id": "BATTLE-RENDER-001"},
        )
        short_fact = distill_message(self.c, short["id"])["facts"][0]
        self.assertIsNone(short_fact["source_sha"])
        full_sha = "a" * 40
        full = self._message(
            "tool-summary",
            f"BATTLE-RENDER-001 PASS at exact SHA {full_sha}.",
            {"task_id": "BATTLE-RENDER-001"},
        )
        full_fact = distill_message(self.c, full["id"])["facts"][0]
        self.assertEqual(full_sha, full_fact["source_sha"])

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

    def test_context_packet_keeps_unverified_memory_out_of_operational_transcript(self):
        claim = self._message(
            "assistant",
            "BATTLE-RENDER-001 discovery: animation timing remains an inference.",
            {"task_id": "BATTLE-RENDER-001"},
        )
        claim_fact = distill_message(self.c, claim["id"])["facts"][0]
        verified_sha = "b" * 40
        supported = self._message(
            "tool-summary",
            f"BATTLE-RENDER-001 build PASS at exact SHA {verified_sha} with supporting test evidence.",
            {"task_id": "BATTLE-RENDER-001"},
        )
        supported_fact = distill_message(self.c, supported["id"])["facts"][0]

        packet = build_context_packet(self.c, "BATTLE-RENDER-001")
        self.assertEqual("Brain only", packet["memory_policy"]["operational_truth_source"])
        self.assertEqual([], packet["transcript_excerpts"])
        self.assertTrue(all("provenance" in fact for fact in packet["structured_memory"]))
        self.assertTrue(all(not fact["operational_truth"] for fact in packet["structured_memory"]))
        self.assertFalse(claim_fact["truth_status"] == "VERIFIED")

        self.c.execute(
            "update memory_facts set truth_status='VERIFIED', confidence=1.0 where id=?",
            (supported_fact["id"],),
        )
        self.c.commit()
        label_only_packet = build_context_packet(self.c, "BATTLE-RENDER-001")
        self.assertEqual([], label_only_packet["transcript_excerpts"])
        self.assertTrue(all(not fact["operational_truth"] for fact in label_only_packet["structured_memory"]))

        self.c.execute(
            "create table verification(ref text primary key, sha text, mode text, status text, duration_sec real, ran_at text, details text)"
        )
        self.c.execute(
            "insert into verification values(?,?,?,?,?,?,?)",
            ("worker/battle", verified_sha, "full-e2e", "PASS", 1.0, "2026-09-27", "exact-sha test"),
        )
        self.c.commit()
        verified_packet = build_context_packet(self.c, "BATTLE-RENDER-001")
        self.assertEqual(1, len(verified_packet["transcript_excerpts"]))
        self.assertEqual(supported["id"], verified_packet["transcript_excerpts"][0]["message_id"])
        verified_fact = next(
            fact
            for fact in verified_packet["structured_memory"]
            if fact["id"] == supported_fact["id"]
        )
        self.assertFalse(verified_fact["operational_truth"])
        self.assertTrue(verified_fact["context_evidence_eligible"])
        self.assertEqual("PASS", verified_fact["provenance"]["exact_sha_verification"])

    def test_context_pack_chat_rejects_expired_lease(self):
        self.c.execute(
            "create table brain_task_leases(task_id text primary key, chat_id text, lease_until_epoch real)"
        )
        self.c.execute(
            "insert into brain_task_leases values(?,?,?)",
            ("BATTLE-RENDER-001", "battle", 1.0),
        )
        self.c.commit()
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "control.sqlite"
            disk = sqlite3.connect(db)
            self.c.backup(disk)
            disk.close()
            env = os.environ.copy()
            env["LOGRES_CONTROL_DB"] = str(db)
            result = subprocess.run(
                [sys.executable, str(CONTEXT_PACK), "--chat", "battle"],
                env=env, text=True, capture_output=True, check=False,
            )
        self.assertEqual(result.returncode, 5, result.stderr)
        self.assertIn("no active task lease", result.stderr)

    def test_context_pack_chat_rejects_task_mismatch(self):
        self.c.execute(
            "create table brain_task_leases(task_id text primary key, chat_id text, lease_until_epoch real)"
        )
        self.c.execute(
            "insert into brain_task_leases values(?,?,?)",
            ("BATTLE-RENDER-001", "battle", 9999999999.0),
        )
        self.c.commit()
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "control.sqlite"
            disk = sqlite3.connect(db)
            self.c.backup(disk)
            disk.close()
            env = os.environ.copy()
            env["LOGRES_CONTROL_DB"] = str(db)
            result = subprocess.run(
                [sys.executable, str(CONTEXT_PACK), "MAP-OTHER-001", "--chat", "battle"],
                env=env, text=True, capture_output=True, check=False,
            )
        self.assertEqual(result.returncode, 6, result.stderr)
        self.assertIn("does not own task", result.stderr)

    def test_chat_start_bootstrap_requests_bounded_memory_context_and_fails_closed(self):
        chat_start = (CONTROL_ROOT / "bin" / "logres-chat-start").read_text()
        self.assertIn("=== RELEVANT TASK CONTEXT ===", chat_start)
        self.assertIn(
            'logres-context-pack" --chat "$CHAT" --fact-limit 12 --knowledge-limit 8 --transcript-limit 8',
            chat_start,
        )
        self.assertIn("CONTEXT_RC=$?", chat_start)
        self.assertIn('[[ "$CONTEXT_RC" == "5" ]]', chat_start)
        self.assertIn('exit "$CONTEXT_RC"', chat_start)
        self.assertNotIn('|| echo "No active task context."', chat_start)

    def test_context_pack_cli_resolves_active_chat_and_returns_memory_context(self):
        msg = self._message(
            "assistant",
            "BATTLE-RENDER-001 discovery: verified battle timing context.",
            {"task_id": "BATTLE-RENDER-001"},
        )
        distill_message(self.c, msg["id"])
        self.c.execute(
            "create table brain_task_leases(task_id text primary key, chat_id text, lease_until_epoch real)"
        )
        self.c.execute(
            "insert into brain_task_leases values(?,?,?)",
            ("BATTLE-RENDER-001", "battle", 9999999999.0),
        )
        self.c.commit()
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "control.sqlite"
            disk = sqlite3.connect(db)
            self.c.backup(disk)
            disk.close()
            env = os.environ.copy()
            env["LOGRES_CONTROL_DB"] = str(db)
            result = subprocess.run(
                [
                    sys.executable,
                    str(CONTEXT_PACK),
                    "--chat",
                    "battle",
                    "--fact-limit",
                    "6",
                    "--knowledge-limit",
                    "4",
                    "--transcript-limit",
                    "3",
                ],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["task"]["id"], "BATTLE-RENDER-001")
        self.assertLessEqual(len(payload["structured_memory"]), 6)
        self.assertTrue(
            any("verified battle timing" in item["statement"] for item in payload["structured_memory"])
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
