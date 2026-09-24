import Phaser from 'phaser'

import {
  LOGRES_ASSETS,
} from '../../ui/LogresRuntimeAssets'

import {
  createTerrainProofRenderer,
} from '../LogresTerrainProofRenderer'

import {
  createLogresPlayableFieldRasterTransform,
  loadLogresPlayableFieldRuntime,
  LOGRES_PLAYABLE_FIELD_MAP_ID,
  projectLogresPlayableFieldTileToRaster,
  type LoadedLogresPlayableFieldRuntime,
  type LogresPlayableFieldRasterTransform,
} from '../LogresPlayableFieldRuntime'

import {
  logresRendererCandidateUrls,
} from '../LogresRendererCandidate'

const PLAYABLE_FIELD_CHIP_TEXTURE_KEY =
  'logres-playable-field-chip'

const PLAYABLE_FIELD_OBJECT_TEXTURE_KEY =
  'logres-playable-field-object'

const PLAYABLE_FIELD_RASTER_TEXTURE_KEY =
  'logres-playable-field-raster'

export interface LogresPlayableFieldSurface {
  readonly runtime:
    LoadedLogresPlayableFieldRuntime

  readonly transform:
    Readonly<LogresPlayableFieldRasterTransform>

  readonly spawnPoint: {
    readonly x: number
    readonly y: number
  }
}

export class LogresFieldRenderController {
  private readonly scene:
    Phaser.Scene

  private fallbackBackdrop:
    Phaser.GameObjects.TileSprite | null =
      null

  constructor(
    scene:
      Phaser.Scene,
  ) {
    this.scene =
      scene
  }

  preload() {
    const playableFieldUrls =
      logresRendererCandidateUrls(
        LOGRES_PLAYABLE_FIELD_MAP_ID,
      )

    this.scene.load.image(
      PLAYABLE_FIELD_CHIP_TEXTURE_KEY,
      playableFieldUrls.chipPng,
    )

    this.scene.load.image(
      PLAYABLE_FIELD_OBJECT_TEXTURE_KEY,
      playableFieldUrls.objPng,
    )
  }

  createFallbackBackdrop() {
    const {
      width,
      height,
    } = this.scene.scale

    this.fallbackBackdrop =
      this.scene.add
        .tileSprite(
          width / 2,
          height / 2,
          width,
          height,
          LOGRES_ASSETS
            .titleBackground
            .key,
        )
  }

  async initialize():
    Promise<LogresPlayableFieldSurface | null> {
    this.scene.registry.set(
      'logres.playableField.status',
      'LOADING',
    )

    try {
      const runtime =
        await loadLogresPlayableFieldRuntime()

      if (
        !this.scene.scene.isActive()
      ) {
        return null
      }

      const chipSource =
        this.scene.textures
          .get(
            PLAYABLE_FIELD_CHIP_TEXTURE_KEY,
          )
          .getSourceImage() as
          HTMLImageElement

      const objectSource =
        this.scene.textures
          .get(
            PLAYABLE_FIELD_OBJECT_TEXTURE_KEY,
          )
          .getSourceImage() as
          HTMLImageElement

      if (
        !chipSource ||
        !objectSource
      ) {
        throw new Error(
          'Recovered field atlases are unavailable',
        )
      }

      const canvas =
        document.createElement(
          'canvas',
        )

      canvas.width =
        1536

      canvas.height =
        1536

      const renderer =
        createTerrainProofRenderer(
          canvas,
          runtime.mesh,
          {
            chip:
              chipSource,
            obj:
              objectSource,
          },
        )

      renderer.render(
        false,
        'both',
        1,
        0,
        0,
      )

      const transform =
        createLogresPlayableFieldRasterTransform(
          runtime.mesh,
          canvas.width,
          canvas.height,
        )

      const rasterCanvas =
        document.createElement(
          'canvas',
        )

      rasterCanvas.width =
        canvas.width

      rasterCanvas.height =
        canvas.height

      const rasterContext =
        rasterCanvas.getContext(
          '2d',
        )

      if (!rasterContext) {
        renderer.dispose()

        throw new Error(
          'Unable to create 2D playable field raster context',
        )
      }

      rasterContext.drawImage(
        canvas,
        0,
        0,
      )

      if (
        this.scene.textures.exists(
          PLAYABLE_FIELD_RASTER_TEXTURE_KEY,
        )
      ) {
        this.scene.textures.remove(
          PLAYABLE_FIELD_RASTER_TEXTURE_KEY,
        )
      }

      const texture =
        this.scene.textures.addCanvas(
          PLAYABLE_FIELD_RASTER_TEXTURE_KEY,
          rasterCanvas,
        )

      if (!texture) {
        renderer.dispose()

        throw new Error(
          'Unable to create playable field raster texture',
        )
      }

      this.scene.add
        .image(
          0,
          0,
          PLAYABLE_FIELD_RASTER_TEXTURE_KEY,
        )
        .setOrigin(
          0,
          0,
        )
        .setDepth(
          -100,
        )

      renderer.dispose()

      this.fallbackBackdrop
        ?.destroy()

      this.fallbackBackdrop =
        null

      const spawnPoint =
        projectLogresPlayableFieldTileToRaster(
          runtime.spawn,
          transform,
        )

      this.scene.registry.set(
        'logres.playableField.status',
        'READY',
      )

      this.scene.registry.set(
        'logres.playableField.mapId',
        runtime.mapId,
      )

      this.scene.registry.set(
        'logres.playableField.mapBindingProvenance',
        runtime.mapBindingProvenance,
      )

      this.scene.registry.set(
        'logres.playableField.projectionEvidence',
        runtime.projectionEvidence,
      )

      this.scene.registry.set(
        'logres.playableField.movementSurfaceComplete',
        runtime.movement
          .movementSurfaceComplete,
      )

      this.scene.registry.set(
        'logres.playableField.tileCount',
        runtime.movement
          .tiles
          .length,
      )

      this.scene.registry.set(
        'logres.playableField.spawnProvenance',
        'RECONSTRUCTED',
      )

      return Object.freeze({
        runtime,
        transform,
        spawnPoint:
          Object.freeze({
            x:
              spawnPoint.x,
            y:
              spawnPoint.y,
          }),
      })
    } catch (
      error
    ) {
      if (
        !this.scene.scene.isActive()
      ) {
        return null
      }

      const message =
        error instanceof
          Error
          ? error.message
          : String(
              error,
            )

      this.scene.registry.set(
        'logres.playableField.status',
        'FALLBACK',
      )

      this.scene.registry.set(
        'logres.playableField.error',
        message,
      )

      console.warn(
        'Playable recovered field unavailable; retaining fallback field',
        message,
      )

      return null
    }
  }
}
