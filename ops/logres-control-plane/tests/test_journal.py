import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(LIB))
from logres_journal import (
    add_decision,
    append_chat_message,
    append_event,
    decisions,
    entity_history,
    export_chat,
    ingest_jsonl,
    list_chats,
    open_chat,
    search_chat,
    show_chat,
)


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(":memory:")
        self.c.row_factory = sqlite3.Row

    def tearDown(self):
        self.c.close()

    def test_append_and_entity_history(self):
        append_event(
            self.c,
            actor="a",
            entity_type="task",
            entity_id="T1",
            action="CREATED",
            payload={"x": 1},
        )
        rows = entity_history(self.c, "task", "T1")
        self.assertEqual(1, len(rows))
        self.assertEqual({"x": 1}, rows[0]["payload"])

    def test_dedupe_is_idempotent(self):
        a = append_event(
            self.c,
            actor="a",
            entity_type="task",
            entity_id="T1",
            action="DONE",
            dedupe_key="k",
        )
        b = append_event(
            self.c,
            actor="b",
            entity_type="task",
            entity_id="T1",
            action="DONE",
            dedupe_key="k",
        )
        self.assertTrue(a["inserted"])
        self.assertFalse(b["inserted"])
        self.assertEqual(a["id"], b["id"])

    def test_decision_preserves_why_and_alternatives(self):
        add_decision(
            self.c,
            actor="lead",
            scope="mission",
            subject="next",
            why="shortens path",
            alternatives=["A", "B"],
            selected="B",
            evidence=["sha:abc"],
            expected_outcome="progress",
        )
        row = decisions(self.c, "mission")[0]
        self.assertEqual("shortens path", row["why"])
        self.assertEqual(["A", "B"], row["alternatives"])
        self.assertEqual("B", row["selected"])

    def test_chat_ingest_is_idempotent_ordered_and_archived(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            transcript = root / "transcript.jsonl"
            transcript.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "ordinal": 1,
                                "id": "m1",
                                "role": "user",
                                "content": "Build the memory brain",
                                "ts": "2026-09-24T22:00:00Z",
                            }
                        ),
                        json.dumps(
                            {
                                "ordinal": 2,
                                "id": "m2",
                                "role": "assistant",
                                "content": "Checking existing control plane",
                                "ts": "2026-09-24T22:00:01Z",
                            }
                        ),
                        json.dumps(
                            {
                                "ordinal": 3,
                                "id": "m3",
                                "role": "user",
                                "content": "Build the memory brain",
                                "ts": "2026-09-24T22:00:02Z",
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            session = open_chat(
                self.c,
                chat_id="memory",
                session_id="chat-001",
                title="Memory Brain",
                archive_root=root / "archive",
            )
            self.assertEqual("chat-001", session["session_id"])
            self.assertEqual(0, session["message_count"])

            first = ingest_jsonl(
                self.c,
                session_id="chat-001",
                transcript_path=transcript,
            )
            second = ingest_jsonl(
                self.c,
                session_id="chat-001",
                transcript_path=transcript,
            )

            self.assertEqual(3, first["inserted"])
            self.assertEqual(0, first["duplicates"])
            self.assertEqual(3, first["archive_appended"])
            self.assertEqual(0, second["inserted"])
            self.assertEqual(3, second["duplicates"])
            self.assertEqual(0, second["archive_appended"])

            rows = show_chat(self.c, "chat-001")
            self.assertEqual([1, 2, 3], [r["ordinal"] for r in rows])
            self.assertEqual(
                ["user", "assistant", "user"],
                [r["role"] for r in rows],
            )
            self.assertNotEqual(
                rows[0]["message_sha256"],
                rows[2]["message_sha256"],
            )

            archive = Path(first["archive_path"])
            self.assertTrue(archive.exists())
            self.assertEqual(3, len(archive.read_text(encoding="utf-8").splitlines()))
            self.assertEqual(0o600, os.stat(archive).st_mode & 0o777)

            sessions = list_chats(self.c, chat_id="memory")
            self.assertEqual(1, len(sessions))
            self.assertEqual(3, sessions[0]["message_count"])

    def test_live_append_allocates_ordinals_and_is_external_id_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            open_chat(
                self.c,
                chat_id="memory",
                session_id="live",
                archive_root=root / "archive",
            )
            first = append_chat_message(
                self.c,
                session_id="live",
                role="user",
                content="first turn",
                external_id="turn-1-user",
            )
            duplicate = append_chat_message(
                self.c,
                session_id="live",
                role="user",
                content="first turn",
                external_id="turn-1-user",
            )
            second = append_chat_message(
                self.c,
                session_id="live",
                role="assistant",
                content="second turn",
                external_id="turn-1-assistant",
            )

            self.assertTrue(first["inserted"])
            self.assertFalse(duplicate["inserted"])
            self.assertTrue(second["inserted"])
            self.assertEqual([1, 2], [r["ordinal"] for r in show_chat(self.c, "live")])
            self.assertEqual(1, first["archive_appended"])
            self.assertEqual(0, duplicate["archive_appended"])
            self.assertEqual(1, second["archive_appended"])

            with self.assertRaisesRegex(ValueError, "different content"):
                append_chat_message(
                    self.c,
                    session_id="live",
                    role="user",
                    content="rewritten",
                    external_id="turn-1-user",
                )


    def test_chat_rejects_rewrite_of_existing_ordinal(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            transcript = root / "one.jsonl"
            transcript.write_text(
                json.dumps({"ordinal": 1, "role": "user", "content": "one"}) + "\n",
                encoding="utf-8",
            )
            open_chat(
                self.c,
                chat_id="memory",
                session_id="chat-immutable",
                archive_root=root / "archive",
            )
            ingest_jsonl(
                self.c,
                session_id="chat-immutable",
                transcript_path=transcript,
            )
            transcript.write_text(
                json.dumps({"ordinal": 1, "role": "user", "content": "changed"}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "different content"):
                ingest_jsonl(
                    self.c,
                    session_id="chat-immutable",
                    transcript_path=transcript,
                )

    def test_chat_search_and_export(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            transcript = root / "search.jsonl"
            original = [
                {"ordinal": 1, "role": "user", "content": "battle renderer"},
                {"ordinal": 2, "role": "assistant", "content": "map renderer"},
                {"ordinal": 3, "role": "tool", "content": {"status": "PASS"}},
            ]
            transcript.write_text(
                "\n".join(json.dumps(x) for x in original) + "\n",
                encoding="utf-8",
            )
            open_chat(
                self.c,
                chat_id="memory",
                session_id="chat-search",
                archive_root=root / "archive",
            )
            ingest_jsonl(
                self.c,
                session_id="chat-search",
                transcript_path=transcript,
            )

            hits = search_chat(
                self.c,
                "renderer",
                session_id="chat-search",
            )
            self.assertEqual(2, len(hits))

            exported = root / "export" / "chat.jsonl"
            result = export_chat(self.c, "chat-search", exported)
            self.assertEqual(3, result["messages"])
            self.assertEqual(64, len(result["sha256"]))
            exported_rows = [
                json.loads(line)
                for line in exported.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(original, exported_rows)
            self.assertEqual(0o600, os.stat(exported).st_mode & 0o777)

    def test_open_chat_is_idempotent_and_refuses_cross_chat_reuse(self):
        with tempfile.TemporaryDirectory() as td:
            first = open_chat(
                self.c,
                chat_id="memory",
                session_id="same",
                title="First",
                archive_root=Path(td),
            )
            second = open_chat(
                self.c,
                chat_id="memory",
                session_id="same",
                title="Updated",
                archive_root=Path(td),
            )
            self.assertEqual(first["opened_at"], second["opened_at"])
            self.assertEqual("Updated", second["title"])
            with self.assertRaisesRegex(ValueError, "already belongs"):
                open_chat(
                    self.c,
                    chat_id="other",
                    session_id="same",
                    archive_root=Path(td),
                )


if __name__ == "__main__":
    unittest.main()
