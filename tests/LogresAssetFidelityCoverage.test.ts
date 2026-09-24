import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_ASSET_FIDELITY_COVERAGE,
  validateLogresAssetFidelityCoverage,
  type LogresAssetLineageRecord,
} from '../src/game/logres/assets/LogresAssetFidelityCoverage'

describe('Logres asset fidelity coverage', () => {
  it('validates the release-critical source-to-runtime lineage ledger', () => {
    expect(() =>
      validateLogresAssetFidelityCoverage(),
    ).not.toThrow()
  })

  it('has complete hash -> transform -> runtime lineage for PASS tutorial HUD assets', () => {
    const pass =
      LOGRES_ASSET_FIDELITY_COVERAGE.records
        .filter((record) => record.status === 'PASS')

    expect(pass).toHaveLength(3)
    for (const record of pass) {
      expect(record.sourceEntry).toMatch(/\.dds$/)
      expect(record.sourceSha256).toMatch(/^[0-9a-f]{64}$/i)
      expect(record.transform).toBe('DDS_TO_PNG_HYDRATION')
      expect(record.runtimeUrl).toMatch(/\.png$/)
      if (record.runtimeKey !== null) {
        expect(record.runtimeKey).toBeTruthy()
      }
      expect(record.sourceProvenance).toBe('CONFIRMED ORIGINAL')
    }
  })

  it('keeps title assets without per-entry source hashes behind an explicit ceiling', () => {
    const ceilings =
      LOGRES_ASSET_FIDELITY_COVERAGE.records
        .filter((record) => record.status === 'EVIDENCE_CEILING')

    expect(ceilings.map((record) => record.key))
      .toEqual([
        'title-background',
        'title-logo',
      ])
    for (const record of ceilings) {
      expect(record.sourceSha256).toBeNull()
      expect(record.runtimeKey).toBeTruthy()
      expect(record.runtimeUrl).toBeTruthy()
    }
  })

  it('fails a PASS record with missing source hash', () => {
    const broken: LogresAssetLineageRecord = {
      key: 'broken',
      sourceEntry: 'broken.dds',
      sourceSha256: null,
      sourceProvenance: 'CONFIRMED ORIGINAL',
      transform: 'DDS_TO_PNG_HYDRATION',
      runtimeKey: 'broken',
      runtimeUrl: '/broken.png',
      status: 'PASS',
      note: 'invalid test record',
    }

    expect(() =>
      validateLogresAssetFidelityCoverage([broken]),
    ).toThrow('PASS asset lineage is incomplete')
  })

  it('fails historical PASS when provenance is current-JP-only', () => {
    const broken: LogresAssetLineageRecord = {
      key: 'jp-only',
      sourceEntry: 'jp.dds',
      sourceSha256:
        'a'.repeat(64),
      sourceProvenance:
        'CURRENT_JP_REFERENCE_ONLY',
      transform: 'DDS_TO_PNG_HYDRATION',
      runtimeKey: 'jp',
      runtimeUrl: '/jp.png',
      status: 'PASS',
      note: 'invalid test record',
    }

    expect(() =>
      validateLogresAssetFidelityCoverage([broken]),
    ).toThrow('current-JP-only provenance')
  })

  it('documents the fail-closed lineage policy', () => {
    expect(
      LOGRES_ASSET_FIDELITY_COVERAGE.policy.passRequirement,
    ).toContain('source hash')
    expect(
      LOGRES_ASSET_FIDELITY_COVERAGE.policy.evidenceCeilingRule,
    ).toContain('cannot be promoted to PASS')
    expect(
      LOGRES_ASSET_FIDELITY_COVERAGE.policy.provenanceRule,
    ).toContain('remain distinct')
  })
})
