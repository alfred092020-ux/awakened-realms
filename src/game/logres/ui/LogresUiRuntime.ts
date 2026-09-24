import {
  LOGRES_GLOBAL_3024_TERMS_GATE,
  LOGRES_GLOBAL_3024_TITLE_LAYOUT,
  LOGRES_GLOBAL_3024_WORLD_SELECTION,
} from '../onboarding/LogresGlobal3024BootEvidence'

import {
  LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE,
  LOGRES_TUTORIAL_HUD_LAYOUT_EVIDENCE,
} from '../tutorial/LogresTutorialHudEvidence'

import {
  LOGRES_TUTORIAL_HUD_RUNTIME_SELECTION,
  LOGRES_TUTORIAL_PARAMETER_BAR_PLACEMENT,
} from '../tutorial/LogresTutorialHudRuntime'

export interface LogresUiRuntimeWorldEntry {
  id: number
  name: string
  group: number
  openDate?: string
}

export interface ResolveLogresUiNavigationInput {
  termsAccepted: boolean
  worldSelectionRequired: boolean
  recoveredWorldLabel?: string | null
  recoveredOpenDateLabel?: string | null
}

export type LogresUiNavigationScene =
  | 'LogresTermsScene'
  | 'LogresWorldSelectScene'
  | 'LogresCharacterCreateScene'

export interface LogresUiNavigationResolution {
  nextScene: LogresUiNavigationScene
  registryPatch: Readonly<Record<string, unknown>>
  worldSelectView?: {
    labelSource: 'RECOVERED_GLOBAL' | 'RECONSTRUCTED_FALLBACK'
    worldLabel: string
    openDateLabel?: string
    worlds: readonly LogresUiRuntimeWorldEntry[]
  }
}

export interface LogresTitleStartTransition
  extends LogresUiNavigationResolution {
  startButtonPosition:
    readonly [number, number]
  startRevealDelayMs: number
  startFadeMs: number
  transitionDelayMs: number
  transitionBoundary:
    'WORLD_RESOLUTION'
  navigationMode:
    'DEFER_TO_WORLD_RESOLUTION_BOUNDARY'
  provenance: string
}

export const LOGRES_UI_RUNTIME_WORLDS:
  readonly Readonly<LogresUiRuntimeWorldEntry>[] =
  Object.freeze([
    Object.freeze({
      id: 1,
      name: '1',
      group: 0,
    }),
  ])

export const LOGRES_TITLE_MENU_RUNTIME =
  Object.freeze({
    startButtonPosition:
      LOGRES_GLOBAL_3024_TITLE_LAYOUT
        .startButtonTopOriginPosition,
    startRevealDelayMs: 1000,
    startFadeMs: 300,
    transitionDelayMs: 1500,
    transitionBoundary:
      'WORLD_RESOLUTION' as const,
    navigationMode:
      'DEFER_TO_WORLD_RESOLUTION_BOUNDARY' as const,
    provenance:
      LOGRES_GLOBAL_3024_TITLE_LAYOUT
        .provenance,
  })

export const LOGRES_UI_HUD_MENU_RUNTIME =
  Object.freeze({
    parameterBar: {
      ...LOGRES_TUTORIAL_HUD_RUNTIME_SELECTION
        .parameterBar,
      placement:
        LOGRES_TUTORIAL_PARAMETER_BAR_PLACEMENT,
    },
    questStart: {
      text:
        LOGRES_TUTORIAL_HUD_RUNTIME_SELECTION
          .questStartText,
      background:
        LOGRES_TUTORIAL_HUD_RUNTIME_SELECTION
          .questStartBackground,
      positioning:
        'EXPLICIT_CALLER_PLACEMENT_UNTIL_LFLA_TRANSFORM_IS_DECODED' as const,
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
      layoutVariant:
        LOGRES_TUTORIAL_HUD_LAYOUT_EVIDENCE
          .layoutVariantSelection,
      runtimeStatus:
        'SUPPORTED_RECONSTRUCTION_ONLY' as const,
      activeSelection: null,
    },
  })

function normalizeRecoveredLabel(
  value: string | null | undefined,
): string | undefined {
  const trimmed =
    value?.trim()

  return trimmed
    ? trimmed
    : undefined
}

