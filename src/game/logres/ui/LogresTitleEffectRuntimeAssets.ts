import type Phaser from 'phaser'

import {
  logresRuntimeUrl,
} from './LogresRuntimeAssets'

export const LOGRES_TITLE_EFFECT_ASSETS = {
  sky: {
    key:
      'logres-global-title-effect-sky',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/title/effect/png/sky00.png',
      ),
  },

  cloud00: {
    key:
      'logres-global-title-effect-cloud-00',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/title/effect/png/cloud00.png',
      ),
  },

  cloud01: {
    key:
      'logres-global-title-effect-cloud-01',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/title/effect/png/cloud01.png',
      ),
  },

  field00: {
    key:
      'logres-global-title-effect-field-00',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/title/effect/png/field00.dds.png',
      ),
  },
} as const

export function preloadLogresTitleEffectAssets(
  scene: Phaser.Scene,
) {
  for (
    const asset of
    Object.values(
      LOGRES_TITLE_EFFECT_ASSETS,
    )
  ) {
    if (
      scene.textures.exists(
        asset.key,
      )
    ) {
      continue
    }

    scene.load.image(
      asset.key,
      asset.url,
    )
  }
}
