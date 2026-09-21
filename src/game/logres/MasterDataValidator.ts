import type {
  LogresMasterData,
} from './MasterTypes'

export interface ValidationResult {
  valid: boolean
  errors: string[]
}

export function validateMasterData(
  data: LogresMasterData,
): ValidationResult {
  const errors: string[] = []

  const jobIds =
    new Set<string>()

  for (const job of data.jobs) {
    if (jobIds.has(job.id)) {
      errors.push(
        `Duplicate job id: ${job.id}`,
      )
    }

    jobIds.add(job.id)
  }

  const monsterIds =
    new Set(
      data.monsters.map(
        (monster) => monster.id,
      ),
    )

  for (const skill of data.skills) {
    for (
      const jobId of
        skill.allowedJobIds
    ) {
      if (!jobIds.has(jobId)) {
        errors.push(
          `Skill ${skill.id} references unknown job ${jobId}`,
        )
      }
    }

    if (skill.power <= 0) {
      errors.push(
        `Skill ${skill.id} has invalid power`,
      )
    }
  }

  for (const drop of data.drops) {
    if (
      !monsterIds.has(
        drop.monsterId,
      )
    ) {
      errors.push(
        `Drop ${drop.id} references unknown monster ${drop.monsterId}`,
      )
    }

    if (
      drop.chance < 0 ||
      drop.chance > 1
    ) {
      errors.push(
        `Drop ${drop.id} has invalid chance`,
      )
    }
  }

  for (const quest of data.quests) {
    if (
      quest.targetMonsterId &&
      !monsterIds.has(
        quest.targetMonsterId,
      )
    ) {
      errors.push(
        `Quest ${quest.id} references unknown monster ${quest.targetMonsterId}`,
      )
    }
  }

  return {
    valid:
      errors.length === 0,
    errors,
  }
}
