import copy
import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
REPO_ROOT = CONTROL_ROOT.parents[1]
LIB_DIR = CONTROL_ROOT / "lib"
sys.path.insert(0, str(LIB_DIR))

import logres_goal_certify
from logres_goal_certify import build_certificate
from logres_mission_coverage import (
    completion_manifest_report,
    load_completion_manifest,
    stable_ids_sha256,
)

MANIFEST_PATH = CONTROL_ROOT / "config" / "completion_manifest.json"
SHA = "a" * 40


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def make_verification_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        create table verification(
          ref text primary key,sha text,mode text,status text,
          duration_sec real,ran_at text,details text
        );
        create table regressions(id integer primary key,status text);
        """
    )
    conn.execute(
        "insert into verification values(?,?,?,?,?,?,?)",
        (
            "v",
            SHA,
            "full-e2e",
            "PASS",
            1.0,
            "2026-09-24T00:00:00+00:00",
            "ok",
        ),
    )
    conn.commit()
    return conn


def content_contracts() -> dict:
    return {
        "schema": "logres-milestone-contract-v1",
        "milestones": {
            "CONTENT-0.5": {
                "title": "content",
                "definition_of_done": "content complete",
                "criteria": [
                    {
                        "id": "verify",
                        "weight": 100,
                        "description": "verified",
                        "check": {
                            "type": "verification",
                            "mode": "full-e2e",
                            "status": "PASS",
                        },
                    }
                ],
            }
        },
    }


class ProjectCompletionManifestTests(unittest.TestCase):
    def test_actual_manifest_accounts_for_full_current_source_corpus(self):
        manifest = load_completion_manifest(MANIFEST_PATH)
        report = completion_manifest_report(
            REPO_ROOT,
            MANIFEST_PATH,
        )

        self.assertEqual(
            "logres-project-completion-manifest-v2",
            manifest["schema"],
        )
        self.assertEqual("2026-09-24.2", manifest["version"])
        self.assertTrue(report["declared_scope_complete"])
        self.assertEqual(14, report["corpus_total"])
        self.assertEqual(8, report["required_count"])
        self.assertEqual(8, report["represented_count"])
        self.assertEqual(6, report["ceiling_or_excluded_count"])
        self.assertEqual(0, report["missing_count"])
        self.assertEqual(0, report["omitted_from_manifest_count"])
        self.assertEqual(0, report["manifest_only_count"])
        for category in report["categories"].values():
            self.assertTrue(category["source_file_hash_match"])
            self.assertTrue(category["source_version_match"])
            self.assertTrue(category["source_inventory_hash_match"])
            self.assertRegex(
                category["source_file_sha256_actual"],
                r"^[0-9a-f]{64}$",
            )
            self.assertRegex(
                category["source_inventory_sha256_actual"],
                r"^[0-9a-f]{64}$",
            )

    def test_completion_claim_never_implies_unknown_historical_total(self):
        report = completion_manifest_report(REPO_ROOT, MANIFEST_PATH)

        self.assertTrue(report["declared_scope_complete"])
        self.assertFalse(report["historical_total_complete"])
        self.assertEqual(
            "UNKNOWABLE_FROM_CURRENT_EVIDENCE",
            report["historical_total_status"],
        )
        self.assertEqual(
            "DECLARED_RECONSTRUCTION_SCOPE_ONLY",
            report["completion_claim"],
        )
        for category in report["categories"].values():
            self.assertEqual(
                "UNKNOWABLE_FROM_CURRENT_EVIDENCE",
                category["historical_total_ceiling"]["status"],
            )

    def test_larger_source_inventory_than_manifest_fails_closed(self):
        base = json.loads(MANIFEST_PATH.read_text())

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = (
                root
                / "src/game/logres/generated/maps/LogresMapContent.ts"
            )
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(
                """
export const LOGRES_MAP_CONTENT_SCHEMA_VERSION =
  'map-content-v1' as const
