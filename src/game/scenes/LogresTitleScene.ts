import Phaser from 'phaser'

import {
  LOGRES_ASSETS,
  preloadLogresAssets,
} from '../logres/ui/LogresRuntimeAssets'

export class LogresTitleScene
  extends Phaser.Scene {
  constructor() {
    super(
      'LogresTitleScene',
    )
  }

  preload() {
    preloadLogresAssets(
      this,
    )

    /*
     * Global client English strings.
     */
    this.load.json(
      'logres-world-select-en',
      '/__logres_ref/config/global/world_select_strings.json',
    )

    this.load.json(
      'logres-system-strings-en',
      '/__logres_ref/config/global/system_strings.json',
    )
  }

  create() {
    const {
      width,
      height,
    } = this.scale

    /*
     * Original Global Logres title background.
     */
    this.add
      .image(
        width / 2,
        height / 2,
        LOGRES_ASSETS
          .titleBackground
          .key,
      )
      .setDisplaySize(
        width,
        height,
      )

    /*
     * Original Global Logres logo asset.
     */
    this.add
      .image(
        width / 2,
        220,
        LOGRES_ASSETS
          .titleLogo
          .key,
      )
      .setDisplaySize(
        650,
        306,
      )

    /*
     * Original Global world-selection artwork.
     */
    this.add
      .image(
        width / 2,
        620,
        LOGRES_ASSETS
          .worldSelect
          .key,
      )
      .setDisplaySize(
        720,
        360,
      )

    /*
     * Original Global NEXT button.
     */
    const next =
      this.add
        .image(
          width / 2,
          height - 170,
          LOGRES_ASSETS
            .titleNext
            .key,
        )
        .setInteractive({
          useHandCursor:
            true,
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
