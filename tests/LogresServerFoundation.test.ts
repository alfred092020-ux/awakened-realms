import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  validateSkillUse,
} from '../src/game/logres/server/AuthorityGuards'

describe(
  'Logres authoritative server foundation',
  () => {
    it(
      'allows a valid job skill',
      () => {
        const result =
          validateSkillUse({
            jobId: 'fighter',
            skillId:
              'reference-power-slash',
            currentEnergy: 10,
            cooldownRemainingMs: 0,
          })

        expect(result.allowed)
          .toBe(true)

        expect(result.energyCost)
          .toBe(3)
      },
    )

    it(
      'rejects skills from the wrong job',
      () => {
        const result =
          validateSkillUse({
            jobId: 'mage',
            skillId:
              'reference-power-slash',
            currentEnergy: 10,
            cooldownRemainingMs: 0,
          })

        expect(result)
          .toEqual({
            allowed: false,
            reason:
              'job-not-allowed',
          })
      },
    )

    it(
      'rejects insufficient energy',
      () => {
        const result =
          validateSkillUse({
            jobId: 'mage',
            skillId:
              'reference-fire-burst',
            currentEnergy: 2,
            cooldownRemainingMs: 0,
          })

        expect(result.reason)
          .toBe(
            'insufficient-energy',
          )
      },
    )

    it(
      'rejects active cooldowns',
      () => {
        const result =
          validateSkillUse({
            jobId: 'ranger',
            skillId:
              'reference-aimed-shot',
            currentEnergy: 10,
            cooldownRemainingMs:
              2500,
          })

        expect(result.reason)
          .toBe(
            'cooldown-active',
          )
      },
    )
  },
)
