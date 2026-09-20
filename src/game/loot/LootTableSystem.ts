export interface LootEntry {
  itemId: string
  chance: number
  minQuantity: number
  maxQuantity: number
}

export interface LootDrop {
  itemId: string
  quantity: number
}

export const SLIME_LOOT_TABLE:
  LootEntry[] = [
    {
      itemId: 'slime-gel',
      chance: 0.85,
      minQuantity: 1,
      maxQuantity: 2,
    },
    {
      itemId: 'minor-potion',
      chance: 0.2,
      minQuantity: 1,
      maxQuantity: 1,
    },
    {
      itemId: 'novice-blade',
      chance: 0.08,
      minQuantity: 1,
      maxQuantity: 1,
    },
    {
      itemId: 'ranger-vest',
      chance: 0.06,
      minQuantity: 1,
      maxQuantity: 1,
    },
    {
      itemId: 'meadow-charm',
      chance: 0.03,
      minQuantity: 1,
      maxQuantity: 1,
    },
  ]

export class LootTableSystem {
  roll(
    entries: LootEntry[],
  ): LootDrop[] {
    const drops: LootDrop[] = []

    for (const entry of entries) {
      if (
        Math.random() >
        entry.chance
      ) {
        continue
      }

      const quantity =
        this.randomInteger(
          entry.minQuantity,
          entry.maxQuantity,
        )

      drops.push({
        itemId: entry.itemId,
        quantity,
      })
    }

    return drops
  }

  private randomInteger(
    minimum: number,
    maximum: number,
  ) {
    const min =
      Math.ceil(minimum)

    const max =
      Math.floor(maximum)

    return Math.floor(
      Math.random() *
        (max - min + 1),
    ) + min
  }
}
