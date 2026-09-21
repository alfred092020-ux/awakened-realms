import Phaser from 'phaser'

import {
  LOGRES_ASSETS,
  preloadLogresAssets,
} from '../logres/ui/LogresRuntimeAssets'

interface EquipmentUiSettings {
  skill_equip_max_normal?:
    number

  skill_equip_group_gap?:
    number
}

interface BattleTexts {
  skill_view?: {
    default_offset?:
      [number, number]
  }
}

interface FieldSettings {
  initial_view_scale?:
    number

  resource_path?: {
    default_background_image?:
      string
  }
}

export class LogresFieldScene
  extends Phaser.Scene {
  constructor() {
    super('LogresFieldScene')
  }

  preload() {
    preloadLogresAssets(this)

    this.load.json(
      'logres-equipment-settings',
      '/__logres_ref/config/japanese/equipment_ui_settings.json',
    )

    this.load.json(
      'logres-battle-settings',
      '/__logres_ref/config/japanese/battle_texts.json',
    )

    this.load.json(
      'logres-field-settings',
      '/__logres_ref/config/japanese/field_settings.json',
    )

    /*
     * Player-facing language always comes
     * from the translated Global client
     * when an equivalent file exists.
     */
    this.load.json(
      'logres-equip-tutorial-en',
      '/__logres_ref/config/global/equip_tutorial_texts.json',
    )

    this.load.json(
      'logres-equipment-text-en',
      '/__logres_ref/config/global/equipment_texts.json',
    )

    this.load.json(
      'logres-quest-text-en',
      '/__logres_ref/config/global/quest_texts.json',
    )

    this.load.json(
      'logres-chat-text-en',
      '/__logres_ref/config/global/chat_text.json',
    )

    this.load.json(
      'logres-inventory-text-en',
      '/__logres_ref/config/global/inventory_text.json',
    )
  }

  create() {
    const {
      width,
      height,
    } = this.scale

    /*
     * The default field background specified by
     * field_settings.json was not present inside
     * the captured package.
     *
     * Strict mode therefore does NOT fabricate
     * a replacement field asset.
     *
     * This backdrop is an actual extracted
     * Logres client texture used only so the
     * reconstruction screen is visible.
     */
    this.add
      .tileSprite(
        width / 2,
        height / 2,
        width,
        height,
        LOGRES_ASSETS
          .titleBackground
          .key,
      )

    const equipment =
      this.cache.json.get(
        'logres-equipment-settings',
      ) as
        EquipmentUiSettings |
        undefined

    const battle =
      this.cache.json.get(
        'logres-battle-settings',
      ) as
        BattleTexts |
        undefined

    const field =
      this.cache.json.get(
        'logres-field-settings',
      ) as
        FieldSettings |
        undefined

    /*
     * All values below come directly from
     * extracted Logres JSON.
     */
    const skillCount =
      equipment
        ?.skill_equip_max_normal ??
      0

    const gap =
      equipment
        ?.skill_equip_group_gap ??
      0

    const offset =
      battle
        ?.skill_view
        ?.default_offset ??
      [0, 0]

    const source =
      this.textures
        .get(
          LOGRES_ASSETS
            .skillBase
            .key,
        )
        .getSourceImage() as
        HTMLImageElement

    const iconWidth =
      source.width

    const totalWidth =
      skillCount > 0
        ? (
            skillCount *
              iconWidth +
            (
              skillCount -
              1
            ) *
              gap
          )
        : 0

    const startX =
      width / 2 -
      totalWidth / 2 +
      iconWidth / 2 +
      offset[0]

    const y =
      height / 2 +
      offset[1]

    for (
      let index = 0;
      index < skillCount;
      index += 1
    ) {
      this.add
        .image(
          startX +
            index *
              (
                iconWidth +
                gap
              ),
          y,
          LOGRES_ASSETS
            .skillBase
            .key,
        )
    }

    /*
     * Read and retain actual field values.
     * We do not invent missing world data.
     */
    this.registry.set(
      'logres.field.initialViewScale',
      field
        ?.initial_view_scale,
    )

    this.registry.set(
      'logres.field.defaultBackgroundImage',
      field
        ?.resource_path
        ?.default_background_image,
    )
  }
}
