import { describe, expect, it } from 'vitest'

import {
  LOGRES_GLOBAL_AREA_ENTER_PROJECTION,
  LOGRES_GLOBAL_BATTLE_HANDLER_EVIDENCE,
  LOGRES_GLOBAL_BATTLE_STATE_CHAIN,
  LOGRES_GLOBAL_CHARACTER_CREATE_TRANSITION,
  LOGRES_GLOBAL_CHARACTER_LOGIN_CODES,
  LOGRES_GLOBAL_ENCOUNTER_ENTRY,
  LOGRES_GLOBAL_FIELD_TRANSITION_CHAIN,
  LOGRES_GLOBAL_LOGIN_BRANCHES,
  LOGRES_GLOBAL_STATE_MACHINE_ARTIFACT,
  LOGRES_GLOBAL_STATE_MACHINE_COUNTS,
  LOGRES_GLOBAL_STATE_MACHINE_GUARDRAILS,
  LOGRES_GLOBAL_STATE_MACHINE_PROVENANCE,
} from '../src/game/logres/reverse/LogresGlobalStateMachineEvidence'

describe('Global 3.0.24 critical state machine', () => {
  it('publishes a bounded machine with exact protocol coverage', () => {
    expect(LOGRES_GLOBAL_STATE_MACHINE_PROVENANCE)
      .toBe('CONFIRMED_GLOBAL_3_0_24_CRITICAL_STATE_MACHINE_WITH_EXPLICIT_SERVER_CEILINGS')
    expect(LOGRES_GLOBAL_STATE_MACHINE_COUNTS)
      .toEqual({ states: 23, transitions: 28, boundProtocolIds: 30 })
  })

  it('recovers login scene branching from Global code', () => {
    expect(LOGRES_GLOBAL_LOGIN_BRANCHES.emptyCharacterList.destination)
      .toBe('ReleaseScene_CharcterMake::create')
    expect(LOGRES_GLOBAL_LOGIN_BRANCHES.existingCharacterList.destination)
      .toBe('ReleaseScene_CharacterLogin::create')
    expect(LOGRES_GLOBAL_LOGIN_BRANCHES.titleFallback.destination)
      .toBe('ReleaseScene_Title::create')
    expect(LOGRES_GLOBAL_LOGIN_BRANCHES.recovery.destination).toBeNull()
  })

  it('recovers character-create and character-login result behavior', () => {
    expect(LOGRES_GLOBAL_CHARACTER_CREATE_TRANSITION.successCode).toBe(0)
    expect(LOGRES_GLOBAL_CHARACTER_CREATE_TRANSITION.successDestination)
      .toBe('ReleaseScene_CharacterLogin::create')
    expect(LOGRES_GLOBAL_CHARACTER_LOGIN_CODES.acceptedCodes)
      .toEqual([1, 2, 3, 4])
    expect(LOGRES_GLOBAL_CHARACTER_LOGIN_CODES.recoveryEmitsRecoveryEvent)
      .toBe(true)
  })

  it('binds field and encounter boundaries to original Global messages', () => {
    expect(LOGRES_GLOBAL_FIELD_TRANSITION_CHAIN.at(-1))
      .toBe('S_GMCL_AREA_ENTER')
    expect(LOGRES_GLOBAL_AREA_ENTER_PROJECTION.opcode).toBe('0x6dff0f05')
    expect(LOGRES_GLOBAL_ENCOUNTER_ENTRY.acceptedCode).toBe(1)
    expect(LOGRES_GLOBAL_ENCOUNTER_ENTRY.retryCode).toBe(2)
    expect(LOGRES_GLOBAL_ENCOUNTER_ENTRY.retrySeconds).toBe(1.0)
  })

  it('binds battle result and reward return without inventing server rules', () => {
    expect(LOGRES_GLOBAL_BATTLE_STATE_CHAIN)
      .toEqual([
        'BATTLE_ENTRY_PENDING',
        'BATTLE_ACCEPTED',
        'BATTLE_INITIALIZING',
        'BOUT_ACTIVE',
        'BATTLE_RESULT',
        'REWARD_PROJECTION',
        'FIELD_RETURN',
      ])
    expect(LOGRES_GLOBAL_BATTLE_HANDLER_EVIDENCE.initialize.opcode)
      .toBe('0xdb83b305')
    expect(LOGRES_GLOBAL_BATTLE_HANDLER_EVIDENCE.result.opcode)
      .toBe('0x5b1ffeba')
    expect(LOGRES_GLOBAL_BATTLE_HANDLER_EVIDENCE.questReturn.opcode)
      .toBe('0xd5567b24')
    expect(LOGRES_GLOBAL_STATE_MACHINE_GUARDRAILS.join(' '))
      .toContain('not invented')
    expect(LOGRES_GLOBAL_STATE_MACHINE_ARTIFACT.sha256)
      .toHaveLength(64)
  })
})
