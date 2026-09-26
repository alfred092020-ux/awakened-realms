import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
REPO_ROOT = CONTROL_ROOT.parents[1]
sys.path.insert(0, str(CONTROL_ROOT / "lib"))

import logres_correctness as lc
import logres_behavior_trace as bt
import logres_visual_truth as vt

POLICY_PATH = CONTROL_ROOT / "config" / "correctness_policy.json"
FARM = CONTROL_ROOT / "bin" / "logres-verify-farm"
GATE = CONTROL_ROOT / "bin" / "logres-gate"
CLI = CONTROL_ROOT / "bin" / "logres-correctness"

SHA = "a" * 40
SHA_B = "b" * 40


def load_policy():
    return lc.load_policy(POLICY_PATH)


def make_plan(policy, paths, sha=SHA):
    return lc.build_plan(
        policy,
        sha=sha,
        ref="worker/test",
        base_ref="origin/feat/logres-reconstruction",
        merge_base_sha="c" * 40,
        paths=paths,
    )


def full_outcomes(specs=None, **overrides):
    outcomes = {
        "sha": SHA,
        "ref": "worker/test",
        "lanes": {
            "unit": {"ran": True, "rc": 0, "path": "local-test+local-build-e2e"},
            "build": {"ran": True, "rc": 0},
            "e2e": {
                "ran": True,
                "rc": 0,
                "workers": 3,
                "tag": "e2e-w3",
                "specs": specs
                if specs is not None
                else [
                    "logres-battle-presentation.spec.mjs",
                    "logres-behavioral-checkpoint.spec.mjs",
                    "logres-behavioral-fidelity.spec.mjs",
                    "logres-playable-battle-input.spec.mjs",
                    "logres-playable-field.spec.mjs",
                    "logres-smoke.spec.mjs",
                    "logres-ui-runtime.spec.mjs",
                    "logres-visual-checkpoints.spec.mjs",
                ],
            },
            "hydration": {"ran": True, "rc": 0},
            "performance": {"required": False, "ran": False, "rc": 0},
            "behavior": {"ran": True, "rc": 0},
            "merge": {
                "behavior": {"ran": True, "ok": True},
                "visual": {"ran": True, "ok": True},
            },
        },
    }
    for key, value in overrides.items():
        outcomes["lanes"][key] = value
    return outcomes


