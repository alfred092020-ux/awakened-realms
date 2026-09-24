import Phaser from 'phaser'

import {
  createLogresBattlePresentation,
} from '../logres/battle/LogresBattlePresentation'

import {
  createLogresBattleStagePresentation,
  type LogresBattleStagePresentation,
} from '../logres/battle/LogresBattleStagePresentation'

import {
  hasRecoveredLogresBattleStageAssets,
  LOGRES_BATTLE_GREEN_JELL_IDLE_ANIMATION_KEY,
  LOGRES_BATTLE_STAGE_ASSETS,
} from '../logres/battle/LogresBattleStageRuntimeAssets'

import {
  LOGRES_TUTORIAL_GREEN_JELL_IDLE_ANIMATION,
} from '../logres/field/LogresFieldActorPresentation'

import {
  LogresGlobalBattleKit,
  type LogresGlobalBattleKitInput,
} from '../logres/battle/LogresGlobalBattleKit'

import {
  LOGRES_ASSETS,
  preloadLogresAssets,
} from '../logres/ui/LogresRuntimeAssets'

import {
  completeReconstructedPlayableBattle,
  LOGRES_PLAYABLE_BATTLE_COMPLETION_PROVENANCE,
  LOGRES_PLAYABLE_BATTLE_FIELD_RETURN_SCENE_KEY,
} from '../logres/battle/ReconstructedLogresPlayableBattleCompletion'

import type {
  ReconstructedLogresInventoryState,
} from '../logres/server/LogresInventoryAuthority'

export interface LogresBattleSceneData
  extends Partial<LogresGlobalBattleKitInput> {}

