import Phaser from 'phaser'

import {
  CloudSaveService,
} from '../cloud/CloudSaveService'

import {
  MetaSaveSystem,
} from '../meta/MetaSaveSystem'

import {
  LeaderboardService,
  calculateProfilePower,
} from '../social/LeaderboardService'

import type {
  LeaderboardEntry,
} from '../social/LeaderboardService'

export class LeaderboardScene
  extends Phaser.Scene {
  private readonly leaderboard =
    new LeaderboardService()

  private readonly cloud =
    new CloudSaveService()

  constructor() {
    super(
      'LeaderboardScene',
    )
  }

  create() {
    const {
      width,
    } = this.scale

    this.cameras.main
      .setBackgroundColor(
        '#080c18',
      )

    this.add
      .rectangle(
        width / 2,
        105,
        width,
        210,
        0x121a30,
      )

    this.add
      .text(
        36,
        38,
        'GLOBAL',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '18px',

          fontStyle:
            'bold',

          color:
            '#8fa0c5',

          letterSpacing:
            4,
        },
      )

    this.add
      .text(
        36,
        67,
        'RANKINGS',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '43px',

          fontStyle:
            'bold',

          color:
            '#f4e4a9',
        },
      )

    this.add
      .text(
        36,
        126,
        'Highest Realm Wave',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '17px',

          color:
            '#8996b2',
        },
      )

    const back =
      this.add
        .text(
          width - 38,
          58,
          'BACK',
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '17px',

            fontStyle:
              'bold',

            color:
              '#9fc5ff',
          },
        )
        .setOrigin(
          1,
          0,
        )
        .setInteractive({
          useHandCursor:
            true,
        })

    back.on(
      'pointerdown',
      () => {
        this.scene.start(
          'HubScene',
        )
      },
    )

    this.add
      .text(
        width / 2,
        620,
        'LOADING RANKINGS...',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '20px',

          color:
            '#8d99b2',
        },
      )
      .setOrigin(
        0.5,
      )
      .setName(
        'loading',
      )

    void this.loadRankings()
  }

  private async loadRankings() {
    const state =
      new MetaSaveSystem()
        .load()

    const account =
      this.cloud
        .getAccount()

    try {
      if (account) {
        await this.leaderboard
          .publishIfSignedIn(
            state,
            Date.now(),
          )
      }

      const [
        entries,
        myRank,
      ] =
        await Promise.all([
          this.leaderboard
            .getTopProfiles(
              12,
            ),

          account
            ? this.leaderboard
                .getMyRank(
                  state.bestWave,
                )
            : Promise.resolve(
                null,
              ),
        ])

      if (
        !this.scene
          .isActive()
      ) {
        return
      }

      this.children
        .getByName(
          'loading',
        )
        ?.destroy()

      this.renderProfile(
        account
          ?.displayName ??
          'Guest Player',

        state.bestWave,

        calculateProfilePower(
          state,
        ),

        myRank,
      )

      this.renderEntries(
        entries,
        account?.uid,
      )
    } catch {
      if (
        !this.scene
          .isActive()
      ) {
        return
      }

      const loading =
        this.children
          .getByName(
            'loading',
          )

      if (
        loading instanceof
        Phaser.GameObjects.Text
      ) {
        loading
          .setText(
            'RANKINGS UNAVAILABLE\nCheck your connection.',
          )
          .setAlign(
            'center',
          )
          .setColor(
            '#ff9aa8',
          )
      }
    }
  }

  private renderProfile(
    name: string,
    bestWave: number,
    power: number,
    rank: number | null,
  ) {
    const {
      width,
    } = this.scale

    this.add
      .rectangle(
        width / 2,
        245,
        width - 64,
        128,
        0x172139,
      )
      .setStrokeStyle(
        2,
        0x4d6593,
      )

    this.add
      .text(
        54,
        205,
        name,
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '22px',

          fontStyle:
            'bold',

          color:
            '#eff4ff',
        },
      )

    this.add
      .text(
        54,
        247,
        `Best Wave ${bestWave}   •   Power ${power}%`,
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '16px',

          color:
            '#9eabc5',
        },
      )

    this.add
      .text(
        width - 54,
        228,
        rank
          ? `#${rank}`
          : 'GUEST',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '32px',

          fontStyle:
            'bold',

          color:
            rank
              ? '#f3d77f'
              : '#77839b',
        },
      )
      .setOrigin(
        1,
        0,
      )
  }

  private renderEntries(
    entries:
      readonly LeaderboardEntry[],

    currentUid:
      string | undefined,
  ) {
    const {
      width,
    } = this.scale

    this.add
      .text(
        36,
        333,
        'TOP PLAYERS',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '17px',

          fontStyle:
            'bold',

          color:
            '#95a2bd',

          letterSpacing:
            3,
        },
      )

    if (
      entries.length ===
      0
    ) {
      this.add
        .text(
          width / 2,
          500,
          'No ranked players yet.\nBe the first to awaken.',
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '19px',

            color:
              '#7e8aa2',

            align:
              'center',
          },
        )
        .setOrigin(
          0.5,
        )

      return
    }

    entries.forEach(
      (
        entry,
        index,
      ) => {
        const y =
          395 +
          index * 66

        const isMe =
          entry.uid ===
          currentUid

        this.add
          .rectangle(
            width / 2,
            y,
            width - 64,
            56,
            isMe
              ? 0x26395b
              : 0x131b2b,
          )
          .setStrokeStyle(
            1,
            isMe
              ? 0x7498d6
              : 0x2b3852,
          )

        this.add
          .text(
            52,
            y,
            `#${entry.rank}`,
            {
              fontFamily:
                'Arial, sans-serif',

              fontSize:
                '18px',

              fontStyle:
                'bold',

              color:
                entry.rank <= 3
                  ? '#f4d982'
                  : '#8998b5',
            },
          )
          .setOrigin(
            0,
            0.5,
          )

        this.add
          .text(
            118,
            y,
            entry.displayName,
            {
              fontFamily:
                'Arial, sans-serif',

              fontSize:
                '17px',

              fontStyle:
                isMe
                  ? 'bold'
                  : 'normal',

              color:
                isMe
                  ? '#eef5ff'
                  : '#c3ccde',
            },
          )
          .setOrigin(
            0,
            0.5,
          )

        this.add
          .text(
            width - 50,
            y,
            `W${entry.bestWave}`,
            {
              fontFamily:
                'Arial, sans-serif',

              fontSize:
                '18px',

              fontStyle:
                'bold',

              color:
                '#9fd2ff',
            },
          )
          .setOrigin(
            1,
            0.5,
          )
      },
    )
  }
}
