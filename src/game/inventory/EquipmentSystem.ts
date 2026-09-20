import type {
  PlayerStats,
} from '../combat/CombatStats'

import {
  getItemDefinition,
} from './ItemCatalog'

import type {
  EquipmentSlot,
  EquipmentState,
} from './ItemTypes'

import type {
  InventorySystem,
} from './InventorySystem'

export interface EquipmentActionResult {
  changed: boolean
  message: string
}

const EQUIPMENT_SLOTS:
  EquipmentSlot[] = [
    'weapon',
    'armor',
    'accessory',
  ]

export class EquipmentSystem {
  private readonly slots:
    EquipmentState = {}

  constructor(
    saved: EquipmentState = {},
  ) {
    for (
      const slot of
      EQUIPMENT_SLOTS
    ) {
      const itemId =
        saved[slot]

      if (!itemId) {
        continue
      }

      const definition =
        getItemDefinition(
          itemId,
        )

      if (
        definition?.equipmentSlot !==
        slot
      ) {
        continue
      }

      this.slots[slot] =
        itemId
    }
  }

  applyLoadedBonuses(
    stats: PlayerStats,
  ) {
    for (
      const slot of
      EQUIPMENT_SLOTS
    ) {
      const itemId =
        this.slots[slot]

      if (!itemId) {
        continue
      }

      this.applyItemBonus(
        itemId,
        stats,
        1,
      )
    }
  }

  equip(
    itemId: string,
    inventory: InventorySystem,
    stats: PlayerStats,
  ): EquipmentActionResult {
    const definition =
      getItemDefinition(
        itemId,
      )

    const slot =
      definition?.equipmentSlot

    if (!definition || !slot) {
      return {
        changed: false,
        message:
          'This item cannot be equipped.',
      }
    }

    if (
      this.slots[slot] ===
      itemId
    ) {
      return {
        changed: false,
        message:
          `${definition.name} is already equipped.`,
      }
    }

    if (
      !inventory.hasItem(
        itemId,
        1,
      )
    ) {
      return {
        changed: false,
        message:
          'You no longer have this item.',
      }
    }

    const removed =
      inventory.removeItem(
        itemId,
        1,
      )

    if (removed !== 1) {
      return {
        changed: false,
        message:
          'Could not equip the item.',
      }
    }

    const oldItemId =
      this.slots[slot]

    if (oldItemId) {
      const returned =
        inventory.addItem(
          oldItemId,
          1,
        )

      if (returned !== 1) {
        inventory.addItem(
          itemId,
          1,
        )

        return {
          changed: false,
          message:
            'Bag is full. Cannot swap equipment.',
        }
      }

      this.applyItemBonus(
        oldItemId,
        stats,
        -1,
      )
    }

    this.slots[slot] =
      itemId

    this.applyItemBonus(
      itemId,
      stats,
      1,
    )

    return {
      changed: true,
      message:
        `Equipped ${definition.name}.`,
    }
  }

  unequip(
    slot: EquipmentSlot,
    inventory: InventorySystem,
    stats: PlayerStats,
  ): EquipmentActionResult {
    const itemId =
      this.slots[slot]

    if (!itemId) {
      return {
        changed: false,
        message:
          'Nothing is equipped in this slot.',
      }
    }

    const returned =
      inventory.addItem(
        itemId,
        1,
      )

    if (returned !== 1) {
      return {
        changed: false,
        message:
          'Bag is full. Cannot unequip.',
      }
    }

    this.applyItemBonus(
      itemId,
      stats,
      -1,
    )

    delete this.slots[slot]

    const definition =
      getItemDefinition(
        itemId,
      )

    return {
      changed: true,
      message:
        `Unequipped ${definition?.name ?? itemId}.`,
    }
  }

  getEquippedItem(
    slot: EquipmentSlot,
  ) {
    return this.slots[slot]
  }

  getSlots():
    EquipmentState {
    return {
      ...this.slots,
    }
  }

  getAttackBonus() {
    let total = 0

    for (
      const slot of
      EQUIPMENT_SLOTS
    ) {
      const itemId =
        this.slots[slot]

      if (!itemId) {
        continue
      }

      total +=
        getItemDefinition(
          itemId,
        )?.attackBonus ?? 0
    }

    return total
  }

  getMaxHpBonus() {
    let total = 0

    for (
      const slot of
      EQUIPMENT_SLOTS
    ) {
      const itemId =
        this.slots[slot]

      if (!itemId) {
        continue
      }

      total +=
        getItemDefinition(
          itemId,
        )?.maxHpBonus ?? 0
    }

    return total
  }

  getBaseStats(
    stats: PlayerStats,
  ): PlayerStats {
    const maxHp =
      Math.max(
        1,
        stats.maxHp -
          this.getMaxHpBonus(),
      )

    return {
      ...stats,

      attack:
        Math.max(
          1,
          stats.attack -
            this.getAttackBonus(),
        ),

      maxHp,

      hp:
        Math.min(
          stats.hp,
          maxHp,
        ),
    }
  }

  private applyItemBonus(
    itemId: string,
    stats: PlayerStats,
    direction: 1 | -1,
  ) {
    const definition =
      getItemDefinition(
        itemId,
      )

    if (!definition) {
      return
    }

    const attackBonus =
      definition.attackBonus ?? 0

    const hpBonus =
      definition.maxHpBonus ?? 0

    stats.attack =
      Math.max(
        1,
        stats.attack +
          attackBonus *
            direction,
      )

    if (direction === 1) {
      stats.maxHp +=
        hpBonus

      stats.hp +=
        hpBonus

      return
    }

    stats.maxHp =
      Math.max(
        1,
        stats.maxHp -
          hpBonus,
      )

    stats.hp =
      Math.min(
        stats.hp,
        stats.maxHp,
      )
  }
}
