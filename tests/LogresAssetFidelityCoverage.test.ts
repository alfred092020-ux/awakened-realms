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
import {
  LOGRES_ASSETS,
} from '../src/game/logres/ui/LogresRuntimeAssets'

describe('Logres asset fidelity coverage', () => {
  it('validates the release-critical source-to-runtime lineage ledger', () => {
    expect(() =>
      validateLogresAssetFidelityCoverage(),
    ).not.toThrow()
  })

  it('preserves complete tutorial HUD lineage', () => {
    const tutorial =
      LOGRES_ASSET_FIDELITY_COVERAGE.records
        .filter((record) => record.key.startsWith('tutorial-'))

    expect(tutorial).toHaveLength(3)
    for (const record of tutorial) {
      expect(record.status).toBe('PASS')
      expect(record.sourceEntry).toMatch(/\.dds$/)
      expect(record.sourceSha256).toMatch(/^[0-9a-f]{64}$/i)
      expect(record.transform).toBe('DDS_TO_PNG_HYDRATION')
      expect(record.runtimeUrl).toMatch(/\.png$/)
      expect(record.sourceProvenance).toBe('CONFIRMED ORIGINAL')
    }
  })

  it('binds release-critical Global title assets to exact indexed source identity and transform', () => {
    const expected = {
      'title-background': {
        sourceEntry: 'gui/title/title_back.dds',
        sourceSha256: 'd5cd1b816d3116a197ae5d1b4faa7648c37b93bf1cb5b604adf76aa7ddf47060',
        transform: 'DDS_TO_PNG_HYDRATION',
        runtime: LOGRES_ASSETS.titleBackground,
      },
      'title-logo': {
        sourceEntry: 'gui/title/effect/png/logo00.png',
        sourceSha256: '41a5dc4cfe16dfb9725f067208f705814ad69f366d8ecc350ff8e493ddabf7fe',
        transform: 'PNG_COPY',
        runtime: LOGRES_ASSETS.titleLogo,
      },
      'title-base': {
        sourceEntry: 'gui/title/title_base01.dds',
        sourceSha256: '7cf76d845ed76a64f7091e62b20efd538aa7968659a96238dfc9c65a4162df3a',
        transform: 'DDS_TO_PNG_HYDRATION',
        runtime: LOGRES_ASSETS.titleBase,
      },
      'title-start': {
        sourceEntry: 'gui/title/title_ok.png',
        sourceSha256: 'b8048b804cca019c14a16936ef9d587c20a36cda86812cf279ec6862777a773a',
        transform: 'PNG_COPY',
        runtime: LOGRES_ASSETS.titleStart,
      },
      'world-select-01': {
        sourceEntry: 'gui/title/world_select01.png',
        sourceSha256: '0cb475b93b3dd510801c208c5950961b2419bba5316871d65a19c0ca975612be',
        transform: 'PNG_COPY',
        runtime: LOGRES_ASSETS.worldSelect,
      },
    } as const

    const release =
      LOGRES_ASSET_FIDELITY_COVERAGE.records
        .filter((record) => record.key in expected)

    expect(release).toHaveLength(5)
    for (const record of release) {
      const target = expected[record.key as keyof typeof expected]
      expect(record.status).toBe('PASS')
      expect(record.sourceEntry).toBe(target.sourceEntry)
      expect(record.sourceSha256).toBe(target.sourceSha256)
      expect(record.transform).toBe(target.transform)
      expect(record.runtimeKey).toBe(target.runtime.key)
      expect(record.runtimeUrl).toBe(target.runtime.url)
      expect(record.sourceProvenance)
        .toBe('CONFIRMED ORIGINAL GLOBAL RUNTIME ASSET INDEX')
    }
  })

  it('has no evidence ceiling for the release-critical title coverage set', () => {
    const releaseKeys = new Set([
      'title-background',
      'title-logo',
      'title-base',
      'title-start',
      'world-select-01',
    ])
    const ceilings =
      LOGRES_ASSET_FIDELITY_COVERAGE.records
        .filter((record) =>
          releaseKeys.has(record.key) &&
          record.status === 'EVIDENCE_CEILING',
        )

    expect(ceilings).toEqual([])
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
