import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
LIB = TEST_DIR.parent / "lib" / "logres_jp_live_reference.py"
SPEC = importlib.util.spec_from_file_location("logres_jp_live_reference", LIB)
module = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(module)


CLIENT = {
    "package_name": "jp.MarvelousAQL.logres",
    "version_name": "12.8.1",
    "version_code": "12101",
    "xapk_sha256": "7803989f3a02d2662f83cefe25e648e04e7d529f650a70ca7911d7b98972c76c",
    "libgame_arm64_sha256": "1564f02b23c9909adc0d26636adfc8e72a7ed9363655af0d1ae22635e55acbeb",
}


class JpLiveReferenceCompilerTests(unittest.TestCase):
    def setUp(self):
        self.contract = {
            "schema_version": 1,
            "classification_default": "VERSION SENSITIVE",
            "client_binding": {
                "package": CLIENT["package_name"],
                "version_name": CLIENT["version_name"],
                "version_code": int(CLIENT["version_code"]),
                "xapk_sha256": CLIENT["xapk_sha256"],
                "libgame_arm64_sha256": CLIENT["libgame_arm64_sha256"],
            },
            "request_dsl": {
                "step_types": [
                    "assert_package", "assert_version", "launch",
                    "wait_activity", "wait_logcat", "screenshot",
                    "record_start", "record_stop", "tap", "swipe",
                    "tap_template", "dump_ui", "logcat_snapshot",
                    "sleep", "checkpoint",
                ],
                "failure_policy": "Fail closed.",
            },
            "safety": {
                "reconstruction_package": "com.nexuscore.awakenedrealms",
                "forbidden_actions": [
                    "pm clear com.nexuscore.awakenedrealms",
                    "uninstall com.nexuscore.awakenedrealms",
                ],
            },
            "capture_packet": {
                "artifacts": ["manifest.json", "inputs.jsonl", "logcat.txt"],
                "required_metadata": [
                    "workflow_id", "client package/version/hashes",
                    "device model/android/build", "started_at", "finished_at",
                    "classification", "input_sequence", "artifacts",
                    "artifact_sha256", "logcat_excerpt_index", "observations",
                    "contradictions", "unresolved",
                ],
                "brain_registration": "Publish packet hash to Brain.",
            },
            "named_workflows": {
                "field_hud": ["wait_logcat:GameField", "screenshot", "logcat_snapshot"],
                "movement_collision": [
                    "field_hud",
                    "tap/swipe grid of bounded targets",
                    "timestamp every input",
                ],
            },
        }
        self.provenance = {
            "classification": "VERSION SENSITIVE",
            "client": dict(CLIENT),
        }

    def test_compiles_named_workflow_deterministically(self):
        first = module.compile_workflow(
            self.contract,
            self.provenance,
            "field_hud",
        )
        second = module.compile_workflow(
            self.contract,
            self.provenance,
            "field_hud",
        )
        self.assertEqual(first, second)
        self.assertEqual("field_hud", first["workflow_id"])
        self.assertEqual("VERSION SENSITIVE", first["classification"])
        self.assertEqual(
            ["wait_logcat", "screenshot", "logcat_snapshot"],
            [step["type"] for step in first["steps"]],
        )
        self.assertEqual("GameField", first["steps"][0]["value"])
    def test_expands_nested_workflow_and_preserves_freeform_as_checkpoint(self):
        plan = module.compile_workflow(
            self.contract,
            self.provenance,
            "movement_collision",
        )
        self.assertEqual(
            [
                "wait_logcat",
                "screenshot",
                "logcat_snapshot",
                "checkpoint",
                "checkpoint",
            ],
            [step["type"] for step in plan["steps"]],
        )
        self.assertEqual(
            "tap/swipe grid of bounded targets",
            plan["steps"][3]["instruction"],
        )

    def test_packet_skeleton_contains_required_capture_fields(self):
        plan = module.compile_workflow(
            self.contract,
            self.provenance,
            "field_hud",
        )
        packet = plan["capture_packet"]
        self.assertEqual("field_hud", packet["workflow_id"])
        self.assertEqual("VERSION SENSITIVE", packet["classification"])
        self.assertEqual([], packet["input_sequence"])
        self.assertEqual({}, packet["artifact_sha256"])
    def test_accepts_canonical_native_library_list(self):
        provenance = copy.deepcopy(self.provenance)
        provenance["client"].pop("libgame_arm64_sha256")
        provenance["client"]["native_libraries"] = [
            {
                "path": "lib/arm64-v8a/libgame.so",
                "sha256": CLIENT["libgame_arm64_sha256"],
            }
        ]
        plan = module.compile_workflow(
            self.contract, provenance, "field_hud"
        )
        self.assertEqual("field_hud", plan["workflow_id"])

    def test_rejects_wrong_client_binding(self):
        wrong = copy.deepcopy(self.provenance)
        wrong["client"]["version_code"] = "99999"
        with self.assertRaisesRegex(module.ReferencePlanError, "version_code"):
            module.compile_workflow(self.contract, wrong, "field_hud")

    def test_rejects_historical_promotion(self):
        contract = copy.deepcopy(self.contract)
        contract["classification_default"] = "CONFIRMED ORIGINAL"
        with self.assertRaisesRegex(module.ReferencePlanError, "VERSION SENSITIVE"):
            module.compile_workflow(contract, self.provenance, "field_hud")

    def test_rejects_forbidden_reconstruction_mutation(self):
        contract = copy.deepcopy(self.contract)
        contract["named_workflows"]["unsafe"] = [
            "pm clear com.nexuscore.awakenedrealms"
        ]
        with self.assertRaisesRegex(module.ReferencePlanError, "forbidden"):
            module.compile_workflow(contract, self.provenance, "unsafe")

    def test_rejects_unknown_workflow(self):
        with self.assertRaisesRegex(module.ReferencePlanError, "unknown workflow"):
            module.compile_workflow(self.contract, self.provenance, "missing")

    def test_all_named_workflows_compile(self):
        for workflow_id in sorted(self.contract["named_workflows"]):
            plan = module.compile_workflow(
                self.contract,
                self.provenance,
                workflow_id,
            )
            self.assertEqual(workflow_id, plan["workflow_id"])


if __name__ == "__main__":
    unittest.main()
