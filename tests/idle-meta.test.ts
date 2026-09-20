import {
  beforeEach,
  describe,
  expect,
  it,
} from 'vitest'

import {
  calculateOfflineReward,
  claimOfflineReward,
  MAX_OFFLINE_MS,
  OFFLINE_ESSENCE_INTERVAL_MS,
} from '../src/game/meta/IdleRewards'

import {
  MetaSaveSystem,
} from '../src/game/meta/MetaSaveSystem'

import {
  claimRunResult,
  getRunModifiersForMeta,
} from '../src/game/meta/MetaRunBridge'

import {
  createDefaultMetaState,
  purchaseMetaUpgrade,
} from '../src/game/meta/MetaProgression'

import {
  RunEngine,
} from '../src/game/roguelike/RunEngine'

describe(
  'Idle meta progression',
  () => {
    beforeEach(() => {
      localStorage.clear()
    })

    it(
      'creates a clean new meta account',
      () => {
        const state =
          createDefaultMetaState(
            1000,
          )

        expect(
          state.essence,
        ).toBe(0)

        expect(
          state.lifetimeRuns,
        ).toBe(0)

        expect(
          state.bestWave,
        ).toBe(0)

        expect(
          state.lastSeenAt,
        ).toBe(1000)
      },
    )

    it(
      'banks Essence from a completed run',
      () => {
        const state =
          createDefaultMetaState(
            1000,
          )

        claimRunResult(
          state,
          {
            won:
              false,

            waveReached:
              18,

            kills:
              17,

            gold:
              250,

            essence:
              9,

            elapsedMs:
              45000,
          },
        )

        expect(
          state.essence,
        ).toBe(9)

        expect(
          state.lifetimeRuns,
        ).toBe(1)

        expect(
          state.bestWave,
        ).toBe(18)
      },
    )

    it(
      'purchases permanent upgrades using Essence',
      () => {
        const state =
          createDefaultMetaState()

        state.essence =
          100

        const result =
          purchaseMetaUpgrade(
            state,
            'attack-training',
          )

        expect(
          result.purchased,
        ).toBe(true)

        expect(
          state.upgrades[
            'attack-training'
          ],
        ).toBe(1)

        expect(
          state.essence,
        ).toBeLessThan(100)
      },
    )

    it(
      'makes future runs start stronger',
      () => {
        const baseState =
          createDefaultMetaState()

        const upgradedState =
          createDefaultMetaState()

        upgradedState.upgrades[
          'attack-training'
        ] = 5

        upgradedState.upgrades[
          'vitality-training'
        ] = 5

        upgradedState.upgrades[
          'haste-training'
        ] = 5

        const baseEngine =
          new RunEngine(
            123,
            getRunModifiersForMeta(
              baseState,
            ),
          )

        const upgradedEngine =
          new RunEngine(
            123,
            getRunModifiersForMeta(
              upgradedState,
            ),
          )

        const base =
          baseEngine
            .getSnapshot()
            .player

        const upgraded =
          upgradedEngine
            .getSnapshot()
            .player

        expect(
          upgraded.attack,
        ).toBeGreaterThan(
          base.attack,
        )

        expect(
          upgraded.maxHp,
        ).toBeGreaterThan(
          base.maxHp,
        )

        expect(
          upgraded.attackIntervalMs,
        ).toBeLessThan(
          base.attackIntervalMs,
        )
      },
    )

    it(
      'earns deterministic offline Essence',
      () => {
        const state =
          createDefaultMetaState(
            1000,
          )

        const now =
          1000 +
          OFFLINE_ESSENCE_INTERVAL_MS *
            10

        const reward =
          calculateOfflineReward(
            state,
            now,
          )

        expect(
          reward.essence,
        ).toBe(10)

        expect(
          reward.capped,
        ).toBe(false)
      },
    )

    it(
      'caps offline rewards at eight hours',
      () => {
        const state =
          createDefaultMetaState(
            1000,
          )

        const reward =
          calculateOfflineReward(
            state,
            1000 +
              MAX_OFFLINE_MS *
                3,
          )

        expect(
          reward.rewardedMs,
        ).toBe(
          MAX_OFFLINE_MS,
        )

        expect(
          reward.capped,
        ).toBe(true)
      },
    )

    it(
      'idle mastery increases offline rewards',
      () => {
        const base =
          createDefaultMetaState(
            1000,
          )

        const upgraded =
          createDefaultMetaState(
            1000,
          )

        upgraded.upgrades[
          'idle-mastery'
        ] = 5

        const now =
          1000 +
          OFFLINE_ESSENCE_INTERVAL_MS *
            20

        const baseReward =
          calculateOfflineReward(
            base,
            now,
          )

        const upgradedReward =
          calculateOfflineReward(
            upgraded,
            now,
          )

        expect(
          upgradedReward
            .essence,
        ).toBeGreaterThan(
          baseReward.essence,
        )
      },
    )

    it(
      'does not allow claiming the same offline period twice',
      () => {
        const state =
          createDefaultMetaState(
            1000,
          )

        const now =
          1000 +
          OFFLINE_ESSENCE_INTERVAL_MS *
            10

        const first =
          claimOfflineReward(
            state,
            now,
          )

        const second =
          claimOfflineReward(
            state,
            now,
          )

        expect(
          first.essence,
        ).toBe(10)

        expect(
          second.essence,
        ).toBe(0)

        expect(
          state.essence,
        ).toBe(10)
      },
    )

    it(
      'persists permanent progression',
      () => {
        const saves =
          new MetaSaveSystem()

        const state =
          createDefaultMetaState(
            5000,
          )

        state.essence =
          77

        state.lifetimeRuns =
          12

        state.bestWave =
          31

        state.upgrades[
          'attack-training'
        ] = 4

        saves.save(
          state,
        )

        const loaded =
          saves.load(
            9999,
          )

        expect(
          loaded.essence,
        ).toBe(77)

        expect(
          loaded.lifetimeRuns,
        ).toBe(12)

        expect(
          loaded.bestWave,
        ).toBe(31)

        expect(
          loaded.upgrades[
            'attack-training'
          ],
        ).toBe(4)

        expect(
          loaded.lastSeenAt,
        ).toBe(5000)
      },
    )

    it(
      'recovers safely from corrupted meta saves',
      () => {
        localStorage.setItem(
          'awakened-realms.meta.v1',
          '{broken',
        )

        const saves =
          new MetaSaveSystem()

        const loaded =
          saves.load(
            12345,
          )

        expect(
          loaded.essence,
        ).toBe(0)

        expect(
          loaded.lastSeenAt,
        ).toBe(12345)
      },
    )
  },
)
