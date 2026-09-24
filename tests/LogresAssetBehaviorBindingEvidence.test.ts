import { describe, expect, it } from 'vitest'

import {
  LOGRES_ASSET_BEHAVIOR_BINDER_ARTIFACT,
  LOGRES_ASSET_BEHAVIOR_BINDER_AUTHORITY,
  LOGRES_ASSET_BEHAVIOR_BINDER_COUNTS,
  LOGRES_ASSET_BEHAVIOR_BINDER_DIRECT_EXAMPLES,
  LOGRES_ASSET_BEHAVIOR_BINDER_EXACT_RESOURCES,
  LOGRES_ASSET_BEHAVIOR_BINDER_GUARDRAILS,
  LOGRES_ASSET_BEHAVIOR_BINDER_PROVENANCE,
  LOGRES_ASSET_BEHAVIOR_BINDER_SOURCES,
  LOGRES_ASSET_BEHAVIOR_BINDER_VERTICAL_COUNTS,
} from '../src/game/logres/reverse/LogresAssetBehaviorBindingEvidence'

describe('MUI+UE Global asset/behavior binder', () => {
  it('binds to the exact semantic/resource/map/protocol/state artifacts', () => {
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_PROVENANCE)
      .toBe('MUIUE_GLOBAL_ASSET_BEHAVIOR_BINDER_WITH_EXPLICIT_AUTHORITY')
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_SOURCES.semanticLiftSha256)
      .toHaveLength(64)
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_SOURCES.resourceSemanticGraphSha256)
      .toHaveLength(64)
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_SOURCES.mapGenealogySha256)
      .toHaveLength(64)
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_SOURCES.protocolSchemaSha256)
      .toHaveLength(64)
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_SOURCES.stateMachineSha256)
      .toHaveLength(64)
  })

  it('produces hundreds of direct Global function-to-resource bindings', () => {
    const counts = LOGRES_ASSET_BEHAVIOR_BINDER_COUNTS
    expect(counts.directGlobalFunctionPatternBindings).toBe(587)
    expect(counts.directGlobalPatternsBound).toBe(501)
    expect(counts.exactGlobalResourceLineage).toBe(14)
    expect(counts.changedPathLineageCandidates).toBe(15)
    expect(counts.semanticFunctionsExamined).toBe(16379)
  })

  it('covers every requested vertical-slice presentation family directly', () => {
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_COUNTS.verticalRolesWithDirectBindings)
      .toBe(7)
    for (const value of Object.values(
      LOGRES_ASSET_BEHAVIOR_BINDER_VERTICAL_COUNTS,
    )) {
      expect(value).toBeGreaterThan(0)
    }
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_VERTICAL_COUNTS.audioBgmSe).toBe(11)
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_VERTICAL_COUNTS.battle).toBe(22)
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_VERTICAL_COUNTS.rewardResult).toBe(40)
  })

  it('contains concrete Global consumer examples', () => {
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_DIRECT_EXAMPLES).toHaveLength(6)
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_DIRECT_EXAMPLES[0].resource)
      .toBe('avatar/scale.json')
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_DIRECT_EXAMPLES[2].resource)
      .toBe('effect/transiton/encount_00.png')
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_DIRECT_EXAMPLES[3].resource)
      .toBe('battle/field/bfd_%03d_%03d.png')
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_DIRECT_EXAMPLES[5].resource)
      .toContain('stamp_complete.lfla')
  })

  it('preserves exact recovered BGM, SE, battle and map package lineage', () => {
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_EXACT_RESOURCES.globalBgm.globalPath)
      .toBe('sound/bgm/000_000_00001.ogg')
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_EXACT_RESOURCES.globalSe.globalPath)
      .toBe('sound/se/100_000_00001.wav')
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_EXACT_RESOURCES.battlePackage.globalPath)
      .toBe('Battle.mbn')
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_EXACT_RESOURCES.fieldMapPackage.globalPath)
      .toBe('map-002/002_000_00001.mbn')
    expect(
      LOGRES_ASSET_BEHAVIOR_BINDER_EXACT_RESOURCES.fieldMapPackage
        .historicalAreaAssignmentClaimed,
    ).toBe(false)
  })

  it('keeps weaker joins explicitly candidate-only', () => {
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_AUTHORITY.directFunctionLiteral)
      .toBe(1)
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_AUTHORITY.exactGlobalResourceLineage)
      .toBe(1)
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_AUTHORITY.changedPathLineageCandidate)
      .toBeLessThan(1)
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_AUTHORITY.runtimePhaseCandidate)
      .toBe(0.35)
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_GUARDRAILS)
      .toContain(
        'Runtime phase/state joins derived from vertical taxonomy are candidate-only at score 0.35 and are not historical asset-selection claims.',
      )
  })

  it('does not manufacture missing protocol or tutorial-map bindings', () => {
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_COUNTS.directBoundProtocolMessages)
      .toBe(0)
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_COUNTS.directBoundStateTransitions)
      .toBe(1)
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_GUARDRAILS)
      .toContain(
        'The Global 002_000_00001 package is proven, but its historical Global tutorial-area assignment is not claimed.',
      )
    expect(LOGRES_ASSET_BEHAVIOR_BINDER_ARTIFACT.sha256).toHaveLength(64)
  })
})
