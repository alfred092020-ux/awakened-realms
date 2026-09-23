import Phaser from 'phaser'

import {
  LogresGlobalBattleKit,
  type LogresGlobalBattleKitInput,
} from '../logres/battle/LogresGlobalBattleKit'

import {
  LOGRES_ASSETS,
  preloadLogresAssets,
} from '../logres/ui/LogresRuntimeAssets'

export interface LogresBattleSceneData
  extends Partial<LogresGlobalBattleKitInput> {}

export class LogresBattleScene
  extends Phaser.Scene {
  private battleKit:
    LogresGlobalBattleKit | null =
      null

  private weaponCover:
    Phaser.GameObjects.Image | null =
      null

  private epText:
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

    const snapshot =
      this.battleKit
        .snapshot()

    const spacing =
      112

    const firstX =
      this.scale.width / 2 -
      spacing * 2

    const y =
      this.scale.height -
      150

    snapshot.weaponPanels
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

    this.events.on(
      'logres-request-normal-attack',
      () => {
        this.emitNormalAttack()
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
      this.events.emit(
        'logres-battle-command',
        this.battleKit
          .createNormalAttack(),
      )
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

    const {
      currentEp,
      epCap,
    } =
      this.battleKit
        .snapshot()

    this.epText.setText(
      epCap === null
        ? `EP ${currentEp}`
        : `EP ${currentEp}/${epCap}`,
    )
  }
}
