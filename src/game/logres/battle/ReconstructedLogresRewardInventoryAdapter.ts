import {
  ReconstructedLogresBattleResolutionFlow,
} from './ReconstructedLogresBattleResolutionFlow'

import {
  applyReconstructedLogresInventoryGrant,
  type ReconstructedLogresInventoryState,
  type ReconstructedLogresRewardLineInput,
} from '../server/LogresInventoryAuthority'

export const LOGRES_RECONSTRUCTED_REWARD_INVENTORY_ADAPTER_PROVENANCE =
  'RECONSTRUCTED' as const

export interface ReconstructedLogresRewardInventoryGrantInput {
  /**
   * Must identify the same reconstruction-local reward stage already recorded
   * by ReconstructedLogresBattleResolutionFlow.
   */
  rewardKey:
    | string
    | null

  /**
   * Replacement-server idempotency key. This is not claimed to be an
   * original Logres reward or inventory identifier.
   */
  grantKey: string

  entries:
    readonly ReconstructedLogresRewardLineInput[]
}

export interface ReconstructedLogresRewardInventoryGrantResult {
  provenance:
    typeof LOGRES_RECONSTRUCTED_REWARD_INVENTORY_ADAPTER_PROVENANCE

  rewardKey:
    | string
    | null

  originalRewardRef:
    | string
    | null

  inventoryProjectionRef:
    | string
    | null

  applied: boolean

  state:
    Readonly<
      ReconstructedLogresInventoryState
    >
}

function normalizeOptionalRef(
  value:
    | string
    | null,
  label: string,
): string | null {
  if (
    value ===
    null
  ) {
    return null
  }

  const normalized =
    value.trim()

  if (!normalized) {
    throw new Error(
      `${label} must be null or non-empty`,
    )
  }

  return normalized
}

/**
 * Persists one already-authorized battle reward into reconstructed inventory.
 *
 * RECONSTRUCTED boundary:
 * - the battle resolution flow owns sequencing and reward identity
 * - inventory authority owns grant validation/idempotency
 * - this adapter does not infer original item IDs, stacking, capacity, or
 *   historical reward packet semantics
 * - persistence does not imply that reward UI has been presented
 */
export function applyReconstructedLogresBattleRewardGrant(
  flow:
    ReconstructedLogresBattleResolutionFlow,
  inventory:
    Readonly<
      ReconstructedLogresInventoryState
    >,
  input:
    ReconstructedLogresRewardInventoryGrantInput,
): ReconstructedLogresRewardInventoryGrantResult {
  const snapshot =
    flow.snapshot()

  if (
    snapshot.phase !==
    'reward-ready'
  ) {
    throw new Error(
      'Battle reward inventory grant requires reward-ready phase',
    )
  }

  const reward =
    snapshot.reward

  if (!reward) {
    throw new Error(
      'Battle reward stage is missing',
    )
  }

  const rewardKey =
    normalizeOptionalRef(
      input.rewardKey,
      'Battle reward grant rewardKey',
    )

  if (
    rewardKey !==
    reward.rewardKey
  ) {
    throw new Error(
      'Battle reward grant does not match the active reward stage',
    )
  }

  const granted =
    applyReconstructedLogresInventoryGrant(
      inventory,
      {
        grantKey:
          input.grantKey,
        entries:
          input.entries,
      },
    )

  return Object.freeze({
    provenance:
      LOGRES_RECONSTRUCTED_REWARD_INVENTORY_ADAPTER_PROVENANCE,
    rewardKey:
      reward.rewardKey,
    originalRewardRef:
      reward.originalRewardRef,
    inventoryProjectionRef:
      reward.inventoryProjectionRef,
    applied:
      granted.applied,
    state:
      granted.state,
  })
}
