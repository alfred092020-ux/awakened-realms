import {
  getMetaUpgrade,
  getMetaUpgradeCost,
} from './MetaUpgradeCatalog'

import type {
  MetaModifiers,
  MetaState,
  MetaUpgradeId,
} from './MetaTypes'

export function createDefaultMetaState(
  now = Date.now(),
): MetaState {
  return {
    version:
      1,

    essence:
      0,

    upgrades: {
      'attack-training':
        0,

      'vitality-training':
        0,

      'haste-training':
        0,

      'idle-mastery':
        0,
    },

    lifetimeRuns:
      0,

    bestWave:
      0,

    lastSeenAt:
      now,
  }
}

export function getMetaModifiers(
  state: MetaState,
): MetaModifiers {
  const attackLevel =
    state.upgrades[
      'attack-training'
    ]

  const vitalityLevel =
    state.upgrades[
      'vitality-training'
    ]

  const hasteLevel =
    state.upgrades[
      'haste-training'
    ]

  const idleLevel =
    state.upgrades[
      'idle-mastery'
    ]

  return {
    attackMultiplier:
      1 +
      attackLevel *
        0.05,

    hpMultiplier:
      1 +
      vitalityLevel *
        0.06,

    attackSpeedMultiplier:
      1 +
      hasteLevel *
        0.03,

    offlineEssenceMultiplier:
      1 +
      idleLevel *
        0.1,
  }
}

export interface PurchaseResult {
  purchased: boolean

  cost: number

  message: string
}

export function purchaseMetaUpgrade(
  state: MetaState,
  id: MetaUpgradeId,
): PurchaseResult {
  const definition =
    getMetaUpgrade(id)

  if (!definition) {
    return {
      purchased:
        false,

      cost:
        0,

      message:
        'Unknown upgrade.',
    }
  }

  const currentLevel =
    state.upgrades[id]

  if (
    currentLevel >=
    definition.maximumLevel
  ) {
    return {
      purchased:
        false,

      cost:
        0,

      message:
        'Upgrade is already max level.',
    }
  }

  const cost =
    getMetaUpgradeCost(
      id,
      currentLevel,
    )

  if (
    state.essence <
    cost
  ) {
    return {
      purchased:
        false,

      cost,

      message:
        'Not enough Essence.',
    }
  }

  state.essence -=
    cost

  state.upgrades[id] =
    currentLevel + 1

  return {
    purchased:
      true,

    cost,

    message:
      `${definition.name} upgraded.`,
  }
}
