import type Phaser from 'phaser'

interface FieldSettings {
  initial_view_scale?:
    number

  resource_path?: {
    default_background_image?:
      string
  }
}

export class LogresFieldCameraController {
  private readonly scene:
    Phaser.Scene

  constructor(
    scene:
      Phaser.Scene,
  ) {
    this.scene =
      scene
  }

  applyInitialSettings() {
    const field =
      this.scene.cache.json.get(
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
      this.scene.cameras.main.setZoom(
        initialViewScale,
      )
    }

    this.scene.registry.set(
      'logres.field.initialViewScale',
      initialViewScale,
    )

    this.scene.registry.set(
      'logres.field.defaultBackgroundImage',
      field
        ?.resource_path
        ?.default_background_image,
    )
  }

  bindPlayableWorld(
    width: number,
    height: number,
    spawnX: number,
    spawnY: number,
    player:
      Phaser.GameObjects.GameObject &
      Phaser.GameObjects.Components.Transform,
  ) {
    this.scene.cameras.main
      .setBounds(
        0,
        0,
        width,
        height,
      )
      .centerOn(
        spawnX,
        spawnY,
      )
      .startFollow(
        player,
        true,
        0.12,
        0.12,
      )
  }
}
