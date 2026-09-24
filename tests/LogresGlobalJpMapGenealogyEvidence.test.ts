import { describe, expect, it } from 'vitest'

import {
  LOGRES_GLOBAL_JP_MAP_CLUSTER_COUNTS,
  LOGRES_GLOBAL_JP_MAP_GENEALOGY_PROVENANCE,
  LOGRES_GLOBAL_JP_MAP_INVENTORY,
  LOGRES_GLOBAL_JP_MAP_STATIC_GRID_SEMANTICS,
  LOGRES_GLOBAL_JP_MILLENNIUM_TREE_MAP,
  LOGRES_GLOBAL_JP_MILLENNIUM_TREE_TEXTURE_AMBIGUITY,
} from '../src/game/logres/reverse/LogresGlobalJpMapGenealogyEvidence'

describe('Global to JP map genealogy evidence', () => {
  it('accounts for the entire current-JP public map manifest', () => {
    expect(LOGRES_GLOBAL_JP_MAP_GENEALOGY_PROVENANCE)
      .toBe('GLOBAL_AUTHORITY_WITH_CURRENT_JP_BYTE_AND_STRUCTURE_LINEAGE')
    expect(LOGRES_GLOBAL_JP_MAP_INVENTORY.jpMapRelatedPackages)
      .toBe(2116)
    expect(
      Object.values(LOGRES_GLOBAL_JP_MAP_INVENTORY.categories)
        .reduce((sum, value) => sum + value, 0),
    ).toBe(2116)
    expect(LOGRES_GLOBAL_JP_MAP_INVENTORY.terrainVariants)
      .toEqual({ base: 738, ans: 525 })
  })

  it('records exact Global to JP identity for 002_000_00001', () => {
    expect(LOGRES_GLOBAL_JP_MILLENNIUM_TREE_MAP.lineageGrade)
      .toBe('GLOBAL_JP_IDENTICAL')
    expect(LOGRES_GLOBAL_JP_MILLENNIUM_TREE_MAP.currentJpBaseByteIdentical)
      .toBe(true)
    expect(LOGRES_GLOBAL_JP_MILLENNIUM_TREE_MAP.currentJpAnsGeometryIdentical)
      .toBe(true)
    expect(LOGRES_GLOBAL_JP_MILLENNIUM_TREE_MAP.counts.grids)
      .toBe(1380)
  })

  it('rejects texture-only conflation with 002_000_00008', () => {
    expect(LOGRES_GLOBAL_JP_MILLENNIUM_TREE_TEXTURE_AMBIGUITY.sameChipAtlasBytes)
      .toBe(true)
    expect(LOGRES_GLOBAL_JP_MILLENNIUM_TREE_TEXTURE_AMBIGUITY.sameObjectAtlasBytes)
      .toBe(true)
    expect(LOGRES_GLOBAL_JP_MILLENNIUM_TREE_TEXTURE_AMBIGUITY.sameMapPayload)
      .toBe(false)
    expect(LOGRES_GLOBAL_JP_MILLENNIUM_TREE_TEXTURE_AMBIGUITY.sameStructureFingerprint)
      .toBe(false)
    expect(LOGRES_GLOBAL_JP_MILLENNIUM_TREE_TEXTURE_AMBIGUITY.atlasReuseCluster)
      .toContain('100_001_00000.mbn')
  })

  it('captures corpus-level map reuse instead of only one candidate', () => {
    expect(LOGRES_GLOBAL_JP_MAP_CLUSTER_COUNTS.exactMapPayloadReuse)
      .toEqual({ groups: 525, members: 1050, largestGroup: 2 })
    expect(LOGRES_GLOBAL_JP_MAP_CLUSTER_COUNTS.structuralReuse.groups)
      .toBe(509)
    expect(LOGRES_GLOBAL_JP_MAP_CLUSTER_COUNTS.baseAtlasReuse.groups)
      .toBe(21)
  })

  it('does not invent a static RegionID field', () => {
    expect(LOGRES_GLOBAL_JP_MAP_STATIC_GRID_SEMANTICS.explicitRegionIdField)
      .toBe(false)
    expect(LOGRES_GLOBAL_JP_MAP_STATIC_GRID_SEMANTICS.confirmedFields)
      .toContain('Prohibition')
    expect(LOGRES_GLOBAL_JP_MAP_STATIC_GRID_SEMANTICS.guardrail)
      .toContain('must not be silently renamed to RegionID')
  })
})
