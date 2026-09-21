import type {
  LogresMasterData,
} from './MasterTypes'

/*
 * Clean-room reconstruction catalog.
 *
 * Names that are known from the original client may be
 * retained as reference terminology during development.
 *
 * Numerical balance values below are NOT claimed to be
 * original Logres server values. They are deliberately
 * marked reconstructed until APK evidence confirms them.
 */

export const LOGRES_REFERENCE_DATA:
  LogresMasterData = {
  jobs: [
    {
      id: 'fighter',
      name: 'Fighter',
      role: 'damage',
      allowedWeapons: [
        'sword',
        'greatsword',
        'axe',
      ],
      baseStats: {
        hp: 135,
        physicalAttack: 26,
        magicalAttack: 8,
        physicalDefense: 18,
        magicalDefense: 12,
      },
      provenance: 'reconstructed',
      notes:
        'Starter balance placeholder. Replace when confirmed.',
    },
    {
      id: 'knight',
      name: 'Knight',
      role: 'tank',
      allowedWeapons: [
        'sword',
        'spear',
      ],
      baseStats: {
        hp: 165,
        physicalAttack: 19,
        magicalAttack: 8,
        physicalDefense: 27,
        magicalDefense: 17,
      },
      provenance: 'reconstructed',
      notes:
        'Starter balance placeholder. Replace when confirmed.',
    },
    {
      id: 'ranger',
      name: 'Ranger',
      role: 'damage',
      allowedWeapons: [
        'bow',
        'dagger',
      ],
      baseStats: {
        hp: 115,
        physicalAttack: 24,
        magicalAttack: 12,
        physicalDefense: 14,
        magicalDefense: 14,
      },
      provenance: 'reconstructed',
      notes:
        'Starter balance placeholder. Replace when confirmed.',
    },
    {
      id: 'priest',
      name: 'Priest',
      role: 'healer',
      allowedWeapons: [
        'staff',
        'wand',
      ],
      baseStats: {
        hp: 120,
        physicalAttack: 9,
        magicalAttack: 24,
        physicalDefense: 13,
        magicalDefense: 25,
      },
      provenance: 'reconstructed',
      notes:
        'Starter balance placeholder. Replace when confirmed.',
    },
    {
      id: 'mage',
      name: 'Mage',
      role: 'damage',
      allowedWeapons: [
        'staff',
        'wand',
      ],
      baseStats: {
        hp: 105,
        physicalAttack: 7,
        magicalAttack: 30,
        physicalDefense: 11,
        magicalDefense: 22,
      },
      provenance: 'reconstructed',
      notes:
        'Starter balance placeholder. Replace when confirmed.',
    },
  ],

  skills: [
    {
      id: 'reference-power-slash',
      name: 'Power Slash',
      element: 'neutral',
      power: 1.45,
      energyCost: 3,
      cooldownMs: 5500,
      allowedJobIds: [
        'fighter',
        'knight',
      ],
      provenance: 'reconstructed',
    },
    {
      id: 'reference-aimed-shot',
      name: 'Aimed Shot',
      element: 'wind',
      power: 1.4,
      energyCost: 3,
      cooldownMs: 5200,
      allowedJobIds: [
        'ranger',
      ],
      provenance: 'reconstructed',
    },
    {
      id: 'reference-heal',
      name: 'Heal',
      element: 'light',
      power: 1.2,
      energyCost: 3,
      cooldownMs: 6000,
      allowedJobIds: [
        'priest',
      ],
      provenance: 'reconstructed',
    },
    {
      id: 'reference-fire-burst',
      name: 'Fire Burst',
      element: 'fire',
      power: 1.55,
      energyCost: 4,
      cooldownMs: 6500,
      allowedJobIds: [
        'mage',
      ],
      provenance: 'reconstructed',
    },
  ],

  monsters: [
    {
      id: 'reference-slime',
      name: 'Slime',
      level: 1,
      element: 'neutral',
      stats: {
        hp: 90,
        physicalAttack: 11,
        magicalAttack: 0,
        physicalDefense: 6,
        magicalDefense: 5,
      },
      xpReward: 20,
      coinReward: 8,
      provenance: 'reconstructed',
    },
  ],

  drops: [],

  quests: [],
}
