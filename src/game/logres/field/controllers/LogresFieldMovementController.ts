import Phaser from 'phaser'

import {
  findReconstructedLogresFieldPath,
} from '../LogresFieldPathfinder'

import type {
  LogresFieldNavigationTile,
} from '../LogresFieldNavigation'

import {
  nearestLogresPlayableFieldTile,
  projectLogresPlayableFieldTileToRaster,
  type LoadedLogresPlayableFieldRuntime,
  type LogresPlayableFieldRasterTransform,
} from '../LogresPlayableFieldRuntime'

import {
  logresDevMs,
} from '../../LogresDevSettings'

export const LOGRES_RECONSTRUCTED_FIELD_STEP_MS =
  90 as const

export type LogresPlayablePlayer =
  Phaser.GameObjects.GameObject &
  Phaser.GameObjects.Components.Transform

export class LogresFieldMovementController {
  private readonly scene:
    Phaser.Scene

  private readonly isLocked:
    () => boolean

  private runtimeValue:
    LoadedLogresPlayableFieldRuntime | null =
      null

  private transformValue:
    Readonly<LogresPlayableFieldRasterTransform> | null =
      null

  private playerValue:
    LogresPlayablePlayer | null =
      null

  private currentTileValue:
    Readonly<LogresFieldNavigationTile> | null =
      null

  private moveTween:
    Phaser.Tweens.Tween | null =
      null

  constructor(
    scene:
      Phaser.Scene,
    isLocked:
      () => boolean,
  ) {
    this.scene =
      scene

    this.isLocked =
      isLocked
  }

  get runtime() {
    return this.runtimeValue
  }

  get transform() {
    return this.transformValue
  }

  get player() {
    return this.playerValue
  }

  get currentTile() {
    return this.currentTileValue
  }

  bind(
    runtime:
      LoadedLogresPlayableFieldRuntime,
    transform:
      Readonly<LogresPlayableFieldRasterTransform>,
    player:
      LogresPlayablePlayer,
    currentTile:
      Readonly<LogresFieldNavigationTile>,
  ) {
    this.runtimeValue =
      runtime

    this.transformValue =
      transform

    this.playerValue =
      player

    this.currentTileValue =
      currentTile

    this.scene.registry.set(
      'logres.playableField.movementTiming',
      `RECONSTRUCTED_${LOGRES_RECONSTRUCTED_FIELD_STEP_MS}MS_PER_GRAPH_STEP`,
    )

    this.syncRegistry()
  }

  bindPointerInput() {
    const onPointerDown =
      (
        pointer:
          Phaser.Input.Pointer,
      ) => {
        this.movePlayerToPointer(
          pointer,
        )
      }

    this.scene.input.on(
      'pointerdown',
      onPointerDown,
    )

    this.scene.events.once(
      Phaser.Scenes.Events.SHUTDOWN,
      () => {
        this.scene.input.off(
          'pointerdown',
          onPointerDown,
        )

        this.stop()
      },
    )
  }

  movePlayerToPointer(
    pointer:
      Phaser.Input.Pointer,
  ) {
    if (
      this.isLocked() ||
      !this.runtimeValue ||
      !this.transformValue ||
      !this.currentTileValue ||
      !this.playerValue
    ) {
      return
    }

    const target =
      nearestLogresPlayableFieldTile(
        pointer.worldX,
        pointer.worldY,
        this.runtimeValue
          .movement
          .tiles,
        this.transformValue,
      )

    if (!target) {
      return
    }

    const path =
      findReconstructedLogresFieldPath(
        this.currentTileValue,
        target,
        this.runtimeValue
          .movement
          .tileAt,
      )

    if (
      !path ||
      path.coords.length <=
        1
    ) {
      return
    }

    this.stop()

    this.walkPath(
      path.coords,
      1,
    )
  }

  stop() {
    this.moveTween
      ?.stop()

    this.moveTween =
      null
  }

  walkPath(
    coords:
      readonly Readonly<{
        col: number
        row: number
      }>[],
    index: number,
    onComplete?:
      () => void,
  ) {
    if (
      !this.runtimeValue ||
      !this.transformValue ||
      !this.playerValue
    ) {
      return
    }

    if (
      index >=
      coords.length
    ) {
      this.moveTween =
        null

      onComplete?.()

      return
    }

    const coord =
      coords[
        index
      ]!

    const tile =
      this.runtimeValue
        .movement
        .tileAt(
          coord.col,
          coord.row,
        )

    if (!tile) {
      return
    }

    const point =
      projectLogresPlayableFieldTileToRaster(
        tile,
        this.transformValue,
      )

    this.moveTween =
      this.scene.tweens.add({
        targets:
          this.playerValue,

        x:
          point.x,

        y:
          point.y,

        duration:
          logresDevMs(
            LOGRES_RECONSTRUCTED_FIELD_STEP_MS,
          ),

        ease:
          'Linear',

        onComplete:
          () => {
            this.currentTileValue =
              tile

            this.syncRegistry()

            this.walkPath(
              coords,
              index +
                1,
              onComplete,
            )
          },
      })
  }

  private syncRegistry() {
    if (
      !this.currentTileValue
    ) {
      return
    }

    this.scene.registry.set(
      'logres.playableField.currentCoord',
      {
        col:
          this.currentTileValue
            .col,
        row:
          this.currentTileValue
            .row,
        level:
          this.currentTileValue
            .level,
      },
    )
  }
}
