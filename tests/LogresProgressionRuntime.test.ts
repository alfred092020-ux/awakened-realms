import { describe, expect, it } from 'vitest'
import {
  InMemoryLogresProgressionPersistence,
  LOGRES_PROGRESSION_EVIDENCE,
  LogresProgressionAuthority,
  createLogresLevelCurve,
} from '../src/game/logres/progression/LogresProgressionRuntime'

const session = {
  accountId: 'faker-account',
  sessionId: 'session-a',
  authenticated: true,
} as const
const characterCurve = createLogresLevelCurve(
  'character-reconstruction-v1',
  [0, 100, 300, 700],
)
const noviceCurve = createLogresLevelCurve(
  'novice-reconstruction-v1',
  [0, 50, 150, 350],
)

function createAuthority(
  store = new InMemoryLogresProgressionPersistence(),
) {
  return {
    store,
    authority: new LogresProgressionAuthority(store, {
      characterCurve,
      jobCurves: { novice: noviceCurve },
    }),
  }
}

function initialize(authority: LogresProgressionAuthority) {
  return authority.initialize(session, {
    characterLevel: 1,
    characterXp: 0,
    activeJobId: 'novice',
    jobs: { novice: { level: 1, xp: 0 } },
  })
}

describe('Logres progression authority', () => {
  it('binds recovered job authority without claiming original XP formulas', () => {
    expect(LOGRES_PROGRESSION_EVIDENCE.jobChangeRequest.name)
      .toBe('C_GMCL_JOB_CHANGE_REQ')
    expect(LOGRES_PROGRESSION_EVIDENCE.jobChangeProjection.name)
      .toBe('S_GMCL_JOB_CHANGE_INFO')
    expect(LOGRES_PROGRESSION_EVIDENCE.serverTables)
      .toContain('S_GMCL_CHAR_LEVEL_MODIFY')
    expect(LOGRES_PROGRESSION_EVIDENCE.formulaPolicy)
      .toContain('No historical XP/level threshold is guessed')
  })

  it('levels character state using an explicit reconstructed curve', () => {
    const { authority } = createAuthority()
    initialize(authority)
    const levelTwo = authority.grantCharacterXp(session, 100, 'char-xp-1')
    expect(levelTwo.characterXp).toBe(100)
    expect(levelTwo.characterLevel).toBe(2)
    const levelThree = authority.grantCharacterXp(session, 200, 'char-xp-2')
    expect(levelThree.characterLevel).toBe(3)
    expect(levelThree.revision).toBe(2)
  })

  it('makes XP grants idempotent by command id', () => {
    const { authority } = createAuthority()
    initialize(authority)
    const first = authority.grantCharacterXp(session, 125, 'same-grant')
    const repeated = authority.grantCharacterXp(session, 125, 'same-grant')
    expect(repeated).toEqual(first)
    expect(repeated.characterXp).toBe(125)
    expect(repeated.revision).toBe(1)
  })

  it('persists job XP and active job across reconnect authority instances', () => {
    const { store, authority } = createAuthority()
    initialize(authority)
    const jobXp = authority.grantJobXp(session, 'novice', 150, 'job-xp-1')
    expect(jobXp.jobs.novice.level).toBe(3)
    const changed = authority.changeJob(session, 'novice', 'job-change-1')
    const reconnect = new LogresProgressionAuthority(store, {
      characterCurve,
      jobCurves: { novice: noviceCurve },
    })
    expect(reconnect.read(session)).toEqual(changed)
  })

  it('fails closed when the historical progression curve is unknown', () => {
    const store = new InMemoryLogresProgressionPersistence()
    const authority = new LogresProgressionAuthority(store, {
      characterCurve: null,
      jobCurves: {},
    })
    authority.initialize(session, {
      characterLevel: 1,
      characterXp: 0,
      activeJobId: null,
      jobs: {},
    })
    expect(() => authority.grantCharacterXp(session, 1, 'unknown-formula'))
      .toThrow('refusing to invent historical progression formula')
  })

  it('rejects unauthenticated mutation and unseeded job changes', () => {
    const { authority } = createAuthority()
    initialize(authority)
    expect(() =>
      authority.grantCharacterXp(
        { ...session, authenticated: false },
        1,
        'no-auth',
      ),
    ).toThrow('authenticated session')
    expect(() => authority.changeJob(session, 'fighter', 'unknown-job'))
      .toThrow('explicitly known job state')
  })
})
