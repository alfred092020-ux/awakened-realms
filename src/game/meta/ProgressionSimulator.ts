import {
  claimOfflineReward,
} from './IdleRewards'

import {
  claimRunResult,
  getRunModifiersForMeta,
} from './MetaRunBridge'

import {
  createDefaultMetaState,
  purchaseMetaUpgrade,
} from './MetaProgression'

import {
  getMetaUpgrade,
  getMetaUpgradeCost,
} from './MetaUpgradeCatalog'

import type {
  MetaState,
  MetaUpgradeId,
  MetaUpgradeLevels,
} from './MetaTypes'

import {
  simulateRun,
} from '../roguelike/RunSimulator'

import type {
  UpgradeDefinition,
  UpgradeId,
} from '../roguelike/RunTypes'

const DAY_MS =
  24 * 60 * 60 * 1000

const RUN_UPGRADE_PRIORITY:
  readonly UpgradeId[] = [
    'power-surge',
    'vital-core',
    'quickening',
    'aegis',
    'renewal',
    'critical-eye',
  ]

const META_UPGRADE_PRIORITY:
  readonly MetaUpgradeId[] = [
    'attack-training',
    'vitality-training',
    'haste-training',
    'idle-mastery',
  ]

export interface ProgressionDay {
  day: number

  offlineEssence:
    number

  runEssence:
    number

  purchases:
    number

  runs:
    number

  wins:
    number

  averageWave:
    number

  bestWave:
    number

  endingEssence:
    number

  upgrades:
    MetaUpgradeLevels
}

export interface ProgressionSimulationReport {
  days:
    number

  runs:
    number

  wins:
    number

  finalEssence:
    number

  finalBestWave:
    number

  totalOfflineEssence:
    number

  totalRunEssence:
    number

  totalPurchases:
    number

  finalUpgrades:
    MetaUpgradeLevels

  timeline:
    ProgressionDay[]

  finalState:
    MetaState
}

function chooseRunUpgrade(
  choices:
    readonly UpgradeDefinition[],
): UpgradeId {
  for (
    const upgradeId of
    RUN_UPGRADE_PRIORITY
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

  const first =
    choices[0]

  if (!first) {
    throw new Error(
      'No run upgrade choices available.',
    )
  }

  return first.id
}

function canPurchase(
  state: MetaState,
  id: MetaUpgradeId,
) {
  const definition =
    getMetaUpgrade(id)

  if (!definition) {
    return false
  }

  const level =
    state.upgrades[id]

  if (
    level >=
    definition.maximumLevel
  ) {
    return false
  }

  const cost =
    getMetaUpgradeCost(
      id,
      level,
    )

  return (
    state.essence >=
    cost
  )
}

function purchaseAvailableUpgrades(
  state: MetaState,
) {
  let purchases = 0
  let safety = 0
  let cursor = 0

  while (true) {
    safety += 1

    if (safety > 500) {
      throw new Error(
        'Meta purchase safety limit reached.',
      )
    }

    let purchased =
      false

    for (
      let offset = 0;
      offset <
      META_UPGRADE_PRIORITY.length;
      offset += 1
    ) {
      const index =
        (
          cursor +
          offset
        ) %
        META_UPGRADE_PRIORITY.length

      const id =
        META_UPGRADE_PRIORITY[
          index
        ]

      if (!id) {
        continue
      }

      if (
        !canPurchase(
          state,
          id,
        )
      ) {
        continue
      }

      const result =
        purchaseMetaUpgrade(
          state,
          id,
        )

      if (
        result.purchased
      ) {
        purchases += 1

        cursor =
          (
            index + 1
          ) %
          META_UPGRADE_PRIORITY.length

        purchased =
          true

        break
      }
    }

    if (!purchased) {
      break
    }
  }

  return purchases
}

export function simulateProgression(
  days: number,
  runsPerDay = 6,
  startingSeed = 100000,
): ProgressionSimulationReport {
  const totalDays =
    Math.max(
      1,
      Math.floor(days),
    )

  const dailyRuns =
    Math.max(
      1,
      Math.floor(
        runsPerDay,
      ),
    )

  let now =
    1_000_000

  const state =
    createDefaultMetaState(
      now,
    )

  const timeline:
    ProgressionDay[] = []

  let totalRuns = 0
  let totalWins = 0

  let totalOfflineEssence =
    0

  let totalRunEssence =
    0

  let totalPurchases =
    0

  for (
    let day = 1;
    day <= totalDays;
    day += 1
  ) {
    now +=
      DAY_MS

    const offlineReward =
      claimOfflineReward(
        state,
        now,
      )

    totalOfflineEssence +=
      offlineReward.essence

    let purchases =
      purchaseAvailableUpgrades(
        state,
      )

    let dayWaveTotal = 0
    let dayBestWave = 0
    let dayWins = 0
    let dayRunEssence = 0

    for (
      let runIndex = 0;
      runIndex <
      dailyRuns;
      runIndex += 1
    ) {
      const seed =
        (
          startingSeed +
          day * 1000 +
          runIndex
        ) >>> 0

      const simulation =
        simulateRun(
          seed,
          chooseRunUpgrade,
          getRunModifiersForMeta(
            state,
          ),
        )

      const result =
        simulation.result

      totalRuns += 1

      if (result.won) {
        totalWins += 1
        dayWins += 1
      }

      dayWaveTotal +=
        result.waveReached

      dayBestWave =
        Math.max(
          dayBestWave,
          result.waveReached,
        )

      dayRunEssence +=
        result.essence

      totalRunEssence +=
        result.essence

      claimRunResult(
        state,
        result,
      )

      purchases +=
        purchaseAvailableUpgrades(
          state,
        )
    }

    totalPurchases +=
      purchases

    timeline.push({
      day,

      offlineEssence:
        offlineReward.essence,

      runEssence:
        dayRunEssence,

      purchases,

      runs:
        dailyRuns,

      wins:
        dayWins,

      averageWave:
        dayWaveTotal /
        dailyRuns,

      bestWave:
        dayBestWave,

      endingEssence:
        state.essence,

      upgrades: {
        ...state.upgrades,
      },
    })
  }

  return {
    days:
      totalDays,

    runs:
      totalRuns,

    wins:
      totalWins,

    finalEssence:
      state.essence,

    finalBestWave:
      state.bestWave,

    totalOfflineEssence,

    totalRunEssence,

    totalPurchases,

    finalUpgrades: {
      ...state.upgrades,
    },

    timeline,

    finalState: {
      ...state,

      upgrades: {
        ...state.upgrades,
      },
    },
  }
}
