import contextlib
import io
import json
import os
import runpy
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
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
        self.assertTrue(all(r["truth_status"] == "CLAIM" for r in rows))
        self.assertTrue(all(r["task_id"] == "BATTLE-RENDER-001" for r in rows))
        self.assertTrue(all(r["session_id"] == "battle-session" for r in rows))
        self.assertTrue(all(r["ordinal"] == 1 for r in rows))

    def test_tool_summary_remains_advisory_claim(self):
        msg = self._message(
            "tool-summary",
            "BATTLE-RENDER-001 full E2E PASS at exact SHA abcdef1234567890.",
            {"task_id": "BATTLE-RENDER-001"},
        )
        result = distill_message(self.c, msg["id"])
        fact = result["facts"][0]
        self.assertEqual("CLAIM", fact["truth_status"])
        self.assertFalse(fact["operational_truth"])

    def test_task_scope_requires_explicit_journal_metadata_and_binds_message_hash(self):
        unscoped = self._message(
            "assistant",
            "BATTLE-RENDER-001 discovery from text only must remain unscoped.",
            {},
        )
        unscoped_facts = distill_message(self.c, unscoped["id"])["facts"]
        self.assertTrue(unscoped_facts)
        self.assertTrue(all(fact["task_id"] is None for fact in unscoped_facts))

        scoped = self._message(
            "assistant",
            "BATTLE-RENDER-001 discovery from explicitly scoped journal metadata.",
            {"task_id": "BATTLE-RENDER-001"},
        )
        scoped_fact = distill_message(self.c, scoped["id"])["facts"][0]
        message_sha = self.c.execute(
            "select message_sha256 from chat_messages where id=?",
            (scoped["id"],),
        ).fetchone()[0]
        self.assertEqual("BATTLE-RENDER-001", scoped_fact["task_id"])
        self.assertEqual(message_sha, scoped_fact["provenance"]["message_sha256"])
        self.assertEqual("journal-metadata", scoped_fact["provenance"]["task_binding"])

    def test_memory_fact_retains_journal_hash_without_source_message(self):
        msg = self._message(
            "assistant",
            "BATTLE-RENDER-001 discovery: persistent journal provenance test.",
            {"task_id": "BATTLE-RENDER-001"},
        )
        fact = distill_message(self.c, msg["id"])["facts"][0]
        original_sha = self.c.execute(
            "select message_sha256 from chat_messages where id=?",
            (msg["id"],),
        ).fetchone()[0]
        stored_sha = self.c.execute(
            "select message_sha256 from memory_facts where id=?",
            (fact["id"],),
        ).fetchone()[0]
        self.assertEqual(original_sha, stored_sha)

        self.c.execute("delete from chat_messages where id=?", (msg["id"],))
        self.c.commit()
        facts = relevant_facts(self.c, "BATTLE-RENDER-001", limit=5)
        retained = next(item for item in facts if item["id"] == fact["id"])
        self.assertEqual(original_sha, retained["provenance"]["message_sha256"])

    def test_schema_migrates_legacy_memory_facts_and_backfills_journal_hash(self):
        c = sqlite3.connect(":memory:")
        c.row_factory = sqlite3.Row
        try:
            ensure_journal(c)
            open_chat(
                c,
                chat_id="legacy",
                session_id="legacy-session",
                archive_root=Path(tempfile.gettempdir()) / "memory-intelligence-tests",
            )
            msg = append_chat_message(
                c,
                session_id="legacy-session",
                role="assistant",
                content="LEGACY-MEMORY-001 discovery: migrate provenance.",
                metadata={"task_id": "LEGACY-MEMORY-001"},
                source_path="test",
            )
            c.executescript(
                """
                create table memory_facts(
                  id integer primary key autoincrement,
                  fingerprint text not null unique,
                  session_id text not null,
                  message_id integer not null,
                  ordinal integer not null,
                  chat_id text not null,
                  role text not null,
                  kind text not null,
                  statement text not null,
                  confidence real not null,
                  truth_status text not null default 'CLAIM',
                  task_id text,
                  source_sha text,
                  metadata_json text not null default '{}',
                  supersedes_id integer,
                  created_at text not null default (datetime('now')),
                  updated_at text not null default (datetime('now'))
                );
                """
            )
            c.execute(
                """
                insert into memory_facts(
                  fingerprint,session_id,message_id,ordinal,chat_id,role,kind,
                  statement,confidence,truth_status,task_id,metadata_json
                ) values(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "legacy-fingerprint",
                    "legacy-session",
                    msg["id"],
                    1,
                    "legacy",
                    "assistant",
                    "discovery",
                    "LEGACY-MEMORY-001 discovery: migrate provenance.",
                    0.5,
                    "CLAIM",
                    "LEGACY-MEMORY-001",
                    "{}",
                ),
            )
            c.execute(
                """
                insert into memory_facts(
                  fingerprint,session_id,message_id,ordinal,chat_id,role,kind,
                  statement,confidence,truth_status,task_id,metadata_json
                ) values(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "orphan-fingerprint",
                    "missing-session",
                    999999,
                    1,
                    "legacy",
                    "assistant",
                    "discovery",
                    "LEGACY-MEMORY-001 discovery: orphan provenance.",
                    0.5,
                    "CLAIM",
                    "LEGACY-MEMORY-001",
                    "{}",
                ),
            )
            c.commit()
            expected_sha = c.execute(
                "select message_sha256 from chat_messages where id=?", (msg["id"],)
            ).fetchone()[0]
            ensure_schema(c)
            columns = {row[1] for row in c.execute("pragma table_info(memory_facts)")}
            stored_sha = c.execute(
                "select message_sha256 from memory_facts where fingerprint='legacy-fingerprint'"
            ).fetchone()[0]
            orphan_sha = c.execute(
                "select message_sha256 from memory_facts where fingerprint='orphan-fingerprint'"
            ).fetchone()[0]
            visible = relevant_facts(c, "LEGACY-MEMORY-001", limit=10)
            self.assertIn("message_sha256", columns)
            self.assertEqual(expected_sha, stored_sha)
            self.assertIsNone(orphan_sha)
            self.assertEqual(
                ["legacy-fingerprint"],
                [item["fingerprint"] for item in visible],
            )
        finally:
            c.close()

    def test_distillation_redacts_credential_shaped_memory(self):
        value = "redactme1234567890"
        msg = self._message(
            "assistant",
            f"BATTLE-RENDER-001 failed with token={value}.",
            {"task_id": "BATTLE-RENDER-001", "secret": value},
        )
        distill_message(self.c, msg["id"])
        row = self.c.execute(
            "select statement,metadata_json from memory_facts where message_id=? limit 1",
            (msg["id"],),
        ).fetchone()
        stored = row[0] + row[1]
        self.assertNotIn(value, stored)
        self.assertIn("[REDACTED]", stored)

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

    def test_memory_does_not_promote_message_supplied_source_sha(self):
        full_sha = "a" * 40
        msg = self._message(
            "tool-summary",
            f"BATTLE-RENDER-001 PASS at exact SHA {full_sha}.",
            {"task_id": "BATTLE-RENDER-001", "source_sha": full_sha},
        )
        fact = distill_message(self.c, msg["id"])["facts"][0]
        self.assertIsNone(fact["source_sha"])
        self.assertIsNone(fact["provenance"]["source_sha"])

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
        unscoped = self._message(
            "assistant",
            "Battle animation evidence indicates timing from an unscoped discussion.",
            {},
        )
        distill_message(self.c, unscoped["id"])

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

    def test_context_packet_redacts_knowledge_label_and_provenance(self):
        value = "redactknowledge1234567890"
        self.c.execute(
            "insert into knowledge_nodes values(?,?,?,?,?,?,?,?,?)",
            (
                "evidence:redact",
                "evidence",
                f"token={value}",
                f"password={value}",
                0.9,
                None,
                None,
                "{}",
                "2026-09-27",
            ),
        )
        self.c.execute(
            "insert into knowledge_edges values(?,?,?,?,?,?,?)",
            (
                "evidence:redact",
                "task:BATTLE-RENDER-001",
                "supports",
                0.9,
                "BATTLE-RENDER-001",
                "{}",
                "2026-09-27",
            ),
        )
        self.c.commit()
        packet = build_context_packet(self.c, "BATTLE-RENDER-001")
        encoded = json.dumps(packet, sort_keys=True)
        self.assertNotIn(value, encoded)
        self.assertIn("[REDACTED]", encoded)
        self.assertGreaterEqual(packet["redactions"], 2)

    def test_context_packet_supports_legacy_knowledge_edges_without_task_id(self):
        self.c.execute("drop table knowledge_edges")
        self.c.execute(
            """
            create table knowledge_edges(
              src text,dst text,relation text,confidence real,
              metadata_json text,updated_at text,
              primary key(src,dst,relation)
            )
            """
        )
        self.c.execute(
            "insert into knowledge_nodes values(?,?,?,?,?,?,?,?,?)",
            (
                "evidence:legacy",
                "evidence",
                "Legacy evidence",
                "Brain",
                0.9,
                None,
                None,
                "{}",
                "2026-09-27",
            ),
        )
        self.c.execute(
            "insert into knowledge_edges values(?,?,?,?,?,?)",
            (
                "evidence:legacy",
                "task:BATTLE-RENDER-001",
                "supports",
                0.9,
                "{}",
                "2026-09-27",
            ),
        )
        self.c.commit()
        packet = build_context_packet(self.c, "BATTLE-RENDER-001")
        self.assertTrue(any(item["node_id"] == "evidence:legacy" for item in packet["knowledge"]))

    def test_context_packet_memory_is_advisory_and_never_replays_raw_transcript(self):
        claim = self._message(
            "assistant",
            "BATTLE-RENDER-001 discovery: animation timing remains an inference.",
            {"task_id": "BATTLE-RENDER-001"},
        )
        claim_fact = distill_message(self.c, claim["id"])["facts"][0]
        supported = self._message(
            "tool-summary",
            "BATTLE-RENDER-001 build PASS with supporting test evidence.",
            {"task_id": "BATTLE-RENDER-001"},
        )
        supported_fact = distill_message(self.c, supported["id"])["facts"][0]

        packet = build_context_packet(self.c, "BATTLE-RENDER-001")
        self.assertEqual("Brain only", packet["memory_policy"]["operational_truth_source"])
        self.assertTrue(packet["memory_policy"]["memory_facts_are_context_only"])
        self.assertFalse(packet["memory_policy"]["raw_transcript_replay"])
        self.assertEqual([], packet["transcript_excerpts"])
        self.assertTrue(all("provenance" in fact for fact in packet["structured_memory"]))
        self.assertTrue(all(not fact["operational_truth"] for fact in packet["structured_memory"]))

        self.c.execute(
            "update memory_facts set truth_status='VERIFIED', confidence=1.0 where id in (?,?)",
            (claim_fact["id"], supported_fact["id"]),
        )
        self.c.commit()
        mutated_packet = build_context_packet(self.c, "BATTLE-RENDER-001")
        self.assertEqual([], mutated_packet["transcript_excerpts"])
        mutated_ids = {claim_fact["id"], supported_fact["id"]}
        self.assertTrue(
            mutated_ids.isdisjoint({fact["id"] for fact in mutated_packet["structured_memory"]})
        )

    def test_context_pack_chat_selects_newest_active_lease_deterministically(self):
        self.c.execute(
            "insert into tasks values(?,?,?,?,?,?,?)",
            ("MAP-OTHER-001", "Map task", "ACTIVE", 0, "map", "", "memory"),
        )
        self.c.execute(
            "create table brain_task_leases(task_id text primary key, chat_id text, lease_until_epoch real)"
        )
        self.c.executemany(
            "insert into brain_task_leases values(?,?,?)",
            [
                ("BATTLE-RENDER-001", "battle", 9999999998.0),
                ("MAP-OTHER-001", "battle", 9999999999.0),
            ],
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
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("MAP-OTHER-001", payload["task"]["id"])

    def test_context_pack_chat_revalidates_lease_before_emit(self):
        self.c.execute(
            "create table brain_task_leases(task_id text primary key, chat_id text, lease_until_epoch real)"
        )
        self.c.execute(
            "insert into brain_task_leases values(?,?,?)",
            ("BATTLE-RENDER-001", "battle", 150.0),
        )
        self.c.commit()
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "control.sqlite"
            disk = sqlite3.connect(db)
            self.c.backup(disk)
            disk.close()
            module = runpy.run_path(str(CONTEXT_PACK), run_name="logres_context_pack_test")
            stderr = io.StringIO()
            stdout = io.StringIO()
            with mock.patch.object(module["time"], "time", side_effect=[100.0, 200.0]):
                with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(stdout):
                    rc = module["main"](["--chat", "battle", "--db", str(db)])
        self.assertEqual(5, rc)
        self.assertIn("lease expired before context emission", stderr.getvalue())
        self.assertEqual("", stdout.getvalue())

    def test_context_pack_emits_while_holding_final_lease_lock(self):
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
            module = runpy.run_path(str(CONTEXT_PACK), run_name="logres_context_pack_lock_test")

            class LockProbe(io.StringIO):
                locked = False

                def write(self, text):
                    probe = sqlite3.connect(db, timeout=0.01)
                    try:
                        probe.execute(
                            "update brain_task_leases set lease_until_epoch=0 where task_id=?",
                            ("BATTLE-RENDER-001",),
                        )
                        probe.commit()
                    except sqlite3.OperationalError:
                        self.locked = True
                    finally:
                        probe.close()
                    return super().write(text)

            stdout = LockProbe()
            with contextlib.redirect_stdout(stdout):
                rc = module["main"](["--chat", "battle", "--db", str(db)])
        self.assertEqual(0, rc)
        self.assertTrue(stdout.locked)
        self.assertIn('"BATTLE-RENDER-001"', stdout.getvalue())

    def test_context_pack_output_file_is_atomic_and_durable_under_lease_lock(self):
        self.c.execute(
            "create table brain_task_leases(task_id text primary key, chat_id text, lease_until_epoch real)"
        )
        self.c.execute(
            "insert into brain_task_leases values(?,?,?)",
            ("BATTLE-RENDER-001", "battle", 9999999999.0),
        )
        self.c.commit()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "control.sqlite"
            output = root / "context.json"
            disk = sqlite3.connect(db)
            self.c.backup(disk)
            disk.close()
            module = runpy.run_path(str(CONTEXT_PACK), run_name="logres_context_pack_file_test")
            with mock.patch.object(module["os"], "replace", wraps=os.replace) as replace_mock:
                with mock.patch.object(module["os"], "fsync", wraps=os.fsync) as fsync_mock:
                    rc = module["main"]([
                        "--chat", "battle", "--db", str(db), "--output-file", str(output)
                    ])
            payload = json.loads(output.read_text())
            leftovers = list(root.glob(".context.json.*"))
        self.assertEqual(0, rc)
        self.assertEqual("BATTLE-RENDER-001", payload["task"]["id"])
        self.assertGreaterEqual(replace_mock.call_count, 1)
        self.assertGreaterEqual(fsync_mock.call_count, 2)
        self.assertEqual([], leftovers)

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
