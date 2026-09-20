import type {
  QuestDefinition,
} from './QuestTypes'

export const MEADOW_MENACE:
  QuestDefinition = {
    id: 'meadow-menace',

    title:
      'Meadow Menace',

    description:
      'Lyra needs help reducing the slime population around Starfall Meadow.',

    targetEnemyId:
      'slime',

    requiredKills:
      5,

    rewardCoins:
      120,

    rewardItems: [
      {
        itemId:
          'minor-potion',
        quantity: 2,
      },
    ],
  }
