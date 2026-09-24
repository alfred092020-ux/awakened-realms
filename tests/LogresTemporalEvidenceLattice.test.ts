import { describe, expect, it } from 'vitest'

import {
  LOGRES_HYPERDIMENSION_SNAPSHOTS,
  LOGRES_HYPERDIMENSION_TEMPORAL_ARTIFACT,
  LOGRES_HYPERDIMENSION_TEMPORAL_COUNTS,
  LOGRES_HYPERDIMENSION_TEMPORAL_LATTICE_ID,
  LOGRES_HYPERDIMENSION_TEMPORAL_POLICY,
  LOGRES_HYPERDIMENSION_TEMPORAL_PROVENANCE,
  LOGRES_HYPERDIMENSION_TEMPORAL_RELATIONS,
} from '../src/game/logres/reverse/LogresTemporalEvidenceLattice'

describe('HYPERDIMENSION temporal evidence lattice', () => {
  it('indexes protocol, resource and map entities across version endpoints', () => {
    expect(LOGRES_HYPERDIMENSION_TEMPORAL_PROVENANCE)
      .toBe('HYPERDIMENSION_VERSION_SCOPED_TEMPORAL_EVIDENCE_LATTICE')
    expect(LOGRES_HYPERDIMENSION_TEMPORAL_COUNTS.entities).toBe(673)
    expect(LOGRES_HYPERDIMENSION_TEMPORAL_COUNTS.protocolMessages).toBe(631)
    expect(LOGRES_HYPERDIMENSION_TEMPORAL_COUNTS.resources).toBe(41)
    expect(LOGRES_HYPERDIMENSION_TEMPORAL_COUNTS.mapPackages).toBe(1)
  })

  it('separates identical endpoints from changed or missing endpoints', () => {
    expect(LOGRES_HYPERDIMENSION_TEMPORAL_COUNTS.endpointIdenticalEntities)
      .toBe(377)
    expect(LOGRES_HYPERDIMENSION_TEMPORAL_COUNTS.changedOrMissingEndpointEntities)
      .toBe(285)
    expect(LOGRES_HYPERDIMENSION_TEMPORAL_COUNTS.comparisonIncompleteEntities)
      .toBe(11)
    expect(
      LOGRES_HYPERDIMENSION_TEMPORAL_COUNTS.endpointIdenticalEntities
      + LOGRES_HYPERDIMENSION_TEMPORAL_COUNTS.changedOrMissingEndpointEntities
      + LOGRES_HYPERDIMENSION_TEMPORAL_COUNTS.comparisonIncompleteEntities
    ).toBe(673)
  })

  it('never treats endpoint identity as continuous nine-year history', () => {
    expect(
      LOGRES_HYPERDIMENSION_TEMPORAL_COUNTS.unobservedIntermediateHistoryEntities
    ).toBe(673)
    expect(LOGRES_HYPERDIMENSION_TEMPORAL_POLICY[0])
      .toContain('endpoint identity only')
  })

  it('keeps the historical target and lineage reference distinct', () => {
    expect(LOGRES_HYPERDIMENSION_SNAPSHOTS.global.authority)
      .toBe('HISTORICAL_TARGET')
    expect(LOGRES_HYPERDIMENSION_SNAPSHOTS.currentJp.authority)
      .toBe('LINEAGE_REFERENCE_ONLY')
    expect(LOGRES_HYPERDIMENSION_TEMPORAL_POLICY[2])
      .toContain('never backfills a missing Global fact')
  })

  it('tracks changed schema, moved bytes, changed bytes and absence separately', () => {
    expect(LOGRES_HYPERDIMENSION_TEMPORAL_RELATIONS)
      .toContain('ENDPOINTS_OPCODE_STABLE_SCHEMA_CHANGED')
    expect(LOGRES_HYPERDIMENSION_TEMPORAL_RELATIONS)
      .toContain('ENDPOINTS_BYTES_IDENTICAL_PATH_CHANGED')
    expect(LOGRES_HYPERDIMENSION_TEMPORAL_RELATIONS)
      .toContain('ENDPOINTS_SAME_PATH_BYTES_CHANGED')
    expect(LOGRES_HYPERDIMENSION_TEMPORAL_RELATIONS)
      .toContain('GLOBAL_PRESENT_CURRENT_JP_ABSENT_OR_RENAMED')
    expect(LOGRES_HYPERDIMENSION_TEMPORAL_ARTIFACT)
      .toContain('logres-hyperdimension-temporal-lattice')
  })

  it('has a deterministic lattice identity', () => {
    expect(LOGRES_HYPERDIMENSION_TEMPORAL_LATTICE_ID).toHaveLength(64)
  })
})
