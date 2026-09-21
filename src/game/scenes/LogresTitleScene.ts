import Phaser from 'phaser'

import {
  LOGRES_ASSETS,
  preloadLogresAssets,
} from '../logres/ui/LogresRuntimeAssets'

export class LogresTitleScene
  extends Phaser.Scene {
  constructor() {
    super('LogresTitleScene')
  }

  preload() {
    preloadLogresAssets(this)
  }

  create() {
    const {
      width,
      height,
    } = this.scale

    this.add
      .tileSprite(
        width / 2,
        height / 2,
        width,
        height,
        LOGRES_ASSETS
          .background
          .key,
      )

    this.add
      .image(
        width / 2,
        160,
        LOGRES_ASSETS
          .titleBase
          .key,
      )

    this.add
      .image(
        width / 2,
        465,
        LOGRES_ASSETS
          .worldSelect
          .key,
      )
      .setDisplaySize(
        720,
        360,
      )

    const next =
      this.add
        .image(
          width / 2,
          height - 180,
          LOGRES_ASSETS
            .titleNext
            .key,
        )
        .setInteractive({
          useHandCursor: true,
        })

    next.on(
      'pointerdown',
      () => {
        this.scene.start(
          'LogresFieldScene',
        )
      },
    )
  }
}
