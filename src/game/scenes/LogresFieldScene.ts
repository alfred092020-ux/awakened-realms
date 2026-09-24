import Phaser from 'phaser'

import {
  LogresFieldActorController,
} from '../logres/field/controllers/LogresFieldActorController'

import {
  LogresFieldEncounterController,
} from '../logres/field/controllers/LogresFieldEncounterController'

import {
  LogresFieldCameraController,
} from '../logres/field/controllers/LogresFieldCameraController'

import {
  LogresFieldHudController,
} from '../logres/field/controllers/LogresFieldHudController'

import {
  LogresFieldMovementController,
} from '../logres/field/controllers/LogresFieldMovementController'

import {
  LogresFieldNpcDialogueController,
} from '../logres/field/controllers/LogresFieldNpcDialogueController'

import {
  LogresFieldRenderController,
} from '../logres/field/controllers/LogresFieldRenderController'

import {
  preloadLogresAssets,
} from '../logres/ui/LogresRuntimeAssets'

export class LogresFieldScene
  extends Phaser.Scene {
  private readonly actorController:
    LogresFieldActorController

  private readonly cameraController:
    LogresFieldCameraController

  private readonly encounterController:
    LogresFieldEncounterController

  private readonly hudController:
    LogresFieldHudController

  private readonly movementController:
    LogresFieldMovementController

  private readonly npcDialogueController:
    LogresFieldNpcDialogueController

  private readonly renderController:
    LogresFieldRenderController

  constructor() {
    super('LogresFieldScene')

    this.actorController =
      new LogresFieldActorController(
        this,
      )

    this.cameraController =
      new LogresFieldCameraController(
        this,
      )

    this.hudController =
      new LogresFieldHudController(
        this,
      )

    this.movementController =
      new LogresFieldMovementController(
        this,
        () =>
          (
            this.encounterController
              .isApproachActive ||
            this.npcDialogueController
              .blocksMovement
          ),
      )

    this.encounterController =
      new LogresFieldEncounterController(
        this,
        this.movementController,
      )

    this.npcDialogueController =
      new LogresFieldNpcDialogueController(
        this,
        this.movementController,
      )

    this.renderController =
      new LogresFieldRenderController(
        this,
      )
  }

  get playableEncounterMarker() {
    return this.actorController
      .marker
  }

  get playablePlayer() {
    return this.actorController
      .player
  }

  get playableNpcMarker() {
    return this.actorController
      .npc
  }

  get playableNpcDialogueSurface() {
    return this.npcDialogueController
      .dialogueSurface
  }

  preload() {
    preloadLogresAssets(this)

    this.actorController
      .preload()

    this.renderController
      .preload()

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
    this.renderController
      .createFallbackBackdrop()

    this.cameraController
      .applyInitialSettings()

    this.hudController
      .create()

    void this.initializePlayableField()
  }

  update() {
    this.hudController.update()
    this.npcDialogueController.update()
  }

  private async initializePlayableField() {
    const surface =
      await this.renderController
        .initialize()

    if (!surface) {
      return
    }

    const {
      runtime,
      transform,
      spawnPoint,
    } = surface

    const player =
      this.actorController
        .createPlayer(
          spawnPoint,
          transform,
        )

    this.movementController
      .bind(
        runtime,
        transform,
        player,
        runtime.spawn,
      )

    this.cameraController
      .bindPlayableWorld(
        transform.width,
        transform.height,
        spawnPoint.x,
        spawnPoint.y,
        player,
      )

    const encounterTile =
      this.actorController
        .createEncounterMarker(
          this.movementController,
          () => {
            this.encounterController
              .approach()
          },
        )

    this.encounterController
      .bindEncounterTile(
        encounterTile,
      )

    const npcTile =
      this.actorController
        .createNpcMarker(
          this.movementController,
          encounterTile,
          () => {
            this.npcDialogueController
              .approach()
          },
        )

    this.npcDialogueController
      .bindNpcTile(
        npcTile,
      )

    this.movementController
      .bindPointerInput()
  }

}
