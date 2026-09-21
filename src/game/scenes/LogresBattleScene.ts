import Phaser from 'phaser'

import {
  LOGRES_CLIENT_FACTS,
} from '../logres/generated/ExtractedClientFacts'

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

export class LogresBattleScene
  extends Phaser.Scene {
  private gestureStartX:
    number | null = null

  constructor() {
    super('LogresBattleScene')
  }

  preload() {
    preloadLogresAssets(
      this,
    )

    this.load.json(
      'logres-equipment-settings',
      '/__logres_ref/config/japanese/equipment_ui_settings.json',
    )

    this.load.json(
      'logres-battle-settings',
      '/__logres_ref/config/japanese/battle_texts.json',
    )
  }

  create() {
    const {
      width,
      height,
    } = this.scale

    this.registry.set(
      'logres.reconstruction.battle',
      'RECONSTRUCTED_BATTLE_SHELL',
    )

    this.add
      .image(
        width / 2,
        height / 2,
        LOGRES_ASSETS
          .fieldBackdrop
          .key,
      )
      .setDisplaySize(
        1810,
        1280,
      )

    this.add
      .rectangle(
        width / 2,
        height / 2,
        width,
        height,
        0x000000,
        0.24,
      )

    const player =
      this.add
        .image(
          width * 0.27,
          height * 0.57,
          LOGRES_ASSETS
            .fieldPlayer
            .key,
        )
        .setDisplaySize(
          160,
          229,
        )

    const enemy =
      this.add
        .image(
          width * 0.73,
          height * 0.44,
          LOGRES_ASSETS
            .fieldEnemyMandora
            .key,
        )
        .setScale(1.75)

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

    const skillCount =
      equipment
        ?.skill_equip_max_normal ??
      LOGRES_CLIENT_FACTS
        .equipment
        .normalSkillSlots

    const gap =
      equipment
        ?.skill_equip_group_gap ??
      0

    const offset =
      battle
        ?.skill_view
        ?.default_offset ??
      LOGRES_CLIENT_FACTS
        .battle
        .skillViewDefaultOffset

    const iconWidth =
      40

    const scale =
      2

    const displayWidth =
      iconWidth *
      scale

    const spacing =
      displayWidth +
      gap

    const totalWidth =
      skillCount > 0
        ? (
            displayWidth +
            (
              skillCount -
              1
            ) *
              spacing
          )
        : 0

    const startX =
      width / 2 -
      totalWidth / 2 +
      displayWidth / 2 +
      offset[0]

    const y =
      height / 2 +
      offset[1]

    for (
      let index = 0;
      index < skillCount;
      index += 1
    ) {
      const slot =
        this.add
          .image(
            startX +
              index *
                spacing,
            y,
            LOGRES_ASSETS
              .skillBase
              .key,
          )
          .setScale(
            scale,
          )
          .setInteractive({
            useHandCursor:
              true,
          })

      slot.on(
        'pointerdown',
        () => {
          this.registry.set(
            'logres.battle.lastCommandSkillSlot',
            index,
          )

          this.tweens.add({
            targets:
              enemy,

            scaleX:
              2.05,

            scaleY:
              2.05,

            yoyo:
              true,

            duration:
              90,
          })

          this.cameras.main.shake(
            90,
            0.003,
          )
        },
      )
    }

    /*
     * Extracted client fact:
     * weapon switching is performed by slide.
     *
     * This shell records the gesture only.
     * It does not invent historical weapon
     * stats, inventory state, or server data.
     */
    this.input.on(
      'pointerdown',
      (
        pointer:
          Phaser.Input.Pointer,
      ) => {
        this.gestureStartX =
          pointer.x
      },
    )

    this.input.on(
      'pointerup',
      (
        pointer:
          Phaser.Input.Pointer,
      ) => {
        if (
          this.gestureStartX ===
          null
        ) {
          return
        }

        const delta =
          pointer.x -
          this.gestureStartX

        this.gestureStartX =
          null

        if (
          Math.abs(
            delta,
          ) <
          80
        ) {
          return
        }

        this.registry.set(
          'logres.battle.weaponSwitchGestureObserved',
          LOGRES_CLIENT_FACTS
            .battle
            .weaponSwitchGesture,
        )

        this.tweens.add({
          targets:
            player,

          alpha:
            0.45,

          yoyo:
            true,

          duration:
            120,
        })
      },
    )

    this.registry.set(
      'logres.battle.epRecoversByAttack',
      LOGRES_CLIENT_FACTS
        .battle
        .epRecoversByAttack,
    )

    this.add
      .image(
        74,
        height - 72,
        LOGRES_ASSETS
          .backButton
          .key,
      )
      .setScale(1.15)
      .setInteractive({
        useHandCursor:
          true,
      })
      .on(
        'pointerdown',
        () => {
          this.scene.start(
            'LogresFieldScene',
          )
        },
      )

    this.add
      .text(
        18,
        18,
        'RECONSTRUCTED BATTLE SHELL',
        {
          fontFamily:
            'sans-serif',

          fontSize:
            '16px',

          color:
            '#ffffff',

          backgroundColor:
            '#00000099',

          padding: {
            x: 8,
            y: 5,
          },
        },
      )
      .setDepth(100)
  }
}
