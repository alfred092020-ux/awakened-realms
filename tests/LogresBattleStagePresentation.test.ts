import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  createLogresBattleStagePresentation,
  LOGRES_BATTLE_STAGE_LAYOUT,
  LOGRES_BATTLE_STAGE_PROVENANCE,
} from '../src/game/logres/battle/LogresBattleStagePresentation'

describe(
  'Logres battle stage presentation',
  () => {
    it(
      'locks the Global native actor/position evidence ceiling without inventing historical values',
      () => {
        expect(
          LOGRES_BATTLE_STAGE_PROVENANCE,
        ).toEqual({
          actorSpawnArchitecture:
            'CONFIRMED_GLOBAL_3_0_24_NATIVE',

          battlePositionStructure:
            'CONFIRMED_GLOBAL_3_0_24_NATIVE_iX_iY',

          battlePositionToScreenTransform:
            'UNRESOLVED',

          screenPlacement:
            'RECONSTRUCTED',

          battleBackgroundResourceFamily:
            'CONFIRMED_GLOBAL_BOUTBG_BFD_PATTERN',

          battleBackgroundCandidate:
            'SUPPORTED_INFERENCE_CURRENT_JP_BFD_002_001',

          historicalBattleBackgroundSelection:
            'UNRESOLVED',

          stageGroundFallback:
            'RECONSTRUCTED_PRESENTATION_ONLY',

          historicalStats:
            'UNRESOLVED',

          historicalPlayerShapeId:
            'UNRESOLVED',

          historicalEnemyShapeId:
            'UNRESOLVED',
        })
      },
    )

    it(
      'uses the character-create gender tuple for player reference art when available',
      () => {
        const male =
          createLogresBattleStagePresentation(
            720,
            1280,
            [
              0,
              'Novice',
              0,
              1,
              1,
              1,
              1,
              1,
            ],
            true,
          )

        const female =
          createLogresBattleStagePresentation(
            720,
            1280,
            [
              0,
              'Novice',
              1,
              1,
              1,
              1,
              1,
              1,
            ],
            true,
          )

        expect(
          male,
        ).toMatchObject({
          mode:
            'RECOVERED_REFERENCE_ART',

          referenceSex:
            'm',

          genderSelection:
            'CHARACTER_CREATE_REQUEST',

          player: {
            art:
              'bod_001_m_reference',

            historicalShapeId:
              'UNRESOLVED',

            historicalBattlePosition:
              'UNRESOLVED',
          },
        })

        expect(
          female,
        ).toMatchObject({
          referenceSex:
            'f',

          genderSelection:
            'CHARACTER_CREATE_REQUEST',

          player: {
            art:
              'bod_001_f_reference',

            historicalShapeId:
              'UNRESOLVED',

            historicalBattlePosition:
              'UNRESOLVED',
          },
        })
      },
    )

    it(
      'uses an explicitly reconstructed male reference only when direct battle QA has no onboarding tuple',
      () => {
        expect(
          createLogresBattleStagePresentation(
            720,
            1280,
            null,
            false,
          ),
        ).toMatchObject({
          mode:
            'PLACEHOLDER_FALLBACK',

          referenceSex:
            'm',

          genderSelection:
            'RECONSTRUCTED_REFERENCE_FALLBACK',
        })
      },
    )

    it(
      'keeps the recovered BFD candidate separate from the unresolved historical tutorial selection',
      () => {
        const recovered =
          createLogresBattleStagePresentation(
            720,
            1280,
            null,
            true,
            true,
          )

        expect(
          recovered.background,
        ).toEqual({
          mode:
            'CURRENT_JP_CANDIDATE',

          resource:
            'battle/field/bfd_002_001.png',

          provenance:
            'SUPPORTED_INFERENCE_CURRENT_JP_BFD_002_001',

          historicalGlobalTutorialSelection:
            'UNRESOLVED',
        })

        const fallback =
          createLogresBattleStagePresentation(
            720,
            1280,
            null,
            true,
            false,
          )

        expect(
          fallback.background,
        ).toMatchObject({
          mode:
            'RECONSTRUCTED_FALLBACK',

          provenance:
            'RECONSTRUCTED_PRESENTATION_ONLY',

          historicalGlobalTutorialSelection:
            'UNRESOLVED',
        })
      },
    )

    it(
      'keeps the tutorial enemy identity evidenced while its historical shape and screen position stay unresolved',
      () => {
        const view =
          createLogresBattleStagePresentation(
            720,
            1280,
            null,
            true,
          )

        expect(
          view.enemy,
        ).toMatchObject({
          art:
            'enm_001_000_000_green_jell_reference',

          artProvenance:
            'SUPPORTED_INFERENCE_CURRENT_JP_REFERENCE_ART',

          identityProvenance:
            'CONFIRMED_GLOBAL_GREEN_JELL_TUTORIAL',

          historicalShapeId:
            'UNRESOLVED',

          historicalBattlePosition:
            'UNRESOLVED',
        })
      },
    )

    it(
      'uses a bounded reconstructed layout that remains above the weapon-control band',
      () => {
        const view =
          createLogresBattleStagePresentation(
            720,
            1280,
            null,
            true,
          )

        expect(
          view.player.x,
        ).toBeCloseTo(
          720 *
            LOGRES_BATTLE_STAGE_LAYOUT
              .player
              .xRatio,
        )

        expect(
          view.enemy.y,
        ).toBeCloseTo(
          1280 *
            LOGRES_BATTLE_STAGE_LAYOUT
              .enemy
              .yRatio,
        )

        expect(
          view.player.y,
        ).toBeLessThan(
          1050,
        )

        expect(
          view.enemy.y,
        ).toBeLessThan(
          view.player.y,
        )

        expect(
          view.ground.provenance,
        ).toBe(
          'RECONSTRUCTED_PRESENTATION_ONLY',
        )
      },
    )

    it(
      'rejects invalid stage dimensions',
      () => {
        expect(
          () =>
            createLogresBattleStagePresentation(
              0,
              1280,
              null,
              true,
            ),
        ).toThrow(
          'positive finite',
        )
      },
    )
  },
)
