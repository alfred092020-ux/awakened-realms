import { describe, expect, it } from 'vitest'

import {
  LOGRES_GLOBAL_3024_EVIDENCE_FUZZER_ARTIFACT,
  LOGRES_GLOBAL_3024_EVIDENCE_FUZZER_COUNTS,
  LOGRES_GLOBAL_3024_EVIDENCE_FUZZER_POLICIES,
  LOGRES_GLOBAL_3024_EVIDENCE_FUZZER_PROVENANCE,
  LOGRES_GLOBAL_3024_KNOWN_RETRY,
  LOGRES_GLOBAL_3024_RESOURCE_MUTATION_GUARD,
  LOGRES_GLOBAL_3024_TRANSITION_MUTATION_GUARDS,
  LOGRES_GLOBAL_3024_UNKNOWN_ENUM_BOUNDARIES,
  LOGRES_GLOBAL_3024_WIRE_MUTATIONS,
} from '../src/game/logres/reverse/LogresEvidenceFuzzerEvidence'

describe('Global 3.0.24 evidence fuzzer', () => {
  it('mutates every critical protocol message deterministically', () => {
    expect(LOGRES_GLOBAL_3024_EVIDENCE_FUZZER_PROVENANCE)
      .toBe('OFFLINE_MUTATION_SUITE_DERIVED_FROM_CONFIRMED_GLOBAL_3_0_24_EVIDENCE')
    expect(LOGRES_GLOBAL_3024_EVIDENCE_FUZZER_COUNTS.criticalSchemaMessages)
      .toBe(30)
    expect(LOGRES_GLOBAL_3024_EVIDENCE_FUZZER_COUNTS.criticalSchemaMessagesMutated)
      .toBe(30)
    expect(LOGRES_GLOBAL_3024_EVIDENCE_FUZZER_COUNTS.totalCases)
      .toBe(109)
  })

  it('rejects malformed recovered transport frames offline', () => {
    expect(LOGRES_GLOBAL_3024_WIRE_MUTATIONS).toHaveLength(7)
    expect(LOGRES_GLOBAL_3024_EVIDENCE_FUZZER_COUNTS.offlineWireRejects)
      .toBe(7)
    expect(LOGRES_GLOBAL_3024_WIRE_MUTATIONS)
      .toContain('wrong_gmcl_contract_id')
  })

  it('preserves unknown enum boundaries as server ceilings', () => {
    expect(LOGRES_GLOBAL_3024_UNKNOWN_ENUM_BOUNDARIES.accountLogin)
      .toEqual([0, 8])
    expect(LOGRES_GLOBAL_3024_UNKNOWN_ENUM_BOUNDARIES.battleEntry)
      .toEqual([0, 3])
    expect(LOGRES_GLOBAL_3024_EVIDENCE_FUZZER_POLICIES.SERVER_BEHAVIOR_UNKNOWN)
      .toContain('evidence ceiling')
  })

  it('keeps exact battle-entry retry timing immutable', () => {
    expect(LOGRES_GLOBAL_3024_KNOWN_RETRY.retryCode).toBe(2)
    expect(LOGRES_GLOBAL_3024_KNOWN_RETRY.retrySeconds).toBe(1)
    expect(LOGRES_GLOBAL_3024_EVIDENCE_FUZZER_COUNTS.evidenceMismatchRejects)
      .toBe(4)
  })

  it('guards illegal transition order and texture-only map substitution', () => {
    expect(LOGRES_GLOBAL_3024_TRANSITION_MUTATION_GUARDS).toHaveLength(8)
    expect(LOGRES_GLOBAL_3024_RESOURCE_MUTATION_GUARD.confirmedCandidate)
      .toBe('002_000_00001')
    expect(LOGRES_GLOBAL_3024_RESOURCE_MUTATION_GUARD.rejectedTextureOnlySubstitute)
      .toBe('002_000_00008')
    expect(LOGRES_GLOBAL_3024_EVIDENCE_FUZZER_ARTIFACT)
      .toContain('global3024-evidence-fuzzer')
  })
})
