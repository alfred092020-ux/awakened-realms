import json
import sqlite3
import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_peer_consultation import (
    DEFAULT_CONFIG,
    build_provenance,
    consult,
    dedupe_key,
    detect_triggers,
    ensure_schema,
    is_exempt,
)


def cfg(**overrides):
    c = dict(DEFAULT_CONFIG)
    c.update(overrides)
    return c


def conn():
    c = sqlite3.connect(":memory:")
    ensure_schema(c)
    return c


class TriggerTests(unittest.TestCase):
    def test_conflicting_evidence_flag(self):
        self.assertIn("conflicting_evidence", detect_triggers({"conflicting_evidence": True}))

    def test_conflicting_evidence_mixed_verdicts(self):
        req = {"evidence": [{"supports": "yes"}, {"supports": "no"}]}
        self.assertIn("conflicting_evidence", detect_triggers(req))

    def test_low_material_confidence(self):
        self.assertIn(
            "low_material_confidence",
            detect_triggers({"confidence": 0.3}, cfg(material_confidence_floor=0.6)),
        )
        self.assertNotIn(
            "low_material_confidence",
            detect_triggers({"confidence": 0.9}, cfg(material_confidence_floor=0.6)),
        )

    def test_architecture_policy_change(self):
        self.assertIn("architecture_policy_change", detect_triggers({"change_kind": "architecture"}))
        self.assertIn("architecture_policy_change", detect_triggers({"change_kind": "policy"}))
        self.assertNotIn("architecture_policy_change", detect_triggers({"change_kind": "docs_only"}))

    def test_ambiguous_history(self):
        req = {"historical_precedents": [{"outcome": "success"}, {"outcome": "failure"}]}
        self.assertIn("ambiguous_history", detect_triggers(req))
        self.assertIn("ambiguous_history", detect_triggers({"ambiguous_history": True}))

    def test_irreversible_high_cost(self):
        self.assertIn("irreversible_high_cost", detect_triggers({"reversible": False}))
        self.assertIn("irreversible_high_cost", detect_triggers({"cost": 0.9}))
        self.assertIn("irreversible_high_cost", detect_triggers({"impact": "critical"}))
        self.assertNotIn("irreversible_high_cost", detect_triggers({"cost": 0.1, "reversible": True}))

    def test_repeated_verification_failure(self):
        self.assertIn(
            "repeated_verification_failure",
            detect_triggers({"verification_failures": 2}, cfg(verification_failure_threshold=2)),
        )
        self.assertNotIn(
            "repeated_verification_failure",
            detect_triggers({"verification_failures": 1}, cfg(verification_failure_threshold=2)),
        )

    def test_planner_implementer_disagreement(self):
        self.assertIn(
            "planner_implementer_disagreement",
            detect_triggers({"planner_recommendation": "A", "implementer_recommendation": "B"}),
        )
        self.assertNotIn(
            "planner_implementer_disagreement",
            detect_triggers({"planner_recommendation": "A", "implementer_recommendation": "A"}),
        )


class ExemptionTests(unittest.TestCase):
    def test_exempt_change_kind(self):
        self.assertTrue(is_exempt({"change_kind": "docs_only"}, cfg()))
        self.assertTrue(is_exempt({"change_kind": "mechanical_refactor"}, cfg()))

    def test_exempt_reason(self):
        self.assertTrue(is_exempt({"exempt_reasons": ["low_risk_reversible"]}, cfg()))

    def test_not_exempt(self):
        self.assertFalse(is_exempt({"change_kind": "architecture"}, cfg()))
        self.assertFalse(is_exempt({}, cfg()))

    def test_exempt_consult_short_circuits(self):
        out = consult(
            conn(),
            {"change_kind": "docs_only", "confidence": 0.1, "question": "q"},
            config=cfg(),
        )
        self.assertEqual("EXEMPT", out["status"])
        self.assertEqual("proceed", out["decision"])


