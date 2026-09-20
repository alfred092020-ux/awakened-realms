import Phaser from 'phaser'

export class MainMenuScene extends Phaser.Scene {
  constructor() {
    super('MainMenuScene')
  }

  create() {
    const { width, height } = this.scale

    for (let i = 0; i < 70; i++) {
      const x = Phaser.Math.Between(0, width)
      const y = Phaser.Math.Between(0, height)
      const radius = Phaser.Math.FloatBetween(0.6, 1.8)

      this.add.circle(x, y, radius, 0xffffff, Phaser.Math.FloatBetween(0.15, 0.65))
    }

    this.add
      .text(width / 2, height * 0.31, 'AWAKENED REALMS', {
        fontFamily: 'Arial, sans-serif',
        fontSize: '72px',
        fontStyle: 'bold',
        color: '#f5e8bd',
        stroke: '#3c294f',
        strokeThickness: 5,
      })
      .setOrigin(0.5)

    this.add
      .text(width / 2, height * 0.42, 'ANIME FANTASY RPG', {
        fontFamily: 'Arial, sans-serif',
        fontSize: '22px',
        color: '#b8b4ca',
        letterSpacing: 8,
      })
      .setOrigin(0.5)

    const button = this.add
      .rectangle(width / 2, height * 0.62, 330, 76, 0xc89d4b)
      .setStrokeStyle(3, 0xf7df9a)
      .setInteractive({ useHandCursor: true })

    const label = this.add
      .text(width / 2, height * 0.62, 'BEGIN JOURNEY', {
        fontFamily: 'Arial, sans-serif',
        fontSize: '27px',
        fontStyle: 'bold',
        color: '#17121d',
      })
      .setOrigin(0.5)

    button.on('pointerover', () => button.setFillStyle(0xe0b65d))
    button.on('pointerout', () => button.setFillStyle(0xc89d4b))

    button.on('pointerdown', () => {
      label.setText('COMING NEXT')
      this.tweens.add({
        targets: button,
        scaleX: 0.96,
        scaleY: 0.96,
        yoyo: true,
        duration: 90,
      })
    })

    this.add
      .text(width / 2, height - 38, 'FOUNDATION BUILD • MILESTONE 1', {
        fontFamily: 'Arial, sans-serif',
        fontSize: '15px',
        color: '#696779',
      })
      .setOrigin(0.5)
  }
}
