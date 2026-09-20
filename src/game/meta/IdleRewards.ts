import {
  getMetaModifiers,
} from './MetaProgression'

import type {
  MetaState,
} from './MetaTypes'

export const MAX_OFFLINE_MS =
  8 * 60 * 60 * 1000

export const OFFLINE_ESSENCE_INTERVAL_MS =
  5 * 60 * 1000

export interface OfflineRewardResult {
  elapsedMs: number

  rewardedMs: number

  essence: number

  capped: boolean
}

export function calculateOfflineReward(
  state: MetaState,
  now: number,
): OfflineRewardResult {
  const elapsedMs =
    Math.max(
      0,
      now -
        state.lastSeenAt,
    )

  const rewardedMs =
    Math.min(
      elapsedMs,
      MAX_OFFLINE_MS,
    )

  const baseEssence =
    Math.floor(
      rewardedMs /
        OFFLINE_ESSENCE_INTERVAL_MS,
    )

  const modifiers =
    getMetaModifiers(
      state,
    )

  const essence =
    Math.floor(
      baseEssence *
        modifiers
          .offlineEssenceMultiplier,
    )

  return {
    elapsedMs,

    rewardedMs,

    essence,

    capped:
      elapsedMs >
      MAX_OFFLINE_MS,
  }
}

export function claimOfflineReward(
  state: MetaState,
  now: number,
) {
  const reward =
    calculateOfflineReward(
      state,
      now,
    )

  state.essence +=
    reward.essence

  state.lastSeenAt =
    Math.max(
      state.lastSeenAt,
      now,
    )

  return reward
}
