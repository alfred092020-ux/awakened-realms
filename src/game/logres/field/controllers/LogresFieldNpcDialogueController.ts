import Phaser from 'phaser'

import {
  LOGRES_NPC_DIALOGUE_EVIDENCE_BOUNDARY,
  LOGRES_RECONSTRUCTED_FIELD_GUIDE_DIALOGUE,
  ReconstructedLogresNpcDialogueAuthority,
} from '../../encounter/ReconstructedLogresNpcDialogueAuthority'

import {
  findReconstructedLogresFieldPath,
} from '../LogresFieldPathfinder'

import type {
  LogresFieldNavigationTile,
} from '../LogresFieldNavigation'

import type {
  LogresFieldMovementController,
} from './LogresFieldMovementController'

export class LogresFieldNpcDialogueController {
  private readonly scene:
    Phaser.Scene

  private readonly movement:
    LogresFieldMovementController

  private readonly authority =
    new ReconstructedLogresNpcDialogueAuthority(
      LOGRES_RECONSTRUCTED_FIELD_GUIDE_DIALOGUE,
    )

  private npcTile:
    Readonly<LogresFieldNavigationTile> | null =
      null

  private approachActiveValue =
    false

  private inputReleasePendingValue =
    false

  private dialogueSurfaceValue:
    Phaser.GameObjects.Container | null =
      null

  private dialogueText:
    Phaser.GameObjects.Text | null =
      null

  private dialogueHint:
    Phaser.GameObjects.Text | null =
      null

  constructor(
    scene:
      Phaser.Scene,
    movement:
      LogresFieldMovementController,
  ) {
    this.scene =
      scene

    this.movement =
      movement
  }

  get isApproachActive() {
    return this.approachActiveValue
  }

  get blocksMovement() {
    return (
      this.approachActiveValue ||
      this.inputReleasePendingValue ||
      this.authority
        .isOpen
    )
  }

  get dialogueSurface() {
    return this.dialogueSurfaceValue
  }

  bindNpcTile(
    tile:
      Readonly<LogresFieldNavigationTile> | null,
  ) {
    this.npcTile =
      tile
  }

  update() {
    this.syncDialogueToCamera()
  }

  approach() {
    const runtime =
      this.movement
        .runtime

    const currentTile =
      this.movement
        .currentTile

    if (
      this.approachActiveValue ||
      this.authority
        .isOpen ||
      !runtime ||
      !currentTile ||
      !this.npcTile
    ) {
      return
    }

    if (
      currentTile.col ===
        this.npcTile.col &&
      currentTile.row ===
        this.npcTile.row &&
      currentTile.level ===
        this.npcTile.level
    ) {
      this.openDialogue()

      return
    }

    const path =
      findReconstructedLogresFieldPath(
        currentTile,
        this.npcTile,
        runtime
          .movement
          .tileAt,
      )

    if (!path) {
      return
    }

    this.approachActiveValue =
      true

    this.scene.registry.set(
      'logres.playableField.npcStatus',
      'APPROACHING',
    )

    this.movement
      .stop()

    this.movement
      .walkPath(
        path.coords,
        1,
        () => {
          this.openDialogue()
        },
      )
  }

  private openDialogue() {
    this.approachActiveValue =
      false

    this.movement
      .stop()

    this.authority
      .bindNpcState({
        characterRef:
          null,
        canTalk:
          true,
        inRange:
          true,
      })

    const intent =
      this.authority
        .requestTalk()

    /*
     * RECONSTRUCTED SERVER-AUTHORITY STUB.
     *
     * Global 3.0.24 proves C_GMCL_CHAR_TALK_REQ, its response
     * handler, NpcDialogueWindow and the talk-gate timing values.
     * The retired response-code meaning and exact dialogue payload
     * are not recovered. Code 0 is therefore only a local stub key:
     * it is not asserted to be an original Global success code.
     */
    const responseStub =
      this.authority
        .openFromReconstructedResponse(
          0,
        )

    this.scene.registry.set(
      'logres.playableField.npcTalkIntent',
      intent,
    )

    this.scene.registry.set(
      'logres.playableField.npcTalkResponseStub',
      responseStub,
    )

    this.scene.registry.set(
      'logres.playableField.npcDialogueEvidence',
      LOGRES_NPC_DIALOGUE_EVIDENCE_BOUNDARY,
    )

    this.scene.registry.set(
      'logres.playableField.npcStatus',
      'DIALOGUE_OPEN',
    )

    this.publishSnapshot()
    this.renderDialogue()
  }

