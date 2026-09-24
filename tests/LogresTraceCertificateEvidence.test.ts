import { describe, expect, it } from 'vitest'

import {
  LOGRES_TRACE_CERTIFICATE_ARTIFACT,
  LOGRES_TRACE_CERTIFICATE_CLASSIFICATIONS,
  LOGRES_TRACE_CERTIFICATE_COUNTS,
  LOGRES_TRACE_CERTIFICATE_GUARDRAILS,
  LOGRES_TRACE_CERTIFICATE_ID,
  LOGRES_TRACE_CERTIFICATE_NEGATIVE_TESTS,
  LOGRES_TRACE_CERTIFICATE_OFFLINE_ONLY,
  LOGRES_TRACE_CERTIFICATE_PRIMARY_CLASSIFICATIONS,
  LOGRES_TRACE_CERTIFICATE_PRIMARY_TRANSITIONS,
  LOGRES_TRACE_CERTIFICATE_PRODUCTION_SERVER_ACCESS,
  LOGRES_TRACE_CERTIFICATE_PROVENANCE,
  LOGRES_TRACE_CERTIFICATE_SOURCES,
} from '../src/game/logres/reverse/LogresTraceCertificateEvidence'

describe('ZENITH offline replayable trace certificate', () => {
  it('is hash-bound to the deterministic certificate artifact', () => {
    expect(LOGRES_TRACE_CERTIFICATE_PROVENANCE)
      .toBe('ZENITH_OFFLINE_REPLAYABLE_TRACE_CERTIFICATE')
    expect(LOGRES_TRACE_CERTIFICATE_ID)
      .toBe('45afc19df46b72790189bad00d0decb0e90d884297bee85446b929c393958731')
    expect(LOGRES_TRACE_CERTIFICATE_ARTIFACT.sha256)
      .toBe('64219a3efc09dfa6424ed78a1711fea8f7f1c7dfe12122089f025d1aec94260f')
  })

  it('certifies the canonical twenty-step first-character loop', () => {
    expect(LOGRES_TRACE_CERTIFICATE_PRIMARY_TRANSITIONS).toHaveLength(20)
    expect(LOGRES_TRACE_CERTIFICATE_COUNTS.primaryTraceSteps).toBe(20)
    expect(LOGRES_TRACE_CERTIFICATE_PRIMARY_TRANSITIONS)
      .toEqual([
        0, 2, 3, 4, 7, 8, 10, 11, 12, 13,
        16, 17, 18, 21, 22, 23, 24, 25, 26, 27,
      ])
  })

  it('classifies every certified step without confidence promotion', () => {
    const classes = LOGRES_TRACE_CERTIFICATE_CLASSIFICATIONS
    expect(
      classes.proven
      + classes.stubbedServerAuthority
      + classes.lineageSupported
      + classes.implementationOnly
      + classes.unresolved,
    ).toBe(LOGRES_TRACE_CERTIFICATE_COUNTS.totalSteps)

    expect(classes.proven).toBe(11)
    expect(classes.stubbedServerAuthority).toBe(15)
    expect(LOGRES_TRACE_CERTIFICATE_PRIMARY_CLASSIFICATIONS)
      .toHaveLength(20)

    expect(LOGRES_TRACE_CERTIFICATE_GUARDRAILS)
      .toContain(
        'SERVER_AUTHORITY_STUB transitions can never be promoted to proven client facts.',
      )
  })

  it('binds every step to state/resource evidence and available protocol/function hashes', () => {
    expect(LOGRES_TRACE_CERTIFICATE_COUNTS.stepsWithResourceHash)
      .toBe(LOGRES_TRACE_CERTIFICATE_COUNTS.totalSteps)
    expect(LOGRES_TRACE_CERTIFICATE_COUNTS.stepsWithProtocolHash)
      .toBe(22)
    expect(LOGRES_TRACE_CERTIFICATE_COUNTS.stepsWithFunctionHash)
      .toBe(3)

    for (const hash of Object.values(LOGRES_TRACE_CERTIFICATE_SOURCES)) {
      expect(hash).toHaveLength(64)
    }
  })

  it('covers primary, movement, NPC and battle-retry traces offline', () => {
    expect(LOGRES_TRACE_CERTIFICATE_COUNTS.traces).toBe(4)
    expect(LOGRES_TRACE_CERTIFICATE_COUNTS.uniqueTransitionIds).toBe(24)
    expect(LOGRES_TRACE_CERTIFICATE_COUNTS.stateMachineTransitions).toBe(28)
    expect(LOGRES_TRACE_CERTIFICATE_OFFLINE_ONLY).toBe(true)
    expect(LOGRES_TRACE_CERTIFICATE_PRODUCTION_SERVER_ACCESS).toBe(false)
  })

  it('locks negative verification for illegal transitions, promotion and tampering', () => {
    expect(LOGRES_TRACE_CERTIFICATE_NEGATIVE_TESTS)
      .toEqual([
        'illegal_transition_rejected',
        'server_authority_promotion_rejected',
        'altered_evidence_hash_rejected',
      ])
    expect(LOGRES_TRACE_CERTIFICATE_GUARDRAILS)
      .toContain(
        'Illegal transition IDs, state-chain breaks and altered evidence hashes fail verification.',
      )
  })

  it('requires the already-PASS consistency and differential prerequisites', () => {
    expect(LOGRES_TRACE_CERTIFICATE_COUNTS.consistencyInvariantsPassed)
      .toBe(21)
    expect(LOGRES_TRACE_CERTIFICATE_COUNTS.differentialChecks).toBe(9)
  })
})
