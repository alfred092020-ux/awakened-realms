import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE,
} from '../src/game/logres/tutorial/LogresTutorialHudEvidence'

import {
  LOGRES_TUTORIAL_HUD_RUNTIME_SELECTION,
  LOGRES_TUTORIAL_PARAMETER_BAR_PLACEMENT,
  resolveLogresTutorialQuestStartPlacement,
} from '../src/game/logres/tutorial/LogresTutorialHudRuntime'

describe(
  'Logres tutorial HUD runtime binding',
  () => {
    it(
      'binds only the confirmed tutorial asset selections',
      () => {
        expect(
          LOGRES_TUTORIAL_HUD_RUNTIME_SELECTION,
        ).toEqual({
          parameterBar: {
            runtimeUrl:
              LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE
                .parameterBar
                .runtimeUrl,
            sourceSha256:
              LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE
                .parameterBar
                .sourceSha256,
          },

          questStartText: {
            runtimeUrl:
              LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE
                .questStartText
                .runtimeUrl,
            sourceSha256:
              LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE
                .questStartText
                .sourceSha256,
          },

          questStartBackground: {
            runtimeUrl:
              LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE
                .questStartBackground
                .runtimeUrl,
            sourceSha256:
              LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE
                .questStartBackground
                .sourceSha256,
          },
        })
      },
    )

    it(
      'keeps the parameter asset position honest about the older-layout inference',
      () => {
        expect(
          LOGRES_TUTORIAL_PARAMETER_BAR_PLACEMENT,
        ).toMatchObject({
          x:
            360,
          y:
            45,
          evidenceLabel:
            'SUPPORTED INFERENCE',
        })
      },
    )

    it(
      'requires explicit finite Quest Start screen coordinates',
      () => {
        expect(
          resolveLogresTutorialQuestStartPlacement({
            centerX:
              360,
            centerY:
              640,
          }),
        ).toEqual({
          centerX:
            360,
          centerY:
            640,
        })

        expect(
          () =>
            resolveLogresTutorialQuestStartPlacement(
              null,
            ),
        ).toThrow(
          'must be an object',
        )

        expect(
          () =>
            resolveLogresTutorialQuestStartPlacement({
              centerX:
                Number.NaN,
              centerY:
                640,
            }),
        ).toThrow(
          'centerX must be a finite number',
        )
      },
    )

    it(
      'does not promote unresolved footer assets into the runtime selection',
      () => {
        expect(
          Object.keys(
            LOGRES_TUTORIAL_HUD_RUNTIME_SELECTION,
          ),
        ).toEqual([
          'parameterBar',
          'questStartText',
          'questStartBackground',
        ])
      },
    )
  },
)
