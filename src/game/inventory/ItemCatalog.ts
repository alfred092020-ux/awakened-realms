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
    healAmount: 45,
  },

  'novice-blade': {
    id: 'novice-blade',
    name: 'Novice Blade',
    description:
      'A dependable starter blade forged for new Rangers.',
    category: 'weapon',
    rarity: 'uncommon',
    maxStack: 1,
    equipmentSlot: 'weapon',
    attackBonus: 6,
  },

  'ranger-vest': {
    id: 'ranger-vest',
    name: 'Ranger Vest',
    description:
      'Light frontier armor reinforced around vital areas.',
    category: 'armor',
    rarity: 'uncommon',
    maxStack: 1,
    equipmentSlot: 'armor',
    maxHpBonus: 30,
  },

  'meadow-charm': {
    id: 'meadow-charm',
    name: 'Meadow Charm',
    description:
      'A crystal charm carrying faint Starfall energy.',
    category: 'accessory',
    rarity: 'rare',
    maxStack: 1,
    equipmentSlot: 'accessory',
    attackBonus: 3,
    maxHpBonus: 15,
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
