import sqlite3
import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_integration import (
    canonical_hash,
    ensure_schema,
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


if __name__ == "__main__":
    unittest.main()
