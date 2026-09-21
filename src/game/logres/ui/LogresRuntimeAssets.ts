import Phaser from 'phaser'

const BASE =
  '/__logres_ref/japanese/gui/common_base/'

export const LOGRES_UI_ASSETS = {
  skillBase:
    'logres-ui-skill-base',

  equipmentSkillBase:
    'logres-ui-equipment-skill-base',

  weaponFrames: [
    'logres-ui-weapon-frame-1',
    'logres-ui-weapon-frame-2',
    'logres-ui-weapon-frame-3',
    'logres-ui-weapon-frame-4',
    'logres-ui-weapon-frame-5',
  ],
} as const

const ASSETS = [
  [
    LOGRES_UI_ASSETS.skillBase,
    'skill_base.png',
  ],
  [
    LOGRES_UI_ASSETS
      .equipmentSkillBase,
    'soubi01_02_skillbase.png',
  ],
  [
    LOGRES_UI_ASSETS
      .weaponFrames[0],
    'system_base02.png',
  ],
  [
    LOGRES_UI_ASSETS
      .weaponFrames[1],
    'system_base07.png',
  ],
  [
    LOGRES_UI_ASSETS
      .weaponFrames[2],
    'system_base10.png',
  ],
  [
    LOGRES_UI_ASSETS
      .weaponFrames[3],
    'system_base13.png',
  ],
  [
    LOGRES_UI_ASSETS
      .weaponFrames[4],
    'system_base16.png',
  ],
] as const

export function preloadLogresRuntimeAssets(
  scene: Phaser.Scene,
) {
  for (const [key, file] of ASSETS) {
    if (
      scene.textures.exists(key)
    ) {
      continue
    }

    scene.load.image(
      key,
      `${BASE}${file}`,
    )
  }
}
