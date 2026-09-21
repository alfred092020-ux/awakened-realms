import Phaser from 'phaser'

import {
  LOGRES_ASSETS,
  preloadLogresAssets,
} from '../logres/ui/LogresRuntimeAssets'

interface FieldSettings {
  initial_view_scale?:
    number

  resource_path?: {
    default_background_image?:
      string
  }
}

export class LogresFieldScene
  extends Phaser.Scene {
  private player?:
    Phaser.GameObjects.Image

  constructor() {
    super('LogresFieldScene')
  }

  preload() {
    preloadLogresAssets(
      this,
    )

    this.load.json(
      'logres-field-settings',
      '/__logres_ref/config/japanese/field_settings.json',
    )

    /*
     * Player-facing language remains sourced
     * from the translated Global client.
     */
    this.load.json(
      'logres-quest-text-en',
      '/__logres_ref/config/global/quest_texts.json',
    )

    this.load.json(
      'logres-chat-text-en',
      '/__logres_ref/config/global/chat_text.json',
    )
  }

  create() {
    const {
      width,
      height,
    } = this.scale

    /*
     * Extracted Global client field artwork.
     *
     * The exact historical map background
     * referenced by field_settings.json is
     * not present in the captured package,
     * so this is explicitly a reconstruction
     * test field rather than a fabricated map.
     */
    this.add
      .image(
        width / 2,
        height / 2,
        LOGRES_ASSETS
          .fieldBackdrop
          .key,
      )
      .setDisplaySize(
        1810,
        1280,
      )

    const field =
      this.cache.json.get(
        'logres-field-settings',
      ) as
        FieldSettings |
        undefined

    const initialViewScale =
      field
        ?.initial_view_scale

    if (
      typeof initialViewScale ===
        'number' &&
      Number.isFinite(
        initialViewScale,
      ) &&
      initialViewScale > 0
    ) {
      this.cameras.main.setZoom(
        initialViewScale,
      )
    }

    this.registry.set(
      'logres.field.initialViewScale',
      initialViewScale,
    )

    this.registry.set(
      'logres.field.defaultBackgroundImage',
      field
        ?.resource_path
        ?.default_background_image,
    )

    this.registry.set(
      'logres.reconstruction.field',
      'RECONSTRUCTED_TEST_FIELD',
    )

    this.player =
      this.add
        .image(
          width * 0.30,
          height * 0.66,
          LOGRES_ASSETS
            .fieldPlayer
            .key,
        )
        .setDisplaySize(
          126,
          180,
        )
        .setDepth(10)

    const enemy =
      this.add
        .image(
          width * 0.75,
          height * 0.40,
          LOGRES_ASSETS
            .fieldEnemyMandora
            .key,
        )
        .setScale(1.35)
        .setDepth(10)
        .setInteractive({
          useHandCursor:
            true,
        })

    enemy.on(
      'pointerdown',
      () => {
        this.registry.set(
          'logres.reconstruction.encounter',
          'RECONSTRUCTED',
        )

        this.scene.start(
          'LogresBattleScene',
        )
      },
    )

    /*
     * RECONSTRUCTED CLIENT GLUE
     *
     * Exact historical movement tuning is
     * not present in the extracted evidence.
     * For this testable slice, a tap directly
     * places the reconstructed player marker
     * at the tapped field coordinate. No fake
     * movement speed or server movement value
     * is introduced.
     */
    this.input.on(
      'pointerdown',
      (
        pointer:
          Phaser.Input.Pointer,
      ) => {
        if (
          !this.player ||
          !this.scene.isActive()
        ) {
          return
        }

        this.player.setPosition(
          Phaser.Math.Clamp(
            pointer.worldX,
            90,
            width - 90,
          ),
          Phaser.Math.Clamp(
            pointer.worldY,
            140,
            height - 160,
          ),
        )

        this.registry.set(
          'logres.reconstruction.fieldMovement',
          'RECONSTRUCTED_DIRECT_TAP',
        )
      },
    )

    this.add
      .text(
        18,
        18,
        'RECONSTRUCTED FIELD TEST',
        {
          fontFamily:
            'sans-serif',

          fontSize:
            '16px',

          color:
            '#ffffff',

          backgroundColor:
            '#00000099',

          padding: {
            x: 8,
            y: 5,
          },
        },
      )
      .setScrollFactor(0)
      .setDepth(100)
  }
}
