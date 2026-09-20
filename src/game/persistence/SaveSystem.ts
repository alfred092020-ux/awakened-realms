import type { PlayerStats } from '../combat/CombatStats'
import type { InventoryStack } from '../inventory/ItemTypes'

interface LegacyPlayerSave {
  version: 1
  level: number
  xp: number
  xpToNext: number
  maxHp: number
  attack: number
  coins: number
}

interface SavedPlayerProgress {
  level: number
  xp: number
  xpToNext: number
  maxHp: number
  attack: number
  coins: number
}

interface SavedInventory {
  items: InventoryStack[]
}

interface SavedEquipment {
  slots: Record<string, unknown>
}

interface GameSaveData {
  version: 2
  player: SavedPlayerProgress
  inventory: SavedInventory
  equipment: SavedEquipment
}

export class SaveSystem {
  private readonly storageKey =
    'awakened-realms.save'

  private readonly legacyStorageKey =
    'awakened-realms.player-progress.v1'

  load(
    fallback: PlayerStats,
  ): PlayerStats {
    try {
      const current =
        this.loadCurrentSave()

      if (current) {
        return this.toPlayerStats(
          current.player,
        )
      }

      const legacy =
        this.loadLegacySave()

      if (legacy) {
        const stats =
          this.toPlayerStats(legacy)

        this.save(stats)

        return stats
      }

      return { ...fallback }
    } catch {
      return { ...fallback }
    }
  }

  loadInventory() {
    try {
      const current =
        this.loadCurrentSave()

      if (!current) {
        return []
      }

      return current.inventory.items.map(
        (item) => ({
          ...item,
        }),
      )
    } catch {
      return []
    }
  }

  save(
    stats: PlayerStats,
    inventoryItems?: InventoryStack[],
  ) {
    try {
      const existing =
        this.loadCurrentSave()

      const saveData: GameSaveData = {
        version: 2,
        player:
          this.toSavedPlayer(stats),
        inventory:
          inventoryItems
            ? {
                items:
                  inventoryItems.map(
                    (item) => ({
                      ...item,
                    }),
                  ),
              }
            : existing?.inventory ?? {
                items: [],
              },
        equipment:
          existing?.equipment ?? {
            slots: {},
          },
      }

      localStorage.setItem(
        this.storageKey,
        JSON.stringify(saveData),
      )

      return true
    } catch {
      return false
    }
  }

  clear() {
    try {
      localStorage.removeItem(
        this.storageKey,
      )

      localStorage.removeItem(
        this.legacyStorageKey,
      )

      return true
    } catch {
      return false
    }
  }

  private loadCurrentSave() {
    const raw = localStorage.getItem(
      this.storageKey,
    )

    if (!raw) {
      return undefined
    }

    const parsed: unknown =
      JSON.parse(raw)

    if (!this.isValidCurrentSave(parsed)) {
      return undefined
    }

    return parsed
  }

  private loadLegacySave() {
    const raw = localStorage.getItem(
      this.legacyStorageKey,
    )

    if (!raw) {
      return undefined
    }

    const parsed: unknown =
      JSON.parse(raw)

    if (!this.isValidLegacySave(parsed)) {
      return undefined
    }

    return parsed
  }

  private toSavedPlayer(
    stats: PlayerStats,
  ): SavedPlayerProgress {
    return {
      level: stats.level,
      xp: stats.xp,
      xpToNext: stats.xpToNext,
      maxHp: stats.maxHp,
      attack: stats.attack,
      coins: stats.coins,
    }
  }

  private toPlayerStats(
    saved: SavedPlayerProgress,
  ): PlayerStats {
    return {
      level: saved.level,
      xp: saved.xp,
      xpToNext: saved.xpToNext,
      hp: saved.maxHp,
      maxHp: saved.maxHp,
      attack: saved.attack,
      coins: saved.coins,
    }
  }

  private isValidCurrentSave(
    value: unknown,
  ): value is GameSaveData {
    if (
      typeof value !== 'object' ||
      value === null
    ) {
      return false
    }

    const save =
      value as Partial<GameSaveData>

    return (
      save.version === 2 &&
      this.isValidPlayer(
        save.player,
      ) &&
      typeof save.inventory ===
        'object' &&
      save.inventory !== null &&
      this.isValidInventory(
        save.inventory.items,
      ) &&
      typeof save.equipment ===
        'object' &&
      save.equipment !== null &&
      typeof save.equipment.slots ===
        'object' &&
      save.equipment.slots !== null
    )
  }

  private isValidLegacySave(
    value: unknown,
  ): value is LegacyPlayerSave {
    if (
      typeof value !== 'object' ||
      value === null
    ) {
      return false
    }

    const save =
      value as Partial<LegacyPlayerSave>

    return (
      save.version === 1 &&
      this.isValidPlayer(save)
    )
  }

  private isValidPlayer(
    value: unknown,
  ): value is SavedPlayerProgress {
    if (
      typeof value !== 'object' ||
      value === null
    ) {
      return false
    }

    const player =
      value as Partial<SavedPlayerProgress>

    return (
      this.isValidNumber(
        player.level,
        1,
      ) &&
      this.isValidNumber(
        player.xp,
        0,
      ) &&
      this.isValidNumber(
        player.xpToNext,
        1,
      ) &&
      this.isValidNumber(
        player.maxHp,
        1,
      ) &&
      this.isValidNumber(
        player.attack,
        1,
      ) &&
      this.isValidNumber(
        player.coins,
        0,
      )
    )
  }

  private isValidInventory(
    value: unknown,
  ): value is InventoryStack[] {
    if (!Array.isArray(value)) {
      return false
    }

    return value.every(
      (item) => {
        if (
          typeof item !== 'object' ||
          item === null
        ) {
          return false
        }

        const stack =
          item as Partial<InventoryStack>

        return (
          typeof stack.itemId ===
            'string' &&
          stack.itemId.length > 0 &&
          typeof stack.quantity ===
            'number' &&
          Number.isInteger(
            stack.quantity,
          ) &&
          stack.quantity > 0
        )
      },
    )
  }

  private isValidNumber(
    value: unknown,
    minimum: number,
  ) {
    return (
      typeof value === 'number' &&
      Number.isFinite(value) &&
      value >= minimum
    )
  }
}