export class LogresBattleScene
  extends Phaser.Scene {
  private presentation:
    ReturnType<typeof createLogresBattlePresentation> | null = null

  private stagePresentation:
    LogresBattleStagePresentation | null =
      null

  private battleKit:
    LogresGlobalBattleKit | null =
      null

  private weaponCover:
    Phaser.GameObjects.Image | null =
      null

  private epText:
    Phaser.GameObjects.Text | null =
      null

  private demoStatusText:
    Phaser.GameObjects.Text | null =
      null

  private demoResolveButton:
    Phaser.GameObjects.Text | null =
      null

  private normalAttackButton:
    Phaser.GameObjects.Text | null =
      null

  private demoReturnButton:
    Phaser.GameObjects.Text | null =
      null

  constructor() {
    super(
      'LogresBattleScene',
    )
  }

  preload() {
    preloadLogresAssets(
      this,
    )
  }

  init(
    data: LogresBattleSceneData,
  ) {
    // Phaser reuses this scene after field return. Old display references
    // must not suppress the next harness result/return controls.
    this.weaponCover = null
    this.epText = null
    this.demoStatusText = null
    this.demoResolveButton = null
    this.normalAttackButton = null
    this.demoReturnButton = null
    this.presentation = null
    this.stagePresentation = null

    this.battleKit =
      new LogresGlobalBattleKit({
        weaponPanels:
          data.weaponPanels ??
          [],
        selectedWeaponSlot:
          data.selectedWeaponSlot ??
          null,
        currentEp:
          data.currentEp ??
          0,
        epCap:
          data.epCap ??
          null,
      })
  }

  create() {
    if (
      this.battleKit ===
      null
    ) {
      throw new Error(
        'Battle kit was not initialized',
      )
    }

    this.cameras.main
      .setBackgroundColor(
        0x101010,
      )

    this.presentation = createLogresBattlePresentation(
      this.battleKit.snapshot(),
      window.location.search,
    )
    this.registry.set('logres.battle.presentation', this.presentation)
    // An old synthetic result must never describe a new live battle.
    for (const key of [
      'logres.demo01.resolution',
      'logres.demo01.rewardApplied',
      'logres.playableBattle.resolution',
      'logres.playableBattle.rewardApplied',
      'logres.playableBattle.fieldReturn',
      'logres.playableBattle.completion',
    ]) {
      this.registry.remove(key)
    }
    this.registry.set('logres.demo01.battleStatus', 'ACTIVE')
    this.registry.set('logres.demo01.battleProvenance', 'RECONSTRUCTED')
    this.registry.set('logres.playableBattle.battleStatus', 'ACTIVE')
    this.registry.set(
      'logres.playableBattle.battleProvenance',
      LOGRES_PLAYABLE_BATTLE_COMPLETION_PROVENANCE,
    )

    this.createBattleStage()

    const spacing =
      112

    const firstX =
      this.scale.width / 2 -
      spacing * 2

    const y =
      this.scale.height -
      150

    this.presentation.weaponPanels
      .forEach(
        (
          panel,
          index,
        ) => {
            const image =
              this.add
                .image(
                  firstX +
                    index *
                      spacing,
                  y,
                  LOGRES_ASSETS
                    .skillBase
                    .key,
                )
                .setScale(
                  2.25,
                )
                .setAlpha(
                  panel.unlocked &&
                    panel.weaponRef !==
                      null
                    ? 1
                    : 0.35,
                )

            if (
              panel.unlocked &&
              panel.weaponRef !==
                null
            ) {
              image
                .setInteractive({
                  useHandCursor:
                    true,
                })
                .on(
                  'pointerup',
                  () => {
                    this.activateSpecial(
                      index,
                    )
                  },
                )
            }

          },
        )

    this.weaponCover =
      this.add
        .image(
          firstX,
          y,
          LOGRES_ASSETS
            .battleWeaponCover
            .key,
        )
        .setScale(
          1.45,
        )
        .setDepth(
          10,
        )
        .setInteractive({
          useHandCursor:
            true,
          draggable:
            true,
        })

    this.input
      .setDraggable(
        this.weaponCover,
      )

    this.weaponCover.on(
      'drag',
      (
        _pointer:
          Phaser.Input.Pointer,
        dragX: number,
      ) => {
        if (
          this.weaponCover ===
          null
        ) {
          return
        }

        this.weaponCover.x =
          Phaser.Math.Clamp(
            dragX,
            firstX,
            firstX +
              spacing * 4,
          )
      },
    )

    this.weaponCover.on(
      'dragend',
      () => {
        this.finishWeaponSlide(
          firstX,
          spacing,
          y,
        )
      },
    )

    this.epText =
      this.add
        .text(
          this.scale.width -
            36,
          y -
            90,
          '',
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize:
              '28px',
            color:
              '#ffffff',
          },
        )
        .setOrigin(
          1,
          0.5,
        )

    this.syncVisualState(
      firstX,
      spacing,
      y,
    )

    this.events.on('logres-request-normal-attack', this.emitNormalAttack, this)
    this.events.once(Phaser.Scenes.Events.SHUTDOWN, () => {
      this.events.off('logres-request-normal-attack', this.emitNormalAttack, this)
    })

    this.createBattleStatusLabel()
    if (!this.presentation.showDemoControls) {
      this.createNormalAttackButton()
    }
    if (this.presentation.showDemoControls) {
      this.createDemo01ResolutionControls()
    }
  }

  private createBattleStage() {
    const recoveredReferenceArtAvailable =
      hasRecoveredLogresBattleStageAssets(
        this,
      )

    this.stagePresentation =
      createLogresBattleStagePresentation(
        this.scale.width,
        this.scale.height,
        this.registry.get(
          'logres.protocol.C_GMCL_CHAR_CREATE_REQ',
        ),
        recoveredReferenceArtAvailable,
      )

    this.registry.set(
      'logres.battle.stagePresentation',
      this.stagePresentation,
    )

    const {
      ground,
      player,
      enemy,
      referenceSex,
    } =
      this.stagePresentation

    /*
     * No Global 3.0.24 battle-background texture is being asserted here.
     * These low-depth shapes only provide visual stage context while the
     * original background-resource binding remains unresolved.
     */
    this.add
      .rectangle(
        ground.x,
        ground.y,
        ground.width,
        ground.height,
        0x17231f,
        0.96,
      )
      .setDepth(
        -100,
      )

    this.add
      .ellipse(
        ground.x,
        ground.y +
          ground.height *
            0.31,
        ground.width *
          0.86,
        ground.height *
          0.28,
        0x31483d,
        0.52,
      )
      .setDepth(
        -90,
      )

    this.add
      .ellipse(
        player.x,
        player.y +
          4,
        112,
        28,
        0x000000,
        0.4,
      )
      .setDepth(
        -20,
      )

    this.add
      .ellipse(
        enemy.x,
        enemy.y +
          4,
        126,
        30,
        0x000000,
        0.4,
      )
      .setDepth(
        -20,
      )

    if (
      recoveredReferenceArtAvailable
    ) {
      const playerAsset =
        referenceSex ===
          'f'
          ? LOGRES_BATTLE_STAGE_ASSETS
              .playerFemale
          : LOGRES_BATTLE_STAGE_ASSETS
              .playerMale

      this.add
        .image(
          player.x,
          player.y,
          playerAsset.key,
        )
        .setOrigin(
          player.anchorX,
          player.anchorY,
        )
        .setScale(
          player.scale,
        )
        .setDepth(
          -10,
        )

      if (
        !this.anims.exists(
          LOGRES_BATTLE_GREEN_JELL_IDLE_ANIMATION_KEY,
        )
      ) {
        this.anims.create({
          key:
            LOGRES_BATTLE_GREEN_JELL_IDLE_ANIMATION_KEY,

          frames:
            LOGRES_BATTLE_STAGE_ASSETS
              .enemyIdleFrames
              .map(
                (
                  asset,
                ) => ({
                  key:
                    asset.key,
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

      this.add
        .sprite(
          enemy.x,
          enemy.y,
          LOGRES_BATTLE_STAGE_ASSETS
            .enemyIdleFrames[
              0
            ]
            .key,
        )
        .setOrigin(
          enemy.anchorX,
          enemy.anchorY,
        )
        .setScale(
          enemy.scale,
        )
        .setDepth(
          -10,
        )
        .play(
          LOGRES_BATTLE_GREEN_JELL_IDLE_ANIMATION_KEY,
        )

      return
    }

    /*
     * Clean/public verification intentionally has no private derivatives.
     * Keep the stage non-empty without claiming these silhouettes as Logres
     * artwork.
     */
    this.add
      .rectangle(
        player.x,
        player.y,
        52,
        112,
        0x7895a4,
        0.9,
      )
      .setOrigin(
        player.anchorX,
        player.anchorY,
      )
      .setDepth(
        -10,
      )

    this.add
      .ellipse(
        enemy.x,
        enemy.y -
          36,
        112,
        82,
        0x6c9b65,
        0.9,
      )
      .setDepth(
        -10,
      )
  }

  private createBattleStatusLabel() {
    this.demoStatusText =
      this.add
        .text(
          24,
          24,
          this.presentation?.showDemoControls
            ? 'DEMO 0.1 • RECONSTRUCTED BATTLE'
            : 'RECONSTRUCTED BATTLE',
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize:
              '20px',
            color:
              '#ffffff',
            backgroundColor:
              '#000000aa',
            padding: {
              x:
                12,
              y:
                8,
            },
          },
        )
        .setDepth(
          100,
        )

  }

  private createDemo01ResolutionControls() {
    this.demoResolveButton =
      this.add
        .text(
          this.scale.width /
            2,
          92,
          'RESOLVE DEMO BATTLE',
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize:
              '24px',
            color:
              '#ffffff',
            backgroundColor:
              '#263238',
            padding: {
              x:
                18,
              y:
                12,
            },
          },
        )
        .setOrigin(
          0.5,
        )
        .setDepth(
          100,
        )
        .setInteractive({
          useHandCursor:
            true,
        })
        .on(
          'pointerup',
          () => {
            this.resolveDemo01Battle()
          },
        )
  }

  private createNormalAttackButton() {
    this.normalAttackButton =
      this.add
        .text(
          this.scale.width /
            2,
          92,
          'NORMAL ATTACK',
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize:
              '24px',
            color:
              '#ffffff',
            backgroundColor:
              '#37474f',
            padding: {
              x:
                18,
              y:
                12,
            },
          },
        )
        .setOrigin(
          0.5,
        )
        .setDepth(
          100,
        )
        .setInteractive({
          useHandCursor:
            true,
        })
        .on(
          'pointerup',
          () => {
            this.events.emit(
              'logres-request-normal-attack',
            )
          },
        )
  }

  private resolveDemo01Battle() {
    if (
      !this.presentation?.showDemoControls ||
      this.registry.get('logres.demo01.battleStatus') !== 'ACTIVE'
    ) {
      return
    }

    const result =
      completeReconstructedPlayableBattle({
        inventory:
          this.readPlayableBattleInventory(),
      })

    this.storeCompletedBattle(
      result,
      'HARNESS_DEMO_CONTROL',
    )
  }

  applyNormalAttackHit(
    epGain: number,
  ) {
    if (
      this.battleKit ===
      null
    ) {
      return
    }

    this.battleKit
      .recordNormalAttackHit(
        epGain,
      )

    this.syncEpText()
  }

  private activateSpecial(
    slotIndex: number,
  ) {
    if (
      this.battleKit ===
      null
    ) {
      return
    }

    try {
      const command =
        this.battleKit
          .tapWeaponPanel(
            slotIndex,
          )

      this.events.emit(
        'logres-battle-command',
        command,
      )

      this.syncEpText()
    } catch {
      this.events.emit(
        'logres-battle-command-rejected',
        {
          type:
            'special-skill',
          weaponSlot:
            slotIndex,
        },
      )
    }
  }

  private emitNormalAttack() {
    if (
      this.battleKit ===
      null
    ) {
      return
    }

    try {
      const command =
        this.battleKit
          .createNormalAttack()

      this.events.emit(
        'logres-battle-command',
        command,
      )

      if (
        this.registry.get(
          'logres.playableBattle.battleStatus',
        ) ===
        'ACTIVE'
      ) {
        this.storeCompletedBattle(
          completeReconstructedPlayableBattle({
            inventory:
              this.readPlayableBattleInventory(),
          }),
          'PLAYABLE_COMMAND_NORMAL_ATTACK',
        )
      }
    } catch {
      this.events.emit(
        'logres-battle-command-rejected',
        {
          type:
            'normal-attack',
        },
      )
    }
  }

  private readPlayableBattleInventory():
    | Readonly<ReconstructedLogresInventoryState>
    | undefined {
    return (
      this.registry.get(
        'logres.playableBattle.inventory',
      ) as
        | Readonly<ReconstructedLogresInventoryState>
        | undefined
    ) ??
      (this.registry.get(
        'logres.demo01.inventory',
      ) as
        | Readonly<ReconstructedLogresInventoryState>
        | undefined)
  }

  private storeCompletedBattle(
    result: ReturnType<
      typeof completeReconstructedPlayableBattle
    >,
    trigger:
      | 'HARNESS_DEMO_CONTROL'
      | 'PLAYABLE_COMMAND_NORMAL_ATTACK',
  ) {
    this.registry.set(
      'logres.playableBattle.inventory',
      result.inventory,
    )
    this.registry.set(
      'logres.playableBattle.rewardApplied',
      result.rewardApplied,
    )
    this.registry.set(
      'logres.playableBattle.resolution',
      result.flow,
    )
    this.registry.set(
      'logres.playableBattle.fieldReturn',
      result.fieldReturn,
    )
    this.registry.set(
      'logres.playableBattle.completion',
      {
        provenance:
          result.provenance,
        trigger,
      },
    )
    this.registry.set(
      'logres.playableBattle.battleStatus',
      'FIELD_RETURN_READY',
    )

    this.registry.set(
      'logres.demo01.inventory',
      result.inventory,
    )
    this.registry.set(
      'logres.demo01.rewardApplied',
      result.rewardApplied,
    )
    this.registry.set(
      'logres.demo01.resolution',
      result.flow,
    )
    this.registry.set(
      'logres.demo01.battleStatus',
      'FIELD_RETURN_READY',
    )

    this.demoStatusText
      ?.setText(
        result.rewardApplied
          ? 'VICTORY • RECONSTRUCTED REWARD RECORDED'
          : 'VICTORY • REWARD ALREADY RECORDED',
      )

    this.demoResolveButton
      ?.disableInteractive()
      .setAlpha(
        0.45,
      )
    this.normalAttackButton
      ?.disableInteractive()
      .setAlpha(
        0.45,
      )

    if (
      this.demoReturnButton !==
      null
    ) {
      return
    }

    this.demoReturnButton =
      this.add
        .text(
          this.scale.width /
            2,
          160,
          'RETURN TO MILLENNIUM TREE',
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize:
              '24px',
            color:
              '#ffffff',
            backgroundColor:
              '#1b5e20',
            padding: {
              x:
                18,
              y:
                12,
            },
          },
        )
        .setOrigin(
          0.5,
        )
        .setDepth(
          100,
        )
        .setInteractive({
          useHandCursor:
            true,
        })
        .on(
          'pointerup',
          () => {
            const fieldReturn =
              this.registry.get(
                'logres.playableBattle.fieldReturn',
              ) as
                | {
                    sceneKey: string
                    fieldName: string
                    movementState: string
                  }
                | undefined

            this.registry.set(
              'logres.playableBattle.battleStatus',
              'RETURNING_TO_FIELD',
            )
            this.registry.set(
              'logres.demo01.battleStatus',
              'RETURNING_TO_FIELD',
            )
            this.registry.set(
              'logres.playableField.currentFieldName',
              fieldReturn?.fieldName ??
                'Millennium Tree',
            )
            this.registry.set(
              'logres.playableField.movementState',
              fieldReturn?.movementState ??
                'READY',
            )

            this.scene.start(
              fieldReturn?.sceneKey ??
                LOGRES_PLAYABLE_BATTLE_FIELD_RETURN_SCENE_KEY,
            )
          },
        )
  }

  private finishWeaponSlide(
    firstX: number,
    spacing: number,
    y: number,
  ) {
    if (
      this.battleKit ===
        null ||
      this.weaponCover ===
        null
    ) {
      return
    }

    const rawIndex =
      Math.round(
        (
          this.weaponCover.x -
          firstX
        ) /
          spacing,
      )

    const slotIndex =
      Phaser.Math.Clamp(
        rawIndex,
        0,
        4,
      )

    try {
      this.battleKit
        .slideWeaponMarkerTo(
          slotIndex,
        )

      this.events.emit(
        'logres-battle-weapon-selected',
        slotIndex,
      )
    } catch {
      // Snap back to the last valid selected weapon.
    }

    this.syncVisualState(
      firstX,
      spacing,
      y,
    )
  }

  private syncVisualState(
    firstX: number,
    spacing: number,
    y: number,
  ) {
    if (
      this.battleKit ===
        null ||
      this.weaponCover ===
        null
    ) {
      return
    }

    const {
      selectedWeaponSlot,
    } =
      this.battleKit
        .snapshot()

    this.weaponCover
      .setVisible(
        selectedWeaponSlot !==
          null,
      )

    if (
      selectedWeaponSlot !==
      null
    ) {
      this.weaponCover
        .setPosition(
          firstX +
            selectedWeaponSlot *
              spacing,
          y,
        )
    }

    this.syncEpText()
  }

  private syncEpText() {
    if (
      this.battleKit ===
        null ||
      this.epText ===
        null
    ) {
      return
    }

    this.presentation = createLogresBattlePresentation(
      this.battleKit.snapshot(),
      window.location.search,
    )
    this.registry.set('logres.battle.presentation', this.presentation)
    this.epText.setText(this.presentation.epLabel)
  }
}
