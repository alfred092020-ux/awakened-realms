export type RunStatus =
  | 'running'
  | 'upgrade'
  | 'dead'
  | 'won'

export type UpgradeId =
  | 'power-surge'
  | 'vital-core'
  | 'quickening'
  | 'critical-eye'
  | 'aegis'
  | 'renewal'

export interface UpgradeDefinition {
  id: UpgradeId
  name: string
  description: string
}

export interface RunModifiers {
  attackMultiplier: number
  hpMultiplier: number
  attackSpeedMultiplier: number
}

export const DEFAULT_RUN_MODIFIERS:
  RunModifiers = {
    attackMultiplier: 1,
    hpMultiplier: 1,
    attackSpeedMultiplier: 1,
  }

export interface RunPlayerStats {
  hp: number
  maxHp: number

  attack: number

  attackIntervalMs:
    number

  critChance:
    number

  critMultiplier:
    number

  damageReduction:
    number

  healOnKill:
    number
}

export interface RunEnemyState {
  wave: number

  boss: boolean

  hp: number
  maxHp: number

  attack: number

  attackIntervalMs:
    number

  xpReward: number
  goldReward: number
}

export interface RunSnapshot {
  seed: number

  status:
    RunStatus

  elapsedMs:
    number

  wave: number
  kills: number

  level: number
  xp: number
  xpToNext: number

  gold: number

  player:
    RunPlayerStats

  enemy:
    RunEnemyState | null

  pendingUpgrades:
    UpgradeDefinition[]
}

export interface RunResult {
  won: boolean

  waveReached:
    number

  kills:
    number

  gold:
    number

  essence:
    number

  elapsedMs:
    number
}
