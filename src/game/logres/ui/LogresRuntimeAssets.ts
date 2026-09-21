import Phaser from 'phaser'

export const LOGRES_ASSETS = {
  background: {
    key: 'logres-bg-rogo',
    url:
      '/__logres_ref/japanese/gui/bg/rogo.dds.png',
  },

  titleBase: {
    key: 'logres-title-base',
    url:
      '/__logres_ref/japanese/gui/title/title_base01.dds.png',
  },

  titleNext: {
    key: 'logres-title-next',
    url:
      '/__logres_ref/japanese/gui/title/title_next.dds.png',
  },

  worldSelect: {
    key: 'logres-world-select',
    url:
      '/__logres_ref/japanese/gui/title/world_select01.dds.png',
  },

  skillBase: {
    key: 'logres-skill-base',
    url:
      '/__logres_ref/japanese/gui/common_base/skill_base.png',
  },

  equipmentSkillBase: {
    key: 'logres-equipment-skill-base',
    url:
      '/__logres_ref/japanese/gui/common_base/soubi01_02_skillbase.png',
  },
} as const

export function preloadLogresAssets(
  scene: Phaser.Scene,
) {
  for (
    const asset of
    Object.values(LOGRES_ASSETS)
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
