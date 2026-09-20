import type {
  MetaUpgradeId,
} from './MetaTypes'

export interface MetaUpgradeDefinition {
  id: MetaUpgradeId

  name: string

  description: string

  maximumLevel: number

  baseCost: number

  costGrowth: number
}

export const META_UPGRADES:
  readonly MetaUpgradeDefinition[] = [
    {
      id:
        'attack-training',

      name:
        'Attack Training',

      description:
        '+5% starting attack per level.',

      maximumLevel:
        20,

      baseCost:
        8,

      costGrowth:
        1.35,
    },

    {
      id:
        'vitality-training',

      name:
        'Vitality Training',

      description:
        '+6% starting HP per level.',

      maximumLevel:
        20,

      baseCost:
        8,

      costGrowth:
        1.35,
    },

    {
      id:
        'haste-training',

      name:
        'Haste Training',

      description:
        '+3% starting attack speed per level.',

      maximumLevel:
        15,

      baseCost:
        10,

      costGrowth:
        1.42,
    },

    {
      id:
        'idle-mastery',

      name:
        'Idle Mastery',

      description:
        '+10% offline Essence earned per level.',

      maximumLevel:
        10,

      baseCost:
        12,

      costGrowth:
        1.5,
    },
  ]

export function getMetaUpgrade(
  id: MetaUpgradeId,
) {
  return META_UPGRADES.find(
    (upgrade) =>
      upgrade.id === id,
  )
}

export function getMetaUpgradeCost(
  id: MetaUpgradeId,
  currentLevel: number,
) {
  const definition =
    getMetaUpgrade(id)

  if (!definition) {
    throw new Error(
      'Unknown meta upgrade.',
    )
  }

  return Math.ceil(
    definition.baseCost *
      Math.pow(
        definition.costGrowth,
        Math.max(
          0,
          currentLevel,
        ),
      ),
  )
}