class ProtocolTests(unittest.TestCase):
    def test_no_trigger_proceeds(self):
        out = consult(conn(), {"question": "q", "confidence": 0.9, "reversible": True}, config=cfg())
        self.assertEqual("NO_TRIGGER", out["status"])
        self.assertEqual("proceed", out["decision"])

    def test_evidence_overrides_peer(self):
        def peer(req, triggers, c):
            return {
                "peer_identity": "p1",
                "peer_engine": "stub",
                "hypotheses": [],
                "recommendation": "reject",
            }

        req = {
            "question": "q",
            "confidence": 0.4,
            "evidence": [{"ref": "t1", "supports": "yes"}],
        }
        out = consult(conn(), req, config=cfg(), peer_pass=peer)
        self.assertEqual("RESOLVED", out["status"])
        self.assertEqual("confirmed_by_evidence", out["provenance"]["confidence"])

    def test_contradicting_evidence_decides(self):
        req = {"question": "q", "confidence": 0.4, "evidence": [{"ref": "t1", "supports": "no"}]}
        out = consult(conn(), req, config=cfg())
        self.assertEqual("RESOLVED", out["status"])
        self.assertEqual("contradicted_by_evidence", out["provenance"]["confidence"])

    def test_disagreement_tiebreak_by_evidence(self):
        def peer(req, triggers, c):
            return {
                "peer_identity": "p1",
                "peer_engine": "stub",
                "hypotheses": [],
                "recommendation": "B",
            }

        req = {
            "question": "q",
            "planner_recommendation": "A",
            "implementer_recommendation": "B",
            "evidence": [{"ref": "test:x", "supports": "yes"}],
        }
        out = consult(conn(), req, config=cfg(), peer_pass=peer)
        self.assertEqual("RESOLVED", out["status"])
        self.assertEqual("decide", out["decision"])

    def test_disagreement_tiebreak_unresolved_escalates_high_impact(self):
        def peer(req, triggers, c):
            return {
                "peer_identity": "p1",
                "peer_engine": "stub",
                "hypotheses": [],
                "recommendation": "B",
            }

        req = {
            "question": "q",
            "planner_recommendation": "A",
            "implementer_recommendation": "B",
            "impact": "high",
            "evidence": [{"ref": "e1", "supports": "yes"}, {"ref": "e2", "supports": "no"}],
        }
        out = consult(conn(), req, config=cfg(), peer_pass=peer)
        self.assertEqual("ESCALATED", out["status"])
        self.assertEqual("escalate", out["decision"])

    def test_unresolved_high_impact_fails_closed(self):
        req = {"question": "q", "confidence": 0.4, "impact": "high"}
        out = consult(conn(), req, config=cfg())
        self.assertEqual("FAIL_CLOSED", out["status"])
        self.assertEqual("escalate", out["decision"])

    def test_unresolved_low_risk_proceeds_when_allowed(self):
        req = {"question": "q", "confidence": 0.4, "impact": "low", "reversible": True}
        out = consult(conn(), req, config=cfg())
        self.assertEqual("PROCEED_LOW_RISK", out["status"])
        self.assertEqual("proceed", out["decision"])

    def test_unresolved_low_risk_bounded_experiment_when_disallowed(self):
        req = {"question": "q", "confidence": 0.4, "impact": "low", "reversible": True}
        out = consult(conn(), req, config=cfg(allow_low_risk_proceed=False))
        self.assertEqual("BOUNDED_EXPERIMENT", out["status"])
        self.assertEqual("bounded_experiment", out["decision"])

    def test_mixed_evidence_low_risk_bounded_experiment(self):
        req = {
            "question": "q",
            "confidence": 0.4,
            "impact": "low",
            "reversible": True,
            "evidence": [{"ref": "a", "supports": "yes"}, {"ref": "b", "supports": "no"}],
        }
        out = consult(conn(), req, config=cfg())
        self.assertEqual("BOUNDED_EXPERIMENT", out["status"])


