import Phaser from 'phaser'

import {
  CloudSaveService,
} from '../cloud/CloudSaveService'

import {
  SocialService,
} from '../social/SocialService'

import type {
  FriendRelationship,
} from '../social/SocialService'

export class PlayerProfileScene
  extends Phaser.Scene {
  private readonly social =
    new SocialService()

  private readonly cloud =
    new CloudSaveService()

  private targetUid =
    ''

  private backScene =
    'FriendsScene'

  private actionText!:
    Phaser.GameObjects.Text

  private actionButton!:
    Phaser.GameObjects.Rectangle

  private relationship:
    FriendRelationship = {
      state:
        'none',
    }

  constructor() {
    super(
      'PlayerProfileScene',
    )
  }

  init(
    data: {
      uid?: string
      backScene?: string
    },
  ) {
    this.targetUid =
      data.uid ?? ''

    this.backScene =
      data.backScene ??
      'FriendsScene'
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
        115,
        width,
        230,
        0x121a30,
      )

    this.add
      .text(
        36,
        45,
        'PLAYER',
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
        75,
        'PROFILE',
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
          this.backScene,
        )
      },
    )

    this.add
      .text(
        width / 2,
        565,
        'LOADING PLAYER...',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '20px',

          color:
            '#8e9ab4',
        },
      )
      .setOrigin(
        0.5,
      )
      .setName(
        'profile-loading',
      )

    void this.loadProfile()
  }

  private async loadProfile() {
    if (!this.targetUid) {
      return
    }

    try {
      const profile =
        await this.social
          .getProfile(
            this.targetUid,
          )

      if (
        !profile ||
        !this.scene
          .isActive()
      ) {
        return
      }

      this.children
        .getByName(
          'profile-loading',
        )
        ?.destroy()

      const {
        width,
      } = this.scale

      this.add
        .circle(
          width / 2,
          300,
          84,
          0x395b90,
        )
        .setStrokeStyle(
          5,
          0x8bb9ef,
        )

      this.add
        .text(
          width / 2,
          300,
          profile.displayName
            .slice(
              0,
              1,
            )
            .toUpperCase(),
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '58px',

            fontStyle:
              'bold',

            color:
              '#edf6ff',
          },
        )
        .setOrigin(
          0.5,
        )

      this.add
        .text(
          width / 2,
          415,
          profile.displayName,
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '32px',

            fontStyle:
              'bold',

            color:
              '#f2f5ff',
          },
        )
        .setOrigin(
          0.5,
        )

      this.addStat(
        70,
        500,
        'BEST WAVE',
        `${profile.bestWave}`,
      )

      this.addStat(
        265,
        500,
        'RUNS',
        `${profile.lifetimeRuns}`,
      )

      this.addStat(
        460,
        500,
        'POWER',
        `${profile.power}%`,
      )

      const account =
        this.cloud
          .getAccount()

      if (
        account?.uid ===
        profile.uid
      ) {
        this.add
          .text(
            width / 2,
            700,
            'THIS IS YOUR PROFILE',
            {
              fontFamily:
                'Arial, sans-serif',

              fontSize:
                '18px',

              fontStyle:
                'bold',

              color:
                '#89dcb5',

              letterSpacing:
                2,
            },
          )
          .setOrigin(
            0.5,
          )

        return
      }

      if (!account) {
        this.add
          .text(
            width / 2,
            700,
            'SIGN IN TO ADD FRIENDS',
            {
              fontFamily:
                'Arial, sans-serif',

              fontSize:
                '18px',

              color:
                '#8d98af',
            },
          )
          .setOrigin(
            0.5,
          )

        return
      }

      this.relationship =
        await this.social
          .getRelationship(
            profile.uid,
          )

      if (
        !this.scene
          .isActive()
      ) {
        return
      }

      this.createActionButton()
    } catch {
      const loading =
        this.children
          .getByName(
            'profile-loading',
          )

      if (
        loading instanceof
        Phaser.GameObjects.Text
      ) {
        loading
          .setText(
            'PLAYER UNAVAILABLE',
          )
          .setColor(
            '#ff9aa8',
          )
      }
    }
  }

  private createActionButton() {
    const {
      width,
    } = this.scale

    this.actionButton =
      this.add
        .rectangle(
          width / 2,
          700,
          width - 150,
          82,
          0x345d93,
        )
        .setStrokeStyle(
          3,
          0x86b6f4,
        )
        .setInteractive({
          useHandCursor:
            true,
        })

    this.actionText =
      this.add
        .text(
          width / 2,
          700,
          '',
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '22px',

            fontStyle:
              'bold',

            color:
              '#eef6ff',
          },
        )
        .setOrigin(
          0.5,
        )

    this.refreshActionText()

    this.actionButton.on(
      'pointerdown',
      () => {
        void this.handleAction()
      },
    )
  }

  private refreshActionText() {
    const labels = {
      none:
        'ADD FRIEND',

      outgoing:
        'REQUEST SENT',

      incoming:
        'ACCEPT FRIEND REQUEST',

      friends:
        'FRIENDS ✓',
    } as const

    this.actionText
      .setText(
        labels[
          this.relationship.state
        ],
      )

    const inactive =
      this.relationship.state ===
        'outgoing' ||
      this.relationship.state ===
        'friends'

    this.actionButton
      .setFillStyle(
        inactive
          ? 0x283244
          : 0x345d93,
      )
  }

  private async handleAction() {
    try {
      if (
        this.relationship.state ===
        'none'
      ) {
        this.relationship =
          await this.social
            .sendFriendRequest(
              this.targetUid,
            )

        this.refreshActionText()

        return
      }

      if (
        this.relationship.state ===
          'incoming' &&
        this.relationship
          .requestId
      ) {
        await this.social
          .respondToRequest(
            this.relationship
              .requestId,
            true,
          )

        this.relationship = {
          state:
            'friends',

          requestId:
            this.relationship
              .requestId,
        }

        this.refreshActionText()
      }
    } catch {
      this.actionText
        .setText(
          'TRY AGAIN',
        )
    }
  }

  private addStat(
    x: number,
    y: number,
    label: string,
    value: string,
  ) {
    this.add
      .rectangle(
        x,
        y,
        170,
        116,
        0x141d30,
      )
      .setOrigin(
        0,
        0,
      )
      .setStrokeStyle(
        2,
        0x344865,
      )

    this.add
      .text(
        x + 15,
        y + 20,
        label,
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '13px',

          fontStyle:
            'bold',

          color:
            '#8593ad',
        },
      )

    this.add
      .text(
        x + 15,
        y + 52,
        value,
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '30px',

          fontStyle:
            'bold',

          color:
            '#edf3ff',
        },
      )
  }
}
