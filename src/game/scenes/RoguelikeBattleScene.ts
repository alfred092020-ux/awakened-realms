import Phaser from 'phaser'

import {
  MetaSession,
} from '../meta/MetaSession'

import {
  RunEngine,
} from '../roguelike/RunEngine'

import type {
  RunSnapshot,
  UpgradeDefinition,
} from '../roguelike/RunTypes'

export class RoguelikeBattleScene
  extends Phaser.Scene {
  private engine!:
    RunEngine

  private session!:
    MetaSession

  private snapshot!:
    RunSnapshot

  private waveText!:
    Phaser.GameObjects.Text

  private levelText!:
    Phaser.GameObjects.Text

  private goldText!:
    Phaser.GameObjects.Text

  private playerHpText!:
    Phaser.GameObjects.Text

  private enemyHpText!:
    Phaser.GameObjects.Text

  private enemyLabel!:
    Phaser.GameObjects.Text

  private playerHpBar!:
    Phaser.GameObjects.Rectangle

  private enemyHpBar!:
    Phaser.GameObjects.Rectangle

  private xpBar!:
    Phaser.GameObjects.Rectangle

  private playerAvatar!:
    Phaser.GameObjects.Arc

  private enemyAvatar!:
    Phaser.GameObjects.Arc

  private enemyAura!:
    Phaser.GameObjects.Arc

  private upgradeObjects:
    Phaser.GameObjects.GameObject[] =
      []

  private upgradeVisible =
    false

  private resultVisible =
    false

  constructor() {
    super(
      'RoguelikeBattleScene',
    )
  }

  create() {
    const {
      width,
      height,
    } = this.scale

    this.cameras.main
      .setBackgroundColor(
        '#080c16',
      )

    this.session =
      new MetaSession()

    this.engine =
      new RunEngine(
        Date.now() >>> 0,
        this.session
          .getRunModifiers(),
      )

    this.snapshot =
      this.engine
        .getSnapshot()

    this.createBackground(
      width,
      height,
    )

    this.createTopHud(
      width,
    )

    this.createBattlefield(
      width,
      height,
    )

    this.renderSnapshot(
      this.snapshot,
    )
  }

  update(
    _time: number,
    delta: number,
  ) {
    if (
      this.resultVisible
    ) {
      return
    }

    const before =
      this.snapshot

    this.engine.advance(
      Math.min(
        delta,
        250,
      ),
    )

    const after =
      this.engine
        .getSnapshot()

    this.detectCombatEvents(
      before,
      after,
    )

    this.renderSnapshot(
      after,
    )

    this.snapshot =
      after

    if (
      after.status ===
        'upgrade' &&
      !this.upgradeVisible
    ) {
      this.showUpgradeChoices(
        after.pendingUpgrades,
      )
    }

    if (
      (
        after.status ===
          'dead' ||
        after.status ===
          'won'
      ) &&
      !this.resultVisible
    ) {
      this.finishRun()
    }
  }

  private createBackground(
    width: number,
    height: number,
  ) {
    this.add
      .rectangle(
        width / 2,
        height / 2,
        width,
        height,
        0x080c16,
      )

    this.add
      .circle(
        width * 0.18,
        height * 0.35,
        240,
        0x2a4c73,
        0.14,
      )

    this.add
      .circle(
        width * 0.88,
        height * 0.44,
        260,
        0x5e376f,
        0.12,
      )

    this.add
      .rectangle(
        width / 2,
        690,
        width - 34,
        690,
        0x10182a,
        0.74,
      )
      .setStrokeStyle(
        2,
        0x263753,
        0.8,
      )

    for (
      let index = 0;
      index < 32;
      index += 1
    ) {
      this.add
        .circle(
          Phaser.Math.Between(
            0,
            width,
          ),
          Phaser.Math.Between(
            200,
            height - 180,
          ),
          Phaser.Math.FloatBetween(
            0.8,
            2.4,
          ),
          0x9bc8ff,
          Phaser.Math.FloatBetween(
            0.08,
            0.28,
          ),
        )
    }
  }

  private createTopHud(
    width: number,
  ) {
    this.add
      .rectangle(
        width / 2,
        75,
        width,
        150,
        0x0d1423,
        0.98,
      )

    this.waveText =
      this.add
        .text(
          32,
          27,
          'WAVE 1',
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize:
              '31px',
            fontStyle:
              'bold',
            color:
              '#f4e4a9',
          },
        )

    this.levelText =
      this.add
        .text(
          32,
          73,
          'LV. 1',
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize:
              '18px',
            fontStyle:
              'bold',
            color:
              '#aeb9d4',
          },
        )

    this.goldText =
      this.add
        .text(
          width - 32,
          48,
          'GOLD 0',
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize:
              '21px',
            fontStyle:
              'bold',
            color:
              '#ffd77b',
          },
        )
        .setOrigin(
          1,
          0.5,
        )

    this.add
      .text(
        width - 32,
        88,
        'AUTO',
        {
          fontFamily:
            'Arial, sans-serif',
          fontSize:
            '14px',
          fontStyle:
            'bold',
          color:
            '#74e6ad',
          letterSpacing:
            3,
        },
      )
      .setOrigin(
        1,
        0.5,
      )

    this.add
      .rectangle(
        32,
        117,
        width - 64,
        10,
        0x242e45,
      )
      .setOrigin(
        0,
        0.5,
      )

    this.xpBar =
      this.add
        .rectangle(
          32,
          117,
          width - 64,
          10,
          0x77a8ff,
        )
        .setOrigin(
          0,
          0.5,
        )
  }

  private createBattlefield(
    width: number,
    height: number,
  ) {
    const enemyX =
      width / 2

    const enemyY =
      420

    const playerX =
      width / 2

    const playerY =
      830

    this.enemyAura =
      this.add
        .circle(
          enemyX,
          enemyY,
          118,
          0x674d85,
          0.16,
        )
        .setStrokeStyle(
          3,
          0x8f74b0,
          0.35,
        )

    this.enemyAvatar =
      this.add
        .circle(
          enemyX,
          enemyY,
          82,
          0xa14c70,
          1,
        )
        .setStrokeStyle(
          6,
          0xe99abc,
          0.8,
        )

    this.add
      .circle(
        enemyX - 27,
        enemyY - 12,
        8,
        0xffffff,
        0.9,
      )

    this.add
      .circle(
        enemyX + 27,
        enemyY - 12,
        8,
        0xffffff,
        0.9,
      )

    this.enemyLabel =
      this.add
        .text(
          enemyX,
          enemyY - 142,
          'ENEMY',
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize:
              '18px',
            fontStyle:
              'bold',
            color:
              '#e8c5d4',
            letterSpacing:
              3,
          },
        )
        .setOrigin(
          0.5,
        )

    this.add
      .rectangle(
        70,
        enemyY + 124,
        width - 140,
        18,
        0x321d2c,
      )
      .setOrigin(
        0,
        0.5,
      )

    this.enemyHpBar =
      this.add
        .rectangle(
          70,
          enemyY + 124,
          width - 140,
          18,
          0xd35673,
        )
        .setOrigin(
          0,
          0.5,
        )

    this.enemyHpText =
      this.add
        .text(
          width / 2,
          enemyY + 152,
          '',
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize:
              '15px',
            color:
              '#c9b6bf',
          },
        )
        .setOrigin(
          0.5,
        )

    this.add
      .text(
        width / 2,
        632,
        'VS',
        {
          fontFamily:
            'Arial, sans-serif',
          fontSize:
            '22px',
          fontStyle:
            'bold',
          color:
            '#56647d',
        },
      )
      .setOrigin(
        0.5,
      )

    const heroAura =
      this.add
        .circle(
          playerX,
          playerY,
          112,
          0x3376a8,
          0.14,
        )
        .setStrokeStyle(
          3,
          0x64b9eb,
          0.28,
        )

    this.tweens.add({
      targets:
        heroAura,
      scale:
        1.08,
      alpha:
        0.22,
      duration:
        1100,
      yoyo:
        true,
      repeat:
        -1,
    })

    this.playerAvatar =
      this.add
        .circle(
          playerX,
          playerY,
          78,
          0x3a7fc2,
          1,
        )
        .setStrokeStyle(
          6,
          0x9bdcff,
          0.9,
        )

    this.add
      .text(
        playerX,
        playerY,
        '✦',
        {
          fontFamily:
            'Arial, sans-serif',
          fontSize:
            '62px',
          fontStyle:
            'bold',
          color:
            '#eaf8ff',
        },
      )
      .setOrigin(
        0.5,
      )

    this.add
      .text(
        playerX,
        playerY + 112,
        'AWAKENED HERO',
        {
          fontFamily:
            'Arial, sans-serif',
          fontSize:
            '17px',
          fontStyle:
            'bold',
          color:
            '#a7d8f6',
          letterSpacing:
            3,
        },
      )
      .setOrigin(
        0.5,
      )

    this.add
      .rectangle(
        70,
        playerY + 160,
        width - 140,
        20,
        0x1c2d37,
      )
      .setOrigin(
        0,
        0.5,
      )

    this.playerHpBar =
      this.add
        .rectangle(
          70,
          playerY + 160,
          width - 140,
          20,
          0x4bc98b,
        )
        .setOrigin(
          0,
          0.5,
        )

    this.playerHpText =
      this.add
        .text(
          width / 2,
          playerY + 191,
          '',
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize:
              '16px',
            color:
              '#b6d7ca',
          },
        )
        .setOrigin(
          0.5,
        )

    this.add
      .text(
        width / 2,
        height - 92,
        'Battles continue automatically',
        {
          fontFamily:
            'Arial, sans-serif',
          fontSize:
            '14px',
          color:
            '#68758e',
        },
      )
      .setOrigin(
        0.5,
      )
  }

  private detectCombatEvents(
    before: RunSnapshot,
    after: RunSnapshot,
  ) {
    if (
      before.enemy &&
      after.enemy &&
      before.enemy.wave ===
        after.enemy.wave &&
      after.enemy.hp <
        before.enemy.hp
    ) {
      const damage =
        before.enemy.hp -
        after.enemy.hp

      this.animatePlayerAttack(
        damage,
      )
    }

    if (
      after.player.hp <
      before.player.hp
    ) {
      const damage =
        before.player.hp -
        after.player.hp

      this.animateEnemyAttack(
        damage,
      )
    }

    if (
      after.wave !==
      before.wave
    ) {
      this.animateNewWave(
        after,
      )
    }
  }

  private animatePlayerAttack(
    damage: number,
  ) {
    const startX =
      this.playerAvatar.x

    const targetX =
      this.enemyAvatar.x

    const targetY =
      this.enemyAvatar.y

    this.tweens.add({
      targets:
        this.playerAvatar,
      y:
        this.playerAvatar.y -
        25,
      scaleX:
        1.08,
      scaleY:
        0.92,
      duration:
        80,
      yoyo:
        true,
    })

    const projectile =
      this.add
        .circle(
          startX,
          this.playerAvatar.y -
            74,
          14,
          0x8edcff,
          1,
        )
        .setStrokeStyle(
          3,
          0xe9fbff,
        )

    this.tweens.add({
      targets:
        projectile,
      x:
        targetX,
      y:
        targetY,
      scale:
        0.35,
      duration:
        125,
      onComplete:
        () => {
          projectile.destroy()

          this.enemyAvatar
            .setScale(
              1.08,
            )

          this.tweens.add({
            targets:
              this.enemyAvatar,
            scale:
              1,
            duration:
              80,
          })

          this.showDamage(
            targetX,
            targetY - 100,
            damage,
            '#eaf8ff',
          )
        },
    })
  }

  private animateEnemyAttack(
    damage: number,
  ) {
    this.tweens.add({
      targets:
        this.enemyAvatar,
      y:
        this.enemyAvatar.y +
        25,
      duration:
        80,
      yoyo:
        true,
    })

    this.playerAvatar
      .setScale(
        0.92,
      )

    this.tweens.add({
      targets:
        this.playerAvatar,
      scale:
        1,
      duration:
        90,
    })

    this.showDamage(
      this.playerAvatar.x,
      this.playerAvatar.y -
        105,
      damage,
      '#ff8f9d',
    )
  }

  private showDamage(
    x: number,
    y: number,
    damage: number,
    color: string,
  ) {
    const text =
      this.add
        .text(
          x,
          y,
          `-${damage}`,
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize:
              '27px',
            fontStyle:
              'bold',
            color,
            stroke:
              '#111722',
            strokeThickness:
              5,
          },
        )
        .setOrigin(
          0.5,
        )
        .setDepth(
          20,
        )

    this.tweens.add({
      targets:
        text,
      y:
        y - 55,
      alpha:
        0,
      duration:
        550,
      ease:
        'Cubic.easeOut',
      onComplete:
        () => {
          text.destroy()
        },
    })
  }

  private animateNewWave(
    snapshot: RunSnapshot,
  ) {
    this.enemyAvatar
      .setScale(
        0.55,
      )

    this.enemyAura
      .setScale(
        0.55,
      )

    this.tweens.add({
      targets: [
        this.enemyAvatar,
        this.enemyAura,
      ],
      scale:
        1,
      duration:
        260,
      ease:
        'Back.easeOut',
    })

    const enemy =
      snapshot.enemy

    if (
      enemy?.boss
    ) {
      this.cameras.main
        .flash(
          220,
          120,
          45,
          65,
          false,
        )
    }
  }

  private renderSnapshot(
    snapshot: RunSnapshot,
  ) {
    this.waveText
      .setText(
        `WAVE ${snapshot.wave}`,
      )

    this.levelText
      .setText(
        `LV. ${snapshot.level}    XP ${snapshot.xp}/${snapshot.xpToNext}`,
      )

    this.goldText
      .setText(
        `GOLD ${snapshot.gold}`,
      )

    const playerRatio =
      Phaser.Math.Clamp(
        snapshot.player.hp /
          snapshot.player.maxHp,
        0,
        1,
      )

    this.playerHpBar
      .setScale(
        playerRatio,
        1,
      )

    this.playerHpText
      .setText(
        `${snapshot.player.hp} / ${snapshot.player.maxHp} HP`,
      )

    const xpRatio =
      Phaser.Math.Clamp(
        snapshot.xp /
          snapshot.xpToNext,
        0,
        1,
      )

    this.xpBar
      .setScale(
        xpRatio,
        1,
      )

    const enemy =
      snapshot.enemy

    if (!enemy) {
      this.enemyHpBar
        .setScale(
          0,
          1,
        )

      this.enemyHpText
        .setText(
          '',
        )

      return
    }

    const enemyRatio =
      Phaser.Math.Clamp(
        enemy.hp /
          enemy.maxHp,
        0,
        1,
      )

    this.enemyHpBar
      .setScale(
        enemyRatio,
        1,
      )

    this.enemyHpText
      .setText(
        `${enemy.hp} / ${enemy.maxHp} HP`,
      )

    if (
      enemy.boss
    ) {
      this.enemyLabel
        .setText(
          `BOSS • WAVE ${enemy.wave}`,
        )
        .setColor(
          '#ffd38f',
        )

      this.enemyAvatar
        .setFillStyle(
          0xb46b36,
        )
        .setStrokeStyle(
          7,
          0xffd17e,
          0.95,
        )

      this.enemyAura
        .setFillStyle(
          0x8f4b29,
          0.25,
        )
        .setStrokeStyle(
          5,
          0xffb45e,
          0.55,
        )
    } else {
      this.enemyLabel
        .setText(
          `ENEMY • WAVE ${enemy.wave}`,
        )
        .setColor(
          '#e8c5d4',
        )

      this.enemyAvatar
        .setFillStyle(
          0xa14c70,
        )
        .setStrokeStyle(
          6,
          0xe99abc,
          0.8,
        )

      this.enemyAura
        .setFillStyle(
          0x674d85,
          0.16,
        )
        .setStrokeStyle(
          3,
          0x8f74b0,
          0.35,
        )
    }
  }

  private showUpgradeChoices(
    upgrades:
      readonly UpgradeDefinition[],
  ) {
    this.upgradeVisible =
      true

    const {
      width,
      height,
    } = this.scale

    const backdrop =
      this.add
        .rectangle(
          width / 2,
          height / 2,
          width,
          height,
          0x050810,
          0.91,
        )
        .setDepth(
          90,
        )

    this.upgradeObjects.push(
      backdrop,
    )

    const title =
      this.add
        .text(
          width / 2,
          255,
          'LEVEL UP',
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize:
              '43px',
            fontStyle:
              'bold',
            color:
              '#f6df91',
            stroke:
              '#392d16',
            strokeThickness:
              5,
          },
        )
        .setOrigin(
          0.5,
        )
        .setDepth(
          100,
        )

    const subtitle =
      this.add
        .text(
          width / 2,
          315,
          'Choose one awakening',
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize:
              '18px',
            color:
              '#aab5cb',
          },
        )
        .setOrigin(
          0.5,
        )
        .setDepth(
          100,
        )

    this.upgradeObjects.push(
      title,
      subtitle,
    )

    upgrades.forEach(
      (
        upgrade,
        index,
      ) => {
        const y =
          455 +
          index * 220

        const card =
          this.add
            .rectangle(
              width / 2,
              y,
              width - 88,
              174,
              0x161e31,
              1,
            )
            .setStrokeStyle(
              3,
              0x5573a7,
              0.9,
            )
            .setInteractive({
              useHandCursor:
                true,
            })
            .setDepth(
              100,
            )

        const number =
          this.add
            .circle(
              89,
              y,
              31,
              0x39578d,
              1,
            )
            .setStrokeStyle(
              2,
              0x81a6e9,
            )
            .setDepth(
              101,
            )

        const numberText =
          this.add
            .text(
              89,
              y,
              `${index + 1}`,
              {
                fontFamily:
                  'Arial, sans-serif',
                fontSize:
                  '21px',
                fontStyle:
                  'bold',
                color:
                  '#f1f6ff',
              },
            )
            .setOrigin(
              0.5,
            )
            .setDepth(
              102,
            )

        const name =
          this.add
            .text(
              142,
              y - 45,
              upgrade.name,
              {
                fontFamily:
                  'Arial, sans-serif',
                fontSize:
                  '25px',
                fontStyle:
                  'bold',
                color:
                  '#eef4ff',
              },
            )
            .setDepth(
              101,
            )

        const description =
          this.add
            .text(
              142,
              y + 2,
              upgrade.description,
              {
                fontFamily:
                  'Arial, sans-serif',
                fontSize:
                  '17px',
                color:
                  '#aeb9ce',
                wordWrap: {
                  width:
                    width - 245,
                },
              },
            )
            .setDepth(
              101,
            )

        const choose =
          this.add
            .text(
              width - 71,
              y + 54,
              'CHOOSE',
              {
                fontFamily:
                  'Arial, sans-serif',
                fontSize:
                  '13px',
                fontStyle:
                  'bold',
                color:
                  '#77a9ef',
                letterSpacing:
                  2,
              },
            )
            .setOrigin(
              1,
              0.5,
            )
            .setDepth(
              101,
            )

        card.on(
          'pointerdown',
          () => {
            card
              .setFillStyle(
                0x263b61,
              )

            this.engine
              .chooseUpgrade(
                upgrade.id,
              )

            this.clearUpgradeChoices()

            this.snapshot =
              this.engine
                .getSnapshot()

            this.renderSnapshot(
              this.snapshot,
            )
          },
        )

        this.upgradeObjects.push(
          card,
          number,
          numberText,
          name,
          description,
          choose,
        )
      },
    )
  }

  private clearUpgradeChoices() {
    for (
      const object of
      this.upgradeObjects
    ) {
      object.destroy()
    }

    this.upgradeObjects =
      []

    this.upgradeVisible =
      false
  }

  private finishRun() {
    this.resultVisible =
      true

    this.clearUpgradeChoices()

    const result =
      this.engine
        .getResult()

    if (!result) {
      return
    }

    this.session.claimRun(
      result,
    )

    const state =
      this.session.getState()

    const {
      width,
      height,
    } = this.scale

    this.add
      .rectangle(
        width / 2,
        height / 2,
        width,
        height,
        0x050810,
        0.94,
      )
      .setDepth(
        200,
      )

    const victory =
      result.won

    this.add
      .text(
        width / 2,
        255,
        victory
          ? 'REALM CLEARED'
          : 'RUN COMPLETE',
        {
          fontFamily:
            'Arial, sans-serif',
          fontSize:
            victory
              ? '43px'
              : '41px',
          fontStyle:
            'bold',
          color:
            victory
              ? '#ffe49a'
              : '#d9e4ff',
          align:
            'center',
          stroke:
            '#21192b',
          strokeThickness:
            6,
        },
      )
      .setOrigin(
        0.5,
      )
      .setDepth(
        210,
      )

    this.add
      .text(
        width / 2,
        345,
        `WAVE ${result.waveReached}`,
        {
          fontFamily:
            'Arial, sans-serif',
          fontSize:
            '52px',
          fontStyle:
            'bold',
          color:
            '#ffffff',
        },
      )
      .setOrigin(
        0.5,
      )
      .setDepth(
        210,
      )

    this.add
      .text(
        width / 2,
        430,
        [
          `Enemies defeated     ${result.kills}`,
          `Gold collected       ${result.gold}`,
          `Essence earned       +${result.essence}`,
          `Best wave            ${state.bestWave}`,
          `Lifetime runs        ${state.lifetimeRuns}`,
        ].join(
          '\n',
        ),
        {
          fontFamily:
            'Arial, sans-serif',
          fontSize:
            '21px',
          color:
            '#b9c4d9',
          lineSpacing:
            18,
          align:
            'left',
        },
      )
      .setOrigin(
        0.5,
        0,
      )
      .setDepth(
        210,
      )

    this.add
      .text(
        width / 2,
        690,
        `✦ ${state.essence} ESSENCE`,
        {
          fontFamily:
            'Arial, sans-serif',
          fontSize:
            '29px',
          fontStyle:
            'bold',
          color:
            '#8fe9ff',
        },
      )
      .setOrigin(
        0.5,
      )
      .setDepth(
        210,
      )

    const again =
      this.add
        .rectangle(
          width / 2,
          830,
          width - 110,
          86,
          0xd2a54b,
        )
        .setStrokeStyle(
          3,
          0xffdf91,
        )
        .setInteractive({
          useHandCursor:
            true,
        })
        .setDepth(
          210,
        )

    this.add
      .text(
        width / 2,
        830,
        'RUN AGAIN',
        {
          fontFamily:
            'Arial, sans-serif',
          fontSize:
            '27px',
          fontStyle:
            'bold',
          color:
            '#19141d',
        },
      )
      .setOrigin(
        0.5,
      )
      .setDepth(
        211,
      )

    const hub =
      this.add
        .rectangle(
          width / 2,
          945,
          width - 110,
          78,
          0x1b263b,
        )
        .setStrokeStyle(
          2,
          0x55729d,
        )
        .setInteractive({
          useHandCursor:
            true,
        })
        .setDepth(
          210,
        )

    this.add
      .text(
        width / 2,
        945,
        'RETURN TO REALM',
        {
          fontFamily:
            'Arial, sans-serif',
          fontSize:
            '22px',
          fontStyle:
            'bold',
          color:
            '#d6e3fa',
        },
      )
      .setOrigin(
        0.5,
      )
      .setDepth(
        211,
      )

    again.on(
      'pointerdown',
      () => {
        this.scene.restart()
      },
    )

    hub.on(
      'pointerdown',
      () => {
        this.scene.start(
          'HubScene',
        )
      },
    )
  }
}
