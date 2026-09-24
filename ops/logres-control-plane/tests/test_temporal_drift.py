import copy
import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_temporal_drift import (
    compare_temporal_lattices,
    drift_fingerprint,
    should_open_review,
)

def entity(
    entity_id="protocol:X",
    relation="ENDPOINTS_IDENTICAL_OPCODE_AND_SCHEMA",
    grade="GLOBAL_JP_IDENTICAL_TOP_LEVEL_SCHEMA",
    uncertainty=None,
    global_value=None,
    jp_value=None,
):
    return {
        "entity_id": entity_id,
        "kind": "protocol_message",
        "relation": relation,
        "source_lineage_grade": grade,
        "temporal_uncertainty": uncertainty or {
            "continuous_history_proven": False,
            "statement": "endpoint only",
        },
        "global": global_value or {"present": True, "opcode_hex": "0x01"},
        "current_jp": jp_value or {"present": True, "opcode_hex": "0x01"},
    }

def lattice(lattice_id, entities):
    return {"lattice_id": lattice_id, "entities": entities}

class TemporalDriftTests(unittest.TestCase):
    def test_identical_lattices_have_no_drift(self):
        before = lattice("a", [entity()])
        after = copy.deepcopy(before)
        after["lattice_id"] = "b"
        report = compare_temporal_lattices(before, after)
        self.assertFalse(report["changed"])
        self.assertFalse(should_open_review(report))
        self.assertEqual(0, report["counts"]["material_changes"])
        self.assertFalse(report["automatic_actions"]["merge"])
        self.assertFalse(report["automatic_actions"]["deploy"])

    def test_predicate_authority_uncertainty_and_endpoint_drift_are_separate(self):
        before = lattice("a", [entity()])
        after = lattice("b", [entity(
            relation="ENDPOINTS_OPCODE_STABLE_SCHEMA_CHANGED",
            grade="JP_LINEAGE_OPCODE_STABLE_SCHEMA_CHANGED",
            uncertainty={
                "continuous_history_proven": False,
                "change_interval": {
                    "after": "2017-05-25",
                    "on_or_before": "2026-09-24",
                },
            },
            jp_value={"present": True, "opcode_hex": "0x01", "args": ["int32"]},
        )])
        report = compare_temporal_lattices(before, after)
        self.assertEqual(
            [
                "AUTHORITY_CHANGED",
                "ENDPOINT_FACT_CHANGED",
                "PREDICATE_CHANGED",
                "UNCERTAINTY_CHANGED",
            ],
            sorted(row["kind"] for row in report["changes"]),
        )
        self.assertTrue(should_open_review(report))

    def test_addition_and_removal_are_material(self):
        before = lattice("a", [entity("resource:A")])
        after = lattice("b", [entity("resource:B")])
        report = compare_temporal_lattices(before, after)
        self.assertEqual(
            ["ENTITY_ADDED", "ENTITY_REMOVED"],
            sorted(row["kind"] for row in report["changes"]),
        )
        self.assertTrue(report["requires_explicit_review"])

    def test_protected_claim_impacts_are_explicit(self):
        before = lattice("a", [entity()])
        after = lattice("b", [entity(
            relation="GLOBAL_PRESENT_CURRENT_JP_ABSENT_OR_RENAMED"
        )])
        report = compare_temporal_lattices(
            before,
            after,
            protected_claims=[
                {
                    "entity_id": "protocol:X",
                    "claim_id": "impl:login",
                    "surface": "implementation",
                    "authority": "GLOBAL_DIRECT",
                },
                {
                    "entity_id": "protocol:X",
                    "claim_id": "truth:login",
                    "surface": "truth_kernel",
                    "authority": "GLOBAL_DIRECT",
                },
            ],
        )
        self.assertEqual(1, report["counts"]["protected_claim_impacts"])
        impacts = report["protected_claim_impacts"][0]["claims"]
        self.assertEqual(
            ["implementation", "truth_kernel"],
            [row["surface"] for row in impacts],
        )

    def test_fingerprint_is_order_independent(self):
        e1 = entity("protocol:A")
        e2 = entity("protocol:B")
        before_a = lattice("old", [e1, e2])
        before_b = lattice("old", [e2, e1])
        after_a = lattice("new", [
            entity("protocol:A", relation="GLOBAL_PRESENT_CURRENT_JP_ABSENT_OR_RENAMED"),
            e2,
        ])
        after_b = lattice("new", [
            e2,
            entity("protocol:A", relation="GLOBAL_PRESENT_CURRENT_JP_ABSENT_OR_RENAMED"),
        ])
        r1 = compare_temporal_lattices(before_a, after_a)
        r2 = compare_temporal_lattices(before_b, after_b)
        self.assertEqual(drift_fingerprint(r1), drift_fingerprint(r2))
        self.assertEqual(r1["dedupe_key"], r2["dedupe_key"])

    def test_no_automatic_action_is_exposed(self):
        before = lattice("a", [entity()])
        after = lattice("b", [entity(
            relation="ENDPOINTS_OPCODE_STABLE_SCHEMA_CHANGED"
        )])
        report = compare_temporal_lattices(before, after)
        self.assertEqual(
            {
                "promote_confidence": False,
                "merge": False,
                "deploy": False,
                "modify_main": False,
            },
            report["automatic_actions"],
        )

if __name__ == "__main__":
    unittest.main()
