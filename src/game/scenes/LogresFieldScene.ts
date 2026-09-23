import Phaser from 'phaser'

import {
  LOGRES_ASSETS,
  preloadLogresAssets,
} from '../logres/ui/LogresRuntimeAssets'

import {
  LOGRES_FIELD_ACTOR_ASSETS,
  preloadLogresFieldActorAssets,
} from '../logres/field/LogresFieldActorRuntimeAssets'

import {
  createTerrainProofRenderer,
} from '../logres/field/LogresTerrainProofRenderer'

import {
  createLogresPlayableFieldRasterTransform,
  loadLogresPlayableFieldRuntime,
  LOGRES_PLAYABLE_FIELD_MAP_ID,
  nearestLogresPlayableFieldTile,
  projectLogresPlayableFieldTileToRaster,
  type LoadedLogresPlayableFieldRuntime,
  type LogresPlayableFieldRasterTransform,
} from '../logres/field/LogresPlayableFieldRuntime'

import {
  logresRendererCandidateUrls,
} from '../logres/field/LogresRendererCandidate'

import {
  findReconstructedLogresFieldPath,
} from '../logres/field/LogresFieldPathfinder'

import {
  LOGRES_GLOBAL_3024_NATIVE_FIELD_PROVENANCE,
  resolveLogresGlobalMoveTarget,
} from '../logres/field/LogresGlobalNativeFieldEvidence'

import {
  LOGRES_TUTORIAL_GREEN_JELL_IDLE_ANIMATION,
  LOGRES_TUTORIAL_GREEN_JELL_PRESENTATION,
  LOGRES_TUTORIAL_POINTER_OFFSET,
  LOGRES_TUTORIAL_POINTER_PRESENTATION,
} from '../logres/field/LogresFieldActorPresentation'

import {
  LOGRES_PLAYER_ACTOR_PRESENTATION,
  logresPlayerMotionApplication,
  logresPlayerReferenceSex,
  readLogresPlayerGenderFromCharacterCreateRequest,
} from '../logres/field/LogresPlayerActorPresentation'

import {
  LOGRES_PLAYER_ACTOR_ASSETS,
  preloadLogresPlayerActorAssets,
} from '../logres/field/LogresPlayerActorRuntimeAssets'

import {
  ReconstructedLogresEncounterAuthority,
} from '../logres/encounter/ReconstructedLogresEncounterAuthority'

import {
  ReconstructedLogresBattleEntryBridge,
} from '../logres/encounter/ReconstructedLogresBattleEntryBridge'

import type {
  LogresFieldNavigationTile,
} from '../logres/field/LogresFieldNavigation'

import {
  logresDevMs,
} from '../logres/LogresDevSettings'

import {
  LOGRES_TUTORIAL_HUD_RUNTIME_SELECTION,
  LOGRES_TUTORIAL_PARAMETER_BAR_PLACEMENT,
  LOGRES_TUTORIAL_QUEST_START_HIDE_EVENT,
  LOGRES_TUTORIAL_QUEST_START_REJECTED_EVENT,
  LOGRES_TUTORIAL_QUEST_START_SHOW_EVENT,
  resolveLogresTutorialQuestStartPlacement,
  type LogresTutorialQuestStartPlacement,
} from '../logres/tutorial/LogresTutorialHudRuntime'

interface EquipmentUiSettings {
  skill_equip_max_normal?:
    number

  skill_equip_group_gap?:
    number
}

interface BattleTexts {
  skill_view?: {
    default_offset?:
      [number, number]
  }
}

interface FieldSettings {
  initial_view_scale?:
    number

  resource_path?: {
    default_background_image?:
      string
  }
}

const PLAYABLE_FIELD_CHIP_TEXTURE_KEY =
  'logres-playable-field-chip'

const PLAYABLE_FIELD_OBJECT_TEXTURE_KEY =
  'logres-playable-field-object'

const PLAYABLE_FIELD_RASTER_TEXTURE_KEY =
  'logres-playable-field-raster'

const RECONSTRUCTED_FIELD_STEP_MS =
  90

