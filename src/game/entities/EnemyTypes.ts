import type {
  LootEntry,
} from '../loot/LootTableSystem'

export interface EnemyDefinition {
  id: string
  name: string
  textureKey: string

  maxHp: number
  aggroRange: number
  attackRange: number
  speed: number

  attackDamage: number
  attackCooldown: number

  bodyWidth: number
  bodyHeight: number

  hpBarColor: number

  xpReward: number
  coinReward: number

  lootTable: LootEntry[]
}
