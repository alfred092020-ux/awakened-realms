import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_TITLE_MENU_RUNTIME,
  LOGRES_UI_HUD_MENU_RUNTIME,
  LOGRES_UI_RUNTIME_WORLDS,
  resolveLogresTermsAgreementTransition,
  resolveLogresTitleStartTransition,
  resolveLogresUiNavigation,
  resolveLogresWorldSelection,
} from '../src/game/logres/ui/LogresUiRuntime'

import {
  LOGRES_GLOBAL_3024_TERMS_GATE,
  LOGRES_GLOBAL_3024_TITLE_LAYOUT,
  LOGRES_GLOBAL_3024_WORLD_SELECTION,
} from '../src/game/logres/onboarding/LogresGlobal3024BootEvidence'

import {
  LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE,
  LOGRES_TUTORIAL_HUD_LAYOUT_EVIDENCE,
} from '../src/game/logres/tutorial/LogresTutorialHudEvidence'

describe(
  'Logres UI runtime',
  () => {
    it(
      'keeps title start timing and destination anchored to Global 3.0.24 evidence',
      () => {
        expect(
          LOGRES_TITLE_MENU_RUNTIME,
        ).toEqual({
          startButtonPosition:
            LOGRES_GLOBAL_3024_TITLE_LAYOUT
              .startButtonTopOriginPosition,
          startRevealDelayMs:
            1000,
          startFadeMs:
            300,
          transitionDelayMs:
            1500,
          transitionBoundary:
            'WORLD_RESOLUTION',
          navigationMode:
            'DEFER_TO_WORLD_RESOLUTION_BOUNDARY',
          provenance:
            'CONFIRMED_ORIGINAL_GLOBAL_3_0_24',
        })

        expect(
          resolveLogresTitleStartTransition({
            termsAccepted:
              false,
            worldSelectionRequired:
              true,
          }),
        ).toMatchObject({
          transitionBoundary:
            'WORLD_RESOLUTION',
          nextScene:
            'LogresTermsScene',
        })

        expect(
          resolveLogresTitleStartTransition({
            termsAccepted:
              true,
            worldSelectionRequired:
              true,
          }),
        ).toMatchObject({
          nextScene:
            'LogresWorldSelectScene',
        })
      },
    )

    it(
      'routes unresolved agreement state back to the reconstructed Terms boundary',
      () => {
        expect(
          resolveLogresUiNavigation({
            termsAccepted:
              false,
            worldSelectionRequired:
              true,
          }),
        ).toEqual({
          nextScene:
            'LogresTermsScene',
          registryPatch: {
            'logres.auth.loginResult':
              LOGRES_GLOBAL_3024_TERMS_GATE
                .loginFailureCode,
            'logres.world.selectorFlowProvenance':
              LOGRES_GLOBAL_3024_WORLD_SELECTION
                .provenance,
          },
        })
      },
    )

    it(
      'skips world selection unless replacement/account state explicitly requires it',
      () => {
        expect(
          resolveLogresUiNavigation({
            termsAccepted:
              true,
            worldSelectionRequired:
              false,
          }),
        ).toEqual({
          nextScene:
            'LogresCharacterCreateScene',
          registryPatch: {
            'logres.world.selectionStatus':
              'SKIPPED_CONDITIONAL',
            'logres.world.selectorFlowProvenance':
              LOGRES_GLOBAL_3024_WORLD_SELECTION
                .provenance,
          },
        })
      },
    )

    it(
      'opens a reconstructed world selector with honest label provenance when required',
      () => {
        expect(
          resolveLogresUiNavigation({
            termsAccepted:
              true,
            worldSelectionRequired:
              true,
            recoveredWorldLabel:
              '  Server  ',
            recoveredOpenDateLabel:
              '  Open Date  ',
          }),
        ).toEqual({
          nextScene:
            'LogresWorldSelectScene',
          registryPatch: {
            'logres.world.selectionStatus':
              'USER_REQUIRED',
            'logres.world.selectorFlowProvenance':
              LOGRES_GLOBAL_3024_WORLD_SELECTION
                .provenance,
            'logres.server.worldCatalogSource':
              'RECONSTRUCTED',
            'logres.ui.worldSelectLabelSource':
              'RECOVERED_GLOBAL',
          },
          worldSelectView: {
            labelSource:
              'RECOVERED_GLOBAL',
            worldLabel:
              'Server',
            openDateLabel:
              'Open Date',
            worlds:
              LOGRES_UI_RUNTIME_WORLDS,
          },
        })

        expect(
          resolveLogresUiNavigation({
            termsAccepted:
              true,
            worldSelectionRequired:
              true,
            recoveredWorldLabel:
              '   ',
          }).worldSelectView,
        ).toMatchObject({
          labelSource:
            'RECONSTRUCTED_FALLBACK',
          worldLabel:
            'World',
        })
      },
    )

    it(
      'records the reconstructed auth boundary and selected world transition without inventing extra semantics',
      () => {
        expect(
          resolveLogresTermsAgreementTransition({
            worldSelectionRequired:
              false,
          }),
        ).toEqual({
          nextScene:
            'LogresCharacterCreateScene',
          registryPatch: {
            'logres.world.selectionStatus':
              'SKIPPED_CONDITIONAL',
            'logres.world.selectorFlowProvenance':
              LOGRES_GLOBAL_3024_WORLD_SELECTION
                .provenance,
            'logres.auth.termsAccepted':
              true,
            'logres.auth.lastOperation':
              'agree_to_terms',
            'logres.auth.termsAcceptanceProvenance':
              'RECONSTRUCTED_AUTH_BOUNDARY',
            'logres.world.firstRunRequirement':
              'CONDITIONAL_NOT_CONFIRMED_MANDATORY',
          },
          worldSelectView:
            undefined,
        })

        expect(
          resolveLogresTermsAgreementTransition({
            worldSelectionRequired:
              true,
            recoveredWorldLabel:
              'World',
          }),
        ).toMatchObject({
          nextScene:
            'LogresWorldSelectScene',
          worldSelectView: {
            labelSource:
              'RECOVERED_GLOBAL',
            worldLabel:
              'World',
          },
        })

        expect(
          resolveLogresWorldSelection(1),
        ).toEqual({
          nextScene:
            'LogresCharacterCreateScene',
          selectedWorld:
            LOGRES_UI_RUNTIME_WORLDS[0],
          registryPatch: {
            'logres.world.selectedId':
              1,
            'logres.world.selectionRequired':
              false,
            'logres.world.selectionStatus':
              'USER_SELECTED',
          },
        })

        expect(
          () =>
            resolveLogresWorldSelection(
              999,
            ),
        ).toThrow(
          'Unknown reconstructed world ID: 999',
        )
      },
    )

    it(
      'keeps the tutorial footer menu assets explicit but unresolved as an active layout selection',
      () => {
        expect(
          LOGRES_UI_HUD_MENU_RUNTIME,
        ).toMatchObject({
          parameterBar: {
            sourceSha256:
              LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE
                .parameterBar
                .sourceSha256,
            placement: {
              x: 360,
              y: 45,
              evidenceLabel:
                'SUPPORTED INFERENCE',
            },
          },
          questStart: {
            positioning:
              'EXPLICIT_CALLER_PLACEMENT_UNTIL_LFLA_TRANSFORM_IS_DECODED',
          },
          footerMenu: {
            underbar:
              LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE
                .fieldUnderbar,
            menuButton:
              LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE
                .fieldMenu,
            center:
              LOGRES_TUTORIAL_HUD_LAYOUT_EVIDENCE
                .fieldHudFooterUnderbarCenter,
            layoutVariant: {
              label:
                'UNRESOLVED',
            },
            runtimeStatus:
              'SUPPORTED_RECONSTRUCTION_ONLY',
            activeSelection:
              null,
          },
        })
      },
    )
  },
)
