import {
  LOGRES_REFERENCE_DATA,
} from '../ReferenceCatalog'

export type SkillRejectionReason =
  | 'unknown-skill'
  | 'job-not-allowed'
  | 'insufficient-energy'
  | 'cooldown-active'

export interface SkillUseContext {
  jobId: string
  skillId: string
  currentEnergy: number
  cooldownRemainingMs: number
}

export interface SkillUseDecision {
  allowed: boolean
  reason?: SkillRejectionReason
  energyCost?: number
  power?: number
}

export function validateSkillUse(
  context: SkillUseContext,
): SkillUseDecision {
  const skill =
    LOGRES_REFERENCE_DATA.skills
      .find(
        (candidate) =>
          candidate.id ===
          context.skillId,
      )

  if (!skill) {
    return {
      allowed: false,
      reason: 'unknown-skill',
    }
  }

  if (
    !skill.allowedJobIds.includes(
      context.jobId,
    )
  ) {
    return {
      allowed: false,
      reason: 'job-not-allowed',
    }
  }

  if (
    context.currentEnergy <
    skill.energyCost
  ) {
    return {
      allowed: false,
      reason: 'insufficient-energy',
    }
  }

  if (
    context.cooldownRemainingMs >
    0
  ) {
    return {
      allowed: false,
      reason: 'cooldown-active',
    }
  }

  return {
    allowed: true,
    energyCost:
      skill.energyCost,
    power:
      skill.power,
  }
}
