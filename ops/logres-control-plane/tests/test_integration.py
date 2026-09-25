import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_integration import (
    append_receipt,
    canonical_hash,
    claim_intent,
    classify_uncertain_failure,
    compatible_capabilities,
    create_intent,
    create_proposal,
    disposition_proposal,
    ensure_schema,
    get_binding,
    get_cursor,
    get_intent,
    list_bindings,
    list_capabilities,
    list_intents,
    list_proposals,
    list_receipts,
    list_targets,
    register_target,
    release_claim,
    renew_claim,
    retry_allowed,
    set_capabilities,
    set_cursor,
    transition_intent,
    upsert_binding,
    validate_sanitized_payload,
)


class IntegrationCoreSchemaTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        self.conn.close()

    def test_schema_creation_is_idempotent_and_complete(self):
        ensure_schema(self.conn)
        ensure_schema(self.conn)

        tables = {
            row[0]
            for row in self.conn.execute(
                "select name from sqlite_master where type='table'"
            )
        }
        self.assertTrue(
            {
                "integration_targets",
                "integration_bindings",
                "integration_intents",
                "integration_claims",
                "integration_receipts",
                "integration_cursors",
                "integration_proposals",
                "integration_capabilities",
            }.issubset(tables)
        )

        indexes = {
            row[0]
            for row in self.conn.execute(
                "select name from sqlite_master where type='index'"
            )
        }
        self.assertIn("integration_intents_queue_idx", indexes)
        self.assertIn("integration_proposals_queue_idx", indexes)

    def test_canonical_hash_is_stable_across_mapping_order(self):
        left = {
            "provider": "linear",
            "payload": {"b": 2, "a": 1},
            "items": [{"y": 2, "x": 1}],
        }
        right = {
            "items": [{"x": 1, "y": 2}],
            "payload": {"a": 1, "b": 2},
            "provider": "linear",
        }
        self.assertEqual(canonical_hash(left), canonical_hash(right))

    def test_secret_like_keys_are_rejected_recursively(self):
        safe = {
            "provider": "linear",
            "metadata": {"workspace_id": "abc", "nested": [{"etag": "v1"}]},
        }
        validate_sanitized_payload(safe)

        forbidden = [
            {"api_key": "secret"},
            {"metadata": {"access_token": "secret"}},
            {"nested": [{"authorization": "Bearer secret"}]},
            {"cookie": "sid=secret"},
            {"refreshToken": "secret"},
            {"client_secret": "secret"},
            {"password": "secret"},
        ]
        for payload in forbidden:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    validate_sanitized_payload(payload)


class IntegrationTargetCapabilityTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_register_target_is_idempotent_and_updates_policy(self):
        first = register_target(
            self.conn,
            provider="linear",
            target_key="logres",
            purpose="work mirror",
            read_policy={"mode": "managed"},
            metadata={"workspace": "one"},
        )
        second = register_target(
            self.conn,
            provider="linear",
            target_key="logres",
            purpose="work mirror updated",
            read_policy={"mode": "managed"},
            metadata={"workspace": "two"},
        )
        self.assertEqual(("linear", "logres"), (first["provider"], first["target_key"]))
        self.assertEqual(1, len(list_targets(self.conn)))
        self.assertEqual("work mirror updated", second["purpose"])
        self.assertEqual({"workspace": "two"}, second["metadata"])

    def test_capabilities_replace_and_expire(self):
        set_capabilities(
            self.conn,
            chat_id="plugins",
            capabilities=["linear.read", "linear.write"],
            expires_at_epoch=200.0,
            target_key="logres",
        )
        set_capabilities(
            self.conn,
            chat_id="plugins",
            capabilities=["linear.read"],
            expires_at_epoch=300.0,
            target_key="logres",
        )
        rows = list_capabilities(self.conn, chat_id="plugins", now_epoch=250.0)
        self.assertEqual(["linear.read"], [row["capability"] for row in rows])
        self.assertEqual(
            ["plugins"],
            [row["chat_id"] for row in compatible_capabilities(
                self.conn,
                capability="linear.read",
                target_key="logres",
                now_epoch=250.0,
            )],
        )
        self.assertEqual(
            [],
            compatible_capabilities(
                self.conn,
                capability="linear.read",
                target_key="logres",
                now_epoch=350.0,
            ),
        )


class IntegrationIntentTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def _create(self, **overrides):
        payload = {
            "provider": "linear",
            "target_key": "logres",
            "operation": "issue.upsert",
            "action_class": "REVERSIBLE_WRITE",
            "canonical_entity_type": "task",
            "canonical_entity_id": "T1",
            "logical_slot": "work-mirror",
            "payload": {"title": "One"},
            "projection_hash": "p1",
            "required_capability": "linear.write",
            "created_by": "plugins",
        }
        payload.update(overrides)
        return create_intent(self.conn, **payload)

    def test_create_intent_is_idempotent_by_dedupe_key(self):
        first = self._create(dedupe_key="linear:T1:p1")
        second = self._create(dedupe_key="linear:T1:p1")
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(1, len(list_intents(self.conn)))

    def test_payload_hash_is_deterministic(self):
        first = self._create(
            dedupe_key="a",
            payload={"b": 2, "a": 1},
            canonical_entity_id="T1",
        )
        second = self._create(
            dedupe_key="b",
            payload={"a": 1, "b": 2},
            canonical_entity_id="T2",
            logical_slot="other",
        )
        self.assertEqual(first["payload_hash"], second["payload_hash"])

    def test_new_projection_supersedes_older_unclaimed_intent(self):
        old = self._create(dedupe_key="old", projection_hash="p1")
        new = self._create(dedupe_key="new", projection_hash="p2")
        self.assertEqual("SUPERSEDED", get_intent(self.conn, old["id"])["state"])
        self.assertEqual(new["id"], get_intent(self.conn, old["id"])["superseded_by"])
        self.assertEqual("NEW", new["state"])

    def test_dispatched_intent_is_not_silently_superseded(self):
        old = self._create(dedupe_key="old-live", projection_hash="p1")
        transition_intent(self.conn, old["id"], expected="NEW", new="CLAIMED")
        transition_intent(self.conn, old["id"], expected="CLAIMED", new="DISPATCHED")
        self._create(dedupe_key="new-live", projection_hash="p2")
        self.assertEqual("DISPATCHED", get_intent(self.conn, old["id"])["state"])


class IntegrationClaimTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_schema(self.conn)
        self.intent = create_intent(
            self.conn,
            provider="linear",
            target_key="logres",
            operation="issue.upsert",
            action_class="REVERSIBLE_WRITE",
            canonical_entity_type="task",
            canonical_entity_id="T1",
            payload={"title": "One"},
            created_by="plugins",
            dedupe_key="claim-test",
            required_capability="linear.write",
        )

    def tearDown(self):
        self.conn.close()

    def test_claim_is_exclusive_and_token_bound(self):
        first = claim_intent(
            self.conn,
            self.intent["id"],
            chat_id="plugins",
            now_epoch=100.0,
            lease_seconds=30,
        )
        self.assertEqual("plugins", first["chat_id"])

        with self.assertRaises(Exception):
            claim_intent(
                self.conn,
                self.intent["id"],
                chat_id="other",
                now_epoch=110.0,
                lease_seconds=30,
            )

        same = claim_intent(
            self.conn,
            self.intent["id"],
            chat_id="plugins",
            now_epoch=110.0,
            lease_seconds=30,
            lease_token=first["lease_token"],
        )
        self.assertEqual(first["lease_token"], same["lease_token"])

    def test_expired_claim_can_be_recovered_and_renewed(self):
        first = claim_intent(
            self.conn,
            self.intent["id"],
            chat_id="plugins",
            now_epoch=100.0,
            lease_seconds=10,
        )
        second = claim_intent(
            self.conn,
            self.intent["id"],
            chat_id="other",
            now_epoch=111.0,
            lease_seconds=20,
        )
        self.assertNotEqual(first["lease_token"], second["lease_token"])
        renewed = renew_claim(
            self.conn,
            self.intent["id"],
            lease_token=second["lease_token"],
            now_epoch=120.0,
            lease_seconds=30,
        )
        self.assertEqual(150.0, renewed["lease_until_epoch"])
        release_claim(
            self.conn,
            self.intent["id"],
            lease_token=second["lease_token"],
        )
        self.assertEqual(
            0,
            self.conn.execute(
                "select count(*) from integration_claims"
            ).fetchone()[0],
        )


class IntegrationUncertainWriteTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def _dispatched(self, action_class):
        intent = create_intent(
            self.conn,
            provider="agentmail",
            target_key="agents",
            operation="send",
            action_class=action_class,
            canonical_entity_type="task",
            canonical_entity_id=action_class,
            payload={"message": "status"},
            created_by="plugins",
            dedupe_key=f"uncertain:{action_class}",
        )
        transition_intent(self.conn, intent["id"], expected="NEW", new="CLAIMED")
        return transition_intent(
            self.conn, intent["id"], expected="CLAIMED", new="DISPATCHED"
        )

    def test_uncertain_mutating_write_enters_reconciling(self):
        intent = self._dispatched("REVERSIBLE_WRITE")
        moved = classify_uncertain_failure(
            self.conn,
            intent["id"],
            error_detail="timeout after dispatch",
        )
        self.assertEqual("RECONCILING", moved["state"])

    def test_uncertain_read_can_be_retryable(self):
        intent = self._dispatched("READ_ONLY")
        moved = classify_uncertain_failure(
            self.conn,
            intent["id"],
            error_detail="network timeout",
        )
        self.assertEqual("RETRYABLE", moved["state"])
        self.assertTrue(retry_allowed(moved))

    def test_irreversible_reconciling_is_not_retryable(self):
        intent = self._dispatched("IRREVERSIBLE_SIDE_EFFECT")
        moved = classify_uncertain_failure(
            self.conn,
            intent["id"],
            error_detail="timeout after send",
        )
        self.assertEqual("RECONCILING", moved["state"])
        self.assertFalse(retry_allowed(moved))
        with self.assertRaises(Exception):
            transition_intent(
                self.conn,
                moved["id"],
                expected="RECONCILING",
                new="CLAIMED",
            )


class IntegrationReceiptBindingTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_schema(self.conn)
        self.intent = create_intent(
            self.conn,
            provider="linear",
            target_key="logres",
            operation="issue.upsert",
            action_class="REVERSIBLE_WRITE",
            canonical_entity_type="task",
            canonical_entity_id="T1",
            logical_slot="work-mirror",
            payload={"title": "One"},
            projection_hash="projection-1",
            created_by="plugins",
            dedupe_key="receipt-intent",
        )

    def tearDown(self):
        self.conn.close()

    def test_receipt_is_append_only_and_deduped_by_receipt_key(self):
        first = append_receipt(
            self.conn,
            intent_id=self.intent["id"],
            receipt_key="r1",
            outcome="SUCCEEDED",
            chat_id="plugins",
            attempt_number=1,
            response_metadata={"status": "ok"},
        )
        second = append_receipt(
            self.conn,
            intent_id=self.intent["id"],
            receipt_key="r1",
            outcome="SUCCEEDED",
            chat_id="plugins",
            attempt_number=1,
            response_metadata={"status": "ok"},
        )
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(1, len(list_receipts(self.conn, self.intent["id"])))

    def test_successful_receipt_can_create_binding(self):
        append_receipt(
            self.conn,
            intent_id=self.intent["id"],
            receipt_key="r-bind",
            outcome="SUCCEEDED",
            chat_id="plugins",
            attempt_number=1,
            provider_entity_type="issue",
            provider_entity_id="LIN-123",
            provider_url="https://linear.example/LIN-123",
            observed_hash="observed-1",
            bind_on_success=True,
        )
        binding = get_binding(
            self.conn,
            provider="linear",
            canonical_entity_type="task",
            canonical_entity_id="T1",
            logical_slot="work-mirror",
        )
        self.assertEqual("LIN-123", binding["provider_entity_id"])
        self.assertEqual("projection-1", binding["projected_hash"])
        self.assertEqual("observed-1", binding["observed_hash"])

    def test_provider_object_cannot_bind_to_two_canonical_entities(self):
        upsert_binding(
            self.conn,
            provider="linear",
            logical_slot="work-mirror",
            canonical_entity_type="task",
            canonical_entity_id="T1",
            provider_entity_type="issue",
            provider_entity_id="LIN-123",
        )
        with self.assertRaises(sqlite3.IntegrityError):
            upsert_binding(
                self.conn,
                provider="linear",
                logical_slot="work-mirror",
                canonical_entity_type="task",
                canonical_entity_id="T2",
                provider_entity_type="issue",
                provider_entity_id="LIN-123",
            )
        self.assertEqual(1, len(list_bindings(self.conn, provider="linear")))


class IntegrationCursorProposalTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_monotonic_cursor_does_not_move_backward(self):
        set_cursor(
            self.conn,
            provider="linear",
            target_key="logres",
            cursor_name="updated",
            cursor_value="200",
            monotonic=True,
        )
        set_cursor(
            self.conn,
            provider="linear",
            target_key="logres",
            cursor_name="updated",
            cursor_value="150",
            monotonic=True,
        )
        self.assertEqual(
            "200",
            get_cursor(
                self.conn,
                provider="linear",
                target_key="logres",
                cursor_name="updated",
            )["cursor_value"],
        )

    def test_proposal_creation_is_idempotent_and_review_is_cas(self):
        first = create_proposal(
            self.conn,
            dedupe_key="proposal-1",
            provider="linear",
            target_key="logres",
            provider_entity_id="LIN-1",
            canonical_entity_type="task",
            canonical_entity_id="T1",
            change_type="description.changed",
            observed={"description": "human edit"},
            canonical={"description": "managed"},
            risk_class="REVIEW",
        )
        second = create_proposal(
            self.conn,
            dedupe_key="proposal-1",
            provider="linear",
            target_key="logres",
            provider_entity_id="LIN-1",
            canonical_entity_type="task",
            canonical_entity_id="T1",
            change_type="description.changed",
            observed={"description": "human edit"},
            canonical={"description": "managed"},
            risk_class="REVIEW",
        )
        self.assertEqual(first["id"], second["id"])
        reviewed = disposition_proposal(
            self.conn,
            first["id"],
            expected="OPEN",
            disposition="ACCEPTED",
            reviewer="plugins",
            note="incorporate through normal Brain workflow",
        )
        self.assertEqual("ACCEPTED", reviewed["disposition"])
        with self.assertRaises(Exception):
            disposition_proposal(
                self.conn,
                first["id"],
                expected="OPEN",
                disposition="REJECTED",
                reviewer="other",
            )
        self.assertEqual(1, len(list_proposals(self.conn)))


class IntegrationCliCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "control.sqlite"
        self.cli = TEST_DIR.parent / "bin" / "logres-integration"
        self.env = os.environ.copy()
        self.env["LOGRES_CONTROL_DB"] = str(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, check=True):
        result = subprocess.run(
            [sys.executable, str(self.cli), "--json", *args],
            text=True,
            capture_output=True,
            env=self.env,
        )
        if check and result.returncode != 0:
            self.fail(
                f"CLI failed {result.returncode}: {result.stderr}\nstdout={result.stdout}"
            )
        return result

    def create_cli_intent(self):
        result = self.run_cli(
            "intent-create",
            "--provider", "linear",
            "--target-key", "logres",
            "--operation", "issue.upsert",
            "--action-class", "REVERSIBLE_WRITE",
            "--entity-type", "task",
            "--entity-id", "T1",
            "--logical-slot", "work-mirror",
            "--payload", '{"title":"One"}',
            "--projection-hash", "p1",
            "--required-capability", "linear.write",
            "--created-by", "plugins",
            "--dedupe-key", "cli-intent-1",
        )
        return json.loads(result.stdout)

    def test_status_json_and_queue_filtering(self):
        status = json.loads(self.run_cli("status").stdout)
        self.assertEqual(0, status["intents"])
        intent = self.create_cli_intent()
        queue = json.loads(
            self.run_cli(
                "queue",
                "--provider", "linear",
                "--state", "NEW",
                "--capability", "linear.write",
            ).stdout
        )
        self.assertEqual([intent["id"]], [row["id"] for row in queue])

    def test_claim_returns_token_and_receipt_persists(self):
        intent = self.create_cli_intent()
        claim = json.loads(
            self.run_cli(
                "claim",
                str(intent["id"]),
                "--chat-id", "plugins",
                "--lease-seconds", "30",
            ).stdout
        )
        self.assertTrue(claim["lease_token"])
        receipt = json.loads(
            self.run_cli(
                "receipt",
                str(intent["id"]),
                "--receipt-key", "cli-r1",
                "--outcome", "SUCCEEDED",
                "--chat-id", "plugins",
                "--attempt", "1",
                "--metadata", '{"status":"ok"}',
            ).stdout
        )
        self.assertEqual("cli-r1", receipt["receipt_key"])
        status = json.loads(self.run_cli("status").stdout)
        self.assertEqual(1, status["receipts"])

    def test_proposal_listing(self):
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        create_proposal(
            conn,
            dedupe_key="cli-proposal",
            provider="linear",
            target_key="logres",
            provider_entity_id="LIN-1",
            canonical_entity_type="task",
            canonical_entity_id="T1",
            change_type="description.changed",
            observed={"description": "human"},
            canonical={"description": "managed"},
            risk_class="REVIEW",
        )
        conn.close()
        proposals = json.loads(self.run_cli("proposals", "--disposition", "OPEN").stdout)
        self.assertEqual(["cli-proposal"], [row["dedupe_key"] for row in proposals])

    def test_secret_payload_is_rejected(self):
        result = self.run_cli(
            "intent-create",
            "--provider", "linear",
            "--target-key", "logres",
            "--operation", "issue.upsert",
            "--action-class", "REVERSIBLE_WRITE",
            "--entity-type", "task",
            "--entity-id", "T1",
            "--payload", '{"api_key":"secret"}',
            "--created-by", "plugins",
            "--dedupe-key", "secret-intent",
            check=False,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("secret-bearing", result.stderr)


class IntegrationCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "control.sqlite"
        self.cli = TEST_DIR.parent / "bin" / "logres-integration"
        self.env = os.environ.copy()
        self.env["LOGRES_CONTROL_DB"] = str(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def _run(self, *args, check=True):
        return subprocess.run(
            [sys.executable, str(self.cli), "--json", *args],
            env=self.env,
            text=True,
            capture_output=True,
            check=check,
        )

    def test_status_json_initializes_schema(self):
        result = self._run("status")
        payload = json.loads(result.stdout)
        self.assertEqual(0, payload["queue_depth"])
        self.assertEqual(0, payload["open_proposals"])
        self.assertTrue(self.db.exists())

    def test_cli_intent_queue_claim_and_receipt(self):
        created = json.loads(
            self._run(
                "intent-create",
                "--provider", "linear",
                "--target", "logres",
                "--operation", "issue.upsert",
                "--action-class", "REVERSIBLE_WRITE",
                "--entity-type", "task",
                "--entity-id", "T1",
                "--dedupe-key", "cli-intent",
                "--created-by", "plugins",
                "--required-capability", "linear.write",
                "--payload-json", '{"title":"One"}',
            ).stdout
        )
        queued = json.loads(
            self._run(
                "queue",
                "--provider", "linear",
                "--capability", "linear.write",
            ).stdout
        )
        self.assertEqual([created["id"]], [row["id"] for row in queued])

        claim = json.loads(
            self._run(
                "claim",
                str(created["id"]),
                "--chat", "plugins",
                "--now-epoch", "100",
                "--lease-seconds", "30",
            ).stdout
        )
        self.assertTrue(claim["lease_token"])

        receipt = json.loads(
            self._run(
                "receipt",
                str(created["id"]),
                "--receipt-key", "cli-r1",
                "--outcome", "SUCCEEDED",
                "--chat", "plugins",
                "--attempt", "1",
                "--metadata-json", '{"ok":true}',
            ).stdout
        )
        self.assertEqual("SUCCEEDED", receipt["outcome"])

    def test_cli_proposals_and_secret_rejection(self):
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        ensure_schema(conn)
        create_proposal(
            conn,
            dedupe_key="p1",
            provider="linear",
            target_key="logres",
            change_type="description.changed",
            observed={"description": "edit"},
            risk_class="REVIEW",
        )
        conn.close()

        proposals = json.loads(self._run("proposals").stdout)
        self.assertEqual(1, len(proposals))

        failed = self._run(
            "intent-create",
            "--provider", "linear",
            "--target", "logres",
            "--operation", "issue.upsert",
            "--action-class", "REVERSIBLE_WRITE",
            "--entity-type", "task",
            "--entity-id", "T2",
            "--dedupe-key", "secret-intent",
            "--created-by", "plugins",
            "--payload-json", '{"api_key":"forbidden"}',
            check=False,
        )
        self.assertNotEqual(0, failed.returncode)
        self.assertIn("secret-bearing key rejected", failed.stderr)


if __name__ == "__main__":
    unittest.main()
