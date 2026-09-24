import { describe, expect, it } from 'vitest'

import {
  LOGRES_GLOBAL_JP_BOOTSTRAP_LINEAGE,
  LOGRES_GLOBAL_JP_EXACT_ASSET_LINEAGE,
  LOGRES_GLOBAL_JP_LINEAGE_GUARDRAILS,
  LOGRES_GLOBAL_JP_MILLENNIUM_TREE,
  LOGRES_GLOBAL_JP_PROTOCOL_LINEAGE,
  LOGRES_GLOBAL_JP_TRANSFER_TIERS,
} from '../src/game/logres/reverse/LogresGlobalJpLineageEvidence'

describe('Global to current-JP lineage evidence', () => {
  it('keeps the Global and current-JP bootstrap endpoints version-labeled', () => {
    expect(LOGRES_GLOBAL_JP_BOOTSTRAP_LINEAGE.global3024.endpoint)
      .toContain('capi-prd.logres-jrpg.com')
    expect(LOGRES_GLOBAL_JP_BOOTSTRAP_LINEAGE.currentJp.endpoint)
      .toContain('capi-sp.mmo-logres.com')
    expect(LOGRES_GLOBAL_JP_BOOTSTRAP_LINEAGE.sharedParserKeys)
      .toHaveLength(18)
    expect(LOGRES_GLOBAL_JP_BOOTSTRAP_LINEAGE.sharedServiceCategories)
      .toHaveLength(17)
  })

  it('records exact opcode continuity without treating JP-only procedures as Global', () => {
    expect(LOGRES_GLOBAL_JP_PROTOCOL_LINEAGE.sharedNames).toBe(470)
    expect(LOGRES_GLOBAL_JP_PROTOCOL_LINEAGE.sharedSameOpcode).toBe(470)
    expect(LOGRES_GLOBAL_JP_PROTOCOL_LINEAGE.sharedChangedOpcode).toBe(0)
    expect(LOGRES_GLOBAL_JP_PROTOCOL_LINEAGE.criticalCore.areaEnter)
      .toBe('0x6dff0f05')
  })

  it('records exact byte-identical asset lineage', () => {
    expect(LOGRES_GLOBAL_JP_EXACT_ASSET_LINEAGE.exactByteMatches).toBe(6)
    expect(LOGRES_GLOBAL_JP_EXACT_ASSET_LINEAGE.files)
      .toContain('002_000_00001.mbn')
    expect(LOGRES_GLOBAL_JP_EXACT_ASSET_LINEAGE.millenniumTreeMapPackageSha256)
      .toBe('ff0cd4ba4e84af9586c4921147fb463a70bd4f822ea10b456eea8eb5ea3a444c')
  })

  it('preserves Millennium Tree historical provenance', () => {
    expect(LOGRES_GLOBAL_JP_MILLENNIUM_TREE.currentJpClassification)
      .toBe('CONFIRMED_CURRENT_JP')
    expect(LOGRES_GLOBAL_JP_MILLENNIUM_TREE.historicalGlobalClassification)
      .toBe('SUPPORTED_INFERENCE')
    expect(LOGRES_GLOBAL_JP_MILLENNIUM_TREE.globalJpPackageByteIdentical)
      .toBe(true)
  })

  it('defines strict transfer tiers and database guardrails', () => {
    expect(LOGRES_GLOBAL_JP_TRANSFER_TIERS.confirmedCrossVersion)
      .toContain('SHA256')
    expect(LOGRES_GLOBAL_JP_LINEAGE_GUARDRAILS.join(' '))
      .toContain('No direct evidence has been recovered')
    expect(LOGRES_GLOBAL_JP_LINEAGE_GUARDRAILS.join(' '))
      .toContain('literally merged')
  })
})
