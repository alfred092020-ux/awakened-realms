import Phaser from 'phaser'

import {
  LOGRES_ASSETS,
  preloadLogresAssets,
} from '../logres/ui/LogresRuntimeAssets'

import {
  logresDevMs,
} from '../logres/LogresDevSettings'

export class LogresTitleScene
  extends Phaser.Scene {
  private transitioning =
    false

  constructor() {
    super(
      'LogresTitleScene',
    )
  }

  preload() {
    preloadLogresAssets(
      this,
    )

    this.load.json(
      'logres-system-strings-en',
      '/__logres_ref/config/global/system_strings.json',
    )
  }

  create() {
    /*
     * Exact root design recovered from
     * gui/title/title.lua:
     *
     * 720 x 1280 design space.
     * title_back is centered at 360,640.
     * The original image is 720 x 1248,
     * so it is not stretched to 1280.
     */
    this.add
      .image(
        360,
        640,
        LOGRES_ASSETS
          .titleBackground
          .key,
      )

    /*
     * title.lua names this button "start".
     * Cocos position: 360,200 from a
     * bottom-origin coordinate system.
     * Phaser equivalent: 360,1080.
     *
     * The same title_ok resource is used
     * for normal and highlighted states.
     */
    const start =
      this.add
        .image(
          360,
          1080,
          LOGRES_ASSETS
            .titleStart
            .key,
        )
        .setAlpha(
          0,
        )
        .setInteractive({
          useHandCursor:
            true,
        })

    /*
     * ReleaseScene_Title::onFadeInStart
     * delays the title control reveal by
     * 1.0 second.
     */
    this.time.delayedCall(
      logresDevMs(
        1000,
      ),
      () => {
        start.setAlpha(
          1,
        )
      },
    )

    start.on(
      'pointerdown',
      () => {
        if (
          this.transitioning
        ) {
          return
        }

        this.transitioning =
          true

        start
          .disableInteractive()

        /*
         * ReleaseScene_Title::onTapStart:
         * start control fades for 0.3 sec.
         */
        this.tweens.add({
          targets:
            start,

          alpha:
            0,

          duration:
            logresDevMs(
              300,
            ),
        })

        /*
         * The native title scene waits
         * 1.5 sec before switching into
         * the login state. Our rebuilt
         * server bootstrap resolves that
         * login boundary into the original
         * player world-selection scene.
         */
        this.time.delayedCall(
          logresDevMs(
            1500,
          ),
          () => {
            this.scene.start(
              'LogresWorldSelectScene',
            )
          },
        )
      },
    )
  }
}
