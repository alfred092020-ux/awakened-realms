import type {
  QuestDefinition,
  QuestId,
} from './QuestTypes'

export const MEADOW_MENACE:
  QuestDefinition = {
    id: 'meadow-menace',

    giverId: 'lyra',
    giverName: 'Lyra',

    title:
      'Meadow Menace',

    description:
      'Lyra needs help reducing the slime population around Starfall Meadow.',

    targetEnemyId:
      'slime',

    progressLabel:
      'Slimes defeated',

    requiredKills: 5,

    rewardCoins: 120,

    rewardItems: [
      {
        itemId:
          'minor-potion',
        quantity: 2,
      },
    ],

    lockedMessage:
      'This quest is not available yet.',

    acceptMessage:
      'The meadow slimes are multiplying too quickly.\nDefeat 5 slimes and return to me.',

    readyMessage:
      'Excellent work. Starfall Meadow is safer because of you.',

    completedMessage:
      'You handled those slimes well, Ranger.\nSeren watches the eastern grove. She may need your help.',
  }

export const MOONVEIL_HUNT:
  QuestDefinition = {
    id: 'moonveil-hunt',

    giverId: 'seren',
    giverName: 'Seren',

    title:
      'Fangs in the Moonlight',

    description:
      'Moonfangs have begun hunting near the paths of Moonveil Grove.',

    targetEnemyId:
      'moonfang',

    progressLabel:
      'Moonfangs defeated',

    requiredKills: 4,

    rewardCoins: 220,

    rewardItems: [
      {
        itemId:
          'minor-potion',
        quantity: 2,
      },
      {
        itemId:
          'meadow-charm',
        quantity: 1,
      },
    ],

    requiresQuestId:
      'meadow-menace',

    lockedMessage:
      'The grove is dangerous tonight.\nFinish helping Lyra in Starfall Meadow first.',

    acceptMessage:
      'Moonfangs are stalking the grove paths.\nDefeat 4 Moonfangs and return to me.',

    readyMessage:
      'The howling has finally quieted.\nYou have earned the trust of Moonveil Grove.',

    completedMessage:
      'Moonveil Grove remembers those who defend it.\nThe deeper wilds will not be so forgiving.',
  }

export const QUEST_DEFINITIONS:
  Record<
    QuestId,
    QuestDefinition
  > = {
    'meadow-menace':
      MEADOW_MENACE,

    'moonveil-hunt':
      MOONVEIL_HUNT,
  }

export const QUEST_ORDER:
  QuestId[] = [
    'meadow-menace',
    'moonveil-hunt',
  ]
