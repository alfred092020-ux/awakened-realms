export type QuestStatus =
  | 'available'
  | 'active'
  | 'ready'
  | 'completed'

export interface QuestRewardItem {
  itemId: string
  quantity: number
}

export interface QuestDefinition {
  id: string
  title: string
  description: string
  targetEnemyId: string
  requiredKills: number
  rewardCoins: number
  rewardItems: QuestRewardItem[]
}

export interface QuestSaveData {
  version: 1
  questId: string
  status: QuestStatus
  progress: number
}

export interface QuestProgressResult {
  changed: boolean
  becameReady: boolean
}

export interface QuestInteractionResult {
  message: string
  accepted: boolean
  claimed: boolean
  rewardCoins: number
  rewardItems: QuestRewardItem[]
}
