import type Phaser from 'phaser'

import {
  logresRuntimeUrl,
} from '../ui/LogresRuntimeAssets'

export const LOGRES_PLAYER_ACTOR_ASSETS = {
  male: {
    key:
      'logres-current-jp-player-avatar-reference-m',

    url:
      logresRuntimeUrl(
        '/__logres_ref/current-jp/player-avatar-reference/player_avatar_reference_m.png',
      ),
  },

  female: {
    key:
      'logres-current-jp-player-avatar-reference-f',

    url:
      logresRuntimeUrl(
        '/__logres_ref/current-jp/player-avatar-reference/player_avatar_reference_f.png',
      ),
  },
} as const

export function preloadLogresPlayerActorAssets(
  scene:
    Phaser.Scene,
) {
  for (
    const asset of
    Object.values(
      LOGRES_PLAYER_ACTOR_ASSETS,
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
