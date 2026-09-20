import Phaser from 'phaser'

import {
  CloudSaveService,
} from '../cloud/CloudSaveService'

import {
  SocialService,
} from '../social/SocialService'

import {
  PresenceService,
} from '../social/PresenceService'

import {
  MultiplayerService,
} from '../social/MultiplayerService'

import type {
  MultiplayerInvite,
} from '../social/MultiplayerService'

import type {
  PublicPlayerProfile,
} from '../social/LeaderboardService'

export class MultiplayerScene
  extends Phaser.Scene {
  private readonly cloud =
    new CloudSaveService()

  private readonly social =
    new SocialService()

  private readonly presence =
    new PresenceService()

  private readonly multiplayer =
    new MultiplayerService()

  private cleanup:
    (() => void)[] =
      []

  private friendObjects:
    Phaser.GameObjects.GameObject[] =
      []

  private inviteObjects:
    Phaser.GameObjects.GameObject[] =
      []

  private statusText!:
    Phaser.GameObjects.Text

  private inviteVersion =
    0

  constructor() {
    super(
      'MultiplayerScene',
    )
  }

  create() {
    const {
      width,
    } = this.scale

    this.cameras.main
      .setBackgroundColor(
        '#070c17',
      )

    this.add
      .rectangle(
        width / 2,
        115,
        width,
        230,
        0x111b31,
      )

    this.add
      .text(
        36,
        42,
        'LIVE',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '18px',

          fontStyle:
            'bold',

          color:
            '#77d8ae',

          letterSpacing:
            4,
        },
      )

    this.add
      .text(
        36,
        72,
        'CO-OP REALM',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '41px',

          fontStyle:
            'bold',

          color:
            '#f4e4a9',
        },
      )

    this.add
      .text(
        36,
        132,
        'Invite an online friend into a live room.',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '16px',

          color:
            '#8e9db7',
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
          'FriendsScene',
        )
      },
    )

    this.statusText =
      this.add
        .text(
          width / 2,
          205,
          'CONNECTING...',
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '15px',

            color:
              '#8592aa',

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
          'Sign in with Google to use multiplayer.',
        )

      return
    }

    void this.presence
      .start()

    const stopInvites =
      this.multiplayer
        .subscribeIncomingInvites(
          (invites) => {
            void this.renderInvites(
              invites,
            )
          },
        )

    this.cleanup.push(
      stopInvites,
    )

    this.events.once(
      Phaser.Scenes.Events.SHUTDOWN,
      () => {
        this.cleanupSubscriptions()
      },
    )

    void this.loadFriends()
  }

  private cleanupSubscriptions() {
    for (
      const stop of
      this.cleanup
    ) {
      stop()
    }

    this.cleanup =
      []
  }

  private clearObjects(
    objects:
      Phaser.GameObjects.GameObject[],
  ) {
    for (
      const object of
      objects
    ) {
      object.destroy()
    }

    objects.length =
      0
  }

  private async loadFriends() {
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

      this.clearObjects(
        this.friendObjects,
      )

      this.addSection(
        'ONLINE FRIENDS',
        525,
        this.friendObjects,
      )

      if (
        overview.friends.length ===
        0
      ) {
        const empty =
          this.add
            .text(
              44,
              580,
              'No friends yet.\nAdd a friend before starting co-op.',
              {
                fontFamily:
                  'Arial, sans-serif',

                fontSize:
                  '18px',

                color:
                  '#78859d',

                lineSpacing:
                  7,
              },
            )

        this.friendObjects.push(
          empty,
        )

        return
      }

      overview.friends
        .slice(
          0,
          6,
        )
        .forEach(
          (
            profile,
            index,
          ) => {
            this.addFriendRow(
              profile,
              590 +
                index * 82,
            )
          },
        )

      this.statusText
        .setText(
          'LIVE PRESENCE ACTIVE',
        )
        .setColor(
          '#78d9ad',
        )
    } catch {
      this.statusText
        .setText(
          'CO-OP DATA UNAVAILABLE',
        )
        .setColor(
          '#ff9aa8',
        )
    }
  }

  private addSection(
    label: string,
    y: number,
    target:
      Phaser.GameObjects.GameObject[],
  ) {
    const text =
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
              '#95a3bd',

            letterSpacing:
              3,
          },
        )

    target.push(
      text,
    )
  }

  private addFriendRow(
    profile:
      PublicPlayerProfile,
    y: number,
  ) {
    const {
      width,
    } = this.scale

    let online =
      false

    let inviting =
      false

    const panel =
      this.add
        .rectangle(
          width / 2,
          y,
          width - 72,
          68,
          0x151f32,
        )
        .setStrokeStyle(
          1,
          0x354a68,
        )
        .setInteractive({
          useHandCursor:
            true,
        })

    const name =
      this.add
        .text(
          52,
          y - 13,
          profile.displayName,
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '18px',

            fontStyle:
              'bold',

            color:
              '#edf3ff',
          },
        )

    const presenceText =
      this.add
        .text(
          52,
          y + 14,
          'CHECKING...',
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '13px',

            color:
              '#7c899f',
          },
        )

    const action =
      this.add
        .text(
          width - 52,
          y,
          '...',
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '15px',

            fontStyle:
              'bold',

            color:
              '#8290a8',
          },
        )
        .setOrigin(
          1,
          0.5,
        )

    const stop =
      this.presence
        .subscribe(
          profile.uid,
          (state) => {
            online =
              state.online

            presenceText
              .setText(
                online
                  ? '● ONLINE'
                  : '○ OFFLINE',
              )
              .setColor(
                online
                  ? '#78d9ad'
                  : '#727f95',
              )

            if (!inviting) {
              action
                .setText(
                  online
                    ? 'INVITE'
                    : 'OFFLINE',
                )
                .setColor(
                  online
                    ? '#8fbdff'
                    : '#68758a',
                )
            }
          },
        )

    this.cleanup.push(
      stop,
    )

    panel.on(
      'pointerdown',
      () => {
        if (
          !online ||
          inviting
        ) {
          return
        }

        inviting =
          true

        action
          .setText(
            'INVITING...',
          )

        void this.multiplayer
          .createInvite(
            profile.uid,
          )
          .then(
            ({
              roomId,
            }) => {
              if (
                !this.scene
                  .isActive()
              ) {
                return
              }

              this.scene.start(
                'CoopLobbyScene',
                {
                  roomId,
                },
              )
            },
          )
          .catch(
            () => {
              inviting =
                false

              action
                .setText(
                  'TRY AGAIN',
                )
                .setColor(
                  '#ff9aa8',
                )
            },
          )
      },
    )

    this.friendObjects.push(
      panel,
      name,
      presenceText,
      action,
    )
  }

  private async renderInvites(
    invites:
      readonly MultiplayerInvite[],
  ) {
    const version =
      ++this.inviteVersion

    this.clearObjects(
      this.inviteObjects,
    )

    this.addSection(
      'CO-OP INVITES',
      275,
      this.inviteObjects,
    )

    if (
      invites.length ===
      0
    ) {
      const none =
        this.add
          .text(
            44,
            325,
            'No pending invites.',
            {
              fontFamily:
                'Arial, sans-serif',

              fontSize:
                '17px',

              color:
                '#77849b',
            },
          )

      this.inviteObjects.push(
        none,
      )

      return
    }

    for (
      let index = 0;
      index <
      Math.min(
        2,
        invites.length,
      );
      index += 1
    ) {
      const invite =
        invites[index]

      if (!invite) {
        continue
      }

      const profile =
        await this.social
          .getProfile(
            invite.fromUid,
          )

      if (
        version !==
          this.inviteVersion ||
        !this.scene
          .isActive()
      ) {
        return
      }

      const y =
        335 +
        index * 82

      const panel =
        this.add
          .rectangle(
            this.scale.width / 2,
            y,
            this.scale.width - 72,
            68,
            0x1a2b3e,
          )
          .setStrokeStyle(
            2,
            0x4e7fa5,
          )

      const name =
        this.add
          .text(
            52,
            y - 13,
            profile
              ?.displayName ??
              'Awakened Player',
            {
              fontFamily:
                'Arial, sans-serif',

              fontSize:
                '18px',

              fontStyle:
                'bold',

              color:
                '#edf6ff',
            },
          )

      const subtitle =
        this.add
          .text(
            52,
            y + 14,
            'invited you to a live co-op room',
            {
              fontFamily:
                'Arial, sans-serif',

              fontSize:
                '13px',

              color:
                '#8da2b7',
            },
          )

      const join =
        this.add
          .text(
            this.scale.width -
              52,
            y,
            'JOIN',
            {
              fontFamily:
                'Arial, sans-serif',

              fontSize:
                '16px',

              fontStyle:
                'bold',

              color:
                '#83e1b5',
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

      join.on(
        'pointerdown',
        () => {
          join
            .setText(
              'JOINING...',
            )

          void this.multiplayer
            .acceptInvite(
              invite,
            )
            .then(
              () => {
                if (
                  this.scene
                    .isActive()
                ) {
                  this.scene.start(
                    'CoopLobbyScene',
                    {
                      roomId:
                        invite.roomId,
                    },
                  )
                }
              },
            )
            .catch(
              () => {
                join
                  .setText(
                    'TRY AGAIN',
                  )
                  .setColor(
                    '#ff9aa8',
                  )
              },
            )
        },
      )

      this.inviteObjects.push(
        panel,
        name,
        subtitle,
        join,
      )
    }
  }
}
