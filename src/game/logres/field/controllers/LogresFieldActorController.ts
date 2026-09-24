import Phaser from 'phaser'

import {
  LOGRES_FIELD_ACTOR_ASSETS,
} from '../LogresFieldActorRuntimeAssets'

import {
  LOGRES_TUTORIAL_GREEN_JELL_IDLE_ANIMATION,
  LOGRES_TUTORIAL_GREEN_JELL_PRESENTATION,
  LOGRES_TUTORIAL_POINTER_OFFSET,
  LOGRES_TUTORIAL_POINTER_PRESENTATION,
} from '../LogresFieldActorPresentation'

import {
  findReconstructedLogresFieldPath,
} from '../LogresFieldPathfinder'

import {
  projectLogresPlayableFieldTileToRaster,
} from '../LogresPlayableFieldRuntime'

import type {
  LogresFieldNavigationTile,
} from '../LogresFieldNavigation'

import {
  logresDevMs,
} from '../../LogresDevSettings'

import type {
  LogresFieldMovementController,
  LogresPlayablePlayer,
} from './LogresFieldMovementController'

const TUTORIAL_GREEN_JELL_IDLE_ANIMATION_KEY =
  'logres-tutorial-green-jell-idle'

export class LogresFieldActorController {
  private readonly scene:
    Phaser.Scene

  private encounterMarker:
    | Phaser.GameObjects.Sprite
    | Phaser.GameObjects.Arc
    | null =
      null

  constructor(
    scene:
      Phaser.Scene,
  ) {
    this.scene =
      scene
  }

  get marker() {
    return this.encounterMarker
  }

  createPlayer(
    spawnPoint:
      Readonly<{
        x: number
        y: number
      }>,
  ): LogresPlayablePlayer {
    return this.scene.add
      .circle(
        spawnPoint.x,
        spawnPoint.y,
        12,
        0xffffff,
        0.95,
      )
      .setStrokeStyle(
        3,
        0x111111,
        1,
      )
      .setDepth(
        900,
      )
  }

