import Phaser from 'phaser'

import {
  MetaSession,
} from '../meta/MetaSession'

import {
  META_UPGRADES,
  getMetaUpgradeCost,
} from '../meta/MetaUpgradeCatalog'

export class HubScene
  extends Phaser.Scene {
  constructor() {
    super('HubScene')
  }

  create() {
    const {
      width,
      height,
    } = this.scale

    const session =
      new MetaSession()

    const offline =
      session.claimOffline(
        Date.now(),
      )

    const state =
      session.getState()

    this.cameras.main
      .setBackgroundColor(
        '#090d19',
      )

    this.add
      .rectangle(
        width / 2,
        165,
        width,
        330,
        0x121a30,
      )

    this.add
      .circle(
        width * 0.82,
        80,
        180,
        0x473875,
        0.22,
      )

    this.add
      .circle(
        width * 0.1,
        275,
        145,
        0x32618a,
        0.16,
      )

    this.add
      .text(
        38,
        42,
        'AWAKENED',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '24px',

          fontStyle:
            'bold',

          color:
            '#9ba8c8',

          letterSpacing:
            4,
        },
      )

    this.add
      .text(
        38,
        73,
        'REALMS',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '48px',

          fontStyle:
            'bold',

          color:
            '#f4e4a9',
        },
      )

    this.add
      .text(
        38,
        137,
        'IDLE ROGUELIKE',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '17px',

          color:
            '#8f9ab5',

          letterSpacing:
            5,
        },
      )

    this.add
      .text(
        width - 38,
        62,
        `✦ ${state.essence}`,
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '30px',

          fontStyle:
            'bold',

          color:
            '#8fe9ff',
        },
      )
      .setOrigin(
        1,
        0.5,
      )

    this.addStatCard(
      38,
      207,
      200,
      92,
      'BEST WAVE',
      `${state.bestWave}`,
    )

    this.addStatCard(
      260,
      207,
      200,
      92,
      'TOTAL RUNS',
      `${state.lifetimeRuns}`,
    )

    this.addStatCard(
      482,
      207,
      200,
      92,
      'POWER',
      this.calculatePower(
        state.upgrades[
          'attack-training'
        ],

        state.upgrades[
          'vitality-training'
        ],

        state.upgrades[
          'haste-training'
        ],
      ),
    )

    if (
      offline.essence >
      0
    ) {
      const offlinePanel =
        this.add
          .rectangle(
            width / 2,
            342,
            width - 76,
            82,
            0x16263a,
            0.96,
          )
          .setStrokeStyle(
            2,
            0x4f97b8,
            0.7,
          )

      this.add
        .text(
          66,
          326,
          'WELCOME BACK',
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '15px',

            fontStyle:
              'bold',

            color:
              '#7da9c5',
          },
        )

      this.add
        .text(
          66,
          348,
          `Offline reward  +${offline.essence} Essence`,
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '22px',

            fontStyle:
              'bold',

            color:
              '#dff8ff',
          },
        )

      this.tweens.add({
        targets:
          offlinePanel,

        alpha: {
          from:
            0.65,

          to:
            1,
        },

        duration:
          650,

        yoyo:
          true,
      })
    } else {
      this.add
        .text(
          38,
          334,
          'PERMANENT AWAKENING',
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '19px',

            fontStyle:
              'bold',

            color:
              '#c8d1e4',

            letterSpacing:
              2,
          },
        )
    }

    this.add
      .text(
        38,
        404,
        'PERMANENT UPGRADES',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '20px',

          fontStyle:
            'bold',

          color:
            '#dbe3f4',

          letterSpacing:
            2,
        },
      )

    META_UPGRADES.forEach(
      (
        definition,
        index,
      ) => {
        const level =
          state.upgrades[
            definition.id
          ]

        const maxed =
          level >=
          definition.maximumLevel

        const cost =
          maxed
            ? 0
            : getMetaUpgradeCost(
                definition.id,
                level,
              )

        const y =
          474 +
          index * 142

        const panel =
          this.add
            .rectangle(
              width / 2,
              y,
              width - 76,
              118,
              0x141b2c,
              0.98,
            )
            .setStrokeStyle(
              2,
              maxed
                ? 0x6d7390
                : 0x394b6e,
            )

        this.add
          .text(
            64,
            y - 34,
            definition.name,
            {
              fontFamily:
                'Arial, sans-serif',

              fontSize:
                '21px',

              fontStyle:
                'bold',

              color:
                '#f0f3fb',
            },
          )

        this.add
          .text(
            64,
            y - 3,
            definition.description,
            {
              fontFamily:
                'Arial, sans-serif',

              fontSize:
                '14px',

              color:
                '#8f9ab2',
            },
          )

        this.add
          .text(
            64,
            y + 31,
            `Lv.${level} / ${definition.maximumLevel}`,
            {
              fontFamily:
                'Arial, sans-serif',

              fontSize:
                '15px',

              fontStyle:
                'bold',

              color:
                '#a9b7d5',
            },
          )

        const button =
          this.add
            .rectangle(
              width - 116,
              y + 4,
              118,
              62,
              maxed
                ? 0x333847
                : 0x425f94,
            )
            .setStrokeStyle(
              2,
              maxed
                ? 0x555c71
                : 0x7ca7ef,
            )

        const buttonText =
          this.add
            .text(
              width - 116,
              y + 4,
              maxed
                ? 'MAX'
                : `✦ ${cost}`,
              {
                fontFamily:
                  'Arial, sans-serif',

                fontSize:
                  '17px',

                fontStyle:
                  'bold',

                color:
                  maxed
                    ? '#858b9d'
                    : '#f4f8ff',
              },
            )
            .setOrigin(
              0.5,
            )

        if (!maxed) {
          button
            .setInteractive({
              useHandCursor:
                true,
            })

          button.on(
            'pointerdown',
            () => {
              const result =
                session.purchase(
                  definition.id,
                )

              if (
                result.purchased
              ) {
                button
                  .setScale(
                    0.94,
                  )

                buttonText
                  .setText(
                    'UPGRADED',
                  )

                this.time
                  .delayedCall(
                    120,
                    () => {
                      this.scene
                        .restart()
                    },
                  )
              } else {
                buttonText
                  .setText(
                    'NEED ✦',
                  )

                this.time
                  .delayedCall(
                    700,
                    () => {
                      buttonText
                        .setText(
                          `✦ ${cost}`,
                        )
                    },
                  )
              }
            },
          )
        }

        panel.setDepth(0)
      },
    )

    const rankingsButton =
      this.add
        .rectangle(
          width / 2,
          height - 215,
          width - 76,
          64,
          0x1d2a42,
        )
        .setStrokeStyle(
          2,
          0x5576a8,
        )
        .setInteractive({
          useHandCursor:
            true,
        })

    this.add
      .text(
        width / 2,
        height - 215,
        'GLOBAL RANKINGS',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '20px',

          fontStyle:
            'bold',

          color:
            '#cfe1ff',

          letterSpacing:
            2,
        },
      )
      .setOrigin(
        0.5,
      )

    rankingsButton.on(
      'pointerdown',
      () => {
        this.scene.start(
          'LeaderboardScene',
        )
      },
    )

    const startButton =
      this.add
        .rectangle(
          width / 2,
          height - 105,
          width - 76,
          86,
          0xd5a84c,
        )
        .setStrokeStyle(
          3,
          0xffe096,
        )
        .setInteractive({
          useHandCursor:
            true,
        })

    this.add
      .text(
        width / 2,
        height - 110,
        'START RUN',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '30px',

          fontStyle:
            'bold',

          color:
            '#171421',
        },
      )
      .setOrigin(
        0.5,
      )

    this.add
      .text(
        width / 2,
        height - 78,
        'Auto battle • Build • Survive',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '13px',

          color:
            '#443718',
        },
      )
      .setOrigin(
        0.5,
      )

    startButton.on(
      'pointerdown',
      () => {
        startButton
          .setScale(
            0.97,
          )

        this.time
          .delayedCall(
            90,
            () => {
              this.scene.start(
                'RoguelikeBattleScene',
              )
            },
          )
      },
    )
  }

  private addStatCard(
    x: number,
    y: number,
    width: number,
    height: number,
    label: string,
    value: string,
  ) {
    this.add
      .rectangle(
        x,
        y,
        width,
        height,
        0x111827,
        0.96,
      )
      .setOrigin(
        0,
        0,
      )
      .setStrokeStyle(
        1,
        0x31405f,
      )

    this.add
      .text(
        x + 16,
        y + 17,
        label,
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '13px',

          fontStyle:
            'bold',

          color:
            '#7e8ba8',
        },
      )

    this.add
      .text(
        x + 16,
        y + 42,
        value,
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '29px',

          fontStyle:
            'bold',

          color:
            '#edf2ff',
        },
      )
  }

  private calculatePower(
    attack: number,
    vitality: number,
    haste: number,
  ) {
    return `${
      100 +
      attack * 5 +
      vitality * 6 +
      haste * 3
    }%`
  }
}
