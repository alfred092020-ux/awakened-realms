import {
  claimOfflineReward,
} from './IdleRewards'

import {
  MetaSaveSystem,
} from './MetaSaveSystem'

import {
  claimRunResult,
  getRunModifiersForMeta,
} from './MetaRunBridge'

import {
  purchaseMetaUpgrade,
} from './MetaProgression'

import type {
  MetaState,
  MetaUpgradeId,
} from './MetaTypes'

import type {
  RunResult,
} from '../roguelike/RunTypes'

export class MetaSession {
  private readonly saves:
    MetaSaveSystem

  private state:
    MetaState

  constructor(
    saves =
      new MetaSaveSystem(),
    now = Date.now(),
  ) {
    this.saves =
      saves

    this.state =
      this.saves.load(
        now,
      )
  }

  claimOffline(
    now = Date.now(),
  ) {
    const reward =
      claimOfflineReward(
        this.state,
        now,
      )

    this.saves.save(
      this.state,
    )

    return reward
  }

  claimRun(
    result: RunResult,
  ) {
    claimRunResult(
      this.state,
      result,
    )

    this.saves.save(
      this.state,
    )
  }

  purchase(
    id: MetaUpgradeId,
  ) {
    const result =
      purchaseMetaUpgrade(
        this.state,
        id,
      )

    if (
      result.purchased
    ) {
      this.saves.save(
        this.state,
      )
    }

    return result
  }

  touch(
    now = Date.now(),
  ) {
    this.state.lastSeenAt =
      Math.max(
        this.state.lastSeenAt,
        now,
      )

    this.saves.save(
      this.state,
    )
  }

  getRunModifiers() {
    return getRunModifiersForMeta(
      this.state,
    )
  }

  getState():
    MetaState {
    return {
      ...this.state,

      upgrades: {
        ...this.state
          .upgrades,
      },
    }
  }
}
