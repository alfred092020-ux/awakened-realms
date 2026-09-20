export type QuestId =
  | 'meadow-menace'
  | 'moonveil-hunt'

export type QuestStatus =
  | 'locked'
  | 'available'
  | 'active'
  | 'ready'
  | 'completed'

export interface QuestRewardItem {
  itemId: string
  quantity: number
}

export interface QuestDefinition {
  id: QuestId
  giverId: string
  giverName: string

  title: string
  description: string

  targetEnemyId: string
  progressLabel: string
  requiredKills: number

  rewardCoins: number
  rewardItems: QuestRewardItem[]

  requiresQuestId?: QuestId

  lockedMessage: string
  acceptMessage: string
  readyMessage: string
  completedMessage: string
}

export interface QuestState {
  status: QuestStatus
  progress: number
}

export interface QuestSaveData {
  version: 2
  quests: Record<
    QuestId,
    QuestState
  >
}

export interface QuestProgressResult {
  changed: boolean
  becameReady: boolean
  questId?: QuestId
}

export interface QuestInteractionResult {
  questId: QuestId
  message: string

  accepted: boolean
  claimed: boolean

  rewardCoins: number
  rewardItems: QuestRewardItem[]
}
