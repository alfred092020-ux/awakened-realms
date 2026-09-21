export interface ServerMutation<T> {
  requestId: string
  playerId: string
  payload: T
}

export interface EquipItemCommand {
  inventoryEntryId: string
  slot: string
}

export interface AcceptQuestCommand {
  questId: string
}

export interface UseSkillCommand {
  battleId: string
  skillId: string
  targetParticipantId: string
  clientSequence: number
}

export interface BasicAttackCommand {
  battleId: string
  targetParticipantId: string
  clientSequence: number
}

export interface MutationResult {
  accepted: boolean
  stateVersion: number
  message?: string
}
