import Phaser from 'phaser'

import {
  LOGRES_ASSETS,
  preloadLogresAssets,
} from '../logres/ui/LogresRuntimeAssets'

import {
  createCharacterCreateRequest,
  type LogresGender,
} from '../logres/protocol/CharacterCreateProtocol'

type CharacterSex =
  | 'man'
  | 'woman'

interface CharacterMakeTexts {
  charactermake_default?: {
    name?: string
  }
}

export class LogresCharacterCreateScene
  extends Phaser.Scene {
  private selection:
    CharacterSex = 'man'

  private character?:
    Phaser.GameObjects.Image

  private changeButton?:
    Phaser.GameObjects.Image

  private titleBase?:
    Phaser.GameObjects.NineSlice

  private title?:
    Phaser.GameObjects.Image

  private okButton?:
    Phaser.GameObjects.Image

  constructor() {
    super(
      'LogresCharacterCreateScene',
    )
  }

  preload() {
    preloadLogresAssets(
      this,
    )

    /*
     * Global English client text.
     */
    this.load.json(
      'logres-charactermake-texts-en',
      '/__logres_ref/config/global/charactermake_texts.json',
    )
  }

  create() {
    this.renderSelection()
    this.createOriginalHeader()
    this.createOriginalOkButton()
  }

  private createOriginalHeader() {
    /*
     * Extracted native ReleaseScene_CharcterMake:
     *
     * Default design: 720x1280
     * title width: 720 * 0.95 = 684
     * title height: 74
     * center X: 360
     * top margin: 20
     * Phaser center Y: 20 + 74 / 2 = 57
     *
     * Extracted slice_info.json:
     * ~58 px left/right
     * ~18.5 px top/bottom
     */

    this.titleBase =
      this.add.nineslice(
        360,
        57,
        LOGRES_ASSETS
          .characterTitleBase
          .key,
        undefined,
        684,
        74,
        57.95,
        57.95,
        18.5,
        18.5,
      )
      .setAlpha(0)
      .setDepth(100)

    this.title =
      this.add
        .image(
          360,
          57,
          LOGRES_ASSETS
            .characterTitle
            .key,
        )
        .setAlpha(0)
        .setDepth(101)

    /*
     * Original client:
     * delay 0.10 sec
     * fade 0.15 sec
     */
    this.time.delayedCall(
      100,
      () => {
        this.tweens.add({
          targets: [
            this.titleBase,
            this.title,
          ],

          alpha:
            1,

          duration:
            150,
        })
      },
    )
  }

  private createOriginalOkButton() {
    /*
     * Original native position:
     *
     * Cocos:
     * x = width * 0.5
     * y = height * 0.1
     *
     * Converted to Phaser top-origin:
     * x = 360
     * y = 1152
     */

    this.okButton =
      this.add
        .image(
          360,
          1152,
          LOGRES_ASSETS
            .characterOk
            .key,
        )
        .setAlpha(0)
        .setDepth(100)
        .setInteractive({
          useHandCursor:
            true,
        })

    /*
     * Original client:
     * delay 0.50 sec
     * fade 0.30 sec
     */
    this.time.delayedCall(
      500,
      () => {
        this.tweens.add({
          targets:
            this.okButton,

          alpha:
            1,

          duration:
            300,
        })
      },
    )

    this.okButton.on(
      'pointerdown',
      () => {
        this.onTapDecide()
      },
    )
  }

  private onTapDecide() {
    if (!this.okButton) {
      return
    }

    this.okButton
      .disableInteractive()

    /*
     * Original client fades the title
     * and OK control over 0.5 seconds
     * when OK is pressed.
     */
    this.tweens.add({
      targets: [
        this.titleBase,
        this.title,
        this.okButton,
      ],

      alpha:
        0,

      duration:
        500,
    })

    const texts =
      this.cache.json.get(
        'logres-charactermake-texts-en',
      ) as
        CharacterMakeTexts |
        undefined

    /*
     * Do NOT invent a fallback name.
     * Global Logres supplies this value.
     */
    const name =
      texts
        ?.charactermake_default
        ?.name

    if (!name) {
      console.error(
        'Global Logres default character name is missing',
      )

      return
    }

    const gender:
      LogresGender =
        this.selection ===
          'man'
          ? 0
          : 1

    /*
     * Native Global client generates
     * both final request values in
     * the inclusive range 1..5.
     */
    const request =
      createCharacterCreateRequest(
        name,
        gender,
        Phaser.Math.Between(
          1,
          5,
        ),
        Phaser.Math.Between(
          1,
          5,
        ),
      )

    /*
     * Original protocol boundary:
     *
     * C_GMCL_CHAR_CREATE_REQ
     *
     * We retain the exact outgoing
     * request in the reconstruction
     * registry.
     *
     * We intentionally do NOT fabricate
     * an original server response here.
     */
    this.registry.set(
      'logres.protocol.C_GMCL_CHAR_CREATE_REQ',
      request,
    )

    console.info(
      'C_GMCL_CHAR_CREATE_REQ',
      request,
    )
  }

  private renderSelection() {
    this.character?.destroy()
    this.changeButton?.destroy()

    /*
     * Exact positions from the extracted
     * Global characterMan.lua /
     * characterWoman.lua.
     */

    if (
      this.selection ===
      'man'
    ) {
      this.character =
        this.add.image(
          360,
          640,
          LOGRES_ASSETS
            .characterMan
            .key,
        )

      this.changeButton =
        this.add
          .image(
            560,
            890,
            LOGRES_ASSETS
              .characterChangeMan
              .key,
          )
          .setInteractive({
            useHandCursor:
              true,
          })

      this.changeButton.on(
        'pointerdown',
        () => {
          this.selection =
            'woman'

          this.renderSelection()
        },
      )

      return
    }

    this.character =
      this.add.image(
        360,
        640,
        LOGRES_ASSETS
          .characterWoman
          .key,
      )

    this.changeButton =
      this.add
        .image(
          160,
          890,
          LOGRES_ASSETS
            .characterChangeWoman
            .key,
        )
        .setInteractive({
          useHandCursor:
            true,
        })

    this.changeButton.on(
      'pointerdown',
      () => {
        this.selection =
          'man'

        this.renderSelection()
      },
    )
  }
}
