import { describe, expect, it } from 'vitest'

import {
  LOGRES_GALAXY_EVIDENCE_CANONICAL_SHA,
  LOGRES_GALAXY_EVIDENCE_MERKLE_ROOT,
  LOGRES_GALAXY_EVIDENCE_SEAL_ALGORITHM,
  LOGRES_GALAXY_EVIDENCE_SEAL_ARTIFACT,
  LOGRES_GALAXY_EVIDENCE_SEAL_COUNTS,
  LOGRES_GALAXY_EVIDENCE_SEAL_POLICY,
  LOGRES_GALAXY_EVIDENCE_SEAL_PROVENANCE,
} from '../src/game/logres/reverse/LogresGalaxyEvidenceSeal'

describe('GALAXY evidence Merkle seal', () => {
  it('seals the authoritative evidence universe deterministically', () => {
    expect(LOGRES_GALAXY_EVIDENCE_SEAL_PROVENANCE)
      .toBe('GALAXY_CRYPTOGRAPHIC_EVIDENCE_SEAL')
    expect(LOGRES_GALAXY_EVIDENCE_MERKLE_ROOT).toHaveLength(64)
    expect(LOGRES_GALAXY_EVIDENCE_CANONICAL_SHA).toHaveLength(40)
    expect(LOGRES_GALAXY_EVIDENCE_SEAL_COUNTS.totalLeaves).toBe(30)
    expect(LOGRES_GALAXY_EVIDENCE_SEAL_COUNTS.authoritativeArtifacts).toBe(12)
    expect(LOGRES_GALAXY_EVIDENCE_SEAL_COUNTS.declaredSources).toBe(17)
  })

  it('contains no missing, stale or conflicting source declarations', () => {
    expect(LOGRES_GALAXY_EVIDENCE_SEAL_COUNTS.declarationConflicts).toBe(0)
    expect(LOGRES_GALAXY_EVIDENCE_SEAL_COUNTS.missingPaths).toBe(0)
    expect(LOGRES_GALAXY_EVIDENCE_SEAL_COUNTS.stalePaths).toBe(0)
  })

  it('uses a canonical binary Merkle construction', () => {
    expect(LOGRES_GALAXY_EVIDENCE_SEAL_ALGORITHM.hash).toBe('SHA-256')
    expect(LOGRES_GALAXY_EVIDENCE_SEAL_ALGORITHM.ordering)
      .toBe('kind,path,sha256 ascending')
    expect(LOGRES_GALAXY_EVIDENCE_SEAL_ALGORITHM.oddLevelRule)
      .toBe('duplicate final hash')
  })

  it('does not copy or elevate private evidence', () => {
    expect(LOGRES_GALAXY_EVIDENCE_SEAL_POLICY[0])
      .toContain('not copied into the repository')
    expect(LOGRES_GALAXY_EVIDENCE_SEAL_POLICY[3])
      .toContain('does not strengthen the historical authority')
  })

  it('points to the generated seal artifact', () => {
    expect(LOGRES_GALAXY_EVIDENCE_SEAL_ARTIFACT)
      .toContain('logres-galaxy-evidence-merkle')
  })
})
