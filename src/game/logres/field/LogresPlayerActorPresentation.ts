export type LogresPlayerGender =
  | 0
  | 1

export type LogresPlayerReferenceSex =
  | 'm'
  | 'f'

export const LOGRES_PLAYER_ACTOR_PRESENTATION =
  Object.freeze({
    source:
      'RECOVERED_CURRENT_JP_PRIVATE_DERIVATIVE',

    bodySelection:
      'RECONSTRUCTED_CURRENT_JP_REFERENCE_BOD_001',

    equipment:
      'NONE',

    historicalGlobalBodyId:
      'UNRESOLVED',

    historicalGlobalEquipmentIds:
      'UNRESOLVED',

    maleMotionApplication:
      'CONFIRMED_CURRENT_JP_RESOURCE',

    femaleMotionApplication:
      'SUPPORTED_INFERENCE_SHARED_HUMANOID_SKELETON',

    worldPlacement:
      'RECONSTRUCTED_NAVIGATION_TILE_BINDING',
  } as const)

export function readLogresPlayerGenderFromCharacterCreateRequest(
  request:
    unknown,
): LogresPlayerGender | null {
  if (
    !Array.isArray(
      request,
    )
  ) {
    return null
  }

  const gender =
    request[
      2
    ]

  if (
    gender ===
      0 ||
    gender ===
      1
  ) {
    return gender
  }

  return null
}

export function logresPlayerReferenceSex(
  gender:
    LogresPlayerGender,
): LogresPlayerReferenceSex {
  return gender ===
    0
    ? 'm'
    : 'f'
}

export function logresPlayerMotionApplication(
  gender:
    LogresPlayerGender,
) {
  return gender ===
    0
    ? LOGRES_PLAYER_ACTOR_PRESENTATION
        .maleMotionApplication
    : LOGRES_PLAYER_ACTOR_PRESENTATION
        .femaleMotionApplication
}
