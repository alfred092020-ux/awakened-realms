import Phaser from 'phaser'

import type {
  WeaponBattleState,
} from '../battle/WeaponBattleState'

import {
  LOGRES_CLIENT_FACTS,
} from '../generated/ExtractedClientFacts'

import {
  LOGRES_UI_ASSETS,
} from './LogresRuntimeAssets'

export interface LogresCommandSkill {
  label: string
  detail: string
  onPressed: () => void
}

export interface LogresBattleHudCallbacks {
  onWeaponChanged: (
    index: number,
  ) => void

  onMessage: (
    message: string,
  ) => void
}

export class LogresBattleHud {
  private readonly scene:
    Phaser.Scene

  private readonly battleState:
    WeaponBattleState

  private readonly callbacks:
    LogresBattleHudCallbacks

  private readonly weaponSlots:
    Phaser.GameObjects.Image[] = []

  private readonly weaponLabels:
    Phaser.GameObjects.Text[] = []

  private readonly commandButtons:
    Phaser.GameObjects.Image[] = []

  private readonly commandCooldowns:
    Phaser.GameObjects.Text[] = []

  private swipeStartX:
    number | null = null

  constructor(
    scene: Phaser.Scene,
    battleState: WeaponBattleState,
    commandSkills:
      LogresCommandSkill[],
    callbacks:
      LogresBattleHudCallbacks,
  ) {
    this.scene = scene
    this.battleState =
      battleState
    this.callbacks =
      callbacks

    this.createWeaponStrip()

    this.createCommandSkills(
      commandSkills,
    )

    this.refreshWeaponStrip()
  }

  refreshWeaponStrip() {
    const snapshot =
      this.battleState
        .getSnapshot()

    for (
      let index = 0;
      index <
        this.weaponSlots.length;
      index += 1
    ) {
      const selected =
        index ===
        snapshot.activeWeaponIndex

      const slot =
        this.weaponSlots[index]

      slot
        .setDisplaySize(
          selected
            ? 72
            : 62,
          selected
            ? 72
            : 62,
        )
        .setAlpha(
          selected
            ? 1
            : 0.68,
        )

      this.weaponLabels[index]
        .setColor(
          selected
            ? '#fff4c2'
            : '#d4d4d4',
        )
        .setScale(
          selected
            ? 1.12
            : 1,
        )
    }
  }

  setCommandCooldown(
    index: number,
    remainingMs: number,
  ) {
    const button =
      this.commandButtons[index]

    const cooldown =
      this.commandCooldowns[index]

    if (
      !button ||
      !cooldown
    ) {
      return
    }

    const cooling =
      remainingMs > 0

    button.setAlpha(
      cooling
        ? 0.38
        : 1,
    )

    cooldown
      .setVisible(cooling)
      .setText(
        cooling
          ? (
              remainingMs /
              1000
            ).toFixed(1)
          : '',
      )
  }

  private createWeaponStrip() {
    const snapshot =
      this.battleState
        .getSnapshot()

    const count =
      snapshot.weapons.length

    const spacing = 72

    const totalWidth =
      count * spacing

    const left =
      (
        this.scene.scale.width -
        totalWidth
      ) / 2

    const y =
      this.scene.scale.height -
      238

    for (
      let index = 0;
      index < count;
      index += 1
    ) {
      const x =
        left +
        spacing * index +
        spacing / 2

      const frameKey =
        LOGRES_UI_ASSETS
          .weaponFrames[
            index %
            LOGRES_UI_ASSETS
              .weaponFrames.length
          ]

      const frame =
        this.scene.add
          .image(
            x,
            y,
            frameKey,
          )
          .setDisplaySize(
            62,
            62,
          )
          .setScrollFactor(0)
          .setDepth(230)

      this.weaponSlots.push(
        frame,
      )

      const label =
        this.scene.add
          .text(
            x,
            y,
            `${index + 1}`,
            {
              fontFamily:
                'Arial, sans-serif',

              fontSize:
                '18px',

              fontStyle:
                'bold',

              color:
                '#d4d4d4',

              stroke:
                '#16110b',

              strokeThickness:
                3,
            },
          )
          .setOrigin(0.5)
          .setScrollFactor(0)
          .setDepth(232)

      this.weaponLabels.push(
        label,
      )
    }

    this.scene.add
      .text(
        this.scene.scale.width / 2,
        y - 52,
        'WEAPONS',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '12px',

          fontStyle:
            'bold',

          color:
            '#f0dda2',

          stroke:
            '#11141c',

          strokeThickness:
            3,
        },
      )
      .setOrigin(0.5)
      .setScrollFactor(0)
      .setDepth(232)

