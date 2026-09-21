import Phaser from 'phaser'

import {
  LOGRES_ASSETS,
  preloadLogresAssets,
} from '../logres/ui/LogresRuntimeAssets'

type CharacterSex =
  | 'man'
  | 'woman'

export class LogresCharacterCreateScene
  extends Phaser.Scene {
  private selection:
    CharacterSex = 'man'

  private character?:
    Phaser.GameObjects.Image

  private changeButton?:
    Phaser.GameObjects.Image

  constructor() {
    super(
      'LogresCharacterCreateScene',
    )
  }

  preload() {
    preloadLogresAssets(
      this,
    )
  }

  create() {
    /*
     * Positions below come directly from:
     *
     * Global client:
     * gui/characreate/characterMan.lua
     * gui/characreate/characterWoman.lua
     *
     * root:
     *   720 x 1280
     *
     * character:
     *   x = 360
     *   y = 640
     *
     * man change button:
     *   relative +200,+250
     *   absolute 560,890
     *
     * woman change button:
     *   relative -200,+250
     *   absolute 160,890
     */

    this.renderSelection()
  }

  private renderSelection() {
    this.character?.destroy()
    this.changeButton?.destroy()

    if (
      this.selection ===
      'man'
    ) {
      this.character =
        this.add.image(
          360,
          640,
          LOGRES_ASSETS
            .characterMan
            .key,
        )

      this.changeButton =
        this.add
          .image(
            560,
            890,
            LOGRES_ASSETS
              .characterChangeMan
              .key,
          )
          .setInteractive({
            useHandCursor:
              true,
          })

      this.changeButton.on(
        'pointerdown',
        () => {
          this.selection =
            'woman'

          this.renderSelection()
        },
      )

      return
    }

    this.character =
      this.add.image(
        360,
        640,
        LOGRES_ASSETS
          .characterWoman
          .key,
      )

    this.changeButton =
      this.add
        .image(
          160,
          890,
          LOGRES_ASSETS
            .characterChangeWoman
            .key,
        )
        .setInteractive({
          useHandCursor:
            true,
        })

    this.changeButton.on(
      'pointerdown',
      () => {
        this.selection =
          'man'

        this.renderSelection()
      },
    )
  }
}
