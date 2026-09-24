import { describe, expect, it } from 'vitest'

import {
  LOGRES_ZENITH_COUNTERFACTUAL_ARTIFACT,
  LOGRES_ZENITH_COUNTERFACTUAL_CLASSES,
  LOGRES_ZENITH_COUNTERFACTUAL_COUNTS,
  LOGRES_ZENITH_COUNTERFACTUAL_GUARDRAILS,
  LOGRES_ZENITH_COUNTERFACTUAL_LAB_ID,
  LOGRES_ZENITH_COUNTERFACTUAL_PROVENANCE,
} from '../src/game/logres/reverse/LogresCounterfactualLabEvidence'

describe('ZENITH Global 3.0.24 counterfactual lab', () => {
  it('proves shortest-path reachability for every recovered client state', () => {
    expect(LOGRES_ZENITH_COUNTERFACTUAL_PROVENANCE)
      .toBe('ZENITH_OFFLINE_COUNTERFACTUAL_MODEL_FROM_CONFIRMED_GLOBAL_CLIENT_EVIDENCE')
    expect(LOGRES_ZENITH_COUNTERFACTUAL_COUNTS.states).toBe(23)
    expect(LOGRES_ZENITH_COUNTERFACTUAL_COUNTS.reachableStates).toBe(23)
    expect(LOGRES_ZENITH_COUNTERFACTUAL_COUNTS.unreachableStates).toBe(0)
    expect(LOGRES_ZENITH_COUNTERFACTUAL_COUNTS.longestShortestTraceState)
      .toBe('FIELD_RETURN')
    expect(LOGRES_ZENITH_COUNTERFACTUAL_COUNTS.longestShortestTraceSteps)
      .toBe(15)
  })

  it('separates client-only transitions from server-authority boundaries', () => {
    expect(
      LOGRES_ZENITH_COUNTERFACTUAL_COUNTS.clientOnlyTransitions
      + LOGRES_ZENITH_COUNTERFACTUAL_COUNTS.serverAuthorityTransitions
    ).toBe(LOGRES_ZENITH_COUNTERFACTUAL_COUNTS.transitions)
    expect(LOGRES_ZENITH_COUNTERFACTUAL_COUNTS.clientOnlyTransitions).toBe(10)
    expect(LOGRES_ZENITH_COUNTERFACTUAL_COUNTS.serverAuthorityTransitions)
      .toBe(18)
  })

  it('classifies every behavioral counterfactual without inventing history', () => {
    expect(LOGRES_ZENITH_COUNTERFACTUAL_COUNTS.behavioralCounterfactualCases)
      .toBe(42)
    expect(
      LOGRES_ZENITH_COUNTERFACTUAL_COUNTS.clientKnownBranches
      + LOGRES_ZENITH_COUNTERFACTUAL_COUNTS.clientImpossible
      + LOGRES_ZENITH_COUNTERFACTUAL_COUNTS.serverUnknown
      + LOGRES_ZENITH_COUNTERFACTUAL_COUNTS.evidenceMismatch
    ).toBe(42)
    expect(LOGRES_ZENITH_COUNTERFACTUAL_COUNTS.clientKnownBranches).toBe(22)
    expect(LOGRES_ZENITH_COUNTERFACTUAL_COUNTS.clientImpossible).toBe(8)
    expect(LOGRES_ZENITH_COUNTERFACTUAL_COUNTS.serverUnknown).toBe(8)
    expect(LOGRES_ZENITH_COUNTERFACTUAL_COUNTS.evidenceMismatch).toBe(4)
  })

  it('keeps unknown server behavior distinct from impossible client sequences', () => {
    expect(LOGRES_ZENITH_COUNTERFACTUAL_CLASSES.SERVER_UNKNOWN)
      .toContain('does not establish how the retired server behaves')
    expect(LOGRES_ZENITH_COUNTERFACTUAL_CLASSES.CLIENT_IMPOSSIBLE)
      .toContain('not an evidenced outgoing transition')
    expect(LOGRES_ZENITH_COUNTERFACTUAL_GUARDRAILS)
      .toContain('Counterfactuals are never promoted to historical observations.')
  })

  it('is deterministic and offline-only', () => {
    expect(LOGRES_ZENITH_COUNTERFACTUAL_LAB_ID).toHaveLength(64)
    expect(LOGRES_ZENITH_COUNTERFACTUAL_GUARDRAILS)
      .toContain('No live production game server is contacted.')
    expect(LOGRES_ZENITH_COUNTERFACTUAL_ARTIFACT)
      .toContain('global3024-counterfactual-lab')
  })
})
