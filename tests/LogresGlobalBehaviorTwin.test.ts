import { describe, expect, it } from 'vitest'

import {
  EvidenceExceededError,
  GLOBAL_BEHAVIOR_TRANSITIONS,
  LogresGlobalBehaviorTwin,
  assertImplementationWithinEvidence,
  compareBehaviorTrace,
  serverAuthorityStub,
  type ImplementationTraceStep,
} from '../src/game/logres/reverse/LogresGlobalBehaviorTwin'
import {
  LOGRES_GLOBAL_BEHAVIOR_TWIN_COUNTS,
  LOGRES_GLOBAL_BEHAVIOR_TWIN_CRITICAL_TRACE,
  LOGRES_GLOBAL_BEHAVIOR_TWIN_EXACT_RULES,
  LOGRES_GLOBAL_BEHAVIOR_TWIN_GUARDRAILS,
  LOGRES_GLOBAL_BEHAVIOR_TWIN_PROVENANCE,
  LOGRES_GLOBAL_BEHAVIOR_TWIN_SOURCES,
} from '../src/game/logres/reverse/LogresGlobalBehaviorTwinEvidence'

const stub = <T>(value: T, ceiling = 'offline deterministic fixture') =>
  serverAuthorityStub(value, ceiling)

describe('OMEGA Global behavior twin', () => {
  it('replays the first-character critical loop through field return', () => {
    const twin = new LogresGlobalBehaviorTwin()
    twin.tapStart()
    twin.receiveAccountLogin(stub(1))
    twin.receiveCharacterList(stub({ count: 0 }))
    twin.resolvePrebeginBranch()
    twin.receiveCharacterCreate(stub(0))
    twin.receiveCharacterLogin(stub(1))
    twin.beginFieldBootstrap()
    twin.receiveFieldSelect(stub({}))
    twin.requestZoneIn()
    twin.receiveAreaEnter(stub({}))
    twin.receiveEnemyAppear(stub({}))
    twin.requestBattleEntry()
    twin.receiveBattleEntry(stub(1))
    twin.receiveBattleInitialize(stub({}))
    twin.receiveBoutInitialize(stub({}))
    twin.requestUseSkill()
    twin.receiveBattleResult(stub({}))
    twin.receiveQuestResult(stub({}))
    twin.receiveQuestReturn(stub({}))
    twin.resumeField()

    expect(twin.state).toBe('AREA_ACTIVE')
    expect(twin.trace).toHaveLength(
      LOGRES_GLOBAL_BEHAVIOR_TWIN_COUNTS.successfulFirstCharacterCriticalTraceSteps,
    )
    const states = [twin.trace[0].from, ...twin.trace.map((step) => step.to)]
    expect(states).toEqual(LOGRES_GLOBAL_BEHAVIOR_TWIN_CRITICAL_TRACE)
    expect(
      twin.trace
        .filter((step) => step.serverAuthority)
        .every((step) => Boolean(step.stubEvidenceCeiling)),
    ).toBe(true)
  })

  it('models movement and NPC interaction as separate field branches', () => {
    const movement = new LogresGlobalBehaviorTwin({ initialState: 'AREA_ACTIVE' })
    movement.requestMove()
    expect(movement.state).toBe('FIELD_MOVEMENT')
    expect(movement.trace[0].message).toBe('C_GMCL_CHAR_MOVE_REQ')

    const npc = new LogresGlobalBehaviorTwin({ initialState: 'AREA_ACTIVE' })
    npc.requestNpcTalk()
    expect(npc.state).toBe('NPC_INTERACTION')
    expect(npc.trace[0].message).toBe('C_GMCL_CHAR_TALK_REQ')
  })

  it('enforces the exact battle-entry retry rule', () => {
    const twin = new LogresGlobalBehaviorTwin({ initialState: 'AREA_ACTIVE' })
    twin.receiveEnemyAppear(stub({}))
    twin.requestBattleEntry()
    twin.receiveBattleEntry(stub(2))
    expect(twin.state).toBe('BATTLE_ENTRY_RETRY_WAIT')
    expect(() => twin.elapseBattleRetry(0.5)).toThrow(EvidenceExceededError)
    expect(() => twin.elapseBattleRetry(2)).toThrow(EvidenceExceededError)
    twin.elapseBattleRetry(1)
    expect(twin.state).toBe('BATTLE_ENTRY_PENDING')
    expect(LOGRES_GLOBAL_BEHAVIOR_TWIN_EXACT_RULES.battleEntryRetrySeconds).toBe(1)
  })

  it('requires explicit authority stubs and rejects unknown result codes', () => {
    const area = new LogresGlobalBehaviorTwin({ initialState: 'ZONEIN' })
    expect(() => area.receiveAreaEnter(undefined as never))
      .toThrow('SERVER_AUTHORITY_STUB')

    const battle = new LogresGlobalBehaviorTwin({
      initialState: 'BATTLE_ENTRY_PENDING',
    })
    expect(() => battle.receiveBattleEntry(stub(99)))
      .toThrow(EvidenceExceededError)

    const create = new LogresGlobalBehaviorTwin({ initialState: 'GENDER_CREATE' })
    expect(() => create.receiveCharacterCreate(stub(1)))
      .toThrow(EvidenceExceededError)
  })

  it('compares implementation traces transition by transition', () => {
    const twin = new LogresGlobalBehaviorTwin({ initialState: 'AREA_ACTIVE' })
    twin.receiveEnemyAppear(stub({}))
    twin.requestBattleEntry()
    twin.receiveBattleEntry(stub(1))

    const actual: ImplementationTraceStep[] = twin.trace.map((step) => ({
      from: step.from,
      to: step.to,
      message: step.message,
      event: step.event,
      serverAuthorityClaim: step.serverAuthority
        ? 'SERVER_STUB'
        : 'CLIENT_PROJECTION',
    }))
    expect(compareBehaviorTrace(twin.trace, actual).pass).toBe(true)

    const changed: ImplementationTraceStep[] = actual.map((step) => ({ ...step }))
    changed[1] = { ...changed[1], to: 'FIELD_RETURN' }
    const comparison = compareBehaviorTrace(twin.trace, changed)
    expect(comparison.pass).toBe(false)
    expect(comparison.mismatches[0]).toContain('step 1')
  })

  it('fails when implementation behavior exceeds recovered evidence', () => {
    expect(() =>
      assertImplementationWithinEvidence([
        {
          from: 'TITLE',
          to: 'BATTLE_RESULT',
          event: 'invented shortcut',
          serverAuthorityClaim: 'CLIENT_PROJECTION',
        },
      ]),
    ).toThrow(EvidenceExceededError)

    expect(() =>
      assertImplementationWithinEvidence([
        {
          from: 'ZONEIN',
          to: 'AREA_ACTIVE',
          message: 'S_GMCL_AREA_ENTER',
          serverAuthorityClaim: 'CONFIRMED_RETIRED_SERVER',
        },
      ]),
    ).toThrow('promotes retired-server authority beyond evidence')
  })

  it('preserves graph dimensions and exact source hashes', () => {
    expect(LOGRES_GLOBAL_BEHAVIOR_TWIN_PROVENANCE)
      .toBe('OMEGA_OFFLINE_GLOBAL_BEHAVIOR_TWIN_WITH_EXPLICIT_SERVER_STUBS')
    expect(GLOBAL_BEHAVIOR_TRANSITIONS).toHaveLength(28)
    expect(
      new Set(
        GLOBAL_BEHAVIOR_TRANSITIONS.flatMap((step) => [step.from, step.to]),
      ).size,
    ).toBe(23)
    expect(
      GLOBAL_BEHAVIOR_TRANSITIONS.filter((step) => step.serverAuthority),
    ).toHaveLength(16)
    expect(LOGRES_GLOBAL_BEHAVIOR_TWIN_SOURCES.offlineProtocolTwinSha256)
      .toHaveLength(64)
    expect(LOGRES_GLOBAL_BEHAVIOR_TWIN_SOURCES.semanticLiftSha256)
      .toHaveLength(64)
  })

  it('keeps external dynamics as explicit evidence ceilings', () => {
    expect(LOGRES_GLOBAL_BEHAVIOR_TWIN_GUARDRAILS)
      .toContain(
        'Battle damage, stats, cooldowns, EP, reward rolls, persistence, matchmaking and exact historical dynamic payloads remain external evidence ceilings.',
      )
    expect(LOGRES_GLOBAL_BEHAVIOR_TWIN_COUNTS.semanticLiftedFunctions)
      .toBe(16379)
  })
})
