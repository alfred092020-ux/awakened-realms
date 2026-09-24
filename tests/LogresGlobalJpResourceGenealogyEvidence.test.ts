import { describe, expect, it } from 'vitest'

import {
  LOGRES_GLOBAL_JP_EXACT_BOOTSTRAP_CONTINUITY,
  LOGRES_GLOBAL_JP_HIGH_VALUE_MOVED_CONTINUITY,
  LOGRES_GLOBAL_JP_RELEASE_MANIFEST,
  LOGRES_GLOBAL_JP_RESOURCE_GENEALOGY_ARTIFACT,
  LOGRES_GLOBAL_JP_RESOURCE_GENEALOGY_COUNTS,
  LOGRES_GLOBAL_JP_RESOURCE_GENEALOGY_PROVENANCE,
  LOGRES_GLOBAL_JP_RESOURCE_LINEAGE_POLICY,
} from '../src/game/logres/reverse/LogresGlobalJpResourceGenealogyEvidence'

describe('Global -> JP resource genealogy', () => {
  it('indexes the exact captured JP release manifest', () => {
    expect(LOGRES_GLOBAL_JP_RESOURCE_GENEALOGY_PROVENANCE)
      .toBe('GLOBAL_AUTHORITY_WITH_CURRENT_JP_PUBLIC_MANIFEST_LINEAGE')
    expect(LOGRES_GLOBAL_JP_RELEASE_MANIFEST.generation).toBe('1790230588')
    expect(LOGRES_GLOBAL_JP_RELEASE_MANIFEST.recordCount).toBe(31241)
    expect(LOGRES_GLOBAL_JP_RESOURCE_GENEALOGY_COUNTS.jpManifestRecords)
      .toBe(31241)
  })

  it('accounts for all recovered Global evidence records', () => {
    expect(LOGRES_GLOBAL_JP_RESOURCE_GENEALOGY_COUNTS.globalBootstrapRecords)
      .toBe(27)
    expect(LOGRES_GLOBAL_JP_RESOURCE_GENEALOGY_COUNTS.recoveredGlobalCacheRecords)
      .toBe(14)
    expect(LOGRES_GLOBAL_JP_RESOURCE_GENEALOGY_COUNTS.combinedGlobalEvidenceRecords)
      .toBe(41)
    expect(
      LOGRES_GLOBAL_JP_RESOURCE_GENEALOGY_COUNTS.exactBytesSamePath
      + LOGRES_GLOBAL_JP_RESOURCE_GENEALOGY_COUNTS.exactBytesRenamedOrMoved
      + LOGRES_GLOBAL_JP_RESOURCE_GENEALOGY_COUNTS.samePathChangedBytes
      + LOGRES_GLOBAL_JP_RESOURCE_GENEALOGY_COUNTS.globalOnlyRecovered
    ).toBe(41)
  })

  it('proves exact continuity without requiring path identity', () => {
    expect(LOGRES_GLOBAL_JP_EXACT_BOOTSTRAP_CONTINUITY).toHaveLength(9)
    expect(LOGRES_GLOBAL_JP_RESOURCE_GENEALOGY_COUNTS.exactIdentityEdges)
      .toBe(14)
    expect(LOGRES_GLOBAL_JP_HIGH_VALUE_MOVED_CONTINUITY.millenniumTreeCandidate.jpPath)
      .toBe('map/002_000_00001.mbn')
    expect(LOGRES_GLOBAL_JP_HIGH_VALUE_MOVED_CONTINUITY.tutorialUi.jpPath)
      .toBe('gui/tutorial.mbn')
    expect(LOGRES_GLOBAL_JP_HIGH_VALUE_MOVED_CONTINUITY.bgmRenumbering.jpPath)
      .toBe('sound/bgm/000_000_00002.ogg')
  })

  it('keeps changed-path and JP-only evidence below byte identity', () => {
    expect(LOGRES_GLOBAL_JP_RESOURCE_GENEALOGY_COUNTS.samePathChangedBytes)
      .toBe(15)
    expect(LOGRES_GLOBAL_JP_RESOURCE_GENEALOGY_COUNTS.jpOnlyOrUncorroborated)
      .toBe(31212)
    expect(LOGRES_GLOBAL_JP_RESOURCE_LINEAGE_POLICY.PATH_CONTINUITY_BYTES_CHANGED)
      .toContain('bytes differ')
    expect(LOGRES_GLOBAL_JP_RESOURCE_LINEAGE_POLICY.JP_ONLY_OR_UNCORROBORATED)
      .toContain('must not be inferred')
  })

  it('treats missing Global remote patch content as an evidence ceiling', () => {
    expect(LOGRES_GLOBAL_JP_RESOURCE_LINEAGE_POLICY.EXTERNAL_CEILING)
      .toContain('independent archival evidence')
    expect(LOGRES_GLOBAL_JP_RESOURCE_GENEALOGY_ARTIFACT)
      .toContain('global-jp-resource-genealogy')
  })
})
