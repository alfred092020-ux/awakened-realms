import { describe, expect, it } from 'vitest'

import {
  LOGRES_OMEGA_CLAIMS_RETIRED_SERVER_INTERNALS,
  LOGRES_OMEGA_CONTRADICTION_STATUS,
  LOGRES_OMEGA_CREATES_NEW_HISTORICAL_FACTS,
  LOGRES_OMEGA_DATABASE,
  LOGRES_OMEGA_GRADE_COUNTS,
  LOGRES_OMEGA_ID,
  LOGRES_OMEGA_INTEGRITY,
  LOGRES_OMEGA_MANIFEST,
  LOGRES_OMEGA_POLICIES,
  LOGRES_OMEGA_PROVENANCE,
  LOGRES_OMEGA_PROVENANCE_GRADES,
  LOGRES_OMEGA_SOURCE_IDENTITIES,
  LOGRES_OMEGA_TABLE_COUNTS,
} from '../src/game/logres/reverse/LogresGlobalReconstructionOmegaEvidence'

describe('OMEGA deterministic reconstruction knowledge base', () => {
  it('is hash-bound to deterministic database and manifest artifacts', () => {
    expect(LOGRES_OMEGA_PROVENANCE)
      .toBe('OMEGA_DETERMINISTIC_GLOBAL_RECONSTRUCTION_KNOWLEDGE_BASE')
    expect(LOGRES_OMEGA_ID).toHaveLength(64)
    expect(LOGRES_OMEGA_DATABASE.sha256)
      .toBe('90f52bd8906aea0043188838b2f742957b00105822115fa0629f3aa8785a85a6')
    expect(LOGRES_OMEGA_MANIFEST.sha256)
      .toBe('ff5d6cc0114e561dab4402536cae82f95e1d50d310f2a3e37efdc1302752838e')
    expect(LOGRES_OMEGA_DATABASE.bytes).toBe(168542208)
  })

  it('uses the canonical provenance ladder without unsupported promotion', () => {
    expect(LOGRES_OMEGA_PROVENANCE_GRADES).toEqual([
      'GLOBAL_DIRECT',
      'GLOBAL_BINARY_DERIVED',
      'GLOBAL_JP_IDENTICAL',
      'SAME_ERA_JP_CORROBORATED',
      'JP_LINEAGE_SUPPORTED',
      'IMPLEMENTATION_VERIFIED',
      'EXTERNAL_CEILING',
    ])
    expect(LOGRES_OMEGA_GRADE_COUNTS.SAME_ERA_JP_CORROBORATED).toBe(0)
    expect(LOGRES_OMEGA_GRADE_COUNTS.GLOBAL_JP_IDENTICAL).toBe(15)
    expect(LOGRES_OMEGA_GRADE_COUNTS.JP_LINEAGE_SUPPORTED).toBe(2131)
  })

  it('assembles all required evidence domains into one database', () => {
    expect(LOGRES_OMEGA_TABLE_COUNTS.claims).toBe(27765)
    expect(LOGRES_OMEGA_TABLE_COUNTS.functionSemantics).toBe(16379)
    expect(LOGRES_OMEGA_TABLE_COUNTS.protocolMessages).toBe(631)
    expect(LOGRES_OMEGA_TABLE_COUNTS.resourceNodes).toBe(44455)
    expect(LOGRES_OMEGA_TABLE_COUNTS.resourceEdges).toBe(95477)
    expect(LOGRES_OMEGA_TABLE_COUNTS.maps).toBe(2118)
    expect(LOGRES_OMEGA_TABLE_COUNTS.stateTransitions).toBe(28)
    expect(LOGRES_OMEGA_TABLE_COUNTS.reconstructionPackets).toBe(12)
    expect(LOGRES_OMEGA_TABLE_COUNTS.implementationLinks).toBe(2160)
  })

  it('requires exact evidence path/hash coverage for every material claim', () => {
    expect(LOGRES_OMEGA_TABLE_COUNTS.claimEvidence).toBe(80635)
    expect(LOGRES_OMEGA_INTEGRITY.missingClaimEvidence).toBe(0)
    expect(LOGRES_OMEGA_POLICIES)
      .toContain(
        'Every material claim has at least one exact evidence path and SHA-256.',
      )
  })

  it('prevents contradictory same-authority claim heads', () => {
    expect(LOGRES_OMEGA_INTEGRITY.sameAuthorityConflictsInClaimHeads)
      .toBe(0)
    expect(LOGRES_OMEGA_CONTRADICTION_STATUS.unresolvedSameAuthorityTie)
      .toBe(1)
    expect(LOGRES_OMEGA_CONTRADICTION_STATUS.quarantinedSameAuthorityTask)
      .toBe('G17-TUT-001')
    expect(LOGRES_OMEGA_CONTRADICTION_STATUS.automaticWinnerSelected)
      .toBe(false)
    expect(LOGRES_OMEGA_POLICIES)
      .toContain(
        'Same-authority unresolved arbiter ties are quarantined outside authoritative claim heads.',
      )
  })

  it('keeps consistency and terminal evidence ceilings explicit', () => {
    expect(LOGRES_OMEGA_INTEGRITY.consistencyStatus).toBe('PASS')
    expect(LOGRES_OMEGA_INTEGRITY.failedConsistencyInvariants).toBe(0)
    expect(LOGRES_OMEGA_INTEGRITY.consistencyPassed)
      .toBe(LOGRES_OMEGA_INTEGRITY.consistencyTotal)
    expect(LOGRES_OMEGA_TABLE_COUNTS.externalCeilings).toBe(9)
    expect(LOGRES_OMEGA_GRADE_COUNTS.EXTERNAL_CEILING).toBe(9)
    expect(LOGRES_OMEGA_CREATES_NEW_HISTORICAL_FACTS).toBe(false)
    expect(LOGRES_OMEGA_CLAIMS_RETIRED_SERVER_INTERNALS).toBe(false)
  })

  it('binds implementation claims to the exact compiler/closure identities', () => {
    expect(LOGRES_OMEGA_SOURCE_IDENTITIES.closureId)
      .toBe('e81e108db86433948da94a1f80e66b43e7f0d696f9ef8051b7d0a2cd66c4b8a9')
    expect(LOGRES_OMEGA_SOURCE_IDENTITIES.closureFactsSha256)
      .toBe('bec04a87dfedd20202653f3d01e0a4ae1e68fa906c287d9e3dd63d95dc93c9bf')
    expect(LOGRES_OMEGA_SOURCE_IDENTITIES.compilerRunId)
      .toBe('c9385e14fb819d308880480e19b71546c7f9e5644b0eed8d2fddd7ad9d1a6b39')
    expect(LOGRES_OMEGA_GRADE_COUNTS.IMPLEMENTATION_VERIFIED).toBe(1166)
  })
})
