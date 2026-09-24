import { describe, expect, it } from 'vitest'

import {
  LOGRES_MINIMAL_SYNTHESIS_ACCEPTANCE,
  LOGRES_MINIMAL_SYNTHESIS_ARTIFACT,
  LOGRES_MINIMAL_SYNTHESIS_AUTHORITY_POLICY,
  LOGRES_MINIMAL_SYNTHESIS_EVIDENCE,
  LOGRES_MINIMAL_SYNTHESIS_PREDICATES,
  LOGRES_MINIMAL_SYNTHESIS_PROVENANCE,
  LOGRES_MINIMAL_SYNTHESIS_RESULT,
  LOGRES_MINIMAL_SYNTHESIS_ROLLBACK,
  LOGRES_MINIMAL_SYNTHESIS_SCOPE,
} from '../src/game/logres/reverse/LogresMinimalSynthesisEvidence'

describe('evidence-sufficient minimal reconstruction synthesis', () => {
  it('is pinned to the exact certified/current differential evidence', () => {
    expect(LOGRES_MINIMAL_SYNTHESIS_PROVENANCE).toBe(
      'ZENITH_EVIDENCE_SUFFICIENT_MINIMAL_RECONSTRUCTION_SYNTHESIS',
    )
    expect(LOGRES_MINIMAL_SYNTHESIS_ARTIFACT.sha256).toHaveLength(64)
    expect(
      LOGRES_MINIMAL_SYNTHESIS_EVIDENCE.certifiedDifferential.sha256,
    ).toHaveLength(64)
    expect(
      LOGRES_MINIMAL_SYNTHESIS_EVIDENCE.currentDifferential.sha256,
    ).toHaveLength(64)
  })

  it('proves the old battle-entry implementation bug existed', () => {
    expect(
      LOGRES_MINIMAL_SYNTHESIS_EVIDENCE.certifiedDifferential
        .implementationBugIds,
    ).toContain('battle-entry-retry-gate-enforcement')
    expect(
      LOGRES_MINIMAL_SYNTHESIS_EVIDENCE.certifiedDifferential
        .implementationBugIds,
    ).toContain('playable-field-battle-entry-wiring')
    expect(LOGRES_MINIMAL_SYNTHESIS_RESULT.packetId).toBe(
      'DIFF-FIX-BATTLE-ENTRY-BOUNDARY',
    )
  })

  it('proves current canonical no longer exposes an implementation fix packet', () => {
    const current = LOGRES_MINIMAL_SYNTHESIS_EVIDENCE.currentDifferential

    expect(current.implementationBugIds).toHaveLength(0)
    expect(current.implementationPacketIds).toHaveLength(0)
    expect(current.classifications.PASS).toBe(7)
    expect(current.classifications.INTENTIONAL_SERVER_STUB).toBe(1)
    expect(current.classifications.UNKNOWN).toBe(1)
  })

  it('therefore synthesizes the mathematically smallest zero-file delta', () => {
    expect(LOGRES_MINIMAL_SYNTHESIS_RESULT.status).toBe(
      'ZERO_DELTA_ALREADY_SATISFIED',
    )
    expect(LOGRES_MINIMAL_SYNTHESIS_RESULT.deltaFileCount).toBe(0)
    expect(LOGRES_MINIMAL_SYNTHESIS_RESULT.filesToModify).toHaveLength(0)
    expect(LOGRES_MINIMAL_SYNTHESIS_RESULT.patchApplied).toBe(false)
    expect(LOGRES_MINIMAL_SYNTHESIS_RESULT.mergePerformed).toBe(false)
    expect(LOGRES_MINIMAL_SYNTHESIS_RESULT.deploymentPerformed).toBe(false)
  })

  it('pins the truth and consistency certificates before accepting zero delta', () => {
    expect(LOGRES_MINIMAL_SYNTHESIS_EVIDENCE.truthKernel.status).toBe(
      'RESOLVED',
    )
    expect(LOGRES_MINIMAL_SYNTHESIS_EVIDENCE.truthKernel.claims)
      .toBeGreaterThan(27000)
    expect(
      LOGRES_MINIMAL_SYNTHESIS_EVIDENCE.consistencyCertificate.status,
    ).toBe('PASS')
    expect(
      LOGRES_MINIMAL_SYNTHESIS_EVIDENCE.consistencyCertificate.failed,
    ).toBe(0)
    expect(
      LOGRES_MINIMAL_SYNTHESIS_EVIDENCE.consistencyCertificate.passed,
    ).toBe(21)
    expect(
      LOGRES_MINIMAL_SYNTHESIS_EVIDENCE.traceCertificate.offlineOnly,
    ).toBe(true)
  })

  it('retains the exact bounded packet scope and verification set', () => {
    expect(LOGRES_MINIMAL_SYNTHESIS_SCOPE.certifiedPacketScope).toEqual([
      'src/game/logres/field/controllers/LogresFieldEncounterController.ts',
      'src/game/logres/encounter/ReconstructedLogresEncounterAuthority.ts',
    ])
    expect(LOGRES_MINIMAL_SYNTHESIS_SCOPE.currentSourceHashes
      .fieldEncounterController).toHaveLength(64)
    expect(LOGRES_MINIMAL_SYNTHESIS_SCOPE.currentSourceHashes
      .encounterAuthority).toHaveLength(64)
    expect(LOGRES_MINIMAL_SYNTHESIS_SCOPE.targetedTests).toHaveLength(3)
    for (const test of LOGRES_MINIMAL_SYNTHESIS_SCOPE.targetedTests) {
      expect(test.sha256).toHaveLength(64)
    }
  })

  it('requires every current implementation predicate before declaring zero delta', () => {
    expect(LOGRES_MINIMAL_SYNTHESIS_PREDICATES.certifiedGapExists).toBe(true)
    expect(LOGRES_MINIMAL_SYNTHESIS_PREDICATES.activeGapExists).toBe(false)
    expect(LOGRES_MINIMAL_SYNTHESIS_PREDICATES.truthKernelResolved).toBe(true)
    expect(
      LOGRES_MINIMAL_SYNTHESIS_PREDICATES.consistencyCertificatePass,
    ).toBe(true)
    expect(
      LOGRES_MINIMAL_SYNTHESIS_PREDICATES.currentSourcePredicatesPass,
    ).toBe(true)
    expect(
      LOGRES_MINIMAL_SYNTHESIS_PREDICATES.currentImplementationPacketPresent,
    ).toBe(false)
    expect(
      LOGRES_MINIMAL_SYNTHESIS_PREDICATES.currentImplementationBugCount,
    ).toBe(0)
    expect(LOGRES_MINIMAL_SYNTHESIS_PREDICATES.sourcePredicates).toHaveLength(8)
  })

  it('preserves all four acceptance rules without inventing retired-server output', () => {
    expect(LOGRES_MINIMAL_SYNTHESIS_ACCEPTANCE).toHaveLength(4)
    expect(LOGRES_MINIMAL_SYNTHESIS_ACCEPTANCE[1]).toContain(
      'entryAccepted',
    )
    expect(LOGRES_MINIMAL_SYNTHESIS_ACCEPTANCE[2]).toContain(
      'exactly 1.0 second',
    )
    expect(LOGRES_MINIMAL_SYNTHESIS_ACCEPTANCE[3]).toContain(
      'reconstructed/server stub',
    )
    expect(
      LOGRES_MINIMAL_SYNTHESIS_AUTHORITY_POLICY
        .retiredServerSemanticsMayBeInvented,
    ).toBe(false)
    expect(
      LOGRES_MINIMAL_SYNTHESIS_AUTHORITY_POLICY
        .unknownServerSemanticsRemainUnknown,
    ).toBe(true)
  })

  it('defines an explicit rollback predicate for future drift', () => {
    expect(LOGRES_MINIMAL_SYNTHESIS_ROLLBACK.invalidateIfAny).toContain(
      'current differential contains implementation packet DIFF-FIX-BATTLE-ENTRY-BOUNDARY',
    )
    expect(LOGRES_MINIMAL_SYNTHESIS_ROLLBACK.verificationCommand).toContain(
      'ReconstructedLogresEncounterAuthority.test.ts',
    )
    expect(
      LOGRES_MINIMAL_SYNTHESIS_ROLLBACK.differentialRegenerationCommand,
    ).toContain('run_global_differential_emulator.py')
  })
})
