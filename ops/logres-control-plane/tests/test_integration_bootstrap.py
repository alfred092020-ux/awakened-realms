import json
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

CONTROL_ROOT = Path(__file__).resolve().parents[1]
LIB = CONTROL_ROOT / "lib"
sys.path.insert(0, str(LIB))

from logres_integration import (
    append_receipt,
    bootstrap_summary,
    claim_intent,
    create_intent,
    create_proposal,
    disposition_proposal,
    ensure_schema,
    release_claim,
    set_capabilities,
    transition_intent,
)


class IntegrationBootstrapHookTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def _intent(
        self,
        *,
        entity_id: str,
        dedupe: str,
        capability: str | None,
        priority: int,
    ):
        return create_intent(
            self.conn,
            provider="linear",
            target_key="logres",
            operation="issue.upsert",
            action_class="REVERSIBLE_WRITE",
            canonical_entity_type="task",
            canonical_entity_id=entity_id,
            payload={"title": f"Task {entity_id}"},
            created_by="bootstrap-test",
            dedupe_key=dedupe,
            priority=priority,
            required_capability=capability,
            task_id=entity_id,
        )

    def test_bootstrap_summary_is_bounded_local_and_capability_compatible(self):
        now = time.time()
        set_capabilities(
            self.conn,
            chat_id="chat-a",
            capabilities=["linear.issue.write", "drive.read"],
            expires_at_epoch=now + 3600,
            target_key="logres",
            metadata={"source": "test"},
        )
        generic = self._intent(
            entity_id="GENERIC",
            dedupe="generic",
            capability=None,
            priority=1,
        )
        allowed = self._intent(
            entity_id="ALLOWED",
            dedupe="allowed",
            capability="linear.issue.write",
            priority=2,
        )
        self._intent(
            entity_id="DENIED",
            dedupe="denied",
            capability="slack.write",
            priority=0,
        )
        self._intent(
            entity_id="TRUNCATED",
            dedupe="truncated",
            capability=None,
            priority=3,
        )

        summary = bootstrap_summary(
            self.conn,
            chat_id="chat-a",
            now_epoch=now,
            limit=2,
        )

        self.assertEqual("local-control-db-only", summary["source"])
        self.assertLessEqual(len(summary["capabilities"]), 4)
        self.assertEqual(
            [generic["id"], allowed["id"]],
            [item["id"] for item in summary["compatible_backlog"]],
        )
        self.assertTrue(summary["backlog_truncated"])
        self.assertTrue(
            all("payload" not in item for item in summary["compatible_backlog"])
        )
        self.assertTrue(
            all("metadata" not in item for item in summary["capabilities"])
        )

    def test_meaningful_state_changes_are_deduped_in_project_journal(self):
        intent = self._intent(
            entity_id="T1",
            dedupe="intent-1",
            capability=None,
            priority=1,
        )
        repeated = self._intent(
            entity_id="T1",
            dedupe="intent-1",
            capability=None,
            priority=1,
        )
        self.assertEqual(intent["id"], repeated["id"])

        claim = claim_intent(
            self.conn,
            intent["id"],
            chat_id="worker-a",
            now_epoch=100.0,
            lease_seconds=60.0,
            lease_token="lease-a",
        )
        transition_intent(
            self.conn,
            intent["id"],
            expected="CLAIMED",
            new="DISPATCHED",
        )
        transition_intent(
            self.conn,
            intent["id"],
            expected="DISPATCHED",
            new="SUCCEEDED",
        )
        append_receipt(
            self.conn,
            intent_id=intent["id"],
            receipt_key="receipt-1",
            outcome="SUCCEEDED",
            chat_id="worker-a",
            attempt_number=1,
            provider_entity_type="issue",
            provider_entity_id="L-1",
            provider_version="v1",
            observed_hash="a" * 64,
            response_metadata={"status": "ok"},
        )
        append_receipt(
            self.conn,
            intent_id=intent["id"],
            receipt_key="receipt-1",
            outcome="SUCCEEDED",
            chat_id="worker-a",
            attempt_number=1,
            provider_entity_type="issue",
            provider_entity_id="L-1",
            provider_version="v1",
            observed_hash="a" * 64,
            response_metadata={"status": "ok"},
        )

        rows = list(
            self.conn.execute(
                """select action,payload_json,dedupe_key
                     from project_journal
                    where entity_type in ('integration_intent','integration_receipt')
                    order by id"""
            )
        )
        actions = [row[0] for row in rows]
        self.assertEqual(1, actions.count("CREATED"))
        self.assertEqual(1, actions.count("STATE_CLAIMED"))
        self.assertEqual(1, actions.count("STATE_DISPATCHED"))
        self.assertEqual(1, actions.count("STATE_SUCCEEDED"))
        self.assertEqual(1, actions.count("OUTCOME_SUCCEEDED"))
        for _, payload_json, dedupe_key in rows:
            payload = json.loads(payload_json)
            self.assertNotIn("api_key", payload)
            self.assertNotIn("response_metadata", payload)
            self.assertTrue(dedupe_key)

        # A separate claim-release lifecycle is journaled without noisy renewals.
        released = self._intent(
            entity_id="T2",
            dedupe="intent-2",
            capability=None,
            priority=4,
        )
        claim_intent(
            self.conn,
            released["id"],
            chat_id="worker-b",
            now_epoch=200.0,
            lease_seconds=60.0,
            lease_token="lease-b",
        )
        release_claim(
            self.conn,
            released["id"],
            lease_token="lease-b",
        )
        release_actions = [
            row[0]
            for row in self.conn.execute(
                """select action from project_journal
                    where entity_type='integration_intent'
                      and entity_id=?
                    order by id""",
                (str(released["id"]),),
            )
        ]
        self.assertEqual(
            ["CREATED", "STATE_CLAIMED", "STATE_NEW"],
            release_actions,
        )

    def test_proposal_disposition_records_only_bounded_lineage(self):
        proposal = create_proposal(
            self.conn,
            dedupe_key="proposal-1",
            provider="drive",
            target_key="logres",
            change_type="document.changed",
            observed={"document_hash": "b" * 64},
            risk_class="REVIEW",
            provider_entity_id="doc-1",
            canonical_entity_type="task",
            canonical_entity_id="T3",
            canonical={"task_id": "T3"},
        )
        disposition_proposal(
            self.conn,
            proposal["id"],
            expected="OPEN",
            disposition="NEEDS_HUMAN",
            reviewer="lead",
            note="review required",
        )

        rows = list(
            self.conn.execute(
                """select action,payload_json from project_journal
                    where entity_type='integration_proposal'
                    order by id"""
            )
        )
        self.assertEqual(
            ["CREATED", "DISPOSITION_NEEDS_HUMAN"],
            [row[0] for row in rows],
        )
        payload_text = "\n".join(row[1] for row in rows)
        self.assertNotIn("document_hash", payload_text)
        self.assertNotIn("review required", payload_text)

    def test_chat_start_uses_only_local_bounded_bootstrap_command(self):
        text = (CONTROL_ROOT / "bin" / "logres-chat-start").read_text()
        self.assertIn("=== CONNECTOR INTEGRATION SUMMARY ===", text)
        self.assertIn(
            'logres-integration" --json bootstrap --chat-id "$CHAT" --limit 5',
            text,
        )
        self.assertNotIn("provider scan", text.lower())

    def test_cli_bootstrap_reads_temp_control_db_without_provider_access(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "control.sqlite"
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            ensure_schema(conn)
            set_capabilities(
                conn,
                chat_id="cli-chat",
                capabilities=["linear.read"],
                expires_at_epoch=time.time() + 300,
            )
            conn.close()

            result = subprocess.run(
                [
                    sys.executable,
                    str(CONTROL_ROOT / "bin" / "logres-integration"),
                    "--json",
                    "bootstrap",
                    "--chat-id",
                    "cli-chat",
                    "--limit",
                    "3",
                ],
                env={"LOGRES_CONTROL_DB": str(db)},
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(result.stdout)
            self.assertEqual("local-control-db-only", payload["source"])
            self.assertEqual("cli-chat", payload["chat_id"])
            self.assertEqual(1, len(payload["capabilities"]))


if __name__ == "__main__":
    unittest.main()
