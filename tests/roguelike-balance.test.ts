import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  simulateManyRuns,
} from '../src/game/roguelike/MassSimulation'

describe(
  'Roguelike mass simulation',
  () => {
    it(
      'runs multiple automated strategies without crashing',
      () => {
        const reports =
          simulateManyRuns(
            100,
            5000,
          )

        expect(
          reports,
        ).toHaveLength(5)

        for (
          const report of
          reports
        ) {
          expect(
            report.runs,
          ).toBe(100)

          expect(
            report.minimumWave,
          ).toBeGreaterThanOrEqual(
            1,
          )

          expect(
            report.maximumWave,
          ).toBeGreaterThanOrEqual(
            report.minimumWave,
          )

          expect(
            report.averageKills,
          ).toBeGreaterThan(0)
        }
      },
    )

    it(
      'produces identical reports from identical seeds',
      () => {
        const first =
          simulateManyRuns(
            25,
            9000,
          )

        const second =
          simulateManyRuns(
            25,
            9000,
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