    const gestureArea =
      this.scene.add
        .zone(
          this.scene.scale.width / 2,
          y,
          totalWidth,
          86,
        )
        .setScrollFactor(0)
        .setDepth(235)
        .setInteractive()

    gestureArea.on(
      'pointerdown',
      (
        pointer:
          Phaser.Input.Pointer,
      ) => {
        this.swipeStartX =
          pointer.x
      },
    )

    gestureArea.on(
      'pointerup',
      (
        pointer:
          Phaser.Input.Pointer,
      ) => {
        if (
          this.swipeStartX ===
          null
        ) {
          return
        }

        const delta =
          pointer.x -
          this.swipeStartX

        this.swipeStartX =
          null

        if (
          Math.abs(delta) >=
          35
        ) {
          this.switchRelative(
            delta < 0
              ? 1
              : -1,
          )

          return
        }

        const relativeX =
          pointer.x - left

        const index =
          Math.floor(
            relativeX /
            spacing,
          )

        this.switchTo(index)
      },
    )

    gestureArea.on(
      'pointerout',
      () => {
        this.swipeStartX =
          null
      },
    )
  }

  private createCommandSkills(
    suppliedSkills:
      LogresCommandSkill[],
  ) {
    const slotCount =
      LOGRES_CLIENT_FACTS
        .equipment
        .normalSkillSlots

    const skills =
      suppliedSkills.slice(
        0,
        slotCount,
      )

    const x =
      this.scene.scale.width -
      90

    const startY =
      this.scene.scale.height -
      520

    const spacing = 105

    this.scene.add
      .text(
        x,
        startY - 65,
        'COMMAND',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '12px',

          fontStyle:
            'bold',

          color:
            '#f1dda5',

          stroke:
            '#11141c',

          strokeThickness:
            3,
        },
      )
      .setOrigin(0.5)
      .setScrollFactor(0)
      .setDepth(232)

    for (
      let index = 0;
      index < slotCount;
      index += 1
    ) {
      const skill =
        skills[index]

      const y =
        startY +
        index * spacing

      const button =
        this.scene.add
          .image(
            x,
            y,
            LOGRES_UI_ASSETS
              .skillBase,
          )
          .setDisplaySize(
            82,
            82,
          )
          .setScrollFactor(0)
          .setDepth(230)
          .setInteractive()

      this.commandButtons.push(
        button,
      )

      this.scene.add
        .image(
          x,
          y + 34,
          LOGRES_UI_ASSETS
            .equipmentSkillBase,
        )
        .setDisplaySize(
          72,
          32,
        )
        .setScrollFactor(0)
        .setDepth(231)
        .setAlpha(0.9)

      this.scene.add
        .text(
          x,
          y - 9,
          skill?.label ??
            `SLOT ${index + 1}`,
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '13px',

            fontStyle:
              'bold',

            color:
              '#31220d',

            stroke:
              '#fff5d8',

            strokeThickness:
              2,

            align:
              'center',
          },
        )
        .setOrigin(0.5)
        .setScrollFactor(0)
        .setDepth(233)

      this.scene.add
        .text(
          x,
          y + 25,
          skill?.detail ??
            'UNMAPPED',
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '9px',

            fontStyle:
              'bold',

            color:
              '#f5e4aa',

            stroke:
              '#21160b',

            strokeThickness:
              2,

            align:
              'center',
          },
        )
        .setOrigin(0.5)
        .setScrollFactor(0)
        .setDepth(233)

      const cooldown =
        this.scene.add
          .text(
            x,
            y,
            '',
            {
              fontFamily:
                'Arial, sans-serif',

              fontSize:
                '22px',

              fontStyle:
                'bold',

              color:
                '#ffffff',

              stroke:
                '#111111',

              strokeThickness:
                6,
            },
          )
          .setOrigin(0.5)
          .setScrollFactor(0)
          .setDepth(235)
          .setVisible(false)

      this.commandCooldowns.push(
        cooldown,
      )

      button.on(
        'pointerdown',
        () => {
          if (skill) {
            skill.onPressed()
            return
          }

          this.callbacks
            .onMessage(
              `Command slot ${index + 1} is not mapped yet`,
            )
        },
      )
    }
  }

  private switchRelative(
    direction: number,
  ) {
    const snapshot =
      this.battleState
        .getSnapshot()

    const count =
      snapshot.weapons.length

    if (count <= 1) {
      return
    }

    const next =
      (
        snapshot.activeWeaponIndex +
        direction +
        count
      ) %
      count

    this.switchTo(next)
  }

  private switchTo(
    index: number,
  ) {
    const changed =
      this.battleState
        .switchWeapon(index)

    if (!changed) {
      return
    }

    this.refreshWeaponStrip()

    this.callbacks
      .onWeaponChanged(index)
  }
}
