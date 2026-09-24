import { describe, expect, it } from 'vitest'

import {
  LOGRES_GLOBAL_JP_FUNCTION_MATCH_ARTIFACT,
  LOGRES_GLOBAL_JP_FUNCTION_MATCH_COUNTS,
  LOGRES_GLOBAL_JP_FUNCTION_MATCH_FEATURES,
  LOGRES_GLOBAL_JP_FUNCTION_MATCH_GUARDRAILS,
  LOGRES_GLOBAL_JP_FUNCTION_MATCH_HIGH_EXAMPLES,
  LOGRES_GLOBAL_JP_FUNCTION_MATCH_PROVENANCE,
  LOGRES_GLOBAL_JP_FUNCTION_MATCH_SOURCES,
} from '../src/game/logres/reverse/LogresGlobalJpFunctionMatchEvidence'

describe('Global 3.0.24 -> current-JP native function matcher', () => {
  it('uses the exact Global and current-JP libgame binaries', () => {
    expect(LOGRES_GLOBAL_JP_FUNCTION_MATCH_PROVENANCE)
      .toBe('GLOBAL_3_0_24_AUTHORITY_WITH_CURRENT_JP_STRUCTURAL_LINEAGE')
    expect(LOGRES_GLOBAL_JP_FUNCTION_MATCH_SOURCES.global3024LibgameSha256)
      .toBe('bf777cfa413b95627152246e9048af5c5fbc9c53e3c49141421360d6e86c814f')
    expect(LOGRES_GLOBAL_JP_FUNCTION_MATCH_SOURCES.currentJpLibgameSha256)
      .toBe('1564f02b23c9909adc0d26636adfc8e72a7ed9363655af0d1ae22635e55acbeb')
  })

  it('accounts for every defined Global lfs function', () => {
    const counts = LOGRES_GLOBAL_JP_FUNCTION_MATCH_COUNTS
    expect(counts.exactSymbolCorrespondences + counts.globalFunctionOnly)
      .toBe(counts.globalDefinedLfsFunctions)
    expect(
      counts.structuralHighResolved
      + counts.structuralMediumResolved
      + counts.unresolvedGlobalFunctions,
    ).toBe(counts.globalFunctionOnly)
    expect(counts.globalDefinedLfsFunctions).toBe(19867)
    expect(counts.currentJpDefinedLfsFunctions).toBe(40077)
  })

  it('keeps exact symbol and body identity separate', () => {
    const counts = LOGRES_GLOBAL_JP_FUNCTION_MATCH_COUNTS
    expect(counts.exactSymbolCorrespondences).toBe(16338)
    expect(counts.exactSymbolNormalizedBodyIdentical).toBe(1584)
    expect(counts.exactSymbolNormalizedBodyChanged).toBe(14753)
    expect(
      counts.exactSymbolNormalizedBodyIdentical
      + counts.exactSymbolNormalizedBodyChanged,
    ).toBeLessThanOrEqual(counts.exactSymbolCorrespondences)
  })

  it('uses instruction, size, string and call-neighborhood evidence', () => {
    expect(LOGRES_GLOBAL_JP_FUNCTION_MATCH_FEATURES)
      .toContain('address-independent normalized AArch64 instruction SHA-256')
    expect(LOGRES_GLOBAL_JP_FUNCTION_MATCH_COUNTS.globalWithStringRefs)
      .toBeGreaterThan(0)
    expect(LOGRES_GLOBAL_JP_FUNCTION_MATCH_COUNTS.currentJpWithStringRefs)
      .toBeGreaterThan(0)
    expect(LOGRES_GLOBAL_JP_FUNCTION_MATCH_COUNTS.globalWithDirectCalls)
      .toBeGreaterThan(0)
    expect(LOGRES_GLOBAL_JP_FUNCTION_MATCH_COUNTS.currentJpWithDirectCalls)
      .toBeGreaterThan(0)
  })

  it('keeps structural heuristics conservative', () => {
    expect(LOGRES_GLOBAL_JP_FUNCTION_MATCH_COUNTS.structuralHighResolved)
      .toBe(41)
    expect(LOGRES_GLOBAL_JP_FUNCTION_MATCH_COUNTS.structuralMediumResolved)
      .toBe(82)
    expect(LOGRES_GLOBAL_JP_FUNCTION_MATCH_COUNTS.unresolvedGlobalFunctions)
      .toBe(3406)
    expect(LOGRES_GLOBAL_JP_FUNCTION_MATCH_COUNTS.targetCollisions).toBe(0)
    expect(LOGRES_GLOBAL_JP_FUNCTION_MATCH_GUARDRAILS)
      .toContain(
        'A matching normalized instruction hash across unrelated classes is insufficient for high-confidence lineage.',
      )
  })

  it('captures concrete signature-evolution examples', () => {
    expect(LOGRES_GLOBAL_JP_FUNCTION_MATCH_HIGH_EXAMPLES)
      .toHaveLength(3)
    expect(LOGRES_GLOBAL_JP_FUNCTION_MATCH_HIGH_EXAMPLES[0].global)
      .toContain('deleteFriend(uidCUID)')
    expect(LOGRES_GLOBAL_JP_FUNCTION_MATCH_HIGH_EXAMPLES[0].currentJp)
      .toContain('UIDType<lfs::uid::tag::CUID>')
    expect(LOGRES_GLOBAL_JP_FUNCTION_MATCH_HIGH_EXAMPLES[2].global)
      .toContain('NetworkSession')
  })

  it('keeps the broader cached symbol surface distinct from FUNC inventory', () => {
    const counts = LOGRES_GLOBAL_JP_FUNCTION_MATCH_COUNTS
    expect(counts.broaderGlobalLfsSymbolSurface).toBe(20240)
    expect(counts.broaderCurrentJpLfsSymbolSurface).toBe(40709)
    expect(counts.broaderCommonLfsSymbolSurface).toBe(16667)
    expect(counts.broaderGlobalLfsSymbolSurface)
      .toBeGreaterThan(counts.globalDefinedLfsFunctions)
    expect(LOGRES_GLOBAL_JP_FUNCTION_MATCH_ARTIFACT)
      .toContain('global-jp-function-match')
  })
})
