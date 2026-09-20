import type {
  PlayerStats,
} from '../combat/CombatStats'

import {
  getItemDefinition,
} from './ItemCatalog'

import type {
  InventorySystem,
} from './InventorySystem'

export interface ConsumableUseResult {
  used: boolean
  message: string
}

export class ConsumableSystem {
  use(
    itemId: string,
    inventory: InventorySystem,
    stats: PlayerStats,
  ): ConsumableUseResult {
    const definition =
      getItemDefinition(itemId)

    if (!definition) {
      return {
        used: false,
        message: 'Unknown item.',
      }
    }

    if (
      definition.category !==
      'consumable'
    ) {
      return {
        used: false,
        message:
          'This item cannot be used from the bag.',
      }
    }

    if (!inventory.hasItem(itemId)) {
      return {
        used: false,
        message:
          'You no longer have this item.',
      }
    }

    const healAmount =
      definition.healAmount ?? 0

    if (healAmount <= 0) {
      return {
        used: false,
        message:
          'This consumable has no usable effect yet.',
      }
    }

    if (stats.hp >= stats.maxHp) {
      return {
        used: false,
        message:
          'HP is already full.',
      }
    }

    const before = stats.hp

    stats.hp = Math.min(
      stats.maxHp,
      stats.hp + healAmount,
    )

    const healed =
      stats.hp - before

    const removed =
      inventory.removeItem(
        itemId,
        1,
      )

    if (removed !== 1) {
      stats.hp = before

      return {
        used: false,
        message:
          'Could not consume the item.',
      }
    }

    return {
      used: true,
      message:
        `${definition.name} restored ${healed} HP.`,
    }
  }
}
