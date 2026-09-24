export const LOGRES_GLOBAL_3024_ENCOUNTER_NATIVE_PROVENANCE =
  'CONFIRMED_GLOBAL_3_0_24_NATIVE' as const

export const LOGRES_GLOBAL_BATTLE_ENTRY_RETRY_RESPONSE_CODE =
  2 as const

export const LOGRES_GLOBAL_BATTLE_ENTRY_RETRY_SECONDS =
  1 as const

export const LOGRES_GLOBAL_BATTLE_ENTRY_ACCEPTED_RESPONSE_CODE =
  1 as const

/**
 * CONFIRMED GLOBAL 3.0.24 gate sequence from
 * Encounter::checkBattleEntry in the signed arm64-v8a libgame.so.
 *
 * These names describe the observed gates without asserting unresolved raw
 * enum values or server-side quest semantics.
 */
export const LOGRES_GLOBAL_BATTLE_ENTRY_GATE_ORDER =
  Object.freeze([
    'GLOBAL_ENCOUNTER_ALLOWED',
    'ENCOUNTER_ENABLED',
    'ENTRY_NOT_ALREADY_ACCEPTED',
    'ENCOUNTER_STATE_PRESENT',
    'RETRY_WAIT_ELAPSED_AND_REQUEST_NOT_PENDING',
    'ENTRY_STATE_ELIGIBLE',
    'QUEST_STATE_ELIGIBLE',
    'DISTANCE_TO_SELF_PLAYER_ELIGIBLE',
    'REQUEST_BATTLE_ENTRY',
  ] as const)

export type LogresGlobalBattleEntryResponseMeaning =
  | 'ENTRY_ACCEPTED'
  | 'RETRY_WAIT_1_SECOND'
  | 'UNRESOLVED'

/**
 * CONFIRMED GLOBAL 3.0.24 response handling from
 * Encounter::receiveBattleEntryResponse:
 * - code 1 sets the encounter's distinct local accepted flag;
 * - code 2 writes exactly 1.0f to the retry wait timer;
 * - code 0 and all other values are deliberately left unresolved.
 */
export function logresGlobalBattleEntryResponseMeaning(
  rawCode: number,
): LogresGlobalBattleEntryResponseMeaning {
  if (
    rawCode ===
    LOGRES_GLOBAL_BATTLE_ENTRY_ACCEPTED_RESPONSE_CODE
  ) {
    return 'ENTRY_ACCEPTED'
  }

  if (
    rawCode ===
    LOGRES_GLOBAL_BATTLE_ENTRY_RETRY_RESPONSE_CODE
  ) {
    return 'RETRY_WAIT_1_SECOND'
  }

  return 'UNRESOLVED'
}
