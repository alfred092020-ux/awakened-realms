import {
  completeReconstructedLogresBattle,
  type ReconstructedLogresBattleCompletionResult,
} from './ReconstructedLogresBattleCompletion'
import type {
  ReconstructedLogresInventoryState,
} from '../server/LogresInventoryAuthority'
import {
  createReconstructedLogresInventory,
} from '../server/LogresInventoryAuthority'

export const LOGRES_PLAYABLE_BATTLE_LOOP_PROVENANCE =
  'RECONSTRUCTED' as const

export const LOGRES_PLAYABLE_BATTLE_REWARD_KEY =
  'playable-tutorial-reconstructed-reward'

export const LOGRES_PLAYABLE_BATTLE_REWARD_ITEM_KEY =
  'playable-tutorial-reconstructed-reward-line'

export const LOGRES_PLAYABLE_BATTLE_GRANT_KEY =
  'playable-tutorial-battle-reward-v1'

export interface ReconstructedLogresPlayableBattleLoopResult {
  provenance:
    typeof LOGRES_PLAYABLE_BATTLE_LOOP_PROVENANCE

  flow:
    ReconstructedLogresBattleCompletionResult['flow']

  inventory:
    Readonly<ReconstructedLogresInventoryState>

  rewardApplied: boolean
}

/**
 * Completes the reconstructed playable tutorial battle after replacement-server
 * authority has selected the local victory outcome.
 *
 * No original result code, item ID, reward table, quantity roll, damage
 * formula, or quest packet is inferred. The replacement reward is deliberately
 * labeled with reconstruction-local identities and is idempotent by grant key.
 */
export function completeReconstructedLogresPlayableBattle(
  inventory:
    Readonly<ReconstructedLogresInventoryState> =
      createReconstructedLogresInventory(),
): ReconstructedLogresPlayableBattleLoopResult {
  return completeReconstructedLogresBattle(
    {
      provenance: LOGRES_PLAYABLE_BATTLE_LOOP_PROVENANCE,
      rewardKey: LOGRES_PLAYABLE_BATTLE_REWARD_KEY,
      itemKey: LOGRES_PLAYABLE_BATTLE_REWARD_ITEM_KEY,
      grantKey: LOGRES_PLAYABLE_BATTLE_GRANT_KEY,
    },
    inventory,
  ) as ReconstructedLogresPlayableBattleLoopResult
}
