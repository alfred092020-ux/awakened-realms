export type ItemRarity =
  | 'common'
  | 'uncommon'
  | 'rare'
  | 'epic'
  | 'legendary'

export type ItemCategory =
  | 'material'
  | 'consumable'
  | 'weapon'
  | 'armor'
  | 'accessory'
  | 'quest'

export type EquipmentSlot =
  | 'weapon'
  | 'armor'
  | 'accessory'

export type EquipmentState =
  Partial<
    Record<
      EquipmentSlot,
      string
    >
  >

export interface ItemDefinition {
  id: string
  name: string
  description: string
  category: ItemCategory
  rarity: ItemRarity
  maxStack: number
  healAmount?: number
  equipmentSlot?: EquipmentSlot
  attackBonus?: number
  maxHpBonus?: number
}

export interface InventoryStack {
  itemId: string
  quantity: number
}
