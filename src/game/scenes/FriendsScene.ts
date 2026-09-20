import Phaser from 'phaser'

import {
  CloudSaveService,
} from '../cloud/CloudSaveService'

import {
  SocialService,
} from '../social/SocialService'

import type {
  PublicPlayerProfile,
} from '../social/LeaderboardService'

export class FriendsScene
  extends Phaser.Scene {
  private readonly social =
    new SocialService()

  private readonly cloud =
    new CloudSaveService()

  private content:
    Phaser.GameObjects.GameObject[] =
      []

  private statusText!:
    Phaser.GameObjects.Text

  constructor() {
    super(
      'FriendsScene',
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
        110,
        width,
        220,
        0x121a30,
      )

    this.add
      .text(
        36,
        42,
        'SOCIAL',
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
        72,
        'FRIENDS',
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

    const search =
      this.add
        .rectangle(
          width / 2,
          180,
          width - 72,
          62,
          0x24395b,
        )
        .setStrokeStyle(
          2,
          0x638bc5,
        )
        .setInteractive({
          useHandCursor:
            true,
        })

    this.add
      .text(
        width / 2,
        180,
        'SEARCH PLAYER',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '19px',

          fontStyle:
            'bold',

          color:
            '#dceaff',

          letterSpacing:
            2,
        },
      )
      .setOrigin(
        0.5,
      )

    search.on(
      'pointerdown',
      () => {
        void this.searchPlayer()
      },
    )

    const multiplayer =
      this.add
        .rectangle(
          width / 2,
          255,
          width - 72,
          58,
          0x1d4b45,
        )
        .setStrokeStyle(
          2,
          0x55a88f,
        )
        .setInteractive({
          useHandCursor:
            true,
        })

    this.add
      .text(
        width / 2,
        255,
        'LIVE CO-OP',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '19px',

          fontStyle:
            'bold',

          color:
            '#c9f7e6',

          letterSpacing:
            3,
        },
      )
      .setOrigin(
        0.5,
      )

    multiplayer.on(
      'pointerdown',
      () => {
        this.scene.start(
          'MultiplayerScene',
        )
      },
    )

    this.statusText =
      this.add
        .text(
          width / 2,
          335,
          '',
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '16px',

            color:
              '#8290aa',

            align:
              'center',
          },
        )
        .setOrigin(
          0.5,
        )

    const account =
      this.cloud
        .getAccount()

    if (!account) {
      this.statusText
        .setText(
          'Sign in with Google to use friends.',
        )

      return
    }

    this.statusText
      .setText(
        'Loading social realm...',
      )

    void this.loadOverview()
  }

  private clearContent() {
    for (
      const object of
      this.content
    ) {
      object.destroy()
    }

    this.content =
      []
  }

  private remember(
    ...objects:
      Phaser.GameObjects.GameObject[]
  ) {
    this.content.push(
      ...objects,
    )
  }

  private async loadOverview() {
    try {
      const overview =
        await this.social
          .getOverview()

      if (
        !this.scene
          .isActive()
      ) {
        return
      }

      this.clearContent()

      this.statusText
        .setText(
          `${overview.friends.length} FRIENDS`,
        )
        .setColor(
          '#87dcb2',
        )

      let y =
        395

      if (
        overview.incoming.length >
        0
      ) {
        this.addSectionTitle(
          'FRIEND REQUESTS',
          y,
        )

        y +=
          55

        for (
          const item of
          overview.incoming
            .slice(
              0,
              3,
            )
        ) {
          this.addIncomingRow(
            item.profile,
            item.request.id,
            y,
          )

          y +=
            76
        }

        y +=
          25
      }

      this.addSectionTitle(
        'YOUR FRIENDS',
        y,
      )

      y +=
        55

      if (
        overview.friends.length ===
        0
      ) {
        const empty =
          this.add
            .text(
              50,
              y,
              'No friends yet.\nSearch for another player by name.',
              {
                fontFamily:
                  'Arial, sans-serif',

                fontSize:
                  '18px',

                color:
                  '#78859e',

                lineSpacing:
                  8,
              },
            )

        this.remember(
          empty,
        )

        y +=
          105
      } else {
        for (
          const profile of
          overview.friends
            .slice(
              0,
              6,
            )
        ) {
          this.addPlayerRow(
            profile,
            y,
            'VIEW',
          )

          y +=
            76
        }
      }

      if (
        overview.outgoing.length >
        0
      ) {
        y +=
          25

        this.addSectionTitle(
          'REQUESTS SENT',
          y,
        )

        y +=
          55

        for (
          const item of
          overview.outgoing
            .slice(
              0,
              3,
            )
        ) {
          this.addPlayerRow(
            item.profile,
            y,
            'SENT',
          )

          y +=
            76
        }
      }
    } catch {
      this.statusText
        .setText(
          'SOCIAL DATA UNAVAILABLE',
        )
        .setColor(
          '#ff9aa8',
        )
    }
  }

  private async searchPlayer() {
    const name =
      window.prompt(
        'Enter the exact player name:',
      )

    if (!name) {
      return
    }

    this.statusText
      .setText(
        'SEARCHING...',
      )
      .setColor(
        '#8d99b2',
      )

    try {
      const account =
        this.cloud
          .getAccount()

      const profiles =
        (
          await this.social
            .searchPlayers(
              name,
            )
        ).filter(
          (profile) =>
            profile.uid !==
            account?.uid,
        )

      if (
        !this.scene
          .isActive()
      ) {
        return
      }

      this.clearContent()

      this.statusText
        .setText(
          profiles.length > 0
            ? `${profiles.length} PLAYER${
                profiles.length === 1
                  ? ''
                  : 'S'
              } FOUND`
            : 'NO PLAYER FOUND',
        )

      let y =
        405

      for (
        const profile of
        profiles.slice(
          0,
          6,
        )
      ) {
        this.addPlayerRow(
          profile,
          y,
          'VIEW',
        )

        y +=
          86
      }

      const restore =
        this.add
          .text(
            this.scale.width / 2,
            920,
            'SHOW FRIENDS',
            {
              fontFamily:
                'Arial, sans-serif',

              fontSize:
                '18px',

              fontStyle:
                'bold',

              color:
                '#8fbaff',
            },
          )
          .setOrigin(
            0.5,
          )
          .setInteractive({
            useHandCursor:
              true,
          })

      restore.on(
        'pointerdown',
        () => {
          void this.loadOverview()
        },
      )

      this.remember(
        restore,
      )
    } catch {
      this.statusText
        .setText(
          'SEARCH FAILED',
        )
        .setColor(
          '#ff9aa8',
        )
    }
  }

  private addSectionTitle(
    label: string,
    y: number,
  ) {
    const title =
      this.add
        .text(
          38,
          y,
          label,
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '16px',

            fontStyle:
              'bold',

            color:
              '#919fbb',

            letterSpacing:
              3,
          },
        )

    this.remember(
      title,
    )
  }

  private addPlayerRow(
    profile:
      PublicPlayerProfile,
    y: number,
    action: string,
  ) {
    const {
      width,
    } = this.scale

    const panel =
      this.add
        .rectangle(
          width / 2,
          y,
          width - 72,
          64,
          0x151e30,
        )
        .setStrokeStyle(
          1,
          0x354663,
        )
        .setInteractive({
          useHandCursor:
            true,
        })

    const name =
      this.add
        .text(
          52,
          y - 11,
          profile.displayName,
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '18px',

            fontStyle:
              'bold',

            color:
              '#e9effb',
          },
        )

    const stats =
      this.add
        .text(
          52,
          y + 13,
          `Wave ${profile.bestWave} • Power ${profile.power}%`,
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '13px',

            color:
              '#8795af',
          },
        )

    const actionText =
      this.add
        .text(
          width - 52,
          y,
          action,
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '14px',

            fontStyle:
              'bold',

            color:
              action ===
                'SENT'
                ? '#7e899e'
                : '#8ebaff',
          },
        )
        .setOrigin(
          1,
          0.5,
        )

    panel.on(
      'pointerdown',
      () => {
        this.scene.start(
          'PlayerProfileScene',
          {
            uid:
              profile.uid,

            backScene:
              'FriendsScene',
          },
        )
      },
    )

    this.remember(
      panel,
      name,
      stats,
      actionText,
    )
  }

  private addIncomingRow(
    profile:
      PublicPlayerProfile,
    requestId: string,
    y: number,
  ) {
    const {
      width,
    } = this.scale

    const panel =
      this.add
        .rectangle(
          width / 2,
          y,
          width - 72,
          64,
          0x1b263b,
        )
        .setStrokeStyle(
          1,
          0x49668f,
        )

    const name =
      this.add
        .text(
          52,
          y - 11,
          profile.displayName,
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '18px',

            fontStyle:
              'bold',

            color:
              '#ecf3ff',
          },
        )

    const text =
      this.add
        .text(
          52,
          y + 13,
          'wants to become friends',
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '13px',

            color:
              '#8797b0',
          },
        )

    const accept =
      this.add
        .text(
          width - 52,
          y,
          'ACCEPT',
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '15px',

            fontStyle:
              'bold',

            color:
              '#8de0b4',
          },
        )
        .setOrigin(
          1,
          0.5,
        )
        .setInteractive({
          useHandCursor:
            true,
        })

    accept.on(
      'pointerdown',
      () => {
        void this
          .acceptRequest(
            requestId,
          )
      },
    )

    this.remember(
      panel,
      name,
      text,
      accept,
    )
  }

  private async acceptRequest(
    requestId: string,
  ) {
    try {
      await this.social
        .respondToRequest(
          requestId,
          true,
        )

      await this.loadOverview()
    } catch {
      this.statusText
        .setText(
          'COULD NOT ACCEPT REQUEST',
        )
        .setColor(
          '#ff9aa8',
        )
    }
  }
}
