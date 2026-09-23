import Phaser from 'phaser'

import {
  LOGRES_ASSETS,
  logresRuntimeUrl,
  preloadLogresAssets,
} from '../logres/ui/LogresRuntimeAssets'

import {
  LOGRES_TITLE_EFFECT_ASSETS,
  preloadLogresTitleEffectAssets,
} from '../logres/ui/LogresTitleEffectRuntimeAssets'

import {
  logresDevMs,
} from '../logres/LogresDevSettings'

import {
  LOGRES_TITLE_FRAME0_BACKGROUND_EVIDENCE,
  LOGRES_TITLE_FRAME0_BACKGROUND_LAYOUT,
  LOGRES_TITLE_IDLE_LOGO_LAYOUT,
} from '../logres/ui/LogresTitleEffectEvidence'

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

    preloadLogresTitleEffectAssets(
      this,
    )

    this.load.json(
      'logres-system-strings-en',
      logresRuntimeUrl(
        '/__logres_ref/config/global/system_strings.json',
      ),
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
      .setDepth(
        -1000,
      )

    const titleEffectReady =
      Object.values(
        LOGRES_TITLE_EFFECT_ASSETS,
      )
        .every(
          (
            asset,
          ) =>
            this.textures.exists(
              asset.key,
            ),
        )

    if (
      titleEffectReady
    ) {
      LOGRES_TITLE_FRAME0_BACKGROUND_LAYOUT
        .forEach(
          (
            layer,
            index,
          ) => {
            const asset =
              LOGRES_TITLE_EFFECT_ASSETS[
                layer.asset
              ]

            this.add
              .image(
                layer.x,
                layer.y,
                asset.key,
              )
              .setOrigin(
                0,
                0,
              )
              .setScale(
                layer.scaleX,
                layer.scaleY,
              )
              .setDepth(
                -900 +
                  index,
              )
          },
        )

      this.registry.set(
        'logres.title.backgroundPresentation',
        {
          status:
            'READY',

          ...LOGRES_TITLE_FRAME0_BACKGROUND_EVIDENCE,
        },
      )
    } else {
      this.registry.set(
        'logres.title.backgroundPresentation',
        {
          status:
            'FALLBACK',

          reason:
            'PRIVATE_TITLE_EFFECT_ASSETS_UNAVAILABLE',
        },
      )
    }

    /*
     * The recovered Global logo00 artwork is 710 x 334, exactly matching the
     * current-JP logo_b.lfla symbol dimensions. The current-JP idle title
     * effect centers that symbol at (360,367) in the native 720x1280 canvas.
     *
     * Applying that transform to the 2017 Global artwork is explicitly
     * SUPPORTED_INFERENCE_CURRENT_JP_LAYOUT. We do not claim the still-missing
     * Global entrance/exit LFLA timeline has been recovered.
     */
    this.add
      .image(
        LOGRES_TITLE_IDLE_LOGO_LAYOUT
          .x,
        LOGRES_TITLE_IDLE_LOGO_LAYOUT
          .y,
        LOGRES_ASSETS
          .titleLogo
          .key,
      )
      .setOrigin(
        0.5,
        0.5,
      )
      .setDepth(
        100,
      )

    this.registry.set(
      'logres.title.logoPresentation',
      {
        asset:
          'RECOVERED_GLOBAL',

        layout:
          LOGRES_TITLE_IDLE_LOGO_LAYOUT
            .globalApplication,

        nativeEvidence:
          LOGRES_TITLE_IDLE_LOGO_LAYOUT
            .nativeEvidence,

        animation:
          'UNRESOLVED_GLOBAL_LFLA',
      },
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
        .setDepth(
          200,
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
