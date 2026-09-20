import {
  simulateRun,
} from './RunSimulator'

import type {
  UpgradeDefinition,
  UpgradeId,
} from './RunTypes'

export interface StrategyReport {
  name: string

  runs: number

  wins: number

  winRate: number

  averageWave: number

  minimumWave: number

  maximumWave: number

  averageKills: number

  averageGold: number

  averageEssence: number

  averageDurationSeconds:
    number

  boss10ReachRate:
    number

  boss20ReachRate:
    number

  boss30ReachRate:
    number

  upgradePicks:
    Record<
      UpgradeId,
      number
    >
}

export type MassSimulationReport =
  StrategyReport[]

const ALL_UPGRADES:
  readonly UpgradeId[] = [
    'power-surge',
    'vital-core',
    'quickening',
    'critical-eye',
    'aegis',
    'renewal',
  ]

function chooseByPriority(
  choices:
    readonly UpgradeDefinition[],
  priority:
    readonly UpgradeId[],
) {
  for (
    const upgradeId of
    priority
  ) {
    if (
      choices.some(
        (choice) =>
          choice.id ===
          upgradeId,
      )
    ) {
      return upgradeId
    }
  }

  const fallback =
    choices[0]

  if (!fallback) {
    throw new Error(
      'No upgrade choices available.',
    )
  }

  return fallback.id
}

const STRATEGIES = [
  {
    name:
      'Offense',

    priority: [
      'power-surge',
      'quickening',
      'critical-eye',
      'renewal',
      'vital-core',
      'aegis',
    ] as const,
  },

  {
    name:
      'Defense',

    priority: [
      'aegis',
      'vital-core',
      'renewal',
      'power-surge',
      'quickening',
      'critical-eye',
    ] as const,
  },

  {
    name:
      'Sustain',

    priority: [
      'renewal',
      'vital-core',
      'aegis',
      'power-surge',
      'quickening',
      'critical-eye',
    ] as const,
  },

  {
    name:
      'Crit',

    priority: [
      'critical-eye',
      'quickening',
      'power-surge',
      'renewal',
      'vital-core',
      'aegis',
    ] as const,
  },

  {
    name:
      'Balanced',

    priority: [
      'power-surge',
      'vital-core',
      'quickening',
      'aegis',
      'renewal',
      'critical-eye',
    ] as const,
  },
] as const

function createEmptyPicks() {
  return {
    'power-surge': 0,
    'vital-core': 0,
    'quickening': 0,
    'critical-eye': 0,
    aegis: 0,
    renewal: 0,
  }
}

function simulateStrategy(
  name: string,
  priority:
    readonly UpgradeId[],
  runs: number,
  startingSeed: number,
): StrategyReport {
  const count =
    Math.max(
      1,
      Math.floor(runs),
    )

  let wins = 0

  let totalWave = 0
  let totalKills = 0
  let totalGold = 0
  let totalEssence = 0
  let totalDurationMs = 0

  let minimumWave =
    Number.POSITIVE_INFINITY

  let maximumWave = 0

  let boss10 = 0
  let boss20 = 0
  let boss30 = 0

  const upgradePicks =
    createEmptyPicks()

  for (
    let index = 0;
    index < count;
    index += 1
  ) {
    const seed =
      (
        startingSeed +
        index
      ) >>> 0

    const simulation =
      simulateRun(
        seed,
        (choices) =>
          chooseByPriority(
            choices,
            priority,
          ),
      )

    const result =
      simulation.result

    if (result.won) {
      wins += 1
    }

    totalWave +=
      result.waveReached

    totalKills +=
      result.kills

    totalGold +=
      result.gold

    totalEssence +=
      result.essence

    totalDurationMs +=
      result.elapsedMs

    minimumWave =
      Math.min(
        minimumWave,
        result.waveReached,
      )

    maximumWave =
      Math.max(
        maximumWave,
        result.waveReached,
      )

    if (
      result.waveReached >= 10
    ) {
      boss10 += 1
    }

    if (
      result.waveReached >= 20
    ) {
      boss20 += 1
    }

    if (
      result.waveReached >= 30
    ) {
      boss30 += 1
    }

    for (
      const upgradeId of
      simulation
        .upgradesChosen
    ) {
      upgradePicks[
        upgradeId
      ] += 1
    }
  }

  return {
    name,

    runs:
      count,

    wins,

    winRate:
      wins / count,

    averageWave:
      totalWave / count,

    minimumWave:
      minimumWave ===
      Number.POSITIVE_INFINITY
        ? 0
        : minimumWave,

    maximumWave,

    averageKills:
      totalKills / count,

    averageGold:
      totalGold / count,

    averageEssence:
      totalEssence / count,

    averageDurationSeconds:
      (
        totalDurationMs /
        count
      ) / 1000,

    boss10ReachRate:
      boss10 / count,

    boss20ReachRate:
      boss20 / count,

    boss30ReachRate:
      boss30 / count,

    upgradePicks,
  }
}

export function simulateManyRuns(
  runsPerStrategy: number,
  startingSeed = 1,
): MassSimulationReport {
  return STRATEGIES.map(
    (
      strategy,
      index,
    ) =>
      simulateStrategy(
        strategy.name,
        strategy.priority,
        runsPerStrategy,
        startingSeed +
          index *
            100000,
      ),
  )
}

export {
  ALL_UPGRADES,
}
