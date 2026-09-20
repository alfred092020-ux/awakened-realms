import Phaser from 'phaser'

export class LoadingScene extends Phaser.Scene {
  constructor() {
    super('LoadingScene')
  }

  create() {
    const { width, height } = this.scale

    this.add
      .text(width / 2, height * 0.38, 'AWAKENED REALMS', {
        fontFamily: 'Arial, sans-serif',
        fontSize: '56px',
        fontStyle: 'bold',
        color: '#f3e6ba',
      })
      .setOrigin(0.5)

    const barWidth = 420
    const barHeight = 12

    this.add
      .rectangle(
        width / 2,
        height * 0.56,
        barWidth,
        barHeight,
        0x252a3c,
      )
      .setOrigin(0.5)

    const progress = this.add
      .rectangle(
        width / 2 - barWidth / 2,
        height * 0.56,
        0,
        barHeight,
        0xe7c46a,
      )
      .setOrigin(0, 0.5)

    this.tweens.add({
      targets: progress,
      width: barWidth,
      duration: 700,
      ease: 'Sine.easeOut',
      onComplete: () => {
        this.time.delayedCall(200, () => {
          this.scene.start('MainMenuScene')
        })
      },
    })
  }
}