export const TEST = {
  entries: [
    { key: 'alpha' },
    { key: 'beta' },
  ],
} as const
"""
            )
            raw = source.read_bytes()

            manifest = copy.deepcopy(base)
            category = manifest["categories"]["maps_regions"]
            category["source_inventory"] = {
                "path": "src/game/logres/generated/maps/LogresMapContent.ts",
                "schema_version": "map-content-v1",
                "file_sha256": hashlib.sha256(raw).hexdigest(),
                "ids": ["alpha"],
                "ids_sha256": stable_ids_sha256(["alpha"]),
            }
            category["targets"] = [
                {
                    "stable_id": "alpha",
                    "disposition": "required",
                    "provenance_class": "TEST",
                }
            ]
            manifest_path = root / "completion_manifest.json"
            write_json(manifest_path, manifest)

            report = completion_manifest_report(root, manifest_path)
            maps = report["categories"]["maps_regions"]

            self.assertFalse(maps["complete"])
            self.assertEqual(["beta"], maps["omitted_from_manifest_ids"])
            self.assertEqual(
                ["beta"],
                maps["omitted_from_source_inventory_ids"],
            )
            self.assertEqual(1, maps["omitted_from_manifest_count"])
            self.assertFalse(maps["source_inventory_hash_match"])
            self.assertFalse(report["declared_scope_complete"])

            category["source_inventory"]["ids"] = ["alpha", "beta"]
            category["source_inventory"]["ids_sha256"] = stable_ids_sha256(
                ["alpha", "beta"]
            )
            category["targets"].append(
                {
                    "stable_id": "beta",
                    "disposition": "excluded",
                    "exclusion_reason": "synthetic bounded test entry",
                }
            )
            write_json(manifest_path, manifest)

            repaired = completion_manifest_report(root, manifest_path)
            repaired_maps = repaired["categories"]["maps_regions"]
            self.assertTrue(repaired_maps["complete"])
            self.assertEqual(2, repaired_maps["corpus_total"])
            self.assertEqual(0, repaired_maps["omitted_from_manifest_count"])

    def test_source_hash_drift_fails_even_when_ids_are_unchanged(self):
        base = json.loads(MANIFEST_PATH.read_text())
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = (
                root
                / "src/game/logres/generated/quests/LogresQuestContent.ts"
            )
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(
                """
export const LOGRES_QUEST_CONTENT_SCHEMA_VERSION =
  'quest-content-v1' as const
export const TEST = { entries: [{ key: 'opening-tutorial' }] } as const
"""
            )

            manifest = copy.deepcopy(base)
            category = manifest["categories"]["quests"]
            category["source_inventory"]["file_sha256"] = "0" * 64
            manifest_path = root / "completion_manifest.json"
            write_json(manifest_path, manifest)

            report = completion_manifest_report(root, manifest_path)
            quests = report["categories"]["quests"]

            self.assertFalse(quests["source_file_hash_match"])
            self.assertTrue(quests["source_inventory_hash_match"])
            self.assertFalse(quests["complete"])

    def test_declared_ids_hash_is_self_validating(self):
        manifest = json.loads(MANIFEST_PATH.read_text())
        manifest["categories"]["quests"]["source_inventory"][
            "ids_sha256"
        ] = "0" * 64

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "manifest.json"
            write_json(path, manifest)
            with self.assertRaisesRegex(ValueError, "ids_sha256 mismatch"):
                load_completion_manifest(path)

    def test_content_certificate_fails_closed_on_incomplete_corpus(self):
        conn = make_verification_db()
        with mock.patch.object(
            logres_goal_certify,
            "completion_manifest_report",
            return_value={
                "declared_scope_complete": False,
                "historical_total_complete": False,
                "historical_total_status":
                    "UNKNOWABLE_FROM_CURRENT_EVIDENCE",
            },
        ):
            cert = build_certificate(
                conn,
                content_contracts(),
                "CONTENT-0.5",
                integration_sha=SHA,
                root=Path("."),
                timestamp="2026-09-24T00:00:00+00:00",
            )

        self.assertFalse(cert["valid"])
        self.assertEqual("FAIL", cert["status"])
        self.assertEqual(
            "DECLARED_RECONSTRUCTION_SCOPE_ONLY",
            cert["completion_claim"],
        )
        self.assertFalse(cert["historical_total_complete"])

    def test_content_certificate_can_pass_declared_scope_without_claiming_history(self):
        conn = make_verification_db()
        with mock.patch.object(
            logres_goal_certify,
            "completion_manifest_report",
            return_value={
                "declared_scope_complete": True,
                "historical_total_complete": False,
                "historical_total_status":
                    "UNKNOWABLE_FROM_CURRENT_EVIDENCE",
            },
        ):
            cert = build_certificate(
                conn,
                content_contracts(),
                "CONTENT-0.5",
                integration_sha=SHA,
                root=Path("."),
                timestamp="2026-09-24T00:00:00+00:00",
            )

        self.assertTrue(cert["valid"])
        self.assertEqual("PASS", cert["status"])
        self.assertFalse(cert["historical_total_complete"])


if __name__ == "__main__":
    unittest.main()
