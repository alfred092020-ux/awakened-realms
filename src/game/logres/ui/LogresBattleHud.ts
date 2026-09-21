import Phaser from 'phaser'

import type {
  WeaponBattleState,
} from '../battle/WeaponBattleState'

import {
  LOGRES_CLIENT_FACTS,
} from '../generated/ExtractedClientFacts'

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
    Phaser.GameObjects.Rectangle[] = []

  private readonly weaponLabels:
    Phaser.GameObjects.Text[] = []

  private readonly commandButtons:
    Phaser.GameObjects.Arc[] = []

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
      let i = 0;
      i < this.weaponSlots.length;
      i += 1
    ) {
      const selected =
        i ===
        snapshot.activeWeaponIndex

      this.weaponSlots[i]
        .setFillStyle(
          selected
            ? 0xb98b37
            : 0x171c27,
          selected
            ? 0.96
            : 0.9,
        )
        .setStrokeStyle(
          selected
            ? 4
            : 2,
          selected
            ? 0xffe099
            : 0x7b8493,
          selected
            ? 1
            : 0.8,
        )

      this.weaponLabels[i]
        .setColor(
          selected
            ? '#fff3c4'
            : '#c1c8d3',
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
        ? 0.42
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

    const spacing = 70

    const totalWidth =
      count * spacing

    const left =
      (
        this.scene.scale.width -
        totalWidth
      ) / 2

    const y =
      this.scene.scale.height -
      235

    for (
      let index = 0;
      index < count;
      index += 1
    ) {
      const x =
        left +
        spacing * index +
        spacing / 2

      const slot =
        this.scene.add
          .rectangle(
            x,
            y,
            58,
            66,
            0x171c27,
            0.9,
          )
          .setStrokeStyle(
            2,
            0x7b8493,
            0.8,
          )
          .setScrollFactor(0)
          .setDepth(230)

      this.weaponSlots.push(
        slot,
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
                '20px',

              fontStyle:
                'bold',

              color:
                '#c1c8d3',
            },
          )
          .setOrigin(0.5)
          .setScrollFactor(0)
          .setDepth(231)

      this.weaponLabels.push(
        label,
      )
    }

    this.scene.add
      .text(
        this.scene.scale.width / 2,
        y - 48,
        'WEAPONS  •  SLIDE TO SWITCH',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '12px',

          fontStyle:
            'bold',

          color:
            '#d3c08b',

          stroke:
            '#11141c',

          strokeThickness:
            3,
        },
      )
      .setOrigin(0.5)
      .setScrollFactor(0)
      .setDepth(231)

    const gestureArea =
      this.scene.add
        .zone(
          this.scene.scale.width / 2,
          y,
          totalWidth,
          82,
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

        this.switchTo(
          index,
        )
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
      88

    const startY =
      this.scene.scale.height -
      510

    const spacing =
      102

    this.scene.add
      .text(
        x,
        startY - 67,
        'COMMAND',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '12px',

          fontStyle:
            'bold',

          color:
            '#e0c98d',

          stroke:
            '#11141c',

          strokeThickness:
            3,
        },
      )
      .setOrigin(0.5)
      .setScrollFactor(0)
      .setDepth(231)

    for (
      let index = 0;
      index < slotCount;
      index += 1
    ) {
      const skill =
        skills[index]

      const y =
        startY +
        index *
          spacing

      const button =
        this.scene.add
          .circle(
            x,
            y,
            43,
            0x25364d,
            0.96,
          )
          .setStrokeStyle(
            3,
            0xc4d8ef,
            0.9,
          )
          .setScrollFactor(0)
          .setDepth(230)
          .setInteractive()

      this.commandButtons.push(
        button,
      )

      this.scene.add
        .text(
          x,
          y - 7,
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
              '#ffffff',

            align:
              'center',
          },
        )
        .setOrigin(0.5)
        .setScrollFactor(0)
        .setDepth(231)

      this.scene.add
        .text(
          x,
          y + 16,
          skill?.detail ??
            'UNMAPPED',
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '9px',

            color:
              '#cbd7e5',

            align:
              'center',
          },
        )
        .setOrigin(0.5)
        .setScrollFactor(0)
        .setDepth(231)

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
                '21px',

              fontStyle:
                'bold',

              color:
                '#ffffff',

              stroke:
                '#111722',

              strokeThickness:
                5,
            },
          )
          .setOrigin(0.5)
          .setScrollFactor(0)
          .setDepth(234)
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
