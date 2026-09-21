import type {
  ProvenanceInfo,
} from './Provenance'

export type Element =
  | 'neutral'
  | 'fire'
  | 'water'
  | 'wind'
  | 'earth'
  | 'light'
  | 'dark'

export type JobRole =
  | 'damage'
  | 'tank'
  | 'support'
  | 'healer'

export type WeaponType =
  | 'sword'
  | 'greatsword'
  | 'bow'
  | 'staff'
  | 'wand'
  | 'spear'
  | 'axe'
  | 'dagger'

export interface BaseStats {
  hp: number
  physicalAttack: number
  magicalAttack: number
  physicalDefense: number
  magicalDefense: number
}

export interface JobDefinition
  extends ProvenanceInfo {
  id: string
  name: string
  role: JobRole
  allowedWeapons: WeaponType[]
  baseStats: BaseStats
}

export interface SkillDefinition
  extends ProvenanceInfo {
  id: string
  name: string
  element: Element
  power: number
  energyCost: number
  cooldownMs: number
  allowedJobIds: string[]
}

export interface MonsterDefinition
  extends ProvenanceInfo {
  id: string
  name: string
  level: number
  element: Element
  stats: BaseStats
  xpReward: number
  coinReward: number
}

export interface DropEntry
  extends ProvenanceInfo {
  id: string
  monsterId: string
  itemId: string
  chance: number
  minQuantity: number
  maxQuantity: number
}

export interface QuestDefinition
  extends ProvenanceInfo {
  id: string
  name: string
  requiredLevel: number
  targetMonsterId?: string
  requiredKills?: number
  xpReward: number
  coinReward: number
}

export interface LogresMasterData {
  jobs: JobDefinition[]
  skills: SkillDefinition[]
  monsters: MonsterDefinition[]
  drops: DropEntry[]
  quests: QuestDefinition[]
}
