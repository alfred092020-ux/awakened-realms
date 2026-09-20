export type MetaUpgradeId =
  | 'attack-training'
  | 'vitality-training'
  | 'haste-training'
  | 'idle-mastery'

export interface MetaUpgradeLevels {
  'attack-training': number
  'vitality-training': number
  'haste-training': number
  'idle-mastery': number
}

export interface MetaState {
  version: 1

  essence: number

  upgrades:
    MetaUpgradeLevels

  lifetimeRuns: number
  bestWave: number

  lastSeenAt: number
}

export interface MetaModifiers {
  attackMultiplier: number
  hpMultiplier: number
  attackSpeedMultiplier: number

  offlineEssenceMultiplier:
    number
}
