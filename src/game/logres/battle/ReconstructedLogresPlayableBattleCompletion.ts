import {
  ReconstructedLogresBattleResolutionFlow,
} from './ReconstructedLogresBattleResolutionFlow'

import {
  applyReconstructedLogresBattleRewardGrant,
} from './ReconstructedLogresRewardInventoryAdapter'

import {
  createReconstructedLogresInventory,
  type ReconstructedLogresInventoryState,
  type ReconstructedLogresRewardLineInput,
} from '../server/LogresInventoryAuthority'

export const LOGRES_PLAYABLE_BATTLE_COMPLETION_PROVENANCE =
  'RECONSTRUCTED' as const

export const LOGRES_PLAYABLE_BATTLE_REWARD_KEY =
  'demo01-reconstructed-reward'

export const LOGRES_PLAYABLE_BATTLE_REWARD_ITEM_KEY =
  'demo01-reconstructed-reward-line'

export const LOGRES_PLAYABLE_BATTLE_GRANT_KEY =
  'demo01-reconstructed-battle-reward-v1'

export const LOGRES_PLAYABLE_BATTLE_FIELD_RETURN_SCENE_KEY =
  'LogresFieldScene' as const

export const LOGRES_PLAYABLE_BATTLE_FIELD_RETURN_FIELD_NAME =
  'Millennium Tree' as const

export const LOGRES_PLAYABLE_BATTLE_FIELD_RETURN_MOVEMENT_STATE =
  'READY' as const

export interface ReconstructedLogresPlayableBattleCompletionInput {
  battleSystemRef?:
    | string
    | null
  inventory?:
    | Readonly<ReconstructedLogresInventoryState>
    | undefined
  resultRef?:
    | string
    | null
  rawOutcomeCode?:
    | number
    | null
  rewardKey?:
    | string
    | null
  originalRewardRef?:
    | string
    | null
  inventoryProjectionRef?:
    | string
    | null
  grantKey?: string
  entries?:
    | readonly ReconstructedLogresRewardLineInput[]
    | undefined
}

export interface ReconstructedLogresPlayableBattleCompletionResult {
  provenance:
    typeof LOGRES_PLAYABLE_BATTLE_COMPLETION_PROVENANCE
  flow:
    ReturnType<
      ReconstructedLogresBattleResolutionFlow['snapshot']
    >
  inventory:
    Readonly<ReconstructedLogresInventoryState>
  rewardApplied: boolean
  fieldReturn: Readonly<{
    sceneKey:
      typeof LOGRES_PLAYABLE_BATTLE_FIELD_RETURN_SCENE_KEY
    fieldName:
      typeof LOGRES_PLAYABLE_BATTLE_FIELD_RETURN_FIELD_NAME
    movementState:
      typeof LOGRES_PLAYABLE_BATTLE_FIELD_RETURN_MOVEMENT_STATE
  }>
}

export function completeReconstructedPlayableBattle(
  input: ReconstructedLogresPlayableBattleCompletionInput = {},
): ReconstructedLogresPlayableBattleCompletionResult {
  const flow =
    new ReconstructedLogresBattleResolutionFlow(
      input.battleSystemRef ??
        null,
    )

  flow.recordResult({
    resultRef:
      input.resultRef ??
      null,
    rawOutcomeCode:
      input.rawOutcomeCode ??
      null,
  })

  flow.markResultPresented()

  flow.recordRewardStage({
    rewardKey:
      input.rewardKey ??
      LOGRES_PLAYABLE_BATTLE_REWARD_KEY,
    originalRewardRef:
      input.originalRewardRef ??
      null,
    inventoryProjectionRef:
      input.inventoryProjectionRef ??
      null,
  })

  const grant =
    applyReconstructedLogresBattleRewardGrant(
      flow,
      input.inventory ??
        createReconstructedLogresInventory(),
      {
        rewardKey:
          input.rewardKey ??
          LOGRES_PLAYABLE_BATTLE_REWARD_KEY,
        grantKey:
          input.grantKey ??
          LOGRES_PLAYABLE_BATTLE_GRANT_KEY,
        entries:
          input.entries ??
          [
            {
              itemKey:
                LOGRES_PLAYABLE_BATTLE_REWARD_ITEM_KEY,
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
      LOGRES_PLAYABLE_BATTLE_COMPLETION_PROVENANCE,
    flow:
      flow.snapshot(),
    inventory:
      grant.state,
    rewardApplied:
      grant.applied,
    fieldReturn:
      Object.freeze({
        sceneKey:
          LOGRES_PLAYABLE_BATTLE_FIELD_RETURN_SCENE_KEY,
        fieldName:
          LOGRES_PLAYABLE_BATTLE_FIELD_RETURN_FIELD_NAME,
        movementState:
          LOGRES_PLAYABLE_BATTLE_FIELD_RETURN_MOVEMENT_STATE,
      }),
  })
}
