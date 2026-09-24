import importlib.machinery
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


TEST_DIR = Path(__file__).resolve().parent
SCRIPT = TEST_DIR.parent / "bin" / "logres-hardware-qa"
loader = importlib.machinery.SourceFileLoader("logres_hardware_qa", str(SCRIPT))
qa = types.ModuleType(loader.name)
loader.exec_module(qa)


def battle_state(
    *,
    show_demo=False,
    accepted=0,
    threshold=3,
    provenance=None,
    fallback_panel=True,
):
    panels = [
        {
            "normalSkillRef": "reconstructed-normal-attack",
            "slotIndex": 0,
            "specialEpCost": None if fallback_panel else 1,
            "specialSkillRef": None if fallback_panel else "special",
            "unlocked": True,
            "weaponRef": "reconstructed-tutorial-weapon",
        },
        *[
            {
                "normalSkillRef": None,
                "slotIndex": index,
                "specialEpCost": None,
                "specialSkillRef": None,
                "unlocked": False,
                "weaponRef": None,
            }
            for index in range(1, 5)
        ],
    ]
    registry = {
        "logres.battle.presentation": {
            "showDemoControls": show_demo,
            "weaponPanels": panels,
        },
        "logres.playableBattle.status": "ACTIVE",
        "logres.playableBattle.authority": {
            "phase": "active",
            "acceptedCommandCount": accepted,
            "victoryThreshold": threshold,
        },
    }
    if provenance is not None:
        registry["logres.playableBattle.inputProvenance"] = provenance
    return {
        "activeScenes": ["LogresBattleScene"],
        "registry": registry,
    }


def victory_state(*, reward=True):
    inventory = {
        "provenance": "RECONSTRUCTED",
        "revision": 1,
        "entries": [
            {
                "itemKey": "playable-tutorial-reconstructed-reward-line",
                "originalItemId": None,
                "quantity": 1,
                "grantKey": "playable-tutorial-battle-reward-v1",
            }
        ],
        "appliedGrantKeys": ["playable-tutorial-battle-reward-v1"],
    }
    return {
        "activeScenes": ["LogresBattleScene"],
        "registry": {
            "logres.playableBattle.status": "FIELD_RETURN_READY",
            "logres.playableBattle.inputProvenance": "RECONSTRUCTED_PLAYABILITY_FALLBACK",
            "logres.playableBattle.authority": {
                "phase": "victory-ready",
                "acceptedCommandCount": 3,
                "victoryThreshold": 3,
            },
            "logres.playableBattle.resolution": {
                "phase": "field-return-ready",
                "provenance": "RECONSTRUCTED",
            },
            "logres.playableBattle.rewardApplied": reward,
            "logres.playableBattle.inventory": inventory,
        },
    }


class HardwareQaTests(unittest.TestCase):
    def test_success_path_uses_weapon_panel_fallback_contract(self):
        plan = qa.playable_battle_plan(
            battle_state(),
            {"width": 720, "height": 1280},
        )
        self.assertEqual(
            {
                "x": 136.0,
                "y": 1130.0,
                "slotIndex": 0,
                "threshold": 3,
                "accepted": 0,
                "inputProvenance": "RECONSTRUCTED_PLAYABILITY_FALLBACK",
            },
            plan,
        )

        progress = battle_state(
            accepted=1,
            provenance="RECONSTRUCTED_PLAYABILITY_FALLBACK",
        )
        self.assertEqual(1, qa.require_command_progress(progress, 1, 3))

        victory = victory_state()
        inventory = qa.require_playable_victory(victory)
        self.assertEqual("RECONSTRUCTED", inventory["provenance"])

        returned = {
            "activeScenes": ["LogresFieldScene"],
            "registry": {
                "logres.playableField.status": "READY",
                "logres.playableBattle.inventory": inventory,
            },
        }
        self.assertTrue(qa.require_field_return(returned, inventory))

    def test_harness_visible_is_rejected(self):
        with self.assertRaisesRegex(qa.QAError, "demo/harness"):
            qa.playable_battle_plan(
                battle_state(show_demo=True),
                {"width": 720, "height": 1280},
            )

    def test_no_fallback_capable_panel_is_rejected(self):
        with self.assertRaisesRegex(qa.QAError, "fallback-capable"):
            qa.playable_battle_plan(
                battle_state(fallback_panel=False),
                {"width": 720, "height": 1280},
            )

    def test_command_progress_requires_fallback_provenance(self):
        with self.assertRaisesRegex(qa.QAError, "input provenance"):
            qa.require_command_progress(
                battle_state(accepted=1),
                1,
                3,
            )

    def test_command_threshold_not_reached_fails_closed(self):
        with self.assertRaisesRegex(qa.QAError, "did not advance"):
            qa.require_command_progress(
                battle_state(
                    accepted=0,
                    provenance="RECONSTRUCTED_PLAYABILITY_FALLBACK",
                ),
                1,
                3,
            )

    def test_missing_reward_fails_closed(self):
        with self.assertRaisesRegex(qa.QAError, "did not apply"):
            qa.require_playable_victory(victory_state(reward=False))

    def test_failed_field_return_fails_closed(self):
        inventory = qa.require_playable_victory(victory_state())
        bad = {
            "activeScenes": ["LogresBattleScene"],
            "registry": {
                "logres.playableField.status": "READY",
                "logres.playableBattle.inventory": inventory,
            },
        }
        with self.assertRaisesRegex(qa.QAError, "LogresFieldScene"):
            qa.require_field_return(bad, inventory)

    def test_runner_targets_panel_not_enemy(self):
        text = SCRIPT.read_text()
        self.assertNotIn('stage=registry.get("logres.battle.stagePresentation")', text)
        self.assertIn("logical_game_size()", text)
        self.assertIn("RECONSTRUCTED_PLAYABILITY_FALLBACK", text)
        self.assertIn('checks["battle_victory_return"]="PASS"', text)
        self.assertIn("tap(360,160)", text)



class HardwareQaPersistenceTests(unittest.TestCase):
    def test_record_db_raises_when_device_proof_indexing_fails(self):
        failed = SimpleNamespace(
            returncode=2,
            stdout="",
            stderr="DEVICE_PROOF_PERSISTENCE_FAILED: database is locked",
        )
        with patch.object(qa.subprocess, "run", return_value=failed):
            with self.assertRaisesRegex(qa.QAError, "DB indexing failed"):
                qa.record_db(
                    "a" * 40,
                    Path("/tmp/exact.apk"),
                    Path("/tmp/device-proof.json"),
                    "PASS",
                    "proof note",
                )

    def test_record_db_requires_persistence_acknowledgement(self):
        ambiguous = SimpleNamespace(
            returncode=0,
            stdout="unexpected output",
            stderr="",
        )
        with patch.object(qa.subprocess, "run", return_value=ambiguous):
            with self.assertRaisesRegex(
                qa.QAError,
                "without persistence acknowledgement",
            ):
                qa.record_db(
                    "a" * 40,
                    Path("/tmp/exact.apk"),
                    Path("/tmp/device-proof.json"),
                    "PASS",
                    "proof note",
                )

    def test_runner_preserves_artifact_and_surfaces_index_failure(self):
        text = SCRIPT.read_text()
        self.assertIn('effective_status="INDEX_FAILED"', text)
        self.assertIn("device-proof-index-error.txt", text)
        self.assertIn('"reconcile_command"', text)
        self.assertIn('update_task(note,proof_status="FAIL")', text)


if __name__ == "__main__":
    unittest.main()