def truth_db(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    bt.ensure_schema(conn)
    vt.ensure_schema(conn)
    conn.executescript(
        """
        create table if not exists device_proofs(
          id integer primary key autoincrement, sha text not null,
          apk_sha256 text, checkpoint text not null, status text not null,
          artifact_path text, note text not null default '',
          created_at text not null, created_epoch real not null
        );
        create table if not exists verification(
          ref text, sha text, mode text, status text,
          duration_sec real, ran_at text, details text
        );
        """
    )
    return conn


def seed_behavior_pass(conn, sha=SHA, provenance=None):
    return bt.record(
        conn,
        sha=sha,
        checkpoint="playable-field-battle-reward-return",
        expected={
            "events": ["FIELD_READY", "BATTLE_ACTIVE"],
            "final_state": {"mapId": "002_000_00001"},
        },
        observed={
            "events": ["FIELD_READY", "BATTLE_ACTIVE"],
            "final_state": {"mapId": "002_000_00001"},
        },
        provenance=provenance
        or {
            "expected_trace": "RECONSTRUCTED_PLAYABILITY_CONTRACT",
            "historical_damage_formula": "UNRESOLVED",
        },
    )


def seed_visual(conn, sha=SHA, checkpoint="field", verdict="REVIEW"):
    return vt.record(
        conn,
        sha=sha,
        checkpoint=checkpoint,
        observed_artifact="/tmp/obs.png",
        verdict=verdict,
        reference_artifact="/tmp/ref.png",
        metrics={"width": 720, "height": 1280},
    )


class PolicyValidationTests(unittest.TestCase):
    def test_committed_policy_loads_and_validates(self):
        policy = load_policy()
        self.assertIn("gameplay", policy["domains"])
        self.assertIn("evaluator", policy["domains"])
        self.assertTrue(
            policy["evaluator"]["requires_independent_verification"]
        )
        self.assertIn("behavior_trace:playable-field-battle-reward-return",
                      policy["l2_oracles"]["gameplay"])

    def test_malformed_policy_fails_closed(self):
        base = load_policy()
        bad_cases = [
            {"schema": 99},
            dict(base, domains={}),
            dict(base, classification=[{"domain": "nope", "globs": ["x"]}]),
            dict(base, l2_oracles={"gameplay": ["bogus:thing"]}),
            dict(base, l2_oracles={"docs": ["e2e:x.spec.mjs"]}),
            dict(base, evaluator={"requires_independent_verification": False}),
            dict(base, unclassified_domain="gameplay"),
        ]
        for bad in bad_cases:
            with self.subTest(bad=str(bad)[:80]):
                if "domains" not in bad or not bad.get("classification"):
                    bad.setdefault(
                        "classification", base["classification"]
                    )
                with self.assertRaises(lc.PolicyError):
                    lc.validate_policy(dict(bad))

    def test_policy_file_invalid_json_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "policy.json"
            path.write_text("{not json")
            with self.assertRaises(lc.PolicyError):
                lc.load_policy(path)


class ClassificationTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy()

    def test_battle_and_gameplay_paths_require_l2(self):
        plan = make_plan(
            self.policy, ["src/game/logres/battle/LogresBattleMath.ts"]
        )
        self.assertIn("battle", plan["domains"])
        self.assertIn("gameplay", plan["domains"])
        self.assertIn("L2", plan["required_levels"])
        self.assertNotIn("L3", plan["required_levels"])
        self.assertIn(
            "behavior_trace:playable-field-battle-reward-return",
            plan["l2_oracles"]["battle"],
        )

    def test_docs_only_change_needs_no_l2(self):
        plan = make_plan(self.policy, ["docs/notes.md", "README.md"])
        self.assertEqual({"docs"}, set(plan["domains"]))
        self.assertEqual(["L0", "L1"], plan["required_levels"])

    def test_protocol_domain_has_no_objective_oracle_so_needs_l3(self):
        plan = make_plan(
            self.policy, ["src/game/logres/protocol/WireFormat.ts"]
        )
        self.assertIn("protocol", plan["l2_domains"])
        self.assertIn("protocol", plan["no_oracle_domains"])
        self.assertIn("L3", plan["required_levels"])

    def test_evaluator_surface_requires_independent_verification(self):
        for path in (
            "ops/logres-control-plane/lib/logres_correctness.py",
            "ops/logres-control-plane/bin/logres-verify-farm",
            "ops/logres-control-plane/config/correctness_policy.json",
            "e2e/logres-behavioral-checkpoint.spec.mjs",
            "scripts/logres/verify_behavior_checkpoint.py",
            "playwright.config.mjs",
        ):
            with self.subTest(path=path):
                plan = make_plan(self.policy, [path])
                self.assertTrue(plan["requires_independent_verification"])
                self.assertIn("L3", plan["required_levels"])

    def test_unclassified_code_root_needs_review(self):
        plan = make_plan(self.policy, ["src/mystery/newthing.ts"])
        self.assertIn("src/mystery/newthing.ts", plan["unclassified"])
        self.assertIn("L3", plan["required_levels"])

    def test_classification_is_deterministic(self):
        paths = [
            "src/game/logres/field/LogresFieldScene.ts",
            "src/game/logres/battle/LogresCombat.ts",
            "tests/LogresField.test.ts",
        ]
        a = make_plan(self.policy, paths)
        b = make_plan(self.policy, list(reversed(paths)))
        self.assertEqual(
            {k: a[k] for k in ("domains", "required_levels", "l2_domains")},
            {k: b[k] for k in ("domains", "required_levels", "l2_domains")},
        )


class LadderEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy()
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.db_path = Path(self.td.name) / "control.sqlite"
        self.conn = truth_db(self.db_path)
        self.addCleanup(self.conn.close)

    def evaluate(self, paths, outcomes=None, truth=None, attestations=None):
        plan = make_plan(self.policy, paths)
        return lc.evaluate(
            plan,
            outcomes if outcomes is not None else full_outcomes(),
            truth if truth is not None else {"behavior": [], "visual": [], "device": [], "verification": []},
            self.policy,
            attestations=attestations or [],
            run_id="test-run",
        )

    def test_docs_only_diff_passes_on_l1(self):
        receipt = self.evaluate(["docs/notes.md"])
        self.assertEqual("PASS", receipt["verdict"])
        self.assertFalse(receipt["levels"]["L2"]["required"])

    def test_gameplay_diff_rejected_on_l1_only_outcomes(self):
        l1_only = full_outcomes(
            specs=[],
            e2e={"ran": False, "rc": 0, "specs": []},
            behavior={"ran": False, "rc": 0},
        )
        receipt = self.evaluate(
            ["src/game/logres/battle/LogresBattleMath.ts"], outcomes=l1_only
        )
        self.assertEqual("BLOCKED", receipt["verdict"])
        self.assertTrue(receipt["blocking_failures"])
        self.assertTrue(
            any("required L2 oracle" in b for b in receipt["blocking_failures"])
        )
        self.assertEqual("L1", receipt["tier"])

    def test_gameplay_diff_fails_when_l2_oracle_fails(self):
        outcomes = full_outcomes()
        outcomes["lanes"]["e2e"]["rc"] = 1
        receipt = self.evaluate(
            ["src/game/logres/battle/LogresBattleMath.ts"], outcomes=outcomes
        )
        self.assertEqual("FAIL", receipt["verdict"])
        self.assertTrue(receipt["failures"])

    def test_l2_evidence_satisfies_fidelity_requirement(self):
        seed_behavior_pass(self.conn)
        seed_visual(self.conn, checkpoint="battle", verdict="REVIEW")
        self.conn.close()
        truth = lc.collect_truth([self.db_path], SHA)
        self.conn = truth_db(self.db_path)
        receipt = self.evaluate(
            ["src/game/logres/battle/LogresBattleMath.ts"], truth=truth
        )
        behavior_checks = [
            c
            for c in receipt["levels"]["L2"]["checks"]
            if c["kind"] == "behavior_trace"
        ]
        self.assertEqual("PASS", behavior_checks[0]["outcome"])
        visual_checks = [
            c for c in receipt["levels"]["L2"]["checks"]
            if c["kind"] == "visual_truth"
        ]
        self.assertEqual(["REVIEW"], [c["outcome"] for c in visual_checks])
        self.assertEqual("PASS", receipt["verdict"])
        self.assertEqual("L2", receipt["tier"])
        self.assertTrue(receipt["evidence"])
        # missing visual evidence for a required domain would have blocked
        truth_missing = {"behavior": [], "visual": [], "device": [],
                         "verification": []}
        blocked = self.evaluate(
            ["src/game/logres/battle/LogresBattleMath.ts"],
            truth=truth_missing,
        )
        self.assertEqual("BLOCKED", blocked["verdict"])

    def test_unresolved_evidence_ceiling_is_preserved_not_upgraded(self):
        seed_behavior_pass(self.conn)
        self.conn.close()
        truth = lc.collect_truth([self.db_path], SHA)
        self.conn = truth_db(self.db_path)
        receipt = self.evaluate(
            ["src/game/logres/battle/LogresBattleMath.ts"], truth=truth
        )
        ceilings = receipt["unresolved_ceilings"]
        damage = [
            c for c in ceilings if c["aspect"] == "historical_damage_formula"
        ]
        self.assertEqual(1, len(damage))
        self.assertEqual("UNRESOLVED", damage[0]["canonical"])
        self.assertFalse(damage[0]["blocking"])
        self.assertFalse(
            any(c["canonical"] == "CONFIRMED ORIGINAL" for c in ceilings)
        )

    def test_visual_review_verdict_recorded_as_ceiling(self):
        seed_visual(self.conn, verdict="REVIEW")
        self.conn.close()
        truth = lc.collect_truth([self.db_path], SHA)
        self.conn = truth_db(self.db_path)
        receipt = self.evaluate(
            ["src/game/scenes/LogresFieldScene.ts"], truth=truth
        )
        review = [
            c for c in receipt["unresolved_ceilings"]
            if c["canonical"] == "REVIEW"
        ]
        self.assertTrue(review)
        self.assertEqual("REVIEW", receipt["visual"]["records"][0]["verdict"])

    def test_visual_fail_record_blocks(self):
        seed_visual(self.conn, verdict="FAIL")
        self.conn.close()
        truth = lc.collect_truth([self.db_path], SHA)
        self.conn = truth_db(self.db_path)
        receipt = self.evaluate(
            ["src/game/scenes/LogresFieldScene.ts"], truth=truth
        )
        self.assertEqual("FAIL", receipt["verdict"])

    def test_evaluator_self_change_blocked_without_attestation(self):
        receipt = self.evaluate(
            ["ops/logres-control-plane/lib/logres_correctness.py"]
        )
        self.assertEqual("BLOCKED", receipt["verdict"])
        self.assertTrue(receipt["requires_independent_verification"])
        self.assertEqual("BLOCKED", receipt["levels"]["L3"]["verdict"])
        self.assertTrue(
            any("independent verification" in r
                for r in receipt["levels"]["L3"]["reasons"])
        )

    def test_evaluator_self_change_passes_with_attestation(self):
        receipt = self.evaluate(
            ["ops/logres-control-plane/lib/logres_correctness.py"],
            attestations=[{"reviewer": "lead", "note": "manual cross-check"}],
        )
        self.assertEqual("PASS", receipt["verdict"])
        self.assertEqual("L3", receipt["tier"])
        self.assertEqual(
            "lead", receipt["levels"]["L3"]["attestation"]["reviewer"]
        )

    def test_missing_required_oracle_cannot_be_attested_away(self):
        receipt = self.evaluate(
            ["src/game/logres/field/LogresFieldScene.ts",
             "ops/logres-control-plane/lib/logres_correctness.py"],
            attestations=[{"reviewer": "lead", "note": "manual"}],
        )
        self.assertEqual("BLOCKED", receipt["verdict"])

    def test_merge_failure_is_blocking_failure(self):
        outcomes = full_outcomes()
        outcomes["lanes"]["merge"]["behavior"] = {"ran": True, "ok": False}
        receipt = self.evaluate(["docs/notes.md"], outcomes=outcomes)
        self.assertEqual("FAIL", receipt["verdict"])
        self.assertTrue(
            any("merge failed" in f for f in receipt["failures"])
        )


class ConfidenceCeilingTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy()

    def test_current_jp_provenance_capped_at_supported_inference(self):
        capped = lc.cap_confidence(
            "CONFIRMED", "CONFIRMED_CURRENT_JP_002_000_00001", self.policy
        )
        self.assertFalse(capped["confirmed_original"])
        self.assertTrue(capped["capped_by_non_global_provenance"])
        self.assertEqual(0.72, capped["score"])

    def test_global_provenance_keeps_confirmed_original(self):
        capped = lc.cap_confidence(
            "CONFIRMED ORIGINAL", "RECOVERED_GLOBAL_MAY_2017", self.policy
        )
        self.assertTrue(capped["confirmed_original"])
        self.assertEqual(1.0, capped["score"])

    def test_medium_low_version_sensitive_never_confirmed(self):
        for label in ("MEDIUM", "LOW", "VERSION SENSITIVE", "RECONSTRUCTED"):
            with self.subTest(label=label):
                capped = lc.cap_confidence(label, "GLOBAL_2017", self.policy)
                self.assertFalse(capped["confirmed_original"])


class ReceiptPersistenceTests(unittest.TestCase):
    def test_exact_sha_receipt_round_trip(self):
        policy = load_policy()
        plan = make_plan(policy, ["docs/notes.md"])
        receipt = lc.evaluate(
            plan,
            full_outcomes(),
            {"behavior": [], "visual": [], "device": [], "verification": []},
            policy,
        )
        self.assertEqual("logres-correctness-receipt/1", receipt["schema"])
        for key in (
            "sha", "ref", "verdict", "tier", "levels", "evidence",
            "trace", "visual", "skips", "blocking_failures",
            "unresolved_ceilings", "receipt_sha256",
        ):
            self.assertIn(key, receipt)
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        row_id = lc.record_receipt(conn, receipt)
        self.assertGreater(row_id, 0)
        latest = lc.latest_receipt(conn, SHA)
        self.assertEqual("PASS", latest["verdict"])
        self.assertEqual(receipt["receipt_sha256"], latest["receipt_sha256"])

    def test_receipt_requires_exact_sha(self):
        conn = sqlite3.connect(":memory:")
        with self.assertRaises(lc.CorrectnessError):
            lc.record_receipt(conn, {"sha": "abc123", "verdict": "PASS"})


class GateFarmIntegrationTests(unittest.TestCase):
    def test_scripts_parse(self):
        for script in (FARM, GATE):
            result = subprocess.run(
                ["bash", "-n", str(script)], capture_output=True, text=True
            )
            self.assertEqual(0, result.returncode, result.stderr)
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(CLI)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_farm_emits_correctness_receipt_and_preserves_gates(self):
        text = FARM.read_text()
        # new ladder wiring
        self.assertIn('CORRECTNESS_BIN="${LOGRES_CORRECTNESS_BIN:', text)
        self.assertIn('"$CORRECTNESS_BIN" plan', text)
        self.assertIn('"$CORRECTNESS_BIN" evaluate', text)
        self.assertIn("--control-db \"$CANONICAL_CONTROL_DB\"", text)
        self.assertIn('correctness_receipt=$CORRECTNESS_RECEIPT', text)
        self.assertIn('VERIFY_FARM BLOCKED correctness ladder', text)
        # truth stores are consulted, not forked
        self.assertIn('--aux-db "$BEHAVIOR_TRACE_DB"', text)
        self.assertIn('--aux-db "$VISUAL_TRUTH_DB"', text)
        # existing gates preserved
        for needle in (
            'exec 9>/tmp/logres-verify-farm.lock',
            'SHA=$(git -C "$BASE" rev-parse "$REF")',
            'hydrate "$E2E_WT"',
            'npm run test:e2e -- "${shared_e2e_specs[@]}" --workers="$E2E_WORKERS"',
            'npm run test:e2e -- "$PERF_SPEC_REL" --workers=1',
            "! -name 'logres-performance.spec.mjs'",
            'export LOGRES_VERIFY_SHA="$SHA"',
            'export LOGRES_RECORD_VISUAL_TRUTH=1',
            'export LOGRES_REQUIRE_VISUAL_TRUTH_RECORD=1',
            'verify_behavior_checkpoint.py',
            'merge_behavior_trace_isolation',
            'merge_visual_truth_isolation',
            'VERIFY_FARM PASS ref=',
        ):
            self.assertIn(needle, text)
        # receipt emitted after merges, before PASS
        self.assertLess(
            text.index('if ! merge_visual_truth_isolation; then'),
            text.index('run_correctness_evaluate complete ok ok'),
        )
        self.assertLess(
            text.index('run_correctness_evaluate complete ok ok'),
            text.index('VERIFY_FARM PASS ref='),
        )
        # receipts also emitted on failure paths
        self.assertIn('run_correctness_evaluate lanes pending pending', text)
        self.assertIn('run_correctness_evaluate lanes failed pending', text)
        self.assertIn('run_correctness_evaluate lanes ok failed', text)

    def test_gate_enforces_receipt_on_fresh_candidate_path(self):
        text = GATE.read_text()
        self.assertIn('"$BIN/logres-verify-farm" "$ref"', text)
        self.assertIn('"$CORRECTNESS" receipt "$sha"', text)
        self.assertIn('"$CORRECTNESS" backfill "$sha"', text)
        self.assertIn('correctness receipt verdict=$verdict', text)
        self.assertIn('logres-gate {fast|candidate|final}', text)
        # cached candidates must carry a PASS receipt (or be rebuilt from
        # recorded evidence) - no receipt falls through to verify-farm
        self.assertIn('lacks a PASS correctness receipt', text)
        # fast/final modes preserved
        self.assertIn('logres-fast-verify', text)
        self.assertIn('logres-verify-all-ref', text)


class CliEndToEndTests(unittest.TestCase):
    def test_plan_and_evaluate_via_cli(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "control.sqlite"
            conn = truth_db(db)
            seed_behavior_pass(conn)
            conn.close()

            env = os.environ.copy()
            env["PYTHONPATH"] = str(CONTROL_ROOT / "lib")
            plan_file = root / "plan.json"
            proc = subprocess.run(
                [
                    sys.executable, str(CLI), "plan",
                    "--paths", "src/game/logres/battle/LogresBattleMath.ts",
                    "--sha", SHA,
                    "--policy", str(POLICY_PATH),
                    "--output", str(plan_file),
                ],
                capture_output=True, text=True, env=env,
            )
            self.assertEqual(0, proc.returncode, proc.stderr)
            plan = json.loads(plan_file.read_text())
            self.assertIn("battle", plan["domains"])
            self.assertIn("L2", plan["required_levels"])

            outcomes_file = root / "outcomes.json"
            outcomes_file.write_text(json.dumps(full_outcomes()))
            receipt_file = root / "receipt.json"
            proc = subprocess.run(
                [
                    sys.executable, str(CLI), "evaluate",
                    "--plan", str(plan_file),
                    "--outcomes", str(outcomes_file),
                    "--sha", SHA,
                    "--policy", str(POLICY_PATH),
                    "--control-db", str(db),
                    "--output", str(receipt_file),
                ],
                capture_output=True, text=True, env=env,
            )
            receipt = json.loads(receipt_file.read_text())
            self.assertIn(receipt["verdict"], ("PASS", "BLOCKED", "FAIL"))
            self.assertEqual(SHA, receipt["sha"])

            proc = subprocess.run(
                [sys.executable, str(CLI), "receipt", SHA,
                 "--control-db", str(db)],
                capture_output=True, text=True, env=env,
            )
            self.assertEqual(0, proc.returncode, proc.stderr)
            stored = json.loads(proc.stdout)
            self.assertEqual(receipt["verdict"], stored["verdict"])

    def test_cli_fails_closed_on_bad_policy(self):
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "bad.json"
            bad.write_text('{"schema": 42}')
            env = os.environ.copy()
            proc = subprocess.run(
                [
                    sys.executable, str(CLI), "plan",
                    "--paths", "src/x.ts",
                    "--policy", str(bad),
                ],
                capture_output=True, text=True, env=env,
            )
            self.assertEqual(2, proc.returncode)
            self.assertIn("fail closed", proc.stderr)


if __name__ == "__main__":
    unittest.main()
