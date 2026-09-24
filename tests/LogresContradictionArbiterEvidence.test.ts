import { describe, expect, it } from 'vitest'

import {
  LOGRES_CONTRADICTION_ARBITER_ARTIFACT,
  LOGRES_CONTRADICTION_ARBITER_COUNTS,
  LOGRES_CONTRADICTION_ARBITER_GUARDRAILS,
  LOGRES_CONTRADICTION_ARBITER_PROVENANCE,
  LOGRES_CONTRADICTION_AUTHORITY_ORDER,
  LOGRES_CONTRADICTION_RESOLVED_EXAMPLES,
  LOGRES_CONTRADICTION_UNRESOLVED_EXAMPLES,
} from '../src/game/logres/reverse/LogresContradictionArbiterEvidence'

describe('Logres contradiction arbiter', () => {
  it('uses deterministic provenance authority rather than recency', () => {
    expect(LOGRES_CONTRADICTION_ARBITER_PROVENANCE)
      .toBe('DETERMINISTIC_ARBITRATION_OVER_EXISTING_PROVENANCE_GRAPH')
    expect(LOGRES_CONTRADICTION_AUTHORITY_ORDER[0]).toBe('GLOBAL_DIRECT')
    expect(LOGRES_CONTRADICTION_AUTHORITY_ORDER.at(-1))
      .toBe('SPECULATION_OR_UNRESOLVED')
  })

  it('resolves only conflicts with a supported authority winner', () => {
    expect(LOGRES_CONTRADICTION_ARBITER_COUNTS.explicitConflictTasks).toBe(15)
    expect(LOGRES_CONTRADICTION_ARBITER_COUNTS.resolvedByAuthority).toBe(6)
    expect(LOGRES_CONTRADICTION_RESOLVED_EXAMPLES.globalStateMachine.winningAuthority)
      .toBe('GLOBAL_DIRECT')
  })

  it('does not manufacture winners from weak evidence', () => {
    expect(LOGRES_CONTRADICTION_ARBITER_COUNTS.unresolvedLowAuthority).toBe(8)
    expect(LOGRES_CONTRADICTION_UNRESOLVED_EXAMPLES.androidVisualQa.result)
      .toBe('UNRESOLVED_LOW_AUTHORITY')
    expect(LOGRES_CONTRADICTION_ARBITER_GUARDRAILS)
      .toContain('Speculation or unresolved evidence can never win merely because it is the only claim.')
  })

  it('preserves same-authority disagreements as unresolved', () => {
    expect(LOGRES_CONTRADICTION_ARBITER_COUNTS.unresolvedSameAuthorityTie)
      .toBe(1)
    expect(LOGRES_CONTRADICTION_UNRESOLVED_EXAMPLES.millenniumTreeVideoTie.result)
      .toBe('UNRESOLVED_SAME_AUTHORITY_TIE')
  })

  it('preserves external ceilings and scope boundaries', () => {
    expect(LOGRES_CONTRADICTION_ARBITER_GUARDRAILS)
      .toContain('External evidence ceilings are preserved as constraints rather than factual rivals.')
    expect(LOGRES_CONTRADICTION_ARBITER_ARTIFACT)
      .toContain('global-contradiction-arbiter')
  })
})
