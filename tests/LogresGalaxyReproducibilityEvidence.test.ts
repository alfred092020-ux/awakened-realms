import { describe, expect, it } from 'vitest'

import {
  LOGRES_GALAXY_REPRO_CANONICAL_SHA,
  LOGRES_GALAXY_REPRO_CAPSULE_ARTIFACT,
  LOGRES_GALAXY_REPRO_CAPSULE_ID,
  LOGRES_GALAXY_REPRO_CAPSULE_PROVENANCE,
  LOGRES_GALAXY_REPRO_COUNTS,
  LOGRES_GALAXY_REPRO_ENVIRONMENT,
  LOGRES_GALAXY_REPRO_MERKLE_ROOT,
  LOGRES_GALAXY_REPRO_PACKAGE_LOCK_SHA256,
  LOGRES_GALAXY_REPRO_POLICY,
} from '../src/game/logres/reverse/LogresGalaxyReproducibilityEvidence'

describe('GALAXY reconstruction reproducibility capsule', () => {
  it('pins the exact evidence universe and canonical source state', () => {
    expect(LOGRES_GALAXY_REPRO_CAPSULE_PROVENANCE)
      .toBe('GALAXY_RECONSTRUCTION_REPRODUCIBILITY_CAPSULE')
    expect(LOGRES_GALAXY_REPRO_CAPSULE_ID).toHaveLength(64)
    expect(LOGRES_GALAXY_REPRO_CANONICAL_SHA).toHaveLength(40)
    expect(LOGRES_GALAXY_REPRO_MERKLE_ROOT).toHaveLength(64)
    expect(LOGRES_GALAXY_REPRO_PACKAGE_LOCK_SHA256).toHaveLength(64)
  })

  it('reverifies every sealed input with zero drift', () => {
    expect(LOGRES_GALAXY_REPRO_COUNTS.sealedInputLeavesVerified).toBe(30)
    expect(LOGRES_GALAXY_REPRO_COUNTS.sealedInputDrift).toBe(0)
  })

  it('pins canonical and not-yet-integrated tools separately', () => {
    expect(LOGRES_GALAXY_REPRO_COUNTS.toolRecords).toBe(11)
    expect(LOGRES_GALAXY_REPRO_COUNTS.canonicalTools).toBe(10)
    expect(LOGRES_GALAXY_REPRO_COUNTS.workerRefTools).toBe(1)
    expect(LOGRES_GALAXY_REPRO_COUNTS.replayRecipes).toBe(11)
  })

  it('records the exact toolchain environment', () => {
    expect(LOGRES_GALAXY_REPRO_ENVIRONMENT.node).toBe('v24.21.0')
    expect(LOGRES_GALAXY_REPRO_ENVIRONMENT.python).toBe('Python 3.12.3')
    expect(LOGRES_GALAXY_REPRO_ENVIRONMENT.git).toContain('2.43.0')
  })

  it('keeps private evidence outside Git and does not elevate provenance', () => {
    expect(LOGRES_GALAXY_REPRO_POLICY[0]).toContain('remain local')
    expect(LOGRES_GALAXY_REPRO_POLICY[3])
      .toContain('does not elevate the historical confidence')
    expect(LOGRES_GALAXY_REPRO_CAPSULE_ARTIFACT)
      .toContain('logres-galaxy-repro-capsule')
  })
})
