import sqlite3
import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_integration import (
    canonical_hash,
    claim_intent,
    compatible_capabilities,
    create_intent,
    ensure_schema,
    get_intent,
    list_capabilities,
    list_intents,
    list_targets,
    register_target,
    release_claim,
    renew_claim,
    set_capabilities,
    transition_intent,
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


if __name__ == "__main__":
    unittest.main()
