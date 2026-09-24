import {
  ReconstructedLogresBattleResolutionFlow,
} from './ReconstructedLogresBattleResolutionFlow'

import {
  applyReconstructedLogresBattleRewardGrant,
} from './ReconstructedLogresRewardInventoryAdapter'

import {
  createReconstructedLogresInventory,
  type ReconstructedLogresInventoryState,
} from '../server/LogresInventoryAuthority'

export interface ReconstructedLogresBattleCompletionConfig {
  provenance: string
  rewardKey: string
  itemKey: string
  grantKey: string
}

export interface ReconstructedLogresBattleCompletionResult {
  provenance: string
  flow: ReturnType<ReconstructedLogresBattleResolutionFlow['snapshot']>
  inventory: Readonly<ReconstructedLogresInventoryState>
  rewardApplied: boolean
}

export function completeReconstructedLogresBattle(
  config: Readonly<ReconstructedLogresBattleCompletionConfig>,
  inventory: Readonly<ReconstructedLogresInventoryState> =
    createReconstructedLogresInventory(),
): ReconstructedLogresBattleCompletionResult {
  const flow = new ReconstructedLogresBattleResolutionFlow(null)

  flow.recordResult({
    resultRef: null,
    rawOutcomeCode: null,
  })
  flow.markResultPresented()
  flow.recordRewardStage({
    rewardKey: config.rewardKey,
    originalRewardRef: null,
    inventoryProjectionRef: null,
  })

  const grant = applyReconstructedLogresBattleRewardGrant(
    flow,
    inventory,
    {
      rewardKey: config.rewardKey,
      grantKey: config.grantKey,
      entries: [
        {
          itemKey: config.itemKey,
          originalItemId: null,
          quantity: 1,
        },
      ],
    },
  )

  flow.markRewardPresented()
  flow.markFieldReturnReady()

  return Object.freeze({
    provenance: config.provenance,
    flow: flow.snapshot(),
    inventory: grant.state,
    rewardApplied: grant.applied,
  })
}
