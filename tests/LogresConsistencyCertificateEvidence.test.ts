import { describe, expect, it } from 'vitest'

import {
  LOGRES_ZENITH_CONSISTENCY_ARTIFACT,
  LOGRES_ZENITH_CONSISTENCY_CERTIFICATE_ID,
  LOGRES_ZENITH_CONSISTENCY_COUNTS,
  LOGRES_ZENITH_CONSISTENCY_GUARANTEES,
  LOGRES_ZENITH_CONSISTENCY_LIMITATIONS,
  LOGRES_ZENITH_CONSISTENCY_PROVENANCE,
  LOGRES_ZENITH_CONSISTENCY_STATUS,
} from '../src/game/logres/reverse/LogresConsistencyCertificateEvidence'

describe('ZENITH reconstruction consistency certificate', () => {
  it('passes every cross-artifact invariant', () => {
    expect(LOGRES_ZENITH_CONSISTENCY_PROVENANCE)
      .toBe('ZENITH_DETERMINISTIC_CROSS_ARTIFACT_CONSISTENCY_CERTIFICATE')
    expect(LOGRES_ZENITH_CONSISTENCY_STATUS).toBe('PASS')
    expect(LOGRES_ZENITH_CONSISTENCY_COUNTS.invariants).toBe(21)
    expect(LOGRES_ZENITH_CONSISTENCY_COUNTS.passed).toBe(21)
    expect(LOGRES_ZENITH_CONSISTENCY_COUNTS.failed).toBe(0)
    expect(LOGRES_ZENITH_CONSISTENCY_COUNTS.missingSourcePaths).toBe(0)
  })

  it('certifies the critical protocol and runtime graph dimensions', () => {
    expect(LOGRES_ZENITH_CONSISTENCY_COUNTS.protocolMessages).toBe(631)
    expect(LOGRES_ZENITH_CONSISTENCY_COUNTS.criticalProtocolBindings).toBe(30)
    expect(LOGRES_ZENITH_CONSISTENCY_COUNTS.stateMachineStates).toBe(23)
    expect(LOGRES_ZENITH_CONSISTENCY_COUNTS.stateMachineTransitions).toBe(28)
    expect(LOGRES_ZENITH_CONSISTENCY_COUNTS.fuzzerCases).toBe(109)
  })

  it('certifies map/resource graph cardinalities', () => {
    expect(LOGRES_ZENITH_CONSISTENCY_COUNTS.jpManifestRecords).toBe(31241)
    expect(LOGRES_ZENITH_CONSISTENCY_COUNTS.jpMapRelatedPackages).toBe(2116)
    expect(LOGRES_ZENITH_CONSISTENCY_COUNTS.semanticResourceNodes).toBe(44455)
    expect(LOGRES_ZENITH_CONSISTENCY_COUNTS.semanticResourceEdges).toBe(95477)
  })

  it('keeps consistency separate from unavailable server truth', () => {
    expect(LOGRES_ZENITH_CONSISTENCY_LIMITATIONS[0])
      .toContain('not completeness of retired-server')
    expect(LOGRES_ZENITH_CONSISTENCY_LIMITATIONS)
      .toContain('Same-authority evidence disagreements remain unresolved.')
    expect(LOGRES_ZENITH_CONSISTENCY_GUARANTEES)
      .toContain('The contradiction arbiter has no speculation/unresolved winners and preserves same-authority ties.')
  })

  it('has a deterministic certificate identity and artifact path', () => {
    expect(LOGRES_ZENITH_CONSISTENCY_CERTIFICATE_ID).toHaveLength(64)
    expect(LOGRES_ZENITH_CONSISTENCY_ARTIFACT)
      .toContain('logres-reconstruction-consistency-certificate')
  })
})
