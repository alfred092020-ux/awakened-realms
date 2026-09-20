import type {
  ItemDefinition,
} from './ItemTypes'

const ITEMS: Record<
  string,
  ItemDefinition
> = {
  'slime-gel': {
    id: 'slime-gel',
    name: 'Slime Gel',
    description:
      'A softly glowing gel gathered from meadow slimes.',
    category: 'material',
    rarity: 'common',
    maxStack: 99,
  },

  'minor-potion': {
    id: 'minor-potion',
    name: 'Minor Potion',
    description:
      'A basic restorative potion used by frontier Rangers.',
    category: 'consumable',
    rarity: 'common',
    maxStack: 20,
  },

  'novice-blade': {
    id: 'novice-blade',
    name: 'Novice Blade',
    description:
      'A simple training weapon issued to new Rangers.',
    category: 'weapon',
    rarity: 'common',
    maxStack: 1,
  },
}

export function getItemDefinition(
  itemId: string,
) {
  return ITEMS[itemId]
}

export function getAllItemDefinitions() {
  return Object.values(ITEMS)
}
