import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_TITLE_EFFECT_DESIGN_HEIGHT,
  LOGRES_TITLE_EFFECT_DESIGN_WIDTH,
  LOGRES_TITLE_EFFECT_SLOT_EVIDENCE,
  LOGRES_TITLE_IDLE_LOGO_LAYOUT,
} from '../src/game/logres/ui/LogresTitleEffectEvidence'

describe(
  'Logres title effect evidence',
  () => {
    it(
      'locks the native title effect design space to 720x1280',
      () => {
        expect(
          LOGRES_TITLE_EFFECT_DESIGN_WIDTH,
        ).toBe(
          720,
        )

        expect(
          LOGRES_TITLE_EFFECT_DESIGN_HEIGHT,
        ).toBe(
          1280,
        )
      },
    )

    it(
      'records the decoded current-JP idle logo center and Global application ceiling',
      () => {
        expect(
          LOGRES_TITLE_IDLE_LOGO_LAYOUT,
        ).toMatchObject({
          x:
            360,

          y:
            367,

          width:
            710,

          height:
            334,

          symbolOffsetX:
            -355,

          symbolOffsetY:
            -167,

          nativeEvidence:
            'CONFIRMED_CURRENT_JP_NATIVE',

          globalApplication:
            'SUPPORTED_INFERENCE_CURRENT_JP_LAYOUT',
        })
      },
    )

    it(
      'keeps the decoded title effect stage mapping explicit',
      () => {
        expect(
          LOGRES_TITLE_EFFECT_SLOT_EVIDENCE,
        ).toEqual({
          logoEntrance:
            'logo_a.lfla',

          logoIdle:
            'logo_b.lfla',

          logoExit:
            'logo_c.lfla',

          startFadeIn:
            'start_a.lfla',

          startFadeOut:
            'start_b.lfla',

          evidence:
            'CONFIRMED_CURRENT_JP_NATIVE',
        })
      },
    )
  },
)
