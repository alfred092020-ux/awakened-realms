import Phaser from 'phaser'

import {
  createLogresBattlePresentation,
} from '../logres/battle/LogresBattlePresentation'

import {
  createLogresBattleStagePresentation,
  type LogresBattleStagePresentation,
} from '../logres/battle/LogresBattleStagePresentation'

import {
  hasRecoveredLogresBattleFieldAsset,
  hasRecoveredLogresBattleStageAssets,
  LOGRES_BATTLE_GREEN_JELL_IDLE_ANIMATION_KEY,
  LOGRES_BATTLE_STAGE_ASSETS,
  preloadLogresBattleStageAssets,
} from '../logres/battle/LogresBattleStageRuntimeAssets'

import {
  LOGRES_TUTORIAL_GREEN_JELL_IDLE_ANIMATION,
} from '../logres/field/LogresFieldActorPresentation'

import {
  LogresGlobalBattleKit,
  LOGRES_RECONSTRUCTED_PLAYABILITY_FALLBACK_PROVENANCE,
  type LogresGlobalBattleKitInput,
  type LogresNormalAttackCommand,
  type LogresSpecialSkillCommand,
} from '../logres/battle/LogresGlobalBattleKit'

import {
  LOGRES_ASSETS,
  preloadLogresAssets,
} from '../logres/ui/LogresRuntimeAssets'

import {
  completeReconstructedLogresDemoBattle,
} from '../logres/battle/ReconstructedLogresDemoBattleLoop'

import {
  completeReconstructedLogresPlayableBattle,
} from '../logres/battle/ReconstructedLogresPlayableBattleLoop'

