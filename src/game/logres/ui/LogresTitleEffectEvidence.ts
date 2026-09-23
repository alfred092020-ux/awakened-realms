export const LOGRES_TITLE_EFFECT_DESIGN_WIDTH =
  720 as const

export const LOGRES_TITLE_EFFECT_DESIGN_HEIGHT =
  1280 as const

/**
 * Current-JP default TitleEffectResources.json maps the title logo stages to:
 * logo_a = entrance, logo_b = idle, logo_c = exit.
 *
 * logo_b.lfla is protobuf-wire encoded. Its root logo transform is centered at
 * (360, 367) in the native 720x1280 effect canvas. The logo00 symbol uses a
 * (-355, -167) translation around a 710x334 image, proving a centered pivot.
 */
export const LOGRES_TITLE_IDLE_LOGO_LAYOUT = Object.freeze({
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
} as const)

export const LOGRES_TITLE_EFFECT_SLOT_EVIDENCE = Object.freeze({
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
} as const)
