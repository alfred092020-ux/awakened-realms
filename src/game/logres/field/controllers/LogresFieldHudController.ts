import Phaser from 'phaser'

import {
  LOGRES_ASSETS,
} from '../../ui/LogresRuntimeAssets'

import {
  LOGRES_TUTORIAL_HUD_RUNTIME_SELECTION,
  LOGRES_TUTORIAL_PARAMETER_BAR_PLACEMENT,
  LOGRES_TUTORIAL_QUEST_START_HIDE_EVENT,
  LOGRES_TUTORIAL_QUEST_START_REJECTED_EVENT,
  LOGRES_TUTORIAL_QUEST_START_SHOW_EVENT,
  resolveLogresTutorialQuestStartPlacement,
  type LogresTutorialQuestStartPlacement,
} from '../../tutorial/LogresTutorialHudRuntime'

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

export class LogresFieldHudController {
  private readonly scene:
    Phaser.Scene

  private tutorialParameterBar:
    Phaser.GameObjects.Image | null =
      null

  private tutorialQuestStartLayer:
    Phaser.GameObjects.Container | null =
      null

  private tutorialQuestStartPlacement:
    Readonly<LogresTutorialQuestStartPlacement> | null =
      null

  constructor(
    scene:
      Phaser.Scene,
  ) {
    this.scene =
      scene
  }

  create() {
    this.createSkillBar()
    this.createTutorialHud()
  }

  update() {
    this.syncTutorialHudToCamera()
  }

  private createSkillBar() {
    const {
      width,
      height,
    } = this.scene.scale

    const equipment =
      this.scene.cache.json.get(
        'logres-equipment-settings',
      ) as
        EquipmentUiSettings |
        undefined

    const battle =
      this.scene.cache.json.get(
        'logres-battle-settings',
      ) as
        BattleTexts |
        undefined

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
      this.scene.textures
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
      this.scene.add
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
  }

  private createTutorialHud() {
    this.tutorialParameterBar =
      this.scene.add
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
      this.scene.add
        .image(
          0,
          0,
          LOGRES_ASSETS
            .tutorialQuestStartBackground
            .key,
        )

    const questText =
      this.scene.add
        .image(
          0,
          0,
          LOGRES_ASSETS
            .tutorialQuestStartText
            .key,
        )

    this.tutorialQuestStartLayer =
      this.scene.add
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
          this.scene.events.emit(
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

    this.scene.events.on(
      LOGRES_TUTORIAL_QUEST_START_SHOW_EVENT,
      showQuestStart,
    )

    this.scene.events.on(
      LOGRES_TUTORIAL_QUEST_START_HIDE_EVENT,
      hideQuestStart,
    )

    this.scene.events.once(
      Phaser.Scenes.Events.SHUTDOWN,
      () => {
        this.scene.events.off(
          LOGRES_TUTORIAL_QUEST_START_SHOW_EVENT,
          showQuestStart,
        )

        this.scene.events.off(
          LOGRES_TUTORIAL_QUEST_START_HIDE_EVENT,
          hideQuestStart,
        )
      },
    )

    this.scene.registry.set(
      'logres.tutorialHud.parameterBar.sourceSha256',
      LOGRES_TUTORIAL_HUD_RUNTIME_SELECTION
        .parameterBar
        .sourceSha256,
    )

    this.scene.registry.set(
      'logres.tutorialHud.parameterBar.placementEvidence',
      LOGRES_TUTORIAL_PARAMETER_BAR_PLACEMENT
        .evidenceLabel,
    )

    this.scene.registry.set(
      'logres.tutorialHud.questStart.positioning',
      'EXPLICIT_CALLER_PLACEMENT_UNTIL_LFLA_TRANSFORM_IS_DECODED',
    )

    this.syncTutorialHudToCamera()
  }

  private syncTutorialHudToCamera() {
    const camera =
      this.scene.cameras.main

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
