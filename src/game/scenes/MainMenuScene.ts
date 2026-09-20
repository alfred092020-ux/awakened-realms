import Phaser from 'phaser'

export class MainMenuScene
  extends Phaser.Scene {
  constructor() {
    super('MainMenuScene')
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

    for (
      let index = 0;
      index < 75;
      index += 1
    ) {
      this.add
        .circle(
          Phaser.Math.Between(
            0,
            width,
          ),

          Phaser.Math.Between(
            0,
            height,
          ),

          Phaser.Math.FloatBetween(
            0.8,
            2.4,
          ),

          0xffffff,

          Phaser.Math.FloatBetween(
            0.12,
            0.6,
          ),
        )
    }

    this.add
      .circle(
        width / 2,
        height * 0.32,
        235,
        0x50396f,
        0.16,
      )

    this.add
      .circle(
        width / 2,
        height * 0.32,
        155,
        0x366996,
        0.12,
      )

    this.add
      .text(
        width / 2,
        height * 0.22,
        'AWAKENED',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '34px',

          fontStyle:
            'bold',

          color:
            '#a4afd0',

          letterSpacing:
            8,
        },
      )
      .setOrigin(
        0.5,
      )

    this.add
      .text(
        width / 2,
        height * 0.28,
        'REALMS',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '76px',

          fontStyle:
            'bold',

          color:
            '#f4e4a9',

          stroke:
            '#302441',

          strokeThickness:
            6,
        },
      )
      .setOrigin(
        0.5,
      )

    this.add
      .text(
        width / 2,
        height * 0.365,
        'IDLE ROGUELIKE',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '20px',

          color:
            '#9ba7c1',

          letterSpacing:
            7,
        },
      )
      .setOrigin(
        0.5,
      )

    this.add
      .text(
        width / 2,
        height * 0.47,
        'Fight automatically.\nChoose your power.\nAwaken stronger.',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '23px',

          color:
            '#c7cee0',

          align:
            'center',

          lineSpacing:
            10,
        },
      )
      .setOrigin(
        0.5,
      )

    const button =
      this.add
        .rectangle(
          width / 2,
          height * 0.69,
          width - 110,
          92,
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

    const label =
      this.add
        .text(
          width / 2,
          height * 0.69,
          'ENTER REALM',
          {
            fontFamily:
              'Arial, sans-serif',

            fontSize:
              '29px',

            fontStyle:
              'bold',

            color:
              '#17131e',
          },
        )
        .setOrigin(
          0.5,
        )

    button.on(
      'pointerdown',
      () => {
        label.setText(
          'AWAKENING...',
        )

        this.tweens.add({
          targets:
            button,

          scaleX:
            0.96,

          scaleY:
            0.96,

          yoyo:
            true,

          duration:
            90,

          onComplete:
            () => {
              this.scene.start(
                'AccountScene',
              )
            },
        })
      },
    )

    this.add
      .text(
        width / 2,
        height - 48,
        'AUTO BATTLE • ROGUELIKE BUILDS • IDLE PROGRESSION',
        {
          fontFamily:
            'Arial, sans-serif',

          fontSize:
            '12px',

          color:
            '#606b84',

          letterSpacing:
            2,
        },
      )
      .setOrigin(
        0.5,
      )
  }
}
