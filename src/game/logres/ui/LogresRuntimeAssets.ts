import type Phaser from 'phaser'

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

  titleStart: {
    key:
      'logres-global-title-start',

    url:
      '/__logres_ref/global/gui/title/title_ok.png',
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

  worldSelect02: {
    key:
      'logres-global-world-select-02',

    url:
      '/__logres_ref/global/gui/title/world_select02.png',
  },

  worldSelect03: {
    key:
      'logres-global-world-select-03',

    url:
      '/__logres_ref/global/gui/title/world_select03.png',
  },

  worldSelect04: {
    key:
      'logres-global-world-select-04',

    url:
      '/__logres_ref/global/gui/title/world_select04.png',
  },

  worldSelect05: {
    key:
      'logres-global-world-select-05',

    url:
      '/__logres_ref/global/gui/title/world_select05.png',
  },

  worldSelect06: {
    key:
      'logres-global-world-select-06',

    url:
      '/__logres_ref/global/gui/title/world_select06.png',
  },

  worldSelect07: {
    key:
      'logres-global-world-select-07',

    url:
      '/__logres_ref/global/gui/title/world_select07.png',
  },

  skillBase: {
    key:
      'logres-global-skill-base',

    url:
      '/__logres_ref/global/gui/common_base/skill_base.png',
  },

  battleWeaponCover: {
    key:
      'logres-global-battle-weapon-cover',

    url:
      '/__logres_ref/global/gui/Battle/bat_select_parts01.dds.png',
  },

  tutorialParameterBar: {
    key:
      'logres-global-tutorial-parameter-bar',

    url:
      '/__logres_ref/global/tutorial-hud/hud/field_parameter.png',
  },

  tutorialQuestStartText: {
    key:
      'logres-global-tutorial-quest-start-text',

    url:
      '/__logres_ref/global/tutorial-hud/telop/quest_start.png',
  },

  tutorialQuestStartBackground: {
    key:
      'logres-global-tutorial-quest-start-background',

    url:
      '/__logres_ref/global/tutorial-hud/telop/quest_bg00.png',
  },

  equipmentSkillBase: {
    key:
      'logres-global-equipment-skill-base',

    url:
      '/__logres_ref/global/gui/common_base/soubi01_02_skillbase.png',
  },

  characterMan: {
    key:
      'logres-global-character-man',

    url:
      '/__logres_ref/global/gui/characreate/charaselect_man.dds.png',
  },

  characterWoman: {
    key:
      'logres-global-character-woman',

    url:
      '/__logres_ref/global/gui/characreate/charaselect_woman.dds.png',
  },

  characterChangeMan: {
    key:
      'logres-global-character-change-man',

    url:
      '/__logres_ref/global/gui/characreate/charaselect_change01.dds.png',
  },

  characterChangeWoman: {
    key:
      'logres-global-character-change-woman',

    url:
      '/__logres_ref/global/gui/characreate/charaselect_change02.dds.png',
  },

  characterTitleBase: {
    key:
      'logres-global-character-title-base',

    url:
      '/__logres_ref/global/gui/characreate/slice/charaselect_titlebase.dds.png',
  },

  characterTitle: {
    key:
      'logres-global-character-title',

    url:
      '/__logres_ref/global/gui/characreate/charaselect_title01.png',
  },

  characterOk: {
    key:
      'logres-global-character-ok',

    url:
      '/__logres_ref/global/gui/characreate/charaselect_ok.png',
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