import {
  LOGRES_PLAYABLE_BATTLE_AUTHORITY_PROVENANCE,
  ReconstructedLogresPlayableBattleAuthority,
} from '../logres/replacement-server/ReconstructedLogresPlayableBattleAuthority'

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

  private playableBattleAuthority:
    ReconstructedLogresPlayableBattleAuthority | null =
      null

  private nextPlayableBattleCommandSequence =
    1

  private weaponCover:
    Phaser.GameObjects.Image | null =
      null

  private playerActor:
    | Phaser.GameObjects.Image
    | Phaser.GameObjects.Rectangle
    | null =
      null

  private enemyActor:
    | Phaser.GameObjects.Sprite
    | Phaser.GameObjects.Ellipse
    | null =
      null

  private weaponCoverPointerDown:
    Readonly<{
      x: number
      y: number
    }> | null =
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

    preloadLogresBattleStageAssets(
      this,
    )
  }

  init(
    data: LogresBattleSceneData,
  ) {
    // Phaser reuses this scene after field return. Old display references
    // must not suppress the next harness result/return controls.
    this.weaponCover = null
    this.playerActor = null
    this.enemyActor = null
    this.weaponCoverPointerDown = null
    this.epText = null
    this.demoStatusText = null
    this.demoResolveButton = null
    this.demoReturnButton = null
    this.presentation = null
    this.stagePresentation = null
    this.nextPlayableBattleCommandSequence = 1
    this.playableBattleAuthority =
      new ReconstructedLogresPlayableBattleAuthority()

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

    // Old completion records must never describe a new live battle. Inventory
    // intentionally survives scene restarts so grant-key idempotency persists.
    for (
      const key of [
        'logres.demo01.resolution',
        'logres.demo01.rewardApplied',
        'logres.playableBattle.resolution',
        'logres.playableBattle.rewardApplied',
        'logres.playableBattle.returnIntent',
      ]
    ) {
      this.registry.remove(key)
    }

    this.registry.set('logres.demo01.battleStatus', 'ACTIVE')
    this.registry.set('logres.demo01.battleProvenance', 'RECONSTRUCTED')

    this.registry.set(
      'logres.playableBattle.status',
      'ACTIVE',
    )
    this.registry.set(
      'logres.playableBattle.provenance',
      LOGRES_PLAYABLE_BATTLE_AUTHORITY_PROVENANCE,
    )
    this.registry.set(
      'logres.playableBattle.authority',
      this.playableBattleAuthority?.snapshot() ?? null,
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

    /*
     * The original Global client proves the five weapon-control positions,
     * while their exact retired battle HUD geometry remains unresolved.
     * Keep this backing rail explicitly reconstructed and preserve the
     * recovered skill-base and selector artwork as the interactive layer.
     */
    this.add
      .rectangle(
        this.scale.width / 2,
        y + 8,
        648,
        132,
        0x090d0c,
        0.88,
      )
      .setStrokeStyle(
        2,
        0x8f7a48,
        0.72,
      )
      .setDepth(
        -1,
      )

    this.add
      .rectangle(
        this.scale.width / 2,
        y - 62,
        616,
        2,
        0xd7c486,
        0.45,
      )
      .setDepth(
        0,
      )

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
                    this.activateWeaponPanel(
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
      'pointerdown',
      (
        pointer:
          Phaser.Input.Pointer,
      ) => {
        this.weaponCoverPointerDown =
          Object.freeze({
            x:
              pointer.x,
            y:
              pointer.y,
          })
      },
    )

    this.weaponCover.on(
      'pointerup',
      (
        pointer:
          Phaser.Input.Pointer,
      ) => {
        this.handleWeaponCoverPointerUp(
          pointer,
        )
      },
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

    this.events.on(
      'logres-battle-command',
      this.handlePlayableBattleCommand,
      this,
    )
    this.events.once(Phaser.Scenes.Events.SHUTDOWN, () => {
      this.events.off(
        'logres-battle-command',
        this.handlePlayableBattleCommand,
        this,
      )
    })

    this.createBattleStatusLabel()
    if (this.presentation.showDemoControls) {
      this.createDemo01ResolutionControls()
    }
  }

  private createBattleStage() {
    const recoveredReferenceArtAvailable =
      hasRecoveredLogresBattleStageAssets(
        this,
      )

    const recoveredBattleFieldAvailable =
      hasRecoveredLogresBattleFieldAsset(
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
        recoveredBattleFieldAvailable,
      )

    this.registry.set(
      'logres.battle.stagePresentation',
      this.stagePresentation,
    )

    const {
      background,
      ground,
      player,
      enemy,
      referenceSex,
    } =
      this.stagePresentation

    if (
      background.mode ===
      'CURRENT_JP_CANDIDATE'
    ) {
      this.add
        .image(
          this.scale.width /
            2,
          this.scale.height /
            2,
          LOGRES_BATTLE_STAGE_ASSETS
            .battleFieldCandidate
            .key,
        )
        .setDisplaySize(
          this.scale.width,
          this.scale.height,
        )
        .setDepth(
          -100,
        )
    } else {
      /*
       * Clean/public verification has no recovered battle-field derivative.
       * Keep a bounded non-historical fallback instead of inventing a Global
       * tutorial background selection.
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
    }

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

      this.playerActor =
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

      this.enemyActor =
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
    this.playerActor =
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

    this.enemyActor =
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
            : 'BATTLE',
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

  private resolveDemo01Battle() {
    if (
      !this.presentation?.showDemoControls ||
      this.registry.get('logres.demo01.battleStatus') !== 'ACTIVE'
    ) {
      return
    }

    const existingInventory =
      this.registry.get(
        'logres.demo01.inventory',
      ) as
        | Readonly<ReconstructedLogresInventoryState>
        | undefined

    const result =
      completeReconstructedLogresDemoBattle(
        existingInventory,
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
          ? 'DEMO VICTORY • RECONSTRUCTED REWARD RECORDED'
          : 'DEMO VICTORY • REWARD ALREADY RECORDED',
      )

    this.demoResolveButton
      ?.disableInteractive()
      .setAlpha(
        0.45,
      )

    this.createFieldReturnControl(
      'logres.demo01.battleStatus',
    )
  }

  private handlePlayableBattleCommand(
    command:
      | Readonly<LogresNormalAttackCommand>
      | Readonly<LogresSpecialSkillCommand>,
  ) {
    if (
      this.playableBattleAuthority ===
        null ||
      this.registry.get(
        'logres.playableBattle.status',
      ) !==
        'ACTIVE'
    ) {
      return
    }

    const commandId =
      `playable-battle-command-${this.nextPlayableBattleCommandSequence}`

    this.nextPlayableBattleCommandSequence +=
      1

    const result =
      this.playableBattleAuthority
        .submitCommand({
          commandId,
          command,
        })

    this.registry.set(
      'logres.playableBattle.authority',
      result.snapshot,
    )

    this.playReconstructedCombatFeedback(
      command.type,
    )

    if (
      result.outcome !==
      'victory'
    ) {
      this.demoStatusText
        ?.setText(
          `BATTLE • ${result.snapshot.acceptedCommandCount}/${result.snapshot.victoryThreshold}`,
        )

      return
    }

    this.resolvePlayableBattle()
  }

  private resolvePlayableBattle() {
    if (
      this.registry.get(
        'logres.playableBattle.status',
      ) !==
      'ACTIVE'
    ) {
      return
    }

    const existingInventory =
      this.registry.get(
        'logres.playableBattle.inventory',
      ) as
        | Readonly<ReconstructedLogresInventoryState>
        | undefined

    const result =
      completeReconstructedLogresPlayableBattle(
        existingInventory,
      )

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
      'logres.playableBattle.status',
      'FIELD_RETURN_READY',
    )

    this.registry.set(
      'logres.playableBattle.returnIntent',
      Object.freeze({
        provenance:
          'RECONSTRUCTED' as const,
        sceneKey:
          'LogresFieldScene' as const,
      }),
    )

    this.demoStatusText
      ?.setText(
        result.rewardApplied
          ? 'VICTORY • REWARD RECORDED'
          : 'VICTORY • REWARD ALREADY RECORDED',
      )

    this.playReconstructedVictoryFeedback()

    this.createFieldReturnControl(
      'logres.playableBattle.status',
    )
  }

  private playReconstructedCombatFeedback(
    commandType:
      | 'normal-attack'
      | 'special-skill',
  ) {
    if (
      this.playerActor ===
        null ||
      this.enemyActor ===
        null
    ) {
      return
    }

    this.registry.set(
      'logres.battle.combatFeedbackProvenance',
      'RECONSTRUCTED_PRESENTATION_ONLY',
    )

    const player =
      this.playerActor

    const enemy =
      this.enemyActor

    const playerStartX =
      this.stagePresentation
        ?.player.x ??
      player.x

    const enemyBaseScale =
      this.stagePresentation
        ?.mode ===
        'RECOVERED_REFERENCE_ART'
        ? this.stagePresentation
            .enemy.scale
        : 1

    this.tweens.killTweensOf(
      player,
    )

    this.tweens.killTweensOf(
      enemy,
    )

    player.setX(
      playerStartX,
    )

    enemy
      .setScale(
        enemyBaseScale,
      )
      .setAlpha(
        1,
      )

    this.tweens.add({
      targets:
        player,
      x:
        playerStartX +
        (
          commandType ===
            'special-skill'
            ? 52
            : 34
        ),
      duration:
        commandType ===
          'special-skill'
          ? 120
          : 90,
      ease:
        'Quad.easeOut',
      yoyo:
        true,
    })

    this.tweens.add({
      targets:
        enemy,
      scaleX:
        enemyBaseScale *
        1.12,
      scaleY:
        enemyBaseScale *
        0.9,
      alpha:
        0.68,
      duration:
        90,
      ease:
        'Quad.easeOut',
      yoyo:
        true,
      onComplete:
        () => {
          if (
            this.enemyActor !==
            enemy
          ) {
            return
          }

          enemy
            .setScale(
              enemyBaseScale,
            )
            .setAlpha(
              1,
            )
        },
    })

    const slash =
      this.add
        .graphics()
        .setDepth(
          20,
        )

    slash
      .lineStyle(
        commandType ===
          'special-skill'
          ? 8
          : 5,
        0xffefb0,
        0.9,
      )
      .beginPath()
      .moveTo(
        enemy.x -
          44,
        enemy.y -
          104,
      )
      .lineTo(
        enemy.x +
          42,
        enemy.y -
          28,
      )
      .strokePath()

    this.tweens.add({
      targets:
        slash,
      alpha:
        0,
      duration:
        170,
      ease:
        'Quad.easeOut',
      onComplete:
        () => {
          slash.destroy()
        },
    })

    this.cameras.main.shake(
      90,
      0.0018,
    )
  }

  private playReconstructedVictoryFeedback() {
    if (
      this.enemyActor ===
      null
    ) {
      return
    }

    const enemy =
      this.enemyActor

    const enemyBaseScale =
      this.stagePresentation
        ?.mode ===
        'RECOVERED_REFERENCE_ART'
        ? this.stagePresentation
            .enemy.scale
        : 1

    this.tweens.killTweensOf(
      enemy,
    )

    enemy
      .setScale(
        enemyBaseScale,
      )
      .setAlpha(
        1,
      )

    this.tweens.add({
      targets:
        enemy,
      alpha:
        0.16,
      y:
        enemy.y +
        18,
      scaleX:
        enemyBaseScale *
        0.78,
      scaleY:
        enemyBaseScale *
        0.78,
      duration:
        260,
      ease:
        'Quad.easeIn',
    })
  }

  private createFieldReturnControl(
    statusKey: string,
  ) {
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
            this.registry.set(
              statusKey,
              'RETURNING_TO_FIELD',
            )

            this.scene.start(
              'LogresFieldScene',
            )
          },
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

  private handleWeaponCoverPointerUp(
    pointer:
      Phaser.Input.Pointer,
  ) {
    const pointerDown =
      this.weaponCoverPointerDown

    this.weaponCoverPointerDown =
      null

    if (
      pointerDown ===
        null ||
      Phaser.Math.Distance.Between(
        pointerDown.x,
        pointerDown.y,
        pointer.x,
        pointer.y,
      ) >
        10 ||
      this.battleKit ===
        null
    ) {
      return
    }

    const selectedWeaponSlot =
      this.battleKit
        .snapshot()
        .selectedWeaponSlot

    if (
      selectedWeaponSlot ===
      null
    ) {
      return
    }

    this.activateWeaponPanel(
      selectedWeaponSlot,
    )
  }

  private activateWeaponPanel(
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

      if (
        command.type ===
        'normal-attack'
      ) {
        this.registry.set(
          'logres.playableBattle.inputProvenance',
          LOGRES_RECONSTRUCTED_PLAYABILITY_FALLBACK_PROVENANCE,
        )
      }

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
