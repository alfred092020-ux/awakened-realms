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

export const LOGRES_TITLE_FRAME0_BACKGROUND_LAYOUT = Object.freeze([
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
] as const)

export const LOGRES_TITLE_FRAME0_BACKGROUND_EVIDENCE =
  Object.freeze({
    layout:
      'CONFIRMED_CURRENT_JP_NATIVE',

    assetFamily:
      'RECOVERED_TITLE_EFFECT_PACKAGE_BYTE_IDENTICAL_TO_LIVE_JP',

    globalApplication:
      'SUPPORTED_INFERENCE_CROSS_VERSION_TITLE_LAYOUT',

    animation:
      'STATIC_FRAME0_ONLY',
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
