import { describe, expect, it } from 'vitest'

import {
  LOGRES_GLOBAL_JP_SEMANTIC_LIFT_ARTIFACT,
  LOGRES_GLOBAL_JP_SEMANTIC_LIFT_CONFIRMED_STATE_EXAMPLES,
  LOGRES_GLOBAL_JP_SEMANTIC_LIFT_COUNTS,
  LOGRES_GLOBAL_JP_SEMANTIC_LIFT_EVIDENCE_LAYERS,
  LOGRES_GLOBAL_JP_SEMANTIC_LIFT_GUARDRAILS,
  LOGRES_GLOBAL_JP_SEMANTIC_LIFT_PROVENANCE,
  LOGRES_GLOBAL_JP_SEMANTIC_LIFT_SOURCES,
} from '../src/game/logres/reverse/LogresGlobalJpSemanticLiftEvidence'

describe('OMEGA Global/JP semantic lift', () => {
  it('binds to the exact function, protocol and state artifacts', () => {
    expect(LOGRES_GLOBAL_JP_SEMANTIC_LIFT_PROVENANCE)
      .toBe('OMEGA_GLOBAL_NATIVE_SEMANTIC_LIFT_WITH_EXPLICIT_PREDICATES')
    expect(LOGRES_GLOBAL_JP_SEMANTIC_LIFT_SOURCES.functionMatchSha256)
      .toBe('9a71e535a3f81a9817512ac911b0d22093c8c55b8dcc9dfbc8fb050106b62372')
    expect(LOGRES_GLOBAL_JP_SEMANTIC_LIFT_SOURCES.protocolSchemaSha256)
      .toHaveLength(64)
    expect(LOGRES_GLOBAL_JP_SEMANTIC_LIFT_SOURCES.stateMachineSha256)
      .toHaveLength(64)
  })

  it('lifts only exact-symbol and structural-high lineage', () => {
    const counts = LOGRES_GLOBAL_JP_SEMANTIC_LIFT_COUNTS
    expect(counts.exactSymbolLifted + counts.structuralHighLifted)
      .toBe(counts.highConfidenceLiftedFunctions)
    expect(counts.highConfidenceLiftedFunctions).toBe(16379)
    expect(counts.structuralMediumCandidatesNotLifted).toBe(82)
    expect(counts.unresolvedGlobalFunctions).toBe(3406)
    expect(counts.missingFunctionInventoryRecords).toBe(0)
  })

  it('carries real Global control-flow and literal evidence', () => {
    const counts = LOGRES_GLOBAL_JP_SEMANTIC_LIFT_COUNTS
    expect(counts.functionsWithCallers).toBeGreaterThan(0)
    expect(counts.functionsWithCallees).toBeGreaterThan(0)
    expect(counts.functionsWithLiterals).toBeGreaterThan(0)
    expect(counts.functionsWithResourceReferenceCandidates).toBeGreaterThan(0)
    expect(LOGRES_GLOBAL_JP_SEMANTIC_LIFT_EVIDENCE_LAYERS[0].authority)
      .toBe('GLOBAL_BINARY_DERIVED_DIRECT_CALL_NEIGHBORHOOD')
  })

  it('binds protocol procedures without importing JP behavior', () => {
    const counts = LOGRES_GLOBAL_JP_SEMANTIC_LIFT_COUNTS
    expect(counts.functionsWithProtocolReferences).toBe(113)
    expect(counts.protocolMessagesReferenced).toBe(106)
    expect(LOGRES_GLOBAL_JP_SEMANTIC_LIFT_GUARDRAILS)
      .toContain('No JP-only behavior is copied into a Global semantic claim.')
  })

  it('keeps confirmed state effects conservative', () => {
    const counts = LOGRES_GLOBAL_JP_SEMANTIC_LIFT_COUNTS
    expect(counts.functionsWithConfirmedStateEffects).toBe(6)
    expect(counts.stateTransitionsBound).toBe(6)
    expect(counts.stateTransitionsTotal).toBe(28)
    expect(LOGRES_GLOBAL_JP_SEMANTIC_LIFT_GUARDRAILS)
      .toContain('Unbound critical-loop transitions remain unbound rather than being guessed.')
  })

  it('records concrete onboarding state reads and writes', () => {
    expect(LOGRES_GLOBAL_JP_SEMANTIC_LIFT_CONFIRMED_STATE_EXAMPLES)
      .toHaveLength(4)
    expect(LOGRES_GLOBAL_JP_SEMANTIC_LIFT_CONFIRMED_STATE_EXAMPLES[0].reads)
      .toEqual(['CHARACTER_LIST'])
    expect(LOGRES_GLOBAL_JP_SEMANTIC_LIFT_CONFIRMED_STATE_EXAMPLES[0].writes)
      .toEqual(['PREBEGIN_INIT'])
    expect(LOGRES_GLOBAL_JP_SEMANTIC_LIFT_CONFIRMED_STATE_EXAMPLES[1].writes)
      .toEqual(['GENDER_CREATE'])
    expect(LOGRES_GLOBAL_JP_SEMANTIC_LIFT_CONFIRMED_STATE_EXAMPLES[3].writes)
      .toEqual(['TERMS_GATE'])
  })

  it('keeps name-derived semantics explicitly heuristic', () => {
    expect(LOGRES_GLOBAL_JP_SEMANTIC_LIFT_EVIDENCE_LAYERS[2].authority)
      .toBe('HEURISTIC_NAME_ONLY')
    expect(LOGRES_GLOBAL_JP_SEMANTIC_LIFT_GUARDRAILS)
      .toContain('Name-derived semantic tags and state-access candidates are search aids only.')
    expect(LOGRES_GLOBAL_JP_SEMANTIC_LIFT_ARTIFACT)
      .toContain('global-jp-semantic-lift')
  })
})
