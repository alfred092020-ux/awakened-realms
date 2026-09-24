export type LogresBattleStageReferenceSex =
  | 'm'
  | 'f'

export interface LogresBattleStageActorPresentation {
  readonly role:
    | 'PLAYER'
    | 'ENEMY'
  readonly x: number
  readonly y: number
  readonly scale: number
  readonly anchorX: number
  readonly anchorY: number
  readonly art:
    string
  readonly artProvenance:
    string
  readonly identityProvenance:
    string
  readonly historicalShapeId:
    'UNRESOLVED'
  readonly historicalBattlePosition:
    'UNRESOLVED'
}

export const LOGRES_BATTLE_STAGE_PROVENANCE =
  Object.freeze({
    actorSpawnArchitecture:
      'CONFIRMED_GLOBAL_3_0_24_NATIVE',

    battlePositionStructure:
      'CONFIRMED_GLOBAL_3_0_24_NATIVE_iX_iY',

    battlePositionToScreenTransform:
      'UNRESOLVED',

    screenPlacement:
      'RECONSTRUCTED',

    stageGround:
      'RECONSTRUCTED_PRESENTATION_ONLY',

    historicalStats:
      'UNRESOLVED',

    historicalPlayerShapeId:
      'UNRESOLVED',

    historicalEnemyShapeId:
      'UNRESOLVED',
  } as const)

export const LOGRES_BATTLE_STAGE_LAYOUT =
  Object.freeze({
    player: {
      xRatio:
        0.32,
      yRatio:
        0.67,
      scale:
        1.45,
    },

    enemy: {
      xRatio:
        0.68,
      yRatio:
        0.44,
      scale:
        1.8,
    },

    ground: {
      centerXRatio:
        0.5,
      centerYRatio:
        0.47,
      widthRatio:
        0.94,
      heightRatio:
        0.67,
    },
  } as const)

export interface LogresBattleStagePresentation {
  readonly mode:
    'RECOVERED_REFERENCE_ART'
    | 'PLACEHOLDER_FALLBACK'
  readonly referenceSex:
    LogresBattleStageReferenceSex
  readonly genderSelection:
    'CHARACTER_CREATE_REQUEST'
    | 'RECONSTRUCTED_REFERENCE_FALLBACK'
  readonly provenance:
    typeof LOGRES_BATTLE_STAGE_PROVENANCE
  readonly ground: {
    readonly x: number
    readonly y: number
    readonly width: number
    readonly height: number
    readonly provenance:
      'RECONSTRUCTED_PRESENTATION_ONLY'
  }
  readonly player:
    LogresBattleStageActorPresentation
  readonly enemy:
    LogresBattleStageActorPresentation
}

function battleStageReferenceSex(
  characterCreateRequest:
    unknown,
): {
  readonly sex:
    LogresBattleStageReferenceSex
  readonly selection:
    'CHARACTER_CREATE_REQUEST'
    | 'RECONSTRUCTED_REFERENCE_FALLBACK'
} {
  if (
    Array.isArray(
      characterCreateRequest,
    )
  ) {
    const gender =
      characterCreateRequest[
        2
      ]

    if (
      gender ===
      0
    ) {
      return {
        sex:
          'm',
        selection:
          'CHARACTER_CREATE_REQUEST',
      }
    }

    if (
      gender ===
      1
    ) {
      return {
        sex:
          'f',
        selection:
          'CHARACTER_CREATE_REQUEST',
      }
    }
  }

  /*
   * Direct battle-scene QA can start without the onboarding registry tuple.
   * A male bod_001 derivative is used only as a presentation reference so the
   * battle does not collapse back to an empty screen. This does not assert a
   * historical Global default gender/body/equipment identity.
   */
  return {
    sex:
      'm',
    selection:
      'RECONSTRUCTED_REFERENCE_FALLBACK',
  }
}

export function createLogresBattleStagePresentation(
  width: number,
  height: number,
  characterCreateRequest:
    unknown,
  recoveredReferenceArtAvailable:
    boolean,
): LogresBattleStagePresentation {
  if (
    !Number.isFinite(
      width,
    ) ||
    width <=
      0 ||
    !Number.isFinite(
      height,
    ) ||
    height <=
      0
  ) {
    throw new Error(
      'Battle stage dimensions must be positive finite numbers',
    )
  }

  const {
    sex,
    selection,
  } =
    battleStageReferenceSex(
      characterCreateRequest,
    )

  const player =
    LOGRES_BATTLE_STAGE_LAYOUT
      .player

  const enemy =
    LOGRES_BATTLE_STAGE_LAYOUT
      .enemy

  const ground =
    LOGRES_BATTLE_STAGE_LAYOUT
      .ground

  return Object.freeze({
    mode:
      recoveredReferenceArtAvailable
        ? 'RECOVERED_REFERENCE_ART'
        : 'PLACEHOLDER_FALLBACK',

    referenceSex:
      sex,

    genderSelection:
      selection,

    provenance:
      LOGRES_BATTLE_STAGE_PROVENANCE,

    ground:
      Object.freeze({
        x:
          width *
          ground.centerXRatio,

        y:
          height *
          ground.centerYRatio,

        width:
          width *
          ground.widthRatio,

        height:
          height *
          ground.heightRatio,

        provenance:
          'RECONSTRUCTED_PRESENTATION_ONLY',
      }),

    player:
      Object.freeze({
        role:
          'PLAYER',

        x:
          width *
          player.xRatio,

        y:
          height *
          player.yRatio,

        scale:
          player.scale,

        anchorX:
          0.5,

        anchorY:
          1,

        art:
          `bod_001_${sex}_reference`,

        artProvenance:
          sex ===
            'm'
            ? 'CONFIRMED_CURRENT_JP_RESOURCE_RECONSTRUCTED_REFERENCE_COMPOSITE'
            : 'SUPPORTED_INFERENCE_CURRENT_JP_SHARED_HUMANOID_SKELETON',

        identityProvenance:
          'RECONSTRUCTED_CURRENT_JP_REFERENCE_BOD_001',

        historicalShapeId:
          'UNRESOLVED',

        historicalBattlePosition:
          'UNRESOLVED',
      }),

    enemy:
      Object.freeze({
        role:
          'ENEMY',

        x:
          width *
          enemy.xRatio,

        y:
          height *
          enemy.yRatio,

        scale:
          enemy.scale,

        anchorX:
          0.5,

        anchorY:
          1,

        art:
          'enm_001_000_000_green_jell_reference',

        artProvenance:
          'SUPPORTED_INFERENCE_CURRENT_JP_REFERENCE_ART',

        identityProvenance:
          'CONFIRMED_GLOBAL_GREEN_JELL_TUTORIAL',

        historicalShapeId:
          'UNRESOLVED',

        historicalBattlePosition:
          'UNRESOLVED',
      }),
  })
}
