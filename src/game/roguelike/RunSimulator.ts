import {
  RunEngine,
} from './RunEngine'

import type {
  RunResult,
  UpgradeDefinition,
  UpgradeId,
} from './RunTypes'

export type UpgradeStrategy =
  (
    choices:
      readonly UpgradeDefinition[],
  ) => UpgradeId

export interface SimulationResult {
  result:
    RunResult

  upgradesChosen:
    UpgradeId[]
}

const DEFAULT_STRATEGY:
  UpgradeStrategy =
  (choices) => {
    const first =
      choices[0]

    if (!first) {
      throw new Error(
        'No upgrade choices were available.',
      )
    }

    return first.id
  }

export function simulateRun(
  seed: number,
  strategy:
    UpgradeStrategy =
      DEFAULT_STRATEGY,
): SimulationResult {
  const engine =
    new RunEngine(seed)

  const upgradesChosen:
    UpgradeId[] = []

  const maximumSimulationMs =
    30 * 60 * 1000

  const stepMs =
    100

  while (true) {
    const snapshot =
      engine.getSnapshot()

    if (
      snapshot.status ===
      'dead' ||
      snapshot.status ===
      'won'
    ) {
      const result =
        engine.getResult()

      if (!result) {
        throw new Error(
          'Run ended without a result.',
        )
      }

      return {
        result,
        upgradesChosen,
      }
    }

    if (
      snapshot.status ===
      'upgrade'
    ) {
      const selected =
        strategy(
          snapshot
            .pendingUpgrades,
        )

      upgradesChosen.push(
        selected,
      )

      engine.chooseUpgrade(
        selected,
      )

      continue
    }

    if (
      snapshot.elapsedMs >=
      maximumSimulationMs
    ) {
      throw new Error(
        'Run exceeded simulation time limit.',
      )
    }

    engine.advance(
      stepMs,
    )
  }
}