export function resolveLogresUiNavigation(
  input: ResolveLogresUiNavigationInput,
): Readonly<LogresUiNavigationResolution> {
  if (
    input.termsAccepted !== true
  ) {
    return Object.freeze({
      nextScene:
        'LogresTermsScene',
      registryPatch:
        Object.freeze({
          'logres.auth.loginResult':
            LOGRES_GLOBAL_3024_TERMS_GATE
              .loginFailureCode,
          'logres.world.selectorFlowProvenance':
            LOGRES_GLOBAL_3024_WORLD_SELECTION
              .provenance,
        }),
    })
  }

  if (
    input.worldSelectionRequired !==
    true
  ) {
    return Object.freeze({
      nextScene:
        'LogresCharacterCreateScene',
      registryPatch:
        Object.freeze({
          'logres.world.selectionStatus':
            'SKIPPED_CONDITIONAL',
          'logres.world.selectorFlowProvenance':
            LOGRES_GLOBAL_3024_WORLD_SELECTION
              .provenance,
        }),
    })
  }

  const recoveredWorldLabel =
    normalizeRecoveredLabel(
      input.recoveredWorldLabel,
    )

  const recoveredOpenDateLabel =
    normalizeRecoveredLabel(
      input.recoveredOpenDateLabel,
    )

  return Object.freeze({
    nextScene:
      'LogresWorldSelectScene',
    registryPatch:
      Object.freeze({
        'logres.world.selectionStatus':
          'USER_REQUIRED',
        'logres.world.selectorFlowProvenance':
          LOGRES_GLOBAL_3024_WORLD_SELECTION
            .provenance,
        'logres.server.worldCatalogSource':
          'RECONSTRUCTED',
        'logres.ui.worldSelectLabelSource':
          recoveredWorldLabel
            ? 'RECOVERED_GLOBAL'
            : 'RECONSTRUCTED_FALLBACK',
      }),
    worldSelectView:
      Object.freeze({
        labelSource:
          recoveredWorldLabel
            ? 'RECOVERED_GLOBAL'
            : 'RECONSTRUCTED_FALLBACK',
        worldLabel:
          recoveredWorldLabel ||
          'World',
        openDateLabel:
          recoveredOpenDateLabel,
        worlds:
          LOGRES_UI_RUNTIME_WORLDS,
      }),
  })
}

export function resolveLogresTitleStartTransition(
  input: ResolveLogresUiNavigationInput,
): Readonly<LogresTitleStartTransition> {
  return Object.freeze({
    ...LOGRES_TITLE_MENU_RUNTIME,
    ...resolveLogresUiNavigation(
      input,
    ),
  })
}

export interface ResolveLogresTermsAgreementInput {
  worldSelectionRequired: boolean
  recoveredWorldLabel?: string | null
  recoveredOpenDateLabel?: string | null
}

export function resolveLogresTermsAgreementTransition(
  input: ResolveLogresTermsAgreementInput,
) {
  const navigation =
    resolveLogresUiNavigation({
      termsAccepted:
        true,
      worldSelectionRequired:
        input.worldSelectionRequired,
      recoveredWorldLabel:
        input.recoveredWorldLabel,
      recoveredOpenDateLabel:
        input.recoveredOpenDateLabel,
    })

  return Object.freeze({
    nextScene:
      navigation.nextScene,
    registryPatch:
      Object.freeze({
        ...navigation.registryPatch,
        'logres.auth.termsAccepted':
          true,
        'logres.auth.lastOperation':
          LOGRES_GLOBAL_3024_TERMS_GATE
            .authOperation,
        'logres.auth.termsAcceptanceProvenance':
          'RECONSTRUCTED_AUTH_BOUNDARY',
        'logres.world.firstRunRequirement':
          LOGRES_GLOBAL_3024_WORLD_SELECTION
            .firstRunRequirement,
      }),
    worldSelectView:
      navigation.worldSelectView,
  })
}

export function resolveLogresWorldSelection(
  worldId: number,
) {
  const world =
    LOGRES_UI_RUNTIME_WORLDS.find(
      (entry) =>
        entry.id === worldId,
    )

  if (!world) {
    throw new Error(
      `Unknown reconstructed world ID: ${worldId}`,
    )
  }

  return Object.freeze({
    nextScene:
      'LogresCharacterCreateScene' as const,
    selectedWorld:
      world,
    registryPatch:
      Object.freeze({
        'logres.world.selectedId':
          world.id,
        'logres.world.selectionRequired':
          false,
        'logres.world.selectionStatus':
          'USER_SELECTED',
      }),
  })
}
