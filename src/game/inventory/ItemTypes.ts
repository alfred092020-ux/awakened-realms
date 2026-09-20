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

export interface ItemDefinition {
  id: string
  name: string
  description: string
  category: ItemCategory
  rarity: ItemRarity
  maxStack: number
}

export interface InventoryStack {
  itemId: string
  quantity: number
}
