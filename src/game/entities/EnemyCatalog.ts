import {
  MOONFANG_LOOT_TABLE,
  SLIME_LOOT_TABLE,
} from '../loot/LootTableSystem'

import type {
  EnemyDefinition,
} from './EnemyTypes'

export const SLIME_ENEMY:
  EnemyDefinition = {
    id: 'slime',
    name: 'Meadow Slime',
    textureKey: 'slime',

    maxHp: 70,
    aggroRange: 360,
    attackRange: 78,
    speed: 105,

    attackDamage: 12,
    attackCooldown: 1100,

    bodyWidth: 48,
    bodyHeight: 38,

    hpBarColor: 0x75d66d,

    xpReward: 40,
    coinReward: 12,

    lootTable:
      SLIME_LOOT_TABLE,
  }

export const MOONFANG_ENEMY:
  EnemyDefinition = {
    id: 'moonfang',
    name: 'Moonfang',
    textureKey: 'moonfang',

    maxHp: 115,
    aggroRange: 430,
    attackRange: 84,
    speed: 145,

    attackDamage: 18,
    attackCooldown: 950,

    bodyWidth: 54,
    bodyHeight: 40,

    hpBarColor: 0x7aa5ef,

    xpReward: 65,
    coinReward: 20,

    lootTable:
      MOONFANG_LOOT_TABLE,
  }
