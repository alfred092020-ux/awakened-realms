from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from logres_chat_contract import (
    CHAT_CONTRACT_STATES,
    ChatContractStore,
)


class ChatContractTests(unittest.TestCase):
    def test_missing_contract_is_absent_until_fail_safe_ensure(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ChatContractStore(temp, clock=lambda: 100.0)
            self.assertIsNone(store.get("logres-master"))
            state = store.ensure(
                "logres-master",
                default_state="PAUSED",
                reason="test bootstrap",
            )
            self.assertEqual("PAUSED", state["state"])

    def test_running_heartbeat_continue_and_resume_sequence(self):
        now = [100.0]
        with tempfile.TemporaryDirectory() as temp:
            store = ChatContractStore(temp, clock=lambda: now[0])

            started = store.set_state(
                "logres-master",
                "RUNNING",
                reason="turn start",
            )
            self.assertEqual("RUNNING", started["state"])
            self.assertEqual(100.0, started["heartbeat_epoch"])

            now[0] = 130.0
            heartbeat = store.heartbeat(
                "logres-master",
                reason="tool progress",
            )
            self.assertEqual(130.0, heartbeat["heartbeat_epoch"])

            now[0] = 140.0
            requested = store.set_state(
                "logres-master",
                "CONTINUE_REQUESTED",
                reason="normal turn handoff",
            )
            self.assertEqual("CONTINUE_REQUESTED", requested["state"])
            self.assertEqual(140.0, requested["state_epoch"])

            now[0] = 170.0
            resumed = store.set_state(
                "logres-master",
                "RUNNING",
                reason="watchdog resumed",
            )
            self.assertEqual("RUNNING", resumed["state"])
            self.assertEqual(170.0, resumed["heartbeat_epoch"])
            self.assertGreater(resumed["sequence"], requested["sequence"])

    def test_heartbeat_requires_running_state(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ChatContractStore(temp, clock=lambda: 100.0)
            store.set_state("logres-master", "WAITING_USER")
            with self.assertRaises(ValueError):
                store.heartbeat("logres-master")

    def test_valid_states_include_explicit_continuation(self):
        self.assertEqual(
            {
                "RUNNING",
                "CONTINUE_REQUESTED",
                "WAITING_USER",
                "PAUSED",
                "DONE",
            },
            set(CHAT_CONTRACT_STATES),
        )

    def test_contract_is_persisted_atomically_in_locked_store(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = ChatContractStore(root, clock=lambda: 100.0)
            store.set_state("logres-master", "RUNNING")
            path = root / "control/android-device/chat-contracts.json"
            payload = json.loads(path.read_text())
            self.assertEqual(
                "RUNNING",
                payload["chats"]["logres-master"]["state"],
            )


if __name__ == "__main__":
    unittest.main()
