import type Phaser from 'phaser'

import {
  logresRuntimeUrl,
} from '../ui/LogresRuntimeAssets'

export const LOGRES_FIELD_ACTOR_ASSETS = {
  tutorialTapPointer: {
    key:
      'logres-current-jp-tutorial-tap-pointer',

    url:
      logresRuntimeUrl(
        '/__logres_ref/current-jp/tutorial-field/tutorial_pointer_tap.png',
      ),
  },

  tutorialGreenJellIdle0: {
    key:
      'logres-current-jp-green-jell-idle-0',

    url:
      logresRuntimeUrl(
        '/__logres_ref/current-jp/tutorial-field/green_jell_idle_0.png',
      ),
  },

  tutorialGreenJellIdle1: {
    key:
      'logres-current-jp-green-jell-idle-1',

    url:
      logresRuntimeUrl(
        '/__logres_ref/current-jp/tutorial-field/green_jell_idle_1.png',
      ),
  },

  tutorialGreenJellIdle2: {
    key:
      'logres-current-jp-green-jell-idle-2',

    url:
      logresRuntimeUrl(
        '/__logres_ref/current-jp/tutorial-field/green_jell_idle_2.png',
      ),
  },

  tutorialGreenJellIdle3: {
    key:
      'logres-current-jp-green-jell-idle-3',

    url:
      logresRuntimeUrl(
        '/__logres_ref/current-jp/tutorial-field/green_jell_idle_3.png',
      ),
  },
} as const

export function preloadLogresFieldActorAssets(
  scene: Phaser.Scene,
) {
  for (
    const asset of
    Object.values(
      LOGRES_FIELD_ACTOR_ASSETS,
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
