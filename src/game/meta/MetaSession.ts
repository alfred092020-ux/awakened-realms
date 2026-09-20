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

import {
  CloudSaveService,
} from '../cloud/CloudSaveService'

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

  private readonly cloud:
    CloudSaveService

  private state:
    MetaState

  constructor(
    saves =
      new MetaSaveSystem(),

    now = Date.now(),

    cloud =
      new CloudSaveService(),
  ) {
    this.saves =
      saves

    this.cloud =
      cloud

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

    this.persist()

    return reward
  }

  claimRun(
    result: RunResult,
  ) {
    claimRunResult(
      this.state,
      result,
    )

    this.persist()
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
      this.persist()
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

    this.persist()
  }

  replaceState(
    state: MetaState,
    updatedAt = Date.now(),
  ) {
    this.state = {
      ...state,

      upgrades: {
        ...state.upgrades,
      },
    }

    this.saves.save(
      this.state,
      updatedAt,
    )
  }

  getUpdatedAt() {
    return this.saves
      .getUpdatedAt()
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

  private persist() {
    const updatedAt =
      Math.max(
        Date.now(),
        this.saves
          .getUpdatedAt() +
          1,
      )

    this.saves.save(
      this.state,
      updatedAt,
    )

    void this.cloud
      .saveIfSignedIn(
        this.state,
        updatedAt,
      )
      .catch(
        () => undefined,
      )
  }
}
