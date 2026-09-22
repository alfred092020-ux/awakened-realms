import {
  LOGRES_CLIENT_FACTS,
} from '../generated/ExtractedClientFacts'

export interface LogresBattleFoundation {
  normalSkillSlots: number
  weaponSwitchGesture: string
  epRecoversByAttack: boolean
  epAnimation: boolean
  skillViewDefaultOffset:
    readonly [number, number]
  commandSkillNameOffset:
    readonly [number, number]
}

/**
 * CONFIRMED ORIGINAL client-side battle facts only.
 *
 * This deliberately excludes damage, enemy stats, cooldowns, reward values,
 * server authority and tutorial opponent identity until those are proven.
 */
export function getLogresBattleFoundation():
  LogresBattleFoundation {
  const {
    battle,
    equipment,
  } = LOGRES_CLIENT_FACTS

  return {
    normalSkillSlots:
      equipment.normalSkillSlots,
    weaponSwitchGesture:
      battle.weaponSwitchGesture,
    epRecoversByAttack:
      battle.epRecoversByAttack,
    epAnimation:
      battle.epAnimation,
    skillViewDefaultOffset:
      battle.skillViewDefaultOffset,
    commandSkillNameOffset:
      battle.commandSkillNameOffset,
  }
}

export function logresNormalSkillSlotIndices():
  readonly number[] {
  const count =
    LOGRES_CLIENT_FACTS
      .equipment
      .normalSkillSlots

  return Object.freeze(
    Array.from(
      {
        length: count,
      },
      (
        _,
        index,
      ) => index,
    ),
  )
}