class CooldownTests(unittest.TestCase):
    def test_dedupe_within_cooldown(self):
        c = conn()
        req = {"question": "q", "confidence": 0.4, "impact": "low", "reversible": True}
        first = consult(c, req, config=cfg())
        second = consult(c, req, config=cfg())
        self.assertEqual("DEDUPED", second["status"])
        self.assertEqual(first["decision"], second["decision"])
        self.assertEqual(first["dedupe_key"], second["dedupe_key"])

    def test_no_cooldown_duplicate_when_expired(self):
        c = conn()
        req = {"question": "q", "confidence": 0.4, "impact": "low", "reversible": True}
        consult(c, req, config=cfg())
        out = consult(c, req, config=cfg(cooldown_seconds=-1))
        self.assertNotEqual("DEDUPED", out["status"])

    def test_dedupe_key_stable(self):
        req = {"question": "q", "task_id": "T1"}
        self.assertEqual(dedupe_key(req, ["a"]), dedupe_key(dict(req), ["a"]))


class ProvenanceTests(unittest.TestCase):
    def test_provenance_fields(self):
        req = {"question": "q?", "confidence": 0.4, "impact": "low", "reversible": True}
        out = consult(conn(), req, config=cfg())
        p = out["provenance"]
        for k in (
            "trigger",
            "question",
            "hypotheses",
            "peer_identity",
            "peer_engine",
            "recommendation_summary",
            "evidence_refs",
            "decision",
            "confidence",
            "status",
        ):
            self.assertIn(k, p)

    def test_secret_keys_redacted(self):
        peer = {
            "peer_identity": "p1",
            "peer_engine": "e",
            "hypotheses": [{"hypothesis": "h", "api_token": "x"}],
            "recommendation": "r",
        }
        p = build_provenance({"question": "q"}, ["t"], peer, {"refs": []}, "d", "c", "s")
        self.assertEqual("[redacted]", p["hypotheses"][0]["api_token"])

    def test_secret_values_redacted(self):
        peer = {
            "peer_identity": "p1",
            "peer_engine": "e",
            "hypotheses": [{"hypothesis": "leak ghp_abcdefghijklmnop"}],
            "recommendation": "r",
        }
        p = build_provenance({"question": "q"}, ["t"], peer, {"refs": []}, "d", "c", "s")
        self.assertEqual("[redacted]", p["hypotheses"][0]["hypothesis"])

    def test_no_transcript_persisted(self):
        c = conn()
        req = {
            "question": "q",
            "confidence": 0.4,
            "impact": "low",
            "reversible": True,
            "transcript": "should-not-persist",
            "raw_prompt": "should-not-persist",
        }
        consult(c, req, config=cfg())
        row = c.execute("select payload_json from peer_consultations").fetchone()
        payload = row[0]
        self.assertNotIn("should-not-persist", payload)


class BudgetTests(unittest.TestCase):
    def test_budget_terminates(self):
        c = conn()
        config = cfg(max_consultations_per_task=2, cooldown_seconds=-1)
        req = {"task_id": "T1", "question": "q", "confidence": 0.4, "impact": "low", "reversible": True}
        consult(c, req, config=config)
        consult(c, req, config=config)
        out = consult(c, req, config=config)
        self.assertEqual("BUDGET_EXHAUSTED", out["status"])
        self.assertEqual("escalate", out["decision"])

    def test_budget_is_per_task(self):
        c = conn()
        config = cfg(max_consultations_per_task=1, cooldown_seconds=-1)
        consult(c, {"task_id": "T1", "question": "q", "confidence": 0.4}, config=config)
        out = consult(c, {"task_id": "T2", "question": "q2", "confidence": 0.4}, config=config)
        self.assertNotEqual("BUDGET_EXHAUSTED", out["status"])

    def test_peer_called_once_per_consult(self):
        calls = []

        def peer(req, triggers, c):
            calls.append(1)
            return {"peer_identity": "p", "peer_engine": "e", "hypotheses": [], "recommendation": "r"}

        c = conn()
        req = {"question": "q", "confidence": 0.4, "impact": "low", "reversible": True}
        consult(c, req, config=cfg(), peer_pass=peer)
        consult(c, req, config=cfg(), peer_pass=peer)  # deduped: no peer call
        self.assertEqual(1, len(calls))


if __name__ == "__main__":
    unittest.main()
