#!/usr/bin/env python3
import importlib.machinery
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "ops/logres-control-plane/bin/logres-hardware-qa"

loader = importlib.machinery.SourceFileLoader(
    "logres_hardware_qa_terms_test",
    str(SCRIPT),
)
spec = importlib.util.spec_from_loader(loader.name, loader)
qa = importlib.util.module_from_spec(spec)
loader.exec_module(qa)


def snapshot(trace, scene="LogresTermsScene"):
    return {
        "activeScenes": [scene],
        "registry": {
            "logres.qa.termsTransitionTrace": trace,
        },
    }


class TermsTransitionTraceTests(unittest.TestCase):
    def test_terms_checkpoint_rejects_already_accepted_clickthrough(self):
        with self.assertRaisesRegex(
            qa.QAError,
            "accepted before",
        ):
            qa.require_terms_rendered(
                snapshot(
                    {
                        "rendered": True,
                        "accepted": True,
                        "freshPointerEdge": False,
                    },
                    "LogresCharacterCreateScene",
                )
            )

    def test_terms_checkpoint_requires_render_trace(self):
        with self.assertRaisesRegex(
            qa.QAError,
            "lacks a rendered",
        ):
            qa.require_terms_rendered(
                {
                    "activeScenes": ["LogresCharacterCreateScene"],
                    "registry": {
                        "logres.auth.termsAccepted": True,
                    },
                }
            )

    def test_fresh_agree_edge_must_be_newer_than_activation_edge(self):
        stale = {
            "rendered": True,
            "accepted": True,
            "freshPointerEdge": True,
            "activationPointerDownTime": 100.0,
            "agreePointerDownTime": 100.0,
        }
        with self.assertRaisesRegex(
            qa.QAError,
            "not newer",
        ):
            qa.require_fresh_terms_acceptance(
                snapshot(stale, "LogresCharacterCreateScene")
            )

        fresh = {
            **stale,
            "agreePointerDownTime": 250.0,
        }
        self.assertEqual(
            qa.require_fresh_terms_acceptance(
                snapshot(fresh, "LogresCharacterCreateScene")
            ),
            fresh,
        )

    def test_terms_scene_source_guards_on_pointer_down_epoch(self):
        source = (
            ROOT / "src/game/scenes/LogresTermsScene.ts"
        ).read_text()
        self.assertIn(
            "pointer.downTime >\n            this.termsSceneInputEpoch",
            source,
        )
        self.assertIn(
            "'logres.qa.termsTransitionTrace'",
            source,
        )


if __name__ == "__main__":
    unittest.main()
