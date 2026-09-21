import Phaser from 'phaser'

export const LOGRES_ASSETS = {
  titleBackground: {
    key:
      'logres-global-title-background',

    url:
      '/__logres_ref/global/gui/title/title_back.dds.png',
  },

  titleLogo: {
    key:
      'logres-global-title-logo',

    url:
      '/__logres_ref/global/gui/title/effect/png/logo00.png',
  },

  titleBase: {
    key:
      'logres-global-title-base',

    url:
      '/__logres_ref/global/gui/title/title_base01.dds.png',
  },

  titleNext: {
    key:
      'logres-global-title-next',

    url:
      '/__logres_ref/global/gui/title/title_next.png',
  },

  worldSelect: {
    key:
      'logres-global-world-select',

    url:
      '/__logres_ref/global/gui/title/world_select01.png',
  },

  skillBase: {
    key:
      'logres-global-skill-base',

    url:
      '/__logres_ref/global/gui/common_base/skill_base.png',
  },

  equipmentSkillBase: {
    key:
      'logres-global-equipment-skill-base',

    url:
      '/__logres_ref/global/gui/common_base/soubi01_02_skillbase.png',
  },
} as const

export function preloadLogresAssets(
  scene: Phaser.Scene,
) {
  for (
    const asset of
    Object.values(
      LOGRES_ASSETS,
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
