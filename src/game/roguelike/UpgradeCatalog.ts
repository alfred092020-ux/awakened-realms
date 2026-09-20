import type {
  UpgradeDefinition,
  UpgradeId,
} from './RunTypes'

export const RUN_UPGRADES:
  readonly UpgradeDefinition[] = [
    {
      id:
        'power-surge',

      name:
        'Power Surge',

      description:
        'Increase attack by 20%.',
    },

    {
      id:
        'vital-core',

      name:
        'Vital Core',

      description:
        'Increase maximum HP by 25% and heal the gained HP.',
    },

    {
      id:
        'quickening',

      name:
        'Quickening',

      description:
        'Attack 15% faster.',
    },

    {
      id:
        'critical-eye',

      name:
        'Critical Eye',

      description:
        'Gain 8% critical hit chance.',
    },

    {
      id:
        'aegis',

      name:
        'Aegis',

      description:
        'Reduce incoming damage by 8%.',
    },

    {
      id:
        'renewal',

      name:
        'Renewal',

      description:
        'Recover 6 HP after every enemy defeated.',
    },
  ]

export function
getRunUpgrade(
  id: UpgradeId,
) {
  return RUN_UPGRADES
    .find(
      (upgrade) =>
        upgrade.id === id,
    )
}
