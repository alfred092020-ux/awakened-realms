import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE,
  LOGRES_TUTORIAL_HUD_DESIGN_SIZE,
  LOGRES_TUTORIAL_HUD_LAYOUT_EVIDENCE,
} from '../src/game/logres/tutorial/LogresTutorialHudEvidence'

describe(
  'Logres tutorial HUD evidence',
  () => {
    it(
      'locks the recovered 720x1280 Global HUD design space',
      () => {
        expect(
          LOGRES_TUTORIAL_HUD_DESIGN_SIZE,
        ).toEqual({
          width:
            720,
          height:
            1280,
        })
      },
    )

    it(
      'selects the captured tutorial parameter bar and rejects the later variant',
      () => {
        const selected =
          LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE
            .parameterBar

        const later =
          LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE
            .parameterBarLaterVariant

        expect(
          selected.sourceEntry,
        ).toBe(
          'field_parameter.dds',
        )

        expect(
          selected.tutorialSelectionLabel,
        ).toBe(
          'CONFIRMED ORIGINAL',
        )

        expect(
          selected.selectedForCapturedTutorial,
        ).toBe(
          true,
        )

        expect(
          later.sourceEntry,
        ).toBe(
          'field_parameter02.astc',
        )

        expect(
          later.sourceLabel,
        ).toBe(
          'CONFIRMED ORIGINAL',
        )

        expect(
          later.selectedForCapturedTutorial,
        ).toBe(
          false,
        )
      },
    )

    it(
      'locks the confirmed quest-start text and scroll assets',
      () => {
        const {
          questStartText,
          questStartBackground,
        } =
          LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE

        expect(
          questStartText.sourceEntry,
        ).toBe(
          'quest_start.dds',
        )

        expect(
          questStartBackground.sourceEntry,
        ).toBe(
          'quest_bg00.dds',
        )

        expect(
          questStartText.tutorialSelectionLabel,
        ).toBe(
          'CONFIRMED ORIGINAL',
        )

        expect(
          questStartBackground.tutorialSelectionLabel,
        ).toBe(
          'CONFIRMED ORIGINAL',
        )
      },
    )

    it(
      'keeps the recovered footer-layout variant unresolved',
      () => {
        expect(
          LOGRES_TUTORIAL_HUD_LAYOUT_EVIDENCE
            .mainHudUnderbarCenter,
        ).toEqual({
          x:
            360,
          y:
            45,
          label:
            'CONFIRMED ORIGINAL',
        })

        expect(
          LOGRES_TUTORIAL_HUD_LAYOUT_EVIDENCE
            .fieldHudFooterUnderbarCenter,
        ).toEqual({
          x:
            360,
          y:
            76,
          label:
            'CONFIRMED ORIGINAL',
        })

        expect(
          LOGRES_TUTORIAL_HUD_LAYOUT_EVIDENCE
            .layoutVariantSelection
            .label,
        ).toBe(
          'UNRESOLVED',
        )
      },
    )
  },
)
