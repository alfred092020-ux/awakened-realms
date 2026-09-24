import type Phaser from 'phaser'

import {
  LOGRES_FIELD_ACTOR_ASSETS,
  preloadLogresFieldActorAssets,
} from '../field/LogresFieldActorRuntimeAssets'

import {
  LOGRES_PLAYER_ACTOR_ASSETS,
  preloadLogresPlayerActorAssets,
} from '../field/LogresPlayerActorRuntimeAssets'

export const LOGRES_BATTLE_STAGE_ASSETS =
  Object.freeze({
    playerMale:
      LOGRES_PLAYER_ACTOR_ASSETS
        .male,

    playerFemale:
      LOGRES_PLAYER_ACTOR_ASSETS
        .female,

    enemyIdleFrames:
      Object.freeze([
        LOGRES_FIELD_ACTOR_ASSETS
          .tutorialGreenJellIdle0,
        LOGRES_FIELD_ACTOR_ASSETS
          .tutorialGreenJellIdle1,
        LOGRES_FIELD_ACTOR_ASSETS
          .tutorialGreenJellIdle2,
        LOGRES_FIELD_ACTOR_ASSETS
          .tutorialGreenJellIdle3,
      ]),
  } as const)

export const LOGRES_BATTLE_GREEN_JELL_IDLE_ANIMATION_KEY =
  'logres-battle-green-jell-idle' as const

export function preloadLogresBattleStageAssets(
  scene:
    Phaser.Scene,
) {
  preloadLogresPlayerActorAssets(
    scene,
  )

  preloadLogresFieldActorAssets(
    scene,
  )
}

export function hasRecoveredLogresBattleStageAssets(
  scene:
    Phaser.Scene,
) {
  return (
    scene.textures.exists(
      LOGRES_BATTLE_STAGE_ASSETS
        .playerMale
        .key,
    ) &&
    scene.textures.exists(
      LOGRES_BATTLE_STAGE_ASSETS
        .playerFemale
        .key,
    ) &&
    LOGRES_BATTLE_STAGE_ASSETS
      .enemyIdleFrames
      .every(
        (
          asset,
        ) =>
          scene.textures.exists(
            asset.key,
          ),
      )
  )
}