  private renderDialogue() {
    this.destroyDialoguePresentation()

    const snapshot =
      this.authority
        .snapshot()

    if (
      snapshot.phase !==
        'DIALOGUE_OPEN' ||
      !snapshot.currentLine
    ) {
      return
    }

    const width =
      Math.min(
        620,
        Math.max(
          320,
          this.scene
            .scale
            .width -
            36,
        ),
      )

    const height =
      154

    const background =
      this.scene.add
        .rectangle(
          0,
          0,
          width,
          height,
          0x0f172a,
          0.96,
        )
        .setStrokeStyle(
          3,
          0xf8fafc,
          0.92,
        )

    this.dialogueText =
      this.scene.add
        .text(
          -width /
            2 +
            22,
          -height /
            2 +
            24,
          snapshot
            .currentLine,
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize:
              '22px',
            color:
              '#ffffff',
            wordWrap: {
              width:
                width -
                44,
            },
          },
        )

    this.dialogueHint =
      this.scene.add
        .text(
          width /
            2 -
            20,
          height /
            2 -
            18,
          'Tap to continue',
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize:
              '14px',
            color:
              '#cbd5e1',
          },
        )
        .setOrigin(
          1,
          1,
        )

    this.dialogueSurfaceValue =
      this.scene.add
        .container(
          0,
          0,
          [
            background,
            this.dialogueText,
            this.dialogueHint,
          ],
        )
        .setSize(
          width,
          height,
        )
        .setDepth(
          1300,
        )
        .setInteractive(
          new Phaser.Geom.Rectangle(
            -width /
              2,
            -height /
              2,
            width,
            height,
          ),
          Phaser.Geom.Rectangle.Contains,
        )

    this.dialogueSurfaceValue
      .input!
      .cursor =
        'pointer'

    this.dialogueSurfaceValue
      .on(
        'pointerdown',
        () => {
          this.advance()
        },
      )

    this.syncDialogueToCamera()

    this.scene.registry.set(
      'logres.playableField.npcDialoguePresentation',
      {
        mode:
          'RECONSTRUCTED_SCRIPT',
        historicalGlobalDialoguePayload:
          'UNRESOLVED',
        positioning:
          'CAMERA_WORLD_POINT_INVERSE_ZOOM',
        visibleSurfaceCount:
          1,
      },
    )
  }

  private syncDialogueToCamera() {
    if (
      !this.dialogueSurfaceValue
    ) {
      return
    }

    const camera =
      this.scene.cameras.main

    const zoom =
      camera.zoom

    if (
      !Number.isFinite(
        zoom,
      ) ||
      zoom <=
        0
    ) {
      return
    }

    const screenX =
      this.scene
        .scale
        .width /
      2

    const screenY =
      this.scene
        .scale
        .height -
      95

    const worldPoint =
      camera.getWorldPoint(
        screenX,
        screenY,
      )

    this.dialogueSurfaceValue
      .setPosition(
        worldPoint.x,
        worldPoint.y,
      )
      .setScale(
        1 /
          zoom,
      )
  }

  private advance() {
    const completed =
      this.authority
        .advance()

    this.publishSnapshot()

    if (completed) {
      /*
       * Keep field movement locked through the remainder of this pointer
       * dispatch. Otherwise the same final dialogue tap can bubble into the
       * scene-level field movement handler after close() releases the talk
       * gate and accidentally move the player away from the NPC.
       */
      this.inputReleasePendingValue =
        true

      this.scene.time.delayedCall(
        0,
        () => {
          this.inputReleasePendingValue =
            false
        },
      )

      this.destroyDialoguePresentation()

      this.scene.registry.set(
        'logres.playableField.npcStatus',
        'READY',
      )

      this.scene.registry.set(
        'logres.playableField.npcDialoguePresentation',
        {
          mode:
            'RECONSTRUCTED_SCRIPT',
          historicalGlobalDialoguePayload:
            'UNRESOLVED',
          visibleSurfaceCount:
            0,
        },
      )

      return
    }

    const snapshot =
      this.authority
        .snapshot()

    this.dialogueText
      ?.setText(
        snapshot
          .currentLine ??
        '',
      )
  }

  private publishSnapshot() {
    this.scene.registry.set(
      'logres.playableField.npcDialogue',
      this.authority
        .snapshot(),
    )
  }

  private destroyDialoguePresentation() {
    if (
      this.dialogueSurfaceValue
    ) {
      this.dialogueSurfaceValue
        .removeAllListeners()

      this.dialogueSurfaceValue
        .removeAll(
          true,
        )

      this.dialogueSurfaceValue
        .destroy()

      this.dialogueSurfaceValue =
        null
    }

    this.dialogueText =
      null

    this.dialogueHint =
      null
  }
}
