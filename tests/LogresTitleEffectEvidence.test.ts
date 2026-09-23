import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_TITLE_EFFECT_DESIGN_HEIGHT,
  LOGRES_TITLE_EFFECT_DESIGN_WIDTH,
  LOGRES_TITLE_EFFECT_SLOT_EVIDENCE,
  LOGRES_TITLE_FRAME0_BACKGROUND_EVIDENCE,
  LOGRES_TITLE_FRAME0_BACKGROUND_LAYOUT,
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
      'locks the decoded frame-0 title background transforms and evidence ceiling',
      () => {
        expect(
          LOGRES_TITLE_FRAME0_BACKGROUND_LAYOUT,
        ).toEqual([
          {
            asset:
              'sky',
            x:
              0,
            y:
              0,
            scaleX:
              2,
            scaleY:
              2,
            sourceEffect:
              'bg_a.lfla',
          },
          {
            asset:
              'cloud00',
            x:
              -271.5,
            y:
              -15.5,
            scaleX:
              2,
            scaleY:
              2,
            sourceEffect:
              'bg_a.lfla',
          },
          {
            asset:
              'cloud00',
            x:
              -419.205,
            y:
              -122.2748,
            scaleX:
              2.504974,
            scaleY:
              2.504974,
            sourceEffect:
              'bg_a.lfla',
          },
          {
            asset:
              'cloud01',
            x:
              -15.19427,
            y:
              126.35001,
            scaleX:
              1.599976,
            scaleY:
              2,
            sourceEffect:
              'bg_a.lfla',
          },
          {
            asset:
              'cloud01',
            x:
              -299.41675,
            y:
              -335.4519,
            scaleX:
              2.812012,
            scaleY:
              3.515015,
            sourceEffect:
              'bg_a.lfla',
          },
          {
            asset:
              'field00',
            x:
              -447.5,
            y:
              0,
            scaleX:
              1,
            scaleY:
              1,
            sourceEffect:
              'bg_b.lfla',
          },
        ])

        expect(
          LOGRES_TITLE_FRAME0_BACKGROUND_EVIDENCE,
        ).toEqual({
          layout:
            'CONFIRMED_CURRENT_JP_NATIVE',
          assetFamily:
            'RECOVERED_TITLE_EFFECT_PACKAGE_BYTE_IDENTICAL_TO_LIVE_JP',
          globalApplication:
            'SUPPORTED_INFERENCE_CROSS_VERSION_TITLE_LAYOUT',
          animation:
            'STATIC_FRAME0_ONLY',
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
