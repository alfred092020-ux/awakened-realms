import Phaser from 'phaser'

import {
  CloudSaveService,
} from '../cloud/CloudSaveService'

import {
  CloudSyncCoordinator,
} from '../cloud/CloudSyncCoordinator'

export class AccountScene
  extends Phaser.Scene {
  private readonly cloud =
    new CloudSaveService()

  private statusText!:
    Phaser.GameObjects.Text

  constructor() {
    super(
      'AccountScene',
    )
  }

  create() {
    const {
      width,
      height,
    } = this.scale

    this.cameras.main
      .setBackgroundColor(
        '#080c18',
      )

    this.add
      .circle(
        width / 2,
        270,
        240,
        0x385b8a,
        0.15,
      )

    this.add
      .text(
        width / 2,
        175,
        'SAVE YOUR REALM',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '40px',

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
        250,
        'Keep your progress across devices\nand protect your awakened account.',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '19px',

          color:
            '#aab5ca',

          align:
            'center',

          lineSpacing:
            9,
        },
      )
      .setOrigin(
        0.5,
      )

    this.statusText =
      this.add
        .text(
          width / 2,
          400,
          'CHECKING ACCOUNT...',
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '17px',

            color:
              '#7f90ad',

            align:
              'center',
          },
        )
        .setOrigin(
          0.5,
        )

    void this
      .renderAccountActions(
        width,
        height,
      )
  }

  private async renderAccountActions(
    width: number,
    _height: number,
  ) {
    const configured =
      this.cloud
        .isConfigured()

    const account =
      await this.cloud
        .waitForAccount()

    if (
      !this.scene
        .isActive()
    ) {
      return
    }

    if (account) {
      this.statusText
        .setText(
          `SIGNED IN\n${
            account.email ??
            account.displayName ??
            'Google Account'
          }`,
        )
        .setColor(
          '#8fe7bb',
        )

      this.addButton(
        width / 2,
        615,
        'CONTINUE WITH CLOUD SAVE',
        0xd2a54b,
        0xffdf91,
        '#17131e',
        () => {
          void this
            .continueWithCloud()
        },
      )

      this.addButton(
        width / 2,
        760,
        'SIGN OUT & USE GUEST',
        0x1b263b,
        0x55729d,
        '#d6e3fa',
        () => {
          void this
            .useGuestAfterSignOut()
        },
      )

      return
    }

    this.statusText
      .setText(
        configured
          ? 'Sign in to enable cloud saves.'
          : 'Google cloud save needs Firebase setup.',
      )

    this.addButton(
      width / 2,
      615,
      configured
        ? 'SIGN IN WITH GOOGLE'
        : 'GOOGLE SIGN-IN • SETUP NEEDED',
      configured
        ? 0xd2a54b
        : 0x343b49,
      configured
        ? 0xffdf91
        : 0x555d6d,
      configured
        ? '#17131e'
        : '#858c9b',
      () => {
        void this
          .signInGoogle()
      },
      configured,
    )

    this.addButton(
      width / 2,
      790,
      'CONTINUE AS GUEST',
      0x1b263b,
      0x55729d,
      '#d6e3fa',
      () => {
        this.scene.start(
          'HubScene',
        )
      },
    )

    this.add
      .text(
        width / 2,
        885,
        'Guest progress stays on this device.\nYou can link Google later.',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '15px',

          color:
            '#707d96',

          align:
            'center',

          lineSpacing:
            6,
        },
      )
      .setOrigin(
        0.5,
      )
  }

  private addButton(
    x: number,
    y: number,
    label: string,
    fill: number,
    stroke: number,
    textColor: string,
    onPress: () => void,
    enabled = true,
  ) {
    const button =
      this.add
        .rectangle(
          x,
          y,
          580,
          92,
          fill,
        )
        .setStrokeStyle(
          3,
          stroke,
        )

    this.add
      .text(
        x,
        y,
        label,
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '22px',

          fontStyle:
            'bold',

          color:
            textColor,

          align:
            'center',
        },
      )
      .setOrigin(
        0.5,
      )

    if (!enabled) {
      return
    }

    button
      .setInteractive({
        useHandCursor:
          true,
      })

    button.on(
      'pointerdown',
      onPress,
    )
  }

  private async signInGoogle() {
    try {
      this.statusText
        .setText(
          'OPENING GOOGLE SIGN-IN...',
        )

      await this.cloud
        .signInWithGoogle()

      await new CloudSyncCoordinator(
        this.cloud,
      ).sync()

      this.scene.start(
        'HubScene',
      )
    } catch (error) {
      const details =
        error instanceof Error
          ? error.message
          : String(error)

      console.error(
        'Google sign-in failed:',
        error,
      )

      this.statusText
        .setText(
          `SIGN-IN FAILED\n${details.slice(0, 180)}`,
        )
        .setColor(
          '#ff9aa8',
        )
    }
  }

  private async continueWithCloud() {
    try {
      this.statusText
        .setText(
          'SYNCING CLOUD SAVE...',
        )

      await new CloudSyncCoordinator(
        this.cloud,
      ).sync()

      this.scene.start(
        'HubScene',
      )
    } catch {
      this.statusText
        .setText(
          'CLOUD SYNC FAILED\nCheck your connection and retry.',
        )
        .setColor(
          '#ff9aa8',
        )
    }
  }

  private async useGuestAfterSignOut() {
    await this.cloud
      .signOut()

    this.scene.start(
      'HubScene',
    )
  }
}
