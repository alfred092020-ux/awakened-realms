import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]
BIN_PATH = REPO / "ops/logres-control-plane/bin/logres-reconstruction-autopilot"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fact_hash(facts):
    return hashlib.sha256(canonical(facts).encode()).hexdigest()


def strong_transition():
    return {
        "id": "state-transition:11",
        "domain": "critical_state_transition",
        "authority": "CONFIRMED_GLOBAL_3_0_24_CLIENT_STATE_MACHINE",
        "classification": "evidence-known-not-implemented",
        "semantic_resolution": "NO_DIRECT_FUNCTION_BINDING",
        "evidence": {
            "from": "FIELD_SELECT",
            "to": "FIELD_INFO",
            "message": "S_GMCL_FIELD_SELECT_REQ",
        },
    }


def strong_protocol():
    return {
        "id": "protocol:C_GMCL_CHAR_MOVE_REQ",
        "domain": "protocol_message",
        "authority": "CONFIRMED_GLOBAL_3_0_24_PROTOCOL_ID",
        "classification": "evidence-known-not-implemented",
        "semantic_resolution": "PROTOCOL_SCHEMA_ONLY",
        "evidence": {
            "name": "C_GMCL_CHAR_MOVE_REQ",
            "id": 123,
            "hex": "0x0000007b",
        },
    }


def weak_jp():
    return {
        "id": "jp-map-lineage:999_000_00001.mbn",
        "domain": "jp_map_lineage_reference",
        "authority": "CURRENT_JP_LINEAGE_REFERENCE_ONLY",
        "classification": "implementation-with-weaker-evidence",
        "semantic_resolution": "NOT_HISTORICAL_GLOBAL_WITHOUT_PREDICATE",
        "evidence": {"path": "999_000_00001.mbn"},
    }


def external():
    return {
        "id": "external-ceiling:00",
        "domain": "external_evidence_ceiling",
        "authority": "EXPLICIT_COMPLETENESS_LEDGER_CEILING",
        "classification": "externally-unrecoverable",
        "semantic_resolution": "TERMINAL_EXTERNAL_FACT",
        "evidence": {"text": "retired server fact", "terminal": True},
    }


def make_closure(path: Path):
    facts = [strong_protocol(), weak_jp(), external(), strong_transition()]
    payload = {
        "closure_id": "c" * 64,
        "facts_sha256": fact_hash(facts),
        "historical_authority": "Global 3.0.24 / 2017-05-25",
        "current_jp_role": "LINEAGE_REFERENCE_ONLY",
        "facts": facts,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def make_truth(path: Path):
    payload = {
        "truth_kernel_id": "t" * 64,
        "claims": [
            {
                "claim_id": "claim:state",
                "fact_id": "state-transition:11",
                "artifact_id": "artifact:truth-state",
                "evidence_sha256": "1" * 64,
            },
            {
                "claim_id": "claim:proto",
                "fact_id": "protocol:C_GMCL_CHAR_MOVE_REQ",
                "artifact_id": "artifact:truth-proto",
                "evidence_sha256": "2" * 64,
            },
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def make_differential(path: Path):
    payload = {
        "differential_divergences": [
            {
                "fact_id": "state-transition:11",
                "gap_type": "implementation",
                "classification": "evidence-known-not-implemented",
                "evidence_id": "diff:state",
                "evidence_hash": "a" * 64,
            },
            {
                "fact_id": "protocol:C_GMCL_CHAR_MOVE_REQ",
                "gap_type": "research",
                "classification": "evidence-known-not-implemented",
                "evidence_id": "diff:proto-research",
                "evidence_hash": "b" * 64,
            },
            {
                "fact_id": "external-ceiling:00",
                "gap_type": "implementation",
                "classification": "externally-unrecoverable",
                "ceiling": "retired server behavior is terminally unknown",
            },
        ]
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


class ReconstructionAutopilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.closure = self.root / "closure.json"
        self.truth = self.root / "truth.json"
        self.differential = self.root / "differential.json"
        self.output = self.root / "output.json"
        make_closure(self.closure)
        make_truth(self.truth)
        make_differential(self.differential)

    def tearDown(self):
        self.temp.cleanup()

    def run_generate(self, *, limit=5):
        run = subprocess.run(
            [
                sys.executable,
                str(BIN_PATH),
                "generate",
                "--closure",
                str(self.closure),
                "--truth-kernel",
                str(self.truth),
                "--differential",
                str(self.differential),
                "--output",
                str(self.output),
                "--limit",
                str(limit),
            ],
            cwd=REPO,
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, run.returncode, run.stdout + run.stderr)
        return json.loads(self.output.read_text())

    def test_generate_uses_truth_and_differential_gaps_only(self):
        payload = self.run_generate()
        self.assertEqual("READY", payload["status"])
        self.assertEqual(1, payload["counts"]["packets"])
        packet = payload["packets"][0]
        self.assertEqual("state-transition:11", packet["source_fact"]["id"])
        self.assertEqual("RECONSTRUCTED", packet["confidence_grade"])
        self.assertTrue(packet["evidence_ids"])
        self.assertTrue(packet["evidence_hashes"])
        self.assertTrue(packet["file_scopes"])
        self.assertTrue(packet["acceptance_tests"])
        self.assertTrue(packet["do_not_infer"])
        self.assertTrue(packet["rollback_conditions"])
        self.assertFalse(packet["automation"]["merge"])
        self.assertFalse(packet["automation"]["deploy"])
        self.assertFalse(packet["automation"]["modify_main"])
        self.assertFalse(packet["child_task_policy"]["allow_research_children"])
        self.assertFalse(packet["child_task_policy"]["allow_unblock_children"])
        self.assertIn(
            "protocol:C_GMCL_CHAR_MOVE_REQ",
            payload["differential_summary"]["research_or_unblock_facts"],
        )

    def test_external_ceiling_without_actionable_gap_is_blocked_evidence(self):
        only_external = {
            "differential_divergences": [
                {
                    "fact_id": "external-ceiling:00",
                    "classification": "externally-unrecoverable",
                    "ceiling": "retired server fact unavailable",
                }
            ]
        }
        self.differential.write_text(json.dumps(only_external))
        payload = self.run_generate()
        self.assertEqual("BLOCKED_EVIDENCE", payload["status"])
        self.assertEqual(0, payload["counts"]["packets"])

    def test_validate_rejects_recursive_and_auto_merge_packet(self):
        payload = self.run_generate()
        packet = payload["packets"][0]
        packet["source_task_id"] = "AUTO-RE-CHILD"
        packet["automation"]["merge"] = True
        self.output.write_text(json.dumps(packet, indent=2, sort_keys=True))

        run = subprocess.run(
            [
                sys.executable,
                str(BIN_PATH),
                "validate",
                str(self.output),
            ],
            cwd=REPO,
            text=True,
            capture_output=True,
        )
        self.assertEqual(2, run.returncode, run.stdout + run.stderr)
        result = json.loads(run.stdout)
        errors = list(result["errors"].values())[0]
        self.assertTrue(any("recursive AUTO-RE/UNBLOCK" in error for error in errors))
        self.assertTrue(any("automatic mutation is forbidden" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
