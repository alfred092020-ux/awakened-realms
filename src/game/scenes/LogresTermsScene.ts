import Phaser from 'phaser'

import {
  LOGRES_ASSETS,
  preloadLogresAssets,
} from '../logres/ui/LogresRuntimeAssets'

import {
  LOGRES_GLOBAL_3024_TERMS_GATE,
  LOGRES_GLOBAL_3024_WORLD_SELECTION,
} from '../logres/onboarding/LogresGlobal3024BootEvidence'

export const LOGRES_TERMS_PLAYER_COPY =
  Object.freeze({
    heading:
      'Agreement',
    section:
      'Terms of Use',
    body:
      Object.freeze([
        'The Terms of Use page is unavailable in this build.',
        'No legal text is reproduced on this screen.',
      ] as const),
    guidance:
      'Continue to proceed.',
    action:
      'Continue',
  } as const)

export class LogresTermsScene
  extends Phaser.Scene {
  private agreeing =
    false

  private termsSceneInputEpoch =
    0

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

    this.termsSceneInputEpoch =
      this.input.activePointer
        .downTime

    this.registry.set(
      'logres.qa.termsTransitionTrace',
      {
        rendered:
          true,
        scene:
          'LogresTermsScene',
        activationPointerDownTime:
          this.termsSceneInputEpoch,
        titleStartInput:
          this.registry.get(
            'logres.qa.titleStartInputTrace',
          ) ?? null,
        accepted:
          false,
        freshPointerEdge:
          false,
        agreePointerDownTime:
          null,
        stalePointerRejections:
          0,
      },
    )

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

    this.registry.set(
      'logres.ui.termsPlayerCopyStatus',
      'NO_LEGAL_COPY_AVAILABLE',
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

    /*
     * Presentation is intentionally neutral rather than asserted-original:
     * the original hosted page is unavailable, while the recovered client
     * only confirms the AgreementWebView/auth boundary.
     */
    this.add
      .rectangle(
        360,
        640,
        720,
        1280,
        0x000000,
        0.48,
      )
      .setDepth(
        -90,
      )

    this.add
      .rectangle(
        360,
        600,
        620,
        760,
        0x231d17,
        0.96,
      )
      .setStrokeStyle(
        4,
        0xc7a45a,
        1,
      )

    this.add
      .text(
        360,
        270,
        LOGRES_TERMS_PLAYER_COPY
          .heading,
        {
          fontFamily:
            'sans-serif',
          fontSize:
            '46px',
          fontStyle:
            'bold',
          color:
            '#f4e4b2',
        },
      )
      .setOrigin(
        0.5,
      )

    this.add
      .rectangle(
        360,
        325,
        500,
        2,
        0xc7a45a,
        0.75,
      )

    this.add
      .text(
        360,
        385,
        LOGRES_TERMS_PLAYER_COPY
          .section,
        {
          fontFamily:
            'sans-serif',
          fontSize:
            '32px',
          fontStyle:
            'bold',
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
        565,
        LOGRES_TERMS_PLAYER_COPY
          .body
          .join(
            '\n\n',
          ),
        {
          align:
            'center',
          fontFamily:
            'sans-serif',
          fontSize:
            '27px',
          color:
            '#f2eee6',
          lineSpacing:
            10,
          wordWrap: {
            width:
              500,
            useAdvancedWrap:
              true,
          },
        },
      )
      .setOrigin(
        0.5,
      )

    this.add
      .text(
        360,
        795,
        LOGRES_TERMS_PLAYER_COPY
          .guidance,
        {
          fontFamily:
            'sans-serif',
          fontSize:
            '25px',
          color:
            '#d9caa5',
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
          0x853a32,
          1,
        )
        .setStrokeStyle(
          4,
          0xd8b765,
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
        LOGRES_TERMS_PLAYER_COPY
          .action,
        {
          fontFamily:
            'sans-serif',
          fontSize:
            '36px',
          fontStyle:
            'bold',
          color:
            '#ffffff',
        },
      )
      .setOrigin(
        0.5,
      )

    agree.on(
      'pointerdown',
      (
        pointer:
          Phaser.Input.Pointer,
      ) => {
        if (
          this.agreeing
        ) {
          return
        }

        const previousTrace =
          this.registry.get(
            'logres.qa.termsTransitionTrace',
          ) as
            Record<string, unknown> |
            undefined

        const freshPointerEdge =
          Number.isFinite(
            pointer.downTime,
          ) &&
          pointer.downTime >
            this.termsSceneInputEpoch

        if (
          !freshPointerEdge
        ) {
          const previousRejections =
            typeof previousTrace
              ?.stalePointerRejections ===
              'number'
              ? previousTrace
                  .stalePointerRejections
              : 0

          this.registry.set(
            'logres.qa.termsTransitionTrace',
            {
              ...previousTrace,
              accepted:
                false,
              freshPointerEdge:
                false,
              rejectedPointerDownTime:
                pointer.downTime,
              stalePointerRejections:
                previousRejections +
                1,
            },
          )

          return
        }

        this.agreeing =
          true

        this.registry.set(
          'logres.qa.termsTransitionTrace',
          {
            ...previousTrace,
            accepted:
              true,
            freshPointerEdge:
              true,
            agreePointerDownTime:
              pointer.downTime,
            acceptedAt:
              this.time.now,
          },
        )

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
