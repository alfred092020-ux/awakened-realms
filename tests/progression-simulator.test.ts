import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  getRunModifiersForMeta,
} from '../src/game/meta/MetaRunBridge'

import {
  simulateProgression,
} from '../src/game/meta/ProgressionSimulator'

describe(
  'Long-term idle progression',
  () => {
    it(
      'simulates a week without manual input',
      () => {
        const report =
          simulateProgression(
            7,
            4,
            12000,
          )

        expect(
          report.days,
        ).toBe(7)

        expect(
          report.runs,
        ).toBe(28)

        expect(
          report.timeline,
        ).toHaveLength(7)

        expect(
          report.totalOfflineEssence,
        ).toBeGreaterThan(0)

        expect(
          report.totalRunEssence,
        ).toBeGreaterThan(0)

        expect(
          report.totalPurchases,
        ).toBeGreaterThan(0)

        expect(
          report.finalState
            .lifetimeRuns,
        ).toBe(28)
      },
    )

    it(
      'permanent progression makes the account stronger',
      () => {
        const report =
          simulateProgression(
            14,
            5,
            90000,
          )

        const modifiers =
          getRunModifiersForMeta(
            report.finalState,
          )

        expect(
          modifiers
            .attackMultiplier,
        ).toBeGreaterThan(1)

        expect(
          modifiers
            .hpMultiplier,
        ).toBeGreaterThan(1)

        expect(
          modifiers
            .attackSpeedMultiplier,
        ).toBeGreaterThan(1)
      },
    )

    it(
      'never exceeds permanent upgrade caps',
      () => {
        const report =
          simulateProgression(
            60,
            8,
            456000,
          )

        expect(
          report.finalUpgrades[
            'attack-training'
          ],
        ).toBeLessThanOrEqual(
          20,
        )

        expect(
          report.finalUpgrades[
            'vitality-training'
          ],
        ).toBeLessThanOrEqual(
          20,
        )

        expect(
          report.finalUpgrades[
            'haste-training'
          ],
        ).toBeLessThanOrEqual(
          15,
        )

        expect(
          report.finalUpgrades[
            'idle-mastery'
          ],
        ).toBeLessThanOrEqual(
          10,
        )
      },
    )

    it(
      'is deterministic with the same inputs',
      () => {
        const first =
          simulateProgression(
            10,
            3,
            70000,
          )

        const second =
          simulateProgression(
            10,
            3,
            70000,
          )

        expect(
          second,
        ).toEqual(
          first,
        )
      },
    )
  },
)
