import { describe, expect, it } from 'vitest'

import {
  LOGRES_GALAXY_WORLD_PLAN_ARTIFACT,
  LOGRES_GALAXY_WORLD_PLAN_BATCHES,
  LOGRES_GALAXY_WORLD_PLAN_COUNTS,
  LOGRES_GALAXY_WORLD_PLAN_DIRECT_MAPS,
  LOGRES_GALAXY_WORLD_PLAN_GUARDRAILS,
  LOGRES_GALAXY_WORLD_PLAN_PROVENANCE,
} from '../src/game/logres/reverse/LogresGalaxyWorldReconstructionPlan'

describe('GALAXY world reconstruction plan', () => {
  it('separates directly proven Global terrain from JP-only candidates', () => {
    expect(LOGRES_GALAXY_WORLD_PLAN_PROVENANCE)
      .toBe('GALAXY_EVIDENCE_RANKED_WORLD_RECONSTRUCTION_PLAN')
    expect(LOGRES_GALAXY_WORLD_PLAN_COUNTS.directGlobalMapIds).toBe(1)
    expect(LOGRES_GALAXY_WORLD_PLAN_DIRECT_MAPS)
      .toEqual(['002_000_00001'])
    expect(LOGRES_GALAXY_WORLD_PLAN_COUNTS.jpBaseTerrainMaps).toBe(738)
    expect(LOGRES_GALAXY_WORLD_PLAN_COUNTS.jpOnlyBaseTerrainMaps).toBe(737)
  })

  it('enumerates the recoverable lineage surface without upgrading it', () => {
    expect(LOGRES_GALAXY_WORLD_PLAN_COUNTS.jpMapFamilies).toBe(111)
    expect(LOGRES_GALAXY_WORLD_PLAN_COUNTS.exactResourceIdentityEdges).toBe(14)
    expect(LOGRES_GALAXY_WORLD_PLAN_COUNTS.samePathChangedResourceEdges).toBe(15)
    expect(LOGRES_GALAXY_WORLD_PLAN_COUNTS.nativeResourcePatterns).toBe(910)
  })

  it('orders batches by evidence strength rather than subjective priority', () => {
    expect(LOGRES_GALAXY_WORLD_PLAN_BATCHES).toHaveLength(5)
    const ranks = LOGRES_GALAXY_WORLD_PLAN_BATCHES.map(batch => batch.evidenceRank)
    expect(ranks).toEqual([4, 4, 3, 2, 1])
    expect(LOGRES_GALAXY_WORLD_PLAN_BATCHES.at(-1)?.disposition)
      .toBe('research_only')
  })

  it('does not overlap active reconstruction scopes at generation time', () => {
    expect(LOGRES_GALAXY_WORLD_PLAN_COUNTS.unsafeBatchIds).toBe(0)
  })

  it('forbids JP-only backporting and unsupported server/world claims', () => {
    expect(LOGRES_GALAXY_WORLD_PLAN_GUARDRAILS[0])
      .toContain('not historical Global facts')
    expect(LOGRES_GALAXY_WORLD_PLAN_GUARDRAILS[4])
      .toContain('remain evidence ceilings')
    expect(LOGRES_GALAXY_WORLD_PLAN_ARTIFACT)
      .toContain('logres-galaxy-world-reconstruction-plan')
  })
})