  createEncounterMarker(
    movement:
      LogresFieldMovementController,
    onActivate:
      () => void,
  ): Readonly<LogresFieldNavigationTile> | null {
    const runtime =
      movement.runtime

    const transform =
      movement.transform

    const currentTile =
      movement.currentTile

    if (
      !runtime ||
      !transform ||
      !currentTile
    ) {
      return null
    }

    const offsets =
      [
        [3, -3],
        [4, 0],
        [0, 4],
        [-3, 3],
        [-4, 0],
        [0, -4],
      ] as const

    let selected:
      Readonly<LogresFieldNavigationTile> | null =
        null

    for (
      const [
        colOffset,
        rowOffset,
      ]
      of offsets
    ) {
      const candidate =
        runtime
          .movement
          .tileAt(
            currentTile.col +
              colOffset,
            currentTile.row +
              rowOffset,
          )

      if (
        !candidate ||
        candidate.prohibited
      ) {
        continue
      }

      const path =
        findReconstructedLogresFieldPath(
          currentTile,
          candidate,
          runtime
            .movement
            .tileAt,
        )

      if (
        path &&
        path.coords.length >
          1
      ) {
        selected =
          candidate

        break
      }
    }

    if (!selected) {
      const sorted =
        [
          ...runtime
            .movement
            .tiles,
        ]
          .filter(
            (
              tile,
            ) =>
              !tile.prohibited &&
              (
                tile.col !==
                  currentTile.col ||
                tile.row !==
                  currentTile.row
              ),
          )
          .sort(
            (
              left,
              right,
            ) => {
              const leftDistance =
                Math.abs(
                  left.col -
                    currentTile.col,
                ) +
                Math.abs(
                  left.row -
                    currentTile.row,
                )

              const rightDistance =
                Math.abs(
                  right.col -
                    currentTile.col,
                ) +
                Math.abs(
                  right.row -
                    currentTile.row,
                )

              return (
                leftDistance -
                rightDistance
              )
            },
          )

      for (
        const candidate
        of sorted.slice(
          0,
          64,
        )
      ) {
        const path =
          findReconstructedLogresFieldPath(
            currentTile,
            candidate,
            runtime
              .movement
              .tileAt,
          )

        if (
          path &&
          path.coords.length >
            1
        ) {
          selected =
            candidate

          break
        }
      }
    }

    if (!selected) {
      this.scene.registry.set(
        'logres.playableField.encounterStatus',
        'UNAVAILABLE',
      )

      return null
    }

    const point =
      projectLogresPlayableFieldTileToRaster(
        selected,
        transform,
      )

    const recoveredEnemyKeys = [
      LOGRES_FIELD_ACTOR_ASSETS
        .tutorialGreenJellIdle0
        .key,
      LOGRES_FIELD_ACTOR_ASSETS
        .tutorialGreenJellIdle1
        .key,
      LOGRES_FIELD_ACTOR_ASSETS
        .tutorialGreenJellIdle2
        .key,
      LOGRES_FIELD_ACTOR_ASSETS
        .tutorialGreenJellIdle3
        .key,
    ] as const

    const hasRecoveredPresentation =
      this.scene.textures.exists(
        LOGRES_FIELD_ACTOR_ASSETS
          .tutorialTapPointer
          .key,
      ) &&
      recoveredEnemyKeys.every(
        (
          key,
        ) =>
          this.scene.textures.exists(
            key,
          ),
      )

    if (
      hasRecoveredPresentation
    ) {
      if (
        !this.scene.anims.exists(
          TUTORIAL_GREEN_JELL_IDLE_ANIMATION_KEY,
        )
      ) {
        this.scene.anims.create({
          key:
            TUTORIAL_GREEN_JELL_IDLE_ANIMATION_KEY,

          frames:
            recoveredEnemyKeys.map(
              (
                key,
              ) => ({
                key,
              }),
            ),

          frameRate:
            LOGRES_TUTORIAL_GREEN_JELL_IDLE_ANIMATION
              .frameRate,

          repeat:
            LOGRES_TUTORIAL_GREEN_JELL_IDLE_ANIMATION
              .repeat,
        })
      }

      const encounterSprite =
        this.scene.add
          .sprite(
            point.x,
            point.y -
              14,
            LOGRES_FIELD_ACTOR_ASSETS
              .tutorialGreenJellIdle0
              .key,
          )
          .setScale(
            transform.fit,
          )
          .setDepth(
            905,
          )
          .setInteractive(
            new Phaser.Geom.Rectangle(
              -35,
              -35,
              140,
              122,
            ),
            Phaser.Geom.Rectangle.Contains,
          )

      encounterSprite.play(
        TUTORIAL_GREEN_JELL_IDLE_ANIMATION_KEY,
      )

      this.encounterMarker =
        encounterSprite

      const pointer =
        this.scene.add
          .image(
            point.x +
              LOGRES_TUTORIAL_POINTER_OFFSET
                .x,
            point.y +
              LOGRES_TUTORIAL_POINTER_OFFSET
                .y,
            LOGRES_FIELD_ACTOR_ASSETS
              .tutorialTapPointer
              .key,
          )
          .setOrigin(
            0.5,
            1,
          )
          .setScale(
            LOGRES_TUTORIAL_POINTER_OFFSET
              .scale,
          )
          .setDepth(
            906,
          )

      this.scene.tweens.add({
        targets:
          pointer,

        y:
          pointer.y -
          6,

        duration:
          logresDevMs(
            500,
          ),

        yoyo:
          true,

        repeat:
          -1,

        ease:
          'Sine.InOut',
      })

      this.scene.registry.set(
        'logres.playableField.encounterVisualPresentation',
        {
          mode:
            'RECOVERED_REFERENCE_ART',

          enemy:
            LOGRES_TUTORIAL_GREEN_JELL_PRESENTATION,

          pointer:
            LOGRES_TUTORIAL_POINTER_PRESENTATION,
        },
      )
    } else {
      this.encounterMarker =
        this.scene.add
          .circle(
            point.x,
            point.y,
            19,
            0xf59e0b,
            0.95,
          )
          .setStrokeStyle(
            4,
            0x3b1f00,
            1,
          )
          .setDepth(
            905,
          )
          .setInteractive({
            useHandCursor:
              true,
          })

      this.scene.add
        .text(
          point.x,
          point.y -
            2,
          '!',
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize:
              '28px',
            color:
              '#ffffff',
            fontStyle:
              'bold',
          },
        )
        .setOrigin(
          0.5,
          0.5,
        )
        .setDepth(
          906,
        )

      this.scene.registry.set(
        'logres.playableField.encounterVisualPresentation',
        {
          mode:
            'RECONSTRUCTED_FALLBACK',
        },
      )
    }

    this.encounterMarker.on(
      'pointerdown',
      onActivate,
    )

    this.scene.registry.set(
      'logres.playableField.encounterStatus',
      'READY',
    )

    this.scene.registry.set(
      'logres.playableField.encounterProvenance',
      'RECONSTRUCTED',
    )

    this.scene.registry.set(
      'logres.playableField.encounterCoord',
      {
        col:
          selected.col,
        row:
          selected.row,
        level:
          selected.level,
      },
    )

    return selected
  }
}
