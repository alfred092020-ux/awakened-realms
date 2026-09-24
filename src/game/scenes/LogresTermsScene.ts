import Phaser from 'phaser'

import {
  LOGRES_ASSETS,
  preloadLogresAssets,
} from '../logres/ui/LogresRuntimeAssets'

import {
  LOGRES_GLOBAL_3024_TERMS_GATE,
  LOGRES_GLOBAL_3024_WORLD_SELECTION,
} from '../logres/onboarding/LogresGlobal3024BootEvidence'

export class LogresTermsScene
  extends Phaser.Scene {
  private agreeing =
    false

  constructor() {
    super(
      'LogresTermsScene',
    )
  }

  preload() {
    preloadLogresAssets(
      this,
    )
  }

  create() {
    this.agreeing =
      false

    /*
     * CONFIRMED ORIGINAL Global 3.0.24 boundary:
     *
     * E_GMCL_ACCLOGIN_NOT_AGREEMENT
     *   -> AgreementWebView
     *   -> HostEntry.webViewUrls.terms
     *   -> agree_to_terms
     *
     * The historical hosted legal page itself has not been recovered.
     * Therefore this scene is deliberately a RECONSTRUCTED WebView shell:
     * it models the original auth/state transition without inventing legal
     * copy or claiming an original native Terms layout.
     */
    this.registry.set(
      'logres.auth.loginResult',
      LOGRES_GLOBAL_3024_TERMS_GATE
        .loginFailureCode,
    )

    this.registry.set(
      'logres.auth.agreementScene',
      LOGRES_GLOBAL_3024_TERMS_GATE
        .agreementScene,
    )

    this.registry.set(
      'logres.auth.termsUrlSource',
      LOGRES_GLOBAL_3024_TERMS_GATE
        .hostEntryField,
    )

    this.registry.set(
      'logres.auth.termsHostedPage',
      LOGRES_GLOBAL_3024_TERMS_GATE
        .exactHostedPage,
    )

    this.registry.set(
      'logres.ui.termsPresentationProvenance',
      'RECONSTRUCTED_WEBVIEW_SHELL',
    )

    this.add
      .image(
        360,
        640,
        LOGRES_ASSETS
          .titleBackground
          .key,
      )
      .setDepth(
        -100,
      )

    this.add
      .rectangle(
        360,
        610,
        640,
        850,
        0x111111,
        0.92,
      )
      .setStrokeStyle(
        2,
        0xdddddd,
        0.8,
      )

    this.add
      .text(
        360,
        235,
        'Agreement',
        {
          fontFamily:
            'sans-serif',
          fontSize:
            '48px',
          color:
            '#ffffff',
        },
      )
      .setOrigin(
        0.5,
      )

    this.add
      .text(
        360,
        585,
        [
          'Original Global Terms were hosted',
          'in an external Agreement WebView.',
          '',
          'The historical hosted page is',
          'unresolved in this reconstruction.',
        ].join(
          '\n',
        ),
        {
          align:
            'center',
          fontFamily:
            'sans-serif',
          fontSize:
            '30px',
          color:
            '#eeeeee',
          lineSpacing:
            12,
        },
      )
      .setOrigin(
        0.5,
      )

    const agree =
      this.add
        .rectangle(
          360,
          1110,
          360,
          100,
          0x2c2c2c,
          1,
        )
        .setStrokeStyle(
          3,
          0xffffff,
          1,
        )
        .setName(
          'terms-agree',
        )
        .setInteractive({
          useHandCursor:
            true,
        })

    this.add
      .text(
        360,
        1110,
        'Agree',
        {
          fontFamily:
            'sans-serif',
          fontSize:
            '38px',
          color:
            '#ffffff',
        },
      )
      .setOrigin(
        0.5,
      )

    agree.on(
      'pointerdown',
      () => {
        if (
          this.agreeing
        ) {
          return
        }

        this.agreeing =
          true

        agree
          .disableInteractive()

        this.registry.set(
          'logres.auth.termsAccepted',
          true,
        )

        this.registry.set(
          'logres.auth.lastOperation',
          LOGRES_GLOBAL_3024_TERMS_GATE
            .authOperation,
        )

        this.registry.set(
          'logres.auth.termsAcceptanceProvenance',
          'RECONSTRUCTED_AUTH_BOUNDARY',
        )

        this.registry.set(
          'logres.world.firstRunRequirement',
          LOGRES_GLOBAL_3024_WORLD_SELECTION
            .firstRunRequirement,
        )

        /*
         * Return to the login/world-resolution boundary. It will either show
         * World Select when replacement/account state explicitly requires it,
         * or immediately continue to the gender-only temporary character flow.
         */
        this.scene.start(
          'LogresWorldSelectScene',
        )
      },
    )
  }
}
