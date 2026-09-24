import { describe, expect, it } from 'vitest'

import {
  LOGRES_GLOBAL_JP_RESOURCE_GRAPH_CRITICAL_EDGES,
  LOGRES_GLOBAL_JP_RESOURCE_GRAPH_POLICY,
  LOGRES_GLOBAL_JP_RESOURCE_SEMANTIC_GRAPH_ARTIFACT,
  LOGRES_GLOBAL_JP_RESOURCE_SEMANTIC_GRAPH_COUNTS,
  LOGRES_GLOBAL_JP_RESOURCE_SEMANTIC_GRAPH_PROVENANCE,
  LOGRES_GLOBAL_JP_RESOURCE_SYSTEM_COUNTS,
} from '../src/game/logres/reverse/LogresGlobalJpResourceSemanticGraphEvidence'

describe('OMEGA Global/JP resource semantic graph', () => {
  it('builds a large queryable graph from bounded evidence', () => {
    expect(LOGRES_GLOBAL_JP_RESOURCE_SEMANTIC_GRAPH_PROVENANCE)
      .toBe('OMEGA_SEMANTIC_RESOURCE_GRAPH_WITH_EXPLICIT_EDGE_AUTHORITY')
    expect(LOGRES_GLOBAL_JP_RESOURCE_SEMANTIC_GRAPH_COUNTS.nodes).toBe(44455)
    expect(LOGRES_GLOBAL_JP_RESOURCE_SEMANTIC_GRAPH_COUNTS.edges).toBe(95477)
    expect(LOGRES_GLOBAL_JP_RESOURCE_SEMANTIC_GRAPH_COUNTS.resources).toBe(31282)
    expect(LOGRES_GLOBAL_JP_RESOURCE_SEMANTIC_GRAPH_COUNTS.maps).toBe(1263)
  })

  it('indexes system-to-resource surfaces for critical reconstruction areas', () => {
    expect(LOGRES_GLOBAL_JP_RESOURCE_SYSTEM_COUNTS.battle).toBeGreaterThan(2000)
    expect(LOGRES_GLOBAL_JP_RESOURCE_SYSTEM_COUNTS.field).toBeGreaterThan(2700)
    expect(LOGRES_GLOBAL_JP_RESOURCE_SYSTEM_COUNTS.onboarding).toBeGreaterThan(300)
    expect(LOGRES_GLOBAL_JP_RESOURCE_SYSTEM_COUNTS.quest).toBeGreaterThan(700)
  })

  it('preserves exact Millennium Tree byte lineage as a graph edge', () => {
    expect(LOGRES_GLOBAL_JP_RESOURCE_GRAPH_CRITICAL_EDGES.millenniumTree.relation)
      .toBe('EXACT_BYTES_LINEAGE')
    expect(LOGRES_GLOBAL_JP_RESOURCE_GRAPH_CRITICAL_EDGES.millenniumTree.target)
      .toBe('resource:jp-current:map/002_000_00001.mbn')
    expect(LOGRES_GLOBAL_JP_RESOURCE_GRAPH_CRITICAL_EDGES.millenniumTree.provenance)
      .toBe('GLOBAL_JP_IDENTICAL_MANIFEST_HASH_AND_SIZE')
  })

  it('captures renamed exact resource continuity', () => {
    expect(LOGRES_GLOBAL_JP_RESOURCE_GRAPH_CRITICAL_EDGES.bgmRenumbering.source)
      .toContain('000_000_00001.ogg')
    expect(LOGRES_GLOBAL_JP_RESOURCE_GRAPH_CRITICAL_EDGES.bgmRenumbering.target)
      .toContain('000_000_00002.ogg')
    expect(LOGRES_GLOBAL_JP_RESOURCE_GRAPH_CRITICAL_EDGES.bgmRenumbering.relation)
      .toBe('EXACT_BYTES_LINEAGE')
  })

  it('keeps taxonomy and JP-only facts below historical authority', () => {
    expect(LOGRES_GLOBAL_JP_RESOURCE_GRAPH_POLICY.systemTaxonomy)
      .toContain('do not upgrade historical behavior confidence')
    expect(LOGRES_GLOBAL_JP_RESOURCE_GRAPH_POLICY.jpOnly)
      .toContain('independent Global predicate')
    expect(LOGRES_GLOBAL_JP_RESOURCE_SEMANTIC_GRAPH_ARTIFACT.sha256)
      .toHaveLength(64)
  })
})
