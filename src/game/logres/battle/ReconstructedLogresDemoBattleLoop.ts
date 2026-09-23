import {
  ReconstructedLogresBattleResolutionFlow,
} from "./ReconstructedLogresBattleResolutionFlow"

import {
  applyReconstructedLogresBattleRewardGrant,
} from "./ReconstructedLogresRewardInventoryAdapter"

import {
  createReconstructedLogresInventory,
  type ReconstructedLogresInventoryState,
} from "../server/LogresInventoryAuthority"

export const LOGRES_DEMO01_BATTLE_LOOP_PROVENANCE =
  "RECONSTRUCTED" as const

export const LOGRES_DEMO01_REWARD_KEY =
  "demo01-reconstructed-reward"

export const LOGRES_DEMO01_REWARD_ITEM_KEY =
  "demo01-reconstructed-reward-line"

export const LOGRES_DEMO01_GRANT_KEY =
  "demo01-reconstructed-battle-reward-v1"

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
  inventory:
    Readonly<ReconstructedLogresInventoryState> =
      createReconstructedLogresInventory(),
): ReconstructedLogresDemoBattleLoopResult {
  const flow =
    new ReconstructedLogresBattleResolutionFlow(
      null,
    )

  flow.recordResult({
    resultRef:
      null,
    rawOutcomeCode:
      null,
  })

  flow.markResultPresented()

  flow.recordRewardStage({
    rewardKey:
      LOGRES_DEMO01_REWARD_KEY,
    originalRewardRef:
      null,
    inventoryProjectionRef:
      null,
  })

  const grant =
    applyReconstructedLogresBattleRewardGrant(
      flow,
      inventory,
      {
        rewardKey:
          LOGRES_DEMO01_REWARD_KEY,
        grantKey:
          LOGRES_DEMO01_GRANT_KEY,
        entries: [
          {
            itemKey:
              LOGRES_DEMO01_REWARD_ITEM_KEY,
            originalItemId:
              null,
            quantity:
              1,
          },
        ],
      },
    )

  flow.markRewardPresented()
  flow.markFieldReturnReady()

  return Object.freeze({
    provenance:
      LOGRES_DEMO01_BATTLE_LOOP_PROVENANCE,
    flow:
      flow.snapshot(),
    inventory:
      grant.state,
    rewardApplied:
      grant.applied,
  })
}
