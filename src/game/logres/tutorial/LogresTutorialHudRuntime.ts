import {
  LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE,
  LOGRES_TUTORIAL_HUD_LAYOUT_EVIDENCE,
} from './LogresTutorialHudEvidence'

export const LOGRES_TUTORIAL_QUEST_START_SHOW_EVENT =
  'logres-tutorial-quest-start-show' as const

export const LOGRES_TUTORIAL_QUEST_START_HIDE_EVENT =
  'logres-tutorial-quest-start-hide' as const

export const LOGRES_TUTORIAL_QUEST_START_REJECTED_EVENT =
  'logres-tutorial-quest-start-rejected' as const

export const LOGRES_TUTORIAL_PARAMETER_BAR_PLACEMENT =
  Object.freeze({
    x:
      LOGRES_TUTORIAL_HUD_LAYOUT_EVIDENCE
        .mainHudUnderbarCenter
        .x,

    y:
      LOGRES_TUTORIAL_HUD_LAYOUT_EVIDENCE
        .mainHudUnderbarCenter
        .y,

    evidenceLabel:
      'SUPPORTED INFERENCE' as const,

    basis:
      'The recovered tutorial parameter asset matches the original frame; its screen placement reuses the confirmed original top-HUD center while the exact older-layout node binding remains unresolved.',
  })

export interface LogresTutorialQuestStartPlacement {
  centerX: number
  centerY: number
}

export interface LogresTutorialHudRuntimeSelection {
  parameterBar: {
    runtimeUrl: string
    sourceSha256: string
  }
  questStartText: {
    runtimeUrl: string
    sourceSha256: string
  }
  questStartBackground: {
    runtimeUrl: string
    sourceSha256: string
  }
}

export const LOGRES_TUTORIAL_HUD_RUNTIME_SELECTION:
  Readonly<LogresTutorialHudRuntimeSelection> =
  Object.freeze({
    parameterBar:
      Object.freeze({
        runtimeUrl:
          LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE
            .parameterBar
            .runtimeUrl,

        sourceSha256:
          LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE
            .parameterBar
            .sourceSha256,
      }),

    questStartText:
      Object.freeze({
        runtimeUrl:
          LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE
            .questStartText
            .runtimeUrl,

        sourceSha256:
          LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE
            .questStartText
            .sourceSha256,
      }),

    questStartBackground:
      Object.freeze({
        runtimeUrl:
          LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE
            .questStartBackground
            .runtimeUrl,

        sourceSha256:
          LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE
            .questStartBackground
            .sourceSha256,
      }),
  })

function finiteCoordinate(
  value: unknown,
  label: string,
): number {
  if (
    typeof value !==
      'number' ||
    !Number.isFinite(
      value,
    )
  ) {
    throw new Error(
      `${label} must be a finite number`,
    )
  }

  return value
}

/**
 * Quest Start motion exists in recovered LFLa data, but its transform has not
 * yet been mechanically decoded. Callers must therefore provide explicit
 * screen-space placement instead of receiving a fabricated default.
 */
export function resolveLogresTutorialQuestStartPlacement(
  value: unknown,
): Readonly<LogresTutorialQuestStartPlacement> {
  if (
    typeof value !==
      'object' ||
    value ===
      null
  ) {
    throw new Error(
      'Quest Start placement must be an object',
    )
  }

  const record =
    value as
      Record<
        string,
        unknown
      >

  return Object.freeze({
    centerX:
      finiteCoordinate(
        record.centerX,
        'Quest Start centerX',
      ),

    centerY:
      finiteCoordinate(
        record.centerY,
        'Quest Start centerY',
      ),
  })
}
