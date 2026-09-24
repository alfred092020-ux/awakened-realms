import {
  completeReconstructedPlayableBattle,
  LOGRES_PLAYABLE_BATTLE_COMPLETION_PROVENANCE,
  LOGRES_PLAYABLE_BATTLE_GRANT_KEY,
  LOGRES_PLAYABLE_BATTLE_REWARD_ITEM_KEY,
  LOGRES_PLAYABLE_BATTLE_REWARD_KEY,
  type ReconstructedLogresInventoryState,
} from './ReconstructedLogresPlayableBattleCompletion'

import {
  ReconstructedLogresBattleResolutionFlow,
} from './ReconstructedLogresBattleResolutionFlow'

export const LOGRES_DEMO01_BATTLE_LOOP_PROVENANCE =
  LOGRES_PLAYABLE_BATTLE_COMPLETION_PROVENANCE

export const LOGRES_DEMO01_REWARD_KEY =
  LOGRES_PLAYABLE_BATTLE_REWARD_KEY

export const LOGRES_DEMO01_REWARD_ITEM_KEY =
  LOGRES_PLAYABLE_BATTLE_REWARD_ITEM_KEY

export const LOGRES_DEMO01_GRANT_KEY =
  LOGRES_PLAYABLE_BATTLE_GRANT_KEY

export interface ReconstructedLogresDemoBattleLoopResult {
  provenance:
    typeof LOGRES_DEMO01_BATTLE_LOOP_PROVENANCE

  flow:
    ReturnType<
      ReconstructedLogresBattleResolutionFlow["snapshot"]
    >

  inventory:
    Readonly<ReconstructedLogresInventoryState>

  rewardApplied: boolean
}

/**
 * Temporary Demo 0.1 bridge.
 *
 * This deliberately does NOT claim original Logres battle-result, reward,
 * item, quantity, quest, or packet semantics. It only proves that the
 * reconstructed result -> reward -> inventory -> field-return authorities can
 * execute as one visible loop while all historical identifiers remain null.
 */
export function completeReconstructedLogresDemoBattle(
  inventory?:
    Readonly<ReconstructedLogresInventoryState>,
): ReconstructedLogresDemoBattleLoopResult {
  const result =
    completeReconstructedPlayableBattle({
      inventory,
    })

  return Object.freeze({
    provenance:
      LOGRES_DEMO01_BATTLE_LOOP_PROVENANCE,
    flow:
      result.flow,
    inventory:
      result.inventory,
    rewardApplied:
      result.rewardApplied,
  })
}
