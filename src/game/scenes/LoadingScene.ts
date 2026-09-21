import Phaser from 'phaser'

export class LoadingScene
  extends Phaser.Scene {
  constructor() {
    super('LoadingScene')
  }

  create() {
    this.scene.start(
      'LogresTitleScene',
    )
  }
}