const TUTORIAL_GREEN_JELL_IDLE_ANIMATION_KEY =
  'logres-tutorial-green-jell-idle'

export class LogresFieldScene
  extends Phaser.Scene {
  private tutorialParameterBar:
    Phaser.GameObjects.Image | null =
      null

  private fallbackBackdrop:
    Phaser.GameObjects.TileSprite | null =
      null

  private playableFieldRuntime:
    LoadedLogresPlayableFieldRuntime | null =
      null

  private playableFieldTransform:
    Readonly<LogresPlayableFieldRasterTransform> | null =
      null

  private playablePlayer:
    | Phaser.GameObjects.Image
    | Phaser.GameObjects.Arc
    | null =
      null

  private playableCurrentTile:
    Readonly<LogresFieldNavigationTile> | null =
      null

  private playableMoveTween:
    Phaser.Tweens.Tween | null =
      null

  private playableEncounterTile:
    Readonly<LogresFieldNavigationTile> | null =
      null

  private playableEncounterMarker:
    | Phaser.GameObjects.Sprite
    | Phaser.GameObjects.Arc
    | null =
      null

  private playableEncounterApproachActive =
    false

  private tutorialQuestStartLayer:
    Phaser.GameObjects.Container | null =
      null

  private tutorialQuestStartPlacement:
    Readonly<LogresTutorialQuestStartPlacement> | null =
      null

  constructor() {
    super('LogresFieldScene')
  }

  preload() {
    preloadLogresAssets(this)
    preloadLogresFieldActorAssets(this)
    preloadLogresPlayerActorAssets(this)

    const playableFieldUrls =
      logresRendererCandidateUrls(
        LOGRES_PLAYABLE_FIELD_MAP_ID,
      )

    this.load.image(
      PLAYABLE_FIELD_CHIP_TEXTURE_KEY,
      playableFieldUrls.chipPng,
    )

    this.load.image(
      PLAYABLE_FIELD_OBJECT_TEXTURE_KEY,
      playableFieldUrls.objPng,
    )

    this.load.json(
      'logres-equipment-settings',
      '/__logres_ref/config/japanese/equipment_ui_settings.json',
    )

    this.load.json(
      'logres-battle-settings',
      '/__logres_ref/config/japanese/battle_texts.json',
    )

    this.load.json(
      'logres-field-settings',
      '/__logres_ref/config/japanese/field_settings.json',
    )

    /*
     * Player-facing language always comes
     * from the translated Global client
     * when an equivalent file exists.
     */
    this.load.json(
      'logres-equip-tutorial-en',
      '/__logres_ref/config/global/equip_tutorial_texts.json',
    )

    this.load.json(
      'logres-equipment-text-en',
      '/__logres_ref/config/global/equipment_texts.json',
    )

    this.load.json(
      'logres-quest-text-en',
      '/__logres_ref/config/global/quest_texts.json',
    )

    this.load.json(
      'logres-chat-text-en',
      '/__logres_ref/config/global/chat_text.json',
    )

    this.load.json(
      'logres-inventory-text-en',
      '/__logres_ref/config/global/inventory_text.json',
    )
  }

  create() {
    const {
      width,
      height,
    } = this.scale

    /*
     * The default field background specified by
     * field_settings.json was not present inside
     * the captured package.
     *
     * Strict mode therefore does NOT fabricate
     * a replacement field asset.
     *
     * This backdrop is an actual extracted
     * Logres client texture used only so the
     * reconstruction screen is visible.
     */
    this.fallbackBackdrop =
      this.add
        .tileSprite(
          width / 2,
          height / 2,
          width,
          height,
          LOGRES_ASSETS
            .titleBackground
            .key,
        )

    const equipment =
      this.cache.json.get(
        'logres-equipment-settings',
      ) as
        EquipmentUiSettings |
        undefined

    const battle =
      this.cache.json.get(
        'logres-battle-settings',
      ) as
        BattleTexts |
        undefined

    const field =
      this.cache.json.get(
        'logres-field-settings',
      ) as
        FieldSettings |
        undefined

    /*
     * All values below come directly from
     * extracted Logres JSON.
     */
    const skillCount =
      equipment
        ?.skill_equip_max_normal ??
      0

    const gap =
      equipment
        ?.skill_equip_group_gap ??
      0

    const offset =
      battle
        ?.skill_view
        ?.default_offset ??
      [0, 0]

    const source =
      this.textures
        .get(
          LOGRES_ASSETS
            .skillBase
            .key,
        )
        .getSourceImage() as
        HTMLImageElement

    const iconWidth =
      source.width

    const totalWidth =
      skillCount > 0
        ? (
            skillCount *
              iconWidth +
            (
              skillCount -
              1
            ) *
              gap
          )
        : 0

    const startX =
      width / 2 -
      totalWidth / 2 +
      iconWidth / 2 +
      offset[0]

    const y =
      height / 2 +
      offset[1]

    for (
      let index = 0;
      index < skillCount;
      index += 1
    ) {
      this.add
        .image(
          startX +
            index *
              (
                iconWidth +
                gap
              ),
          y,
          LOGRES_ASSETS
            .skillBase
            .key,
        )
    }

    const initialViewScale =
      field
        ?.initial_view_scale

    /*
     * field_settings.json supplies the
     * original client's initial field view
     * scale. Apply it directly when present
     * rather than inventing a fallback value.
     */
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

    /*
     * Read and retain actual field values.
     * We do not invent missing world data.
     */
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

    this.createTutorialHud()

    this.registry.set(
      'logres.playableField.status',
      'LOADING',
    )

    void this.initializePlayableField()
  }

  update() {
    this.syncTutorialHudToCamera()
  }

  private async initializePlayableField() {
    try {
      const runtime =
        await loadLogresPlayableFieldRuntime()

      if (
        !this.scene.isActive()
      ) {
        return
      }

      const chipSource =
        this.textures
          .get(
            PLAYABLE_FIELD_CHIP_TEXTURE_KEY,
          )
          .getSourceImage() as
          HTMLImageElement

      const objectSource =
        this.textures
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

      /*
       * Phaser CanvasTexture requires a 2D canvas. The terrain proof owns a
       * WebGL context, and browsers do not allow that same canvas to acquire a
       * second 2D context. Preserve the rendered frame into a separate 2D
       * canvas before registering it with Phaser.
       */
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
        this.textures.exists(
          PLAYABLE_FIELD_RASTER_TEXTURE_KEY,
        )
      ) {
        this.textures.remove(
          PLAYABLE_FIELD_RASTER_TEXTURE_KEY,
        )
      }

      const texture =
        this.textures.addCanvas(
          PLAYABLE_FIELD_RASTER_TEXTURE_KEY,
          rasterCanvas,
        )

      if (!texture) {
        renderer.dispose()

        throw new Error(
          'Unable to create playable field raster texture',
        )
      }

      this.add
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

      this.playableFieldRuntime =
        runtime

      this.playableFieldTransform =
        transform

      this.playableCurrentTile =
        runtime.spawn

      const spawnPoint =
        projectLogresPlayableFieldTileToRaster(
          runtime.spawn,
          transform,
        )

      const playerGender =
        readLogresPlayerGenderFromCharacterCreateRequest(
          this.registry.get(
            'logres.protocol.C_GMCL_CHAR_CREATE_REQ',
          ),
        )

      const referenceSex =
        playerGender ===
          null
          ? null
          : logresPlayerReferenceSex(
              playerGender,
            )

      const referenceAsset =
        referenceSex ===
          'f'
          ? LOGRES_PLAYER_ACTOR_ASSETS
              .female
          : LOGRES_PLAYER_ACTOR_ASSETS
              .male

      const hasRecoveredPlayerPresentation =
        referenceSex !==
          null &&
        this.textures.exists(
          referenceAsset
            .key,
        )

      if (
        hasRecoveredPlayerPresentation &&
        playerGender !==
          null
      ) {
        this.playablePlayer =
          this.add
            .image(
              spawnPoint.x,
              spawnPoint.y,
              referenceAsset
                .key,
            )
            .setOrigin(
              0.5,
              1,
            )
            .setScale(
              transform.fit,
            )
            .setDepth(
              900,
            )

        this.registry.set(
          'logres.playableField.playerVisualPresentation',
          {
            mode:
              'RECOVERED_REFERENCE_ART',

            gender:
              playerGender,

            referenceSex,

            ...LOGRES_PLAYER_ACTOR_PRESENTATION,

            motionApplication:
              logresPlayerMotionApplication(
                playerGender,
              ),

            scaleSource:
              'PLAYABLE_FIELD_TRANSFORM_FIT',

            anchor:
              'BOTTOM_CENTER_NAVIGATION_TILE',
          },
        )
      } else {
        this.playablePlayer =
          this.add
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

        this.registry.set(
          'logres.playableField.playerVisualPresentation',
          {
            mode:
              'PLACEHOLDER_FALLBACK',

            reason:
              playerGender ===
                null
                ? 'CHARACTER_CREATE_GENDER_UNAVAILABLE'
                : 'PRIVATE_REFERENCE_ASSET_UNAVAILABLE',
          },
        )
      }

      this.cameras.main
        .setBounds(
          0,
          0,
          transform.width,
          transform.height,
        )
        .centerOn(
          spawnPoint.x,
          spawnPoint.y,
        )
        .startFollow(
          this.playablePlayer,
          true,
          0.12,
          0.12,
        )

      this.createReconstructedEncounterMarker()

      const onPointerDown =
        (
          pointer:
            Phaser.Input.Pointer,
        ) => {
          this.movePlayablePlayerToPointer(
            pointer,
          )
        }

      this.input.on(
        'pointerdown',
        onPointerDown,
      )

      this.events.once(
        Phaser.Scenes.Events.SHUTDOWN,
        () => {
          this.input.off(
            'pointerdown',
            onPointerDown,
          )

          this.playableMoveTween
            ?.stop()

          this.playableMoveTween =
            null
        },
      )

      this.registry.set(
        'logres.playableField.status',
        'READY',
      )

      this.registry.set(
        'logres.playableField.mapId',
        runtime.mapId,
      )

      this.registry.set(
        'logres.playableField.mapBindingProvenance',
        runtime.mapBindingProvenance,
      )

      this.registry.set(
        'logres.playableField.projectionEvidence',
        runtime.projectionEvidence,
      )

      this.registry.set(
        'logres.playableField.movementSurfaceComplete',
        runtime.movement
          .movementSurfaceComplete,
      )

      this.registry.set(
        'logres.playableField.tileCount',
        runtime.movement
          .tiles
          .length,
      )

      this.registry.set(
        'logres.playableField.spawnProvenance',
        'RECONSTRUCTED',
      )

      this.registry.set(
        'logres.playableField.movementTiming',
        `RECONSTRUCTED_${RECONSTRUCTED_FIELD_STEP_MS}MS_PER_GRAPH_STEP`,
      )

      this.registry.set(
        'logres.playableField.moveDestinationResolver',
        LOGRES_GLOBAL_3024_NATIVE_FIELD_PROVENANCE,
      )

      this.syncPlayableFieldRegistry()
    } catch (
      error
    ) {
      if (
        !this.scene.isActive()
      ) {
        return
      }

      const message =
        error instanceof
          Error
          ? error.message
          : String(
              error,
            )

      this.registry.set(
        'logres.playableField.status',
        'FALLBACK',
      )

      this.registry.set(
        'logres.playableField.error',
        message,
      )

      console.warn(
        'Playable recovered field unavailable; retaining fallback field',
        message,
      )
    }
  }

  private movePlayablePlayerToPointer(
    pointer:
      Phaser.Input.Pointer,
  ) {
    if (
      this.playableEncounterApproachActive ||
      !this.playableFieldRuntime ||
      !this.playableFieldTransform ||
      !this.playableCurrentTile ||
      !this.playablePlayer
    ) {
      return
    }

    const requestedTarget =
      nearestLogresPlayableFieldTile(
        pointer.worldX,
        pointer.worldY,
        this.playableFieldRuntime
          .movement
          .tiles,
        this.playableFieldTransform,
        true,
      )

    if (!requestedTarget) {
      return
    }

    const destinationResolution =
      resolveLogresGlobalMoveTarget(
        this.playableCurrentTile,
        requestedTarget,
        this.playableFieldRuntime
          .movement
          .tileAt,
      )

    if (!destinationResolution) {
      return
    }

    const target =
      destinationResolution
        .resolved

    this.registry.set(
      'logres.playableField.lastMoveDestinationResolution',
      {
        provenance:
          destinationResolution
            .provenance,

        requested:
          destinationResolution
            .requested,

        resolved: {
          col:
            target.col,

          row:
            target.row,
        },

        usedFallback:
          destinationResolution
            .usedFallback,
      },
    )

    const path =
      findReconstructedLogresFieldPath(
        this.playableCurrentTile,
        target,
        this.playableFieldRuntime
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

    this.playableMoveTween
      ?.stop()

    this.playableMoveTween =
      null

    this.walkPlayablePath(
      path.coords,
      1,
    )
  }

  private walkPlayablePath(
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
      !this.playableFieldRuntime ||
      !this.playableFieldTransform ||
      !this.playablePlayer
    ) {
      return
    }

    if (
      index >=
      coords.length
    ) {
      this.playableMoveTween =
        null

      onComplete?.()

      return
    }

    const coord =
      coords[
        index
      ]!

    const tile =
      this.playableFieldRuntime
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
        this.playableFieldTransform,
      )

    this.playableMoveTween =
      this.tweens.add({
        targets:
          this.playablePlayer,

        x:
          point.x,

        y:
          point.y,

        duration:
          logresDevMs(
            RECONSTRUCTED_FIELD_STEP_MS,
          ),

        ease:
          'Linear',

        onComplete:
          () => {
            this.playableCurrentTile =
              tile

            this.syncPlayableFieldRegistry()

            this.walkPlayablePath(
              coords,
              index +
                1,
              onComplete,
            )
          },
      })
  }

  private createReconstructedEncounterMarker() {
    if (
      !this.playableFieldRuntime ||
      !this.playableFieldTransform ||
      !this.playableCurrentTile
    ) {
      return
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
        this.playableFieldRuntime
          .movement
          .tileAt(
            this.playableCurrentTile
              .col +
              colOffset,
            this.playableCurrentTile
              .row +
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
          this.playableCurrentTile,
          candidate,
          this.playableFieldRuntime
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
          ...this.playableFieldRuntime
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
                  this.playableCurrentTile
                    ?.col ||
                tile.row !==
                  this.playableCurrentTile
                    ?.row
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
                    this.playableCurrentTile!
                      .col,
                ) +
                Math.abs(
                  left.row -
                    this.playableCurrentTile!
                      .row,
                )

              const rightDistance =
                Math.abs(
                  right.col -
                    this.playableCurrentTile!
                      .col,
                ) +
                Math.abs(
                  right.row -
                    this.playableCurrentTile!
                      .row,
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
            this.playableCurrentTile,
            candidate,
            this.playableFieldRuntime
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
      this.registry.set(
        'logres.playableField.encounterStatus',
        'UNAVAILABLE',
      )

      return
    }

    this.playableEncounterTile =
      selected

    const point =
      projectLogresPlayableFieldTileToRaster(
        selected,
        this.playableFieldTransform,
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
      this.textures.exists(
        LOGRES_FIELD_ACTOR_ASSETS
          .tutorialTapPointer
          .key,
      ) &&
      recoveredEnemyKeys.every(
        (
          key,
        ) =>
          this.textures.exists(
            key,
          ),
      )

    if (
      hasRecoveredPresentation
    ) {
      if (
        !this.anims.exists(
          TUTORIAL_GREEN_JELL_IDLE_ANIMATION_KEY,
        )
      ) {
        this.anims.create({
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

      const actorScale =
        this.playableFieldTransform
          .fit

      const encounterSprite =
        this.add
          .sprite(
            point.x,
            point.y -
              14,
            LOGRES_FIELD_ACTOR_ASSETS
              .tutorialGreenJellIdle0
              .key,
          )
          .setScale(
            actorScale,
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

      this.playableEncounterMarker =
        encounterSprite

      const pointer =
        this.add
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

      this.tweens.add({
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

      this.registry.set(
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
      this.playableEncounterMarker =
        this.add
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

      this.add
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

      this.registry.set(
        'logres.playableField.encounterVisualPresentation',
        {
          mode:
            'RECONSTRUCTED_FALLBACK',
        },
      )
    }

    this.playableEncounterMarker.on(
      'pointerdown',
      () => {
        this.approachReconstructedEncounter()
      },
    )

    this.registry.set(
      'logres.playableField.encounterStatus',
      'READY',
    )

    this.registry.set(
      'logres.playableField.encounterProvenance',
      'RECONSTRUCTED',
    )

    this.registry.set(
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
  }

  private approachReconstructedEncounter() {
    if (
      this.playableEncounterApproachActive ||
      !this.playableFieldRuntime ||
      !this.playableCurrentTile ||
      !this.playableEncounterTile
    ) {
      return
    }

    const path =
      findReconstructedLogresFieldPath(
        this.playableCurrentTile,
        this.playableEncounterTile,
        this.playableFieldRuntime
          .movement
          .tileAt,
      )

    if (!path) {
      return
    }

    this.playableEncounterApproachActive =
      true

    this.playableMoveTween
      ?.stop()

    this.playableMoveTween =
      null

    this.walkPlayablePath(
      path.coords,
      1,
      () => {
        this.launchReconstructedEncounter()
      },
    )
  }

  private launchReconstructedEncounter() {
    if (
      !this.playableEncounterTile
    ) {
      this.playableEncounterApproachActive =
        false

      return
    }

    const encounter =
      new ReconstructedLogresEncounterAuthority({
        encounterKey:
          'reconstructed-tutorial-field-encounter',

        areaRef:
          null,

        symbolRef:
          null,

        mapPosition:
          null,

        rawEntryState:
          null,

        eligibility: {
          globalEncounterAllowed:
            true,

          encounterEnabled:
            true,

          entryStateEligible:
            true,

          questAllowsEncounter:
            true,

          distanceEligible:
            true,
        },
      })

    const bridge =
      new ReconstructedLogresBattleEntryBridge(
        encounter,
      )

    const intent =
      bridge.requestEntry()

    const launch =
      bridge.recordBattleInitialized({
        battleSystemRef:
          null,

        battleKit: {
          weaponPanels: [
            {
              unlocked:
                true,

              weaponRef:
                'reconstructed-tutorial-weapon',

              normalSkillRef:
                'reconstructed-normal-attack',

              specialSkillRef:
                null,

              specialEpCost:
                null,
            },
          ],

          selectedWeaponSlot:
            0,

          currentEp:
            0,

          epCap:
            null,
        },
      })

    this.registry.set(
      'logres.playableField.encounterIntent',
      intent,
    )

    this.registry.set(
      'logres.playableField.encounterAuthority',
      encounter.snapshot(),
    )

    this.registry.set(
      'logres.playableField.battleLaunchProvenance',
      launch.provenance,
    )

    this.registry.set(
      'logres.playableField.battleKitIdentityProvenance',
      'RECONSTRUCTED_LOCAL_IDENTIFIERS',
    )

    this.scene.start(
      launch.sceneKey,
      launch.sceneData,
    )
  }

  private syncPlayableFieldRegistry() {
    if (
      !this.playableCurrentTile
    ) {
      return
    }

    this.registry.set(
      'logres.playableField.currentCoord',
      {
        col:
          this.playableCurrentTile
            .col,
        row:
          this.playableCurrentTile
            .row,
        level:
          this.playableCurrentTile
            .level,
      },
    )
  }

  private createTutorialHud() {
    this.tutorialParameterBar =
      this.add
        .image(
          0,
          0,
          LOGRES_ASSETS
            .tutorialParameterBar
            .key,
        )
        .setDepth(
          1000,
        )

    const questBackground =
      this.add
        .image(
          0,
          0,
          LOGRES_ASSETS
            .tutorialQuestStartBackground
            .key,
        )

    const questText =
      this.add
        .image(
          0,
          0,
          LOGRES_ASSETS
            .tutorialQuestStartText
            .key,
        )

    this.tutorialQuestStartLayer =
      this.add
        .container(
          0,
          0,
          [
            questBackground,
            questText,
          ],
        )
        .setDepth(
          1010,
        )
        .setVisible(
          false,
        )

    const showQuestStart =
      (
        placementValue:
          unknown,
      ) => {
        try {
          this.tutorialQuestStartPlacement =
            resolveLogresTutorialQuestStartPlacement(
              placementValue,
            )

          this.tutorialQuestStartLayer
            ?.setVisible(
              true,
            )

          this.syncTutorialHudToCamera()
        } catch (
          error
        ) {
          this.events.emit(
            LOGRES_TUTORIAL_QUEST_START_REJECTED_EVENT,
            {
              message:
                error instanceof
                  Error
                  ? error.message
                  : String(
                      error,
                    ),
            },
          )
        }
      }

    const hideQuestStart =
      () => {
        this.tutorialQuestStartPlacement =
          null

        this.tutorialQuestStartLayer
          ?.setVisible(
            false,
          )
      }

    this.events.on(
      LOGRES_TUTORIAL_QUEST_START_SHOW_EVENT,
      showQuestStart,
    )

    this.events.on(
      LOGRES_TUTORIAL_QUEST_START_HIDE_EVENT,
      hideQuestStart,
    )

    this.events.once(
      Phaser.Scenes.Events.SHUTDOWN,
      () => {
        this.events.off(
          LOGRES_TUTORIAL_QUEST_START_SHOW_EVENT,
          showQuestStart,
        )

        this.events.off(
          LOGRES_TUTORIAL_QUEST_START_HIDE_EVENT,
          hideQuestStart,
        )
      },
    )

    this.registry.set(
      'logres.tutorialHud.parameterBar.sourceSha256',
      LOGRES_TUTORIAL_HUD_RUNTIME_SELECTION
        .parameterBar
        .sourceSha256,
    )

    this.registry.set(
      'logres.tutorialHud.parameterBar.placementEvidence',
      LOGRES_TUTORIAL_PARAMETER_BAR_PLACEMENT
        .evidenceLabel,
    )

    this.registry.set(
      'logres.tutorialHud.questStart.positioning',
      'EXPLICIT_CALLER_PLACEMENT_UNTIL_LFLA_TRANSFORM_IS_DECODED',
    )

    this.syncTutorialHudToCamera()
  }

  private syncTutorialHudToCamera() {
    const camera =
      this.cameras.main

    const zoom =
      camera.zoom

    if (
      !Number.isFinite(
        zoom,
      ) ||
      zoom <= 0
    ) {
      return
    }

    if (
      this.tutorialParameterBar
    ) {
      const worldPoint =
        camera.getWorldPoint(
          LOGRES_TUTORIAL_PARAMETER_BAR_PLACEMENT
            .x,
          LOGRES_TUTORIAL_PARAMETER_BAR_PLACEMENT
            .y,
        )

      this.tutorialParameterBar
        .setPosition(
          worldPoint.x,
          worldPoint.y,
        )
        .setScale(
          1 /
            zoom,
        )
    }

    if (
      this.tutorialQuestStartLayer &&
      this.tutorialQuestStartPlacement
    ) {
      const worldPoint =
        camera.getWorldPoint(
          this.tutorialQuestStartPlacement
            .centerX,
          this.tutorialQuestStartPlacement
            .centerY,
        )

      this.tutorialQuestStartLayer
        .setPosition(
          worldPoint.x,
          worldPoint.y,
        )
        .setScale(
          1 /
            zoom,
        )
    }
  }
}
