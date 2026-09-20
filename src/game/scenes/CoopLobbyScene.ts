import Phaser from 'phaser'

import {
  CloudSaveService,
} from '../cloud/CloudSaveService'

import {
  SocialService,
} from '../social/SocialService'

import {
  MultiplayerService,
} from '../social/MultiplayerService'

import type {
  MultiplayerRoom,
} from '../social/MultiplayerService'

export class CoopLobbyScene
  extends Phaser.Scene {
  private readonly cloud =
    new CloudSaveService()

  private readonly social =
    new SocialService()

  private readonly multiplayer =
    new MultiplayerService()

  private roomId =
    ''

  private stopRoom:
    (() => void) |
    undefined

  private statusText!:
    Phaser.GameObjects.Text

  private hostText!:
    Phaser.GameObjects.Text

  private guestText!:
    Phaser.GameObjects.Text

  private loadedRoomKey =
    ''

  constructor() {
    super(
      'CoopLobbyScene',
    )
  }

  init(
    data: {
      roomId?: string
    },
  ) {
    this.roomId =
      data.roomId ??
      ''
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
      .circle(
        width / 2,
        330,
        250,
        0x315f87,
        0.12,
      )

    this.add
      .text(
        width / 2,
        105,
        'CO-OP LOBBY',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '42px',

          fontStyle:
            'bold',

          color:
            '#f4e4a9',
        },
      )
      .setOrigin(
        0.5,
      )

    this.add
      .text(
        width / 2,
        165,
        'LIVE REALTIME ROOM',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '16px',

          fontStyle:
            'bold',

          color:
            '#79dcae',

          letterSpacing:
            4,
        },
      )
      .setOrigin(
        0.5,
      )

    this.hostText =
      this.createPlayerCard(
        290,
        'HOST',
      )

    this.guestText =
      this.createPlayerCard(
        500,
        'GUEST',
      )

    this.statusText =
      this.add
        .text(
          width / 2,
          690,
          'CONNECTING TO ROOM...',
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '21px',

            fontStyle:
              'bold',

            color:
              '#9aa8bf',

            align:
              'center',
          },
        )
        .setOrigin(
          0.5,
        )

    const leave =
      this.add
        .rectangle(
          width / 2,
          860,
          width - 120,
          76,
          0x253149,
        )
        .setStrokeStyle(
          2,
          0x586e91,
        )
        .setInteractive({
          useHandCursor:
            true,
        })

    this.add
      .text(
        width / 2,
        860,
        'LEAVE LOBBY',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '21px',

          fontStyle:
            'bold',

          color:
            '#d4e1f6',
        },
      )
      .setOrigin(
        0.5,
      )

    leave.on(
      'pointerdown',
      () => {
        void this.leaveLobby()
      },
    )

    if (!this.roomId) {
      this.statusText
        .setText(
          'ROOM NOT FOUND',
        )
        .setColor(
          '#ff9aa8',
        )

      return
    }

    this.stopRoom =
      this.multiplayer
        .subscribeRoom(
          this.roomId,
          (room) => {
            void this.handleRoom(
              room,
            )
          },
        )

    this.events.once(
      Phaser.Scenes.Events.SHUTDOWN,
      () => {
        this.stopRoom?.()
      },
    )
  }

  private createPlayerCard(
    y: number,
    role: string,
  ) {
    const {
      width,
    } = this.scale

    this.add
      .rectangle(
        width / 2,
        y,
        width - 110,
        150,
        0x151f32,
      )
      .setStrokeStyle(
        2,
        0x3f5878,
      )

    this.add
      .text(
        70,
        y - 48,
        role,
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '14px',

          fontStyle:
            'bold',

          color:
            '#8293af',

          letterSpacing:
            3,
        },
      )

    return this.add
      .text(
        70,
        y - 5,
        'CONNECTING...',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '26px',

          fontStyle:
            'bold',

          color:
            '#edf4ff',
        },
      )
  }

  private async handleRoom(
    room:
      MultiplayerRoom |
      undefined,
  ) {
    if (
      !room ||
      room.status ===
        'closed'
    ) {
      this.statusText
        .setText(
          'ROOM CLOSED',
        )
        .setColor(
          '#ff9aa8',
        )

      return
    }

    if (
      this.loadedRoomKey !==
      `${room.hostUid}:${room.guestUid}`
    ) {
      this.loadedRoomKey =
        `${room.hostUid}:${room.guestUid}`

      const [
        host,
        guest,
      ] =
        await Promise.all([
          this.social
            .getProfile(
              room.hostUid,
            ),

          this.social
            .getProfile(
              room.guestUid,
            ),
        ])

      if (
        !this.scene
          .isActive()
      ) {
        return
      }

      const account =
        this.cloud
          .getAccount()

      this.hostText
        .setText(
          `${
            host
              ?.displayName ??
            'Awakened Player'
          }${
            account?.uid ===
              room.hostUid
              ? '  • YOU'
              : ''
          }`,
        )

      this.guestText
        .setText(
          `${
            guest
              ?.displayName ??
            'Awakened Player'
          }${
            account?.uid ===
              room.guestUid
              ? '  • YOU'
              : ''
          }`,
        )
    }

    if (
      room.status ===
      'ready'
    ) {
      this.statusText
        .setText(
          '● BOTH PLAYERS CONNECTED\nREADY FOR CO-OP',
        )
        .setColor(
          '#79dfaf',
        )

      return
    }

    this.statusText
      .setText(
        'WAITING FOR FRIEND TO JOIN...',
      )
      .setColor(
        '#a1adc2',
      )
  }

  private async leaveLobby() {
    try {
      await this.multiplayer
        .closeRoom(
          this.roomId,
        )
    } finally {
      this.scene.start(
        'MultiplayerScene',
      )
    }
  }
}
