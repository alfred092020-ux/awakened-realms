import { describe, expect, it } from 'vitest'

import {
  LOGRES_GALAXY_CAUSAL_TWIN_ARTIFACT,
  LOGRES_GALAXY_CAUSAL_TWIN_AUTHORITY_POLICY,
  LOGRES_GALAXY_CAUSAL_TWIN_COUNTS,
  LOGRES_GALAXY_CAUSAL_TWIN_CRITICAL_CHAINS,
  LOGRES_GALAXY_CAUSAL_TWIN_PROVENANCE,
  LOGRES_GALAXY_CAUSAL_TWIN_QUERY_CONTRACT,
  LOGRES_GALAXY_CAUSAL_TWIN_REVERSE_IMPACT_EXAMPLES,
  LOGRES_GALAXY_CAUSAL_TWIN_SOURCES,
} from '../src/game/logres/reverse/LogresGalaxyCausalTwinEvidence'

describe('Galaxy Global 3.0.24 client causal twin', () => {
  it('is pinned to the exact prerequisite evidence artifacts', () => {
    expect(LOGRES_GALAXY_CAUSAL_TWIN_PROVENANCE).toBe(
      'GALAXY_GLOBAL_3024_CLIENT_CAUSAL_TWIN_WITH_AUTHORITY_BOUNDARIES',
    )

    for (const hash of Object.values(LOGRES_GALAXY_CAUSAL_TWIN_SOURCES)) {
      expect(hash).toHaveLength(64)
    }

    expect(LOGRES_GALAXY_CAUSAL_TWIN_ARTIFACT.sha256).toHaveLength(64)
  })

  it('covers the complete recovered state-transition backbone', () => {
    expect(LOGRES_GALAXY_CAUSAL_TWIN_COUNTS.states).toBe(23)
    expect(LOGRES_GALAXY_CAUSAL_TWIN_COUNTS.stateTransitions).toBe(28)
    expect(LOGRES_GALAXY_CAUSAL_TWIN_COUNTS.nodes).toBe(1224)
    expect(LOGRES_GALAXY_CAUSAL_TWIN_COUNTS.edges).toBe(1066)
    expect(LOGRES_GALAXY_CAUSAL_TWIN_COUNTS.causalEdges).toBe(57)
    expect(LOGRES_GALAXY_CAUSAL_TWIN_COUNTS.boundTransitionFunctions).toBe(6)
  })

  it('links functions, protocol, resources, implementation and tests', () => {
    const kinds = LOGRES_GALAXY_CAUSAL_TWIN_COUNTS.nodeKinds
    const relations = LOGRES_GALAXY_CAUSAL_TWIN_COUNTS.edgeRelations

    expect(kinds.globalFunction).toBe(503)
    expect(kinds.protocolMessage).toBe(124)
    expect(kinds.resourcePattern).toBe(501)
    expect(kinds.globalResource).toBe(14)
    expect(kinds.implementation).toBeGreaterThan(0)
    expect(kinds.test).toBeGreaterThan(0)

    expect(relations.implementsClientTransitionEffect).toBe(7)
    expect(relations.triggersRecoveredClientReaction).toBe(22)
    expect(relations.referencesProtocolMessage).toBe(113)
    expect(relations.resourceDependencyOfFunction).toBe(587)
    expect(relations.affectsImplementation).toBe(90)
    expect(relations.affectsTest).toBe(53)
  })

  it('keeps retired-server authority outside the recovered client graph', () => {
    const policy = LOGRES_GALAXY_CAUSAL_TWIN_AUTHORITY_POLICY

    expect(policy.historicalAuthority).toBe('GLOBAL_3_0_24_CLIENT_ONLY')
    expect(policy.retiredServerCausalityInferred).toBe(false)
    expect(policy.serverMessagesAreExternalInputs).toBe(true)
    expect(policy.clientReactionsAfterServerInputsMayBeConfirmed).toBe(true)
    expect(LOGRES_GALAXY_CAUSAL_TWIN_COUNTS.serverAuthorityBoundaryEdges)
      .toBeGreaterThan(0)

    expect(policy.unresolved).toContain(
      'Retired-server decision logic, matchmaking, persistence, economy, dynamic reward rolls and exact production payload selection remain outside client evidence.',
    )
  })

  it('preserves the client-vs-server boundary across the critical slice', () => {
    expect(LOGRES_GALAXY_CAUSAL_TWIN_CRITICAL_CHAINS).toHaveLength(11)

    const battleRequest = LOGRES_GALAXY_CAUSAL_TWIN_CRITICAL_CHAINS
      .find(row => row.transitionIndex === 17)
    const battleAccepted = LOGRES_GALAXY_CAUSAL_TWIN_CRITICAL_CHAINS
      .find(row => row.transitionIndex === 18)
    const battleRetry = LOGRES_GALAXY_CAUSAL_TWIN_CRITICAL_CHAINS
      .find(row => row.transitionIndex === 19)
    const result = LOGRES_GALAXY_CAUSAL_TWIN_CRITICAL_CHAINS
      .find(row => row.transitionIndex === 24)

    expect(battleRequest?.serverAuthorityBoundary).toBe(false)
    expect(battleAccepted?.serverAuthorityBoundary).toBe(true)
    expect(battleRetry?.serverAuthorityBoundary).toBe(true)
    expect(result?.serverAuthorityBoundary).toBe(true)
  })

  it('answers reverse impact for battle-entry response changes', () => {
    const impact =
      LOGRES_GALAXY_CAUSAL_TWIN_REVERSE_IMPACT_EXAMPLES.battleEntryResponse

    expect(impact.runtimeStates).toContain('BATTLE_ACCEPTED')
    expect(impact.runtimeStates).toContain('BATTLE_ENTRY_RETRY_WAIT')
    expect(impact.runtimeStates).toContain('BATTLE_INITIALIZING')
    expect(impact.implementationRefs).toContain(
      'src/game/logres/field/LogresGlobal3024FieldEvidence.ts',
    )
    expect(impact.implementationRefs).toContain(
      'src/game/logres/battle/LogresGlobal3024BattleEvidence.ts',
    )
    expect(impact.testRefs).toContain(
      'tests/LogresGlobal3024FieldEvidence.test.ts',
    )
  })

  it('propagates battle result/reward return impact without claiming server logic', () => {
    const result =
      LOGRES_GALAXY_CAUSAL_TWIN_REVERSE_IMPACT_EXAMPLES.battleResult
    const fieldReturn =
      LOGRES_GALAXY_CAUSAL_TWIN_REVERSE_IMPACT_EXAMPLES.fieldReturnProjection

    expect(result.runtimeStates).toEqual([
      'BATTLE_RESULT',
      'FIELD_RETURN',
      'REWARD_PROJECTION',
    ])
    expect(result.implementationRefs).toContain(
      'src/game/logres/systems/LogresGlobal3024SystemsEvidence.ts',
    )
    expect(fieldReturn.runtimeStates).toContain('FIELD_RETURN')
    expect(fieldReturn.runtimeStates).toContain('AREA_ACTIVE')
    expect(
      LOGRES_GALAXY_CAUSAL_TWIN_AUTHORITY_POLICY.retiredServerCausalityInferred,
    ).toBe(false)
  })

  it('maps Global resource evidence to affected client surfaces conservatively', () => {
    const avatar =
      LOGRES_GALAXY_CAUSAL_TWIN_REVERSE_IMPACT_EXAMPLES.avatarScale
    const map =
      LOGRES_GALAXY_CAUSAL_TWIN_REVERSE_IMPACT_EXAMPLES.exactFieldPackage

    expect(avatar.runtimeStates).toContain('PREBEGIN_INIT')
    expect(avatar.implementationRefs).toContain(
      'src/game/scenes/LogresCharacterCreateScene.ts',
    )
    expect(avatar.testRefs).toContain(
      'tests/LogresAssetBehaviorBindingEvidence.test.ts',
    )

    expect(map.historicalTutorialAreaAssignmentClaimed).toBe(false)
    expect(map.runtimeStates).toHaveLength(0)
  })

  it('exposes a deterministic bounded reverse-impact contract', () => {
    expect(LOGRES_GALAXY_CAUSAL_TWIN_COUNTS.reverseImpactRoots).toBe(105)
    expect(LOGRES_GALAXY_CAUSAL_TWIN_QUERY_CONTRACT.maxDepth).toBe(6)
    expect(
      LOGRES_GALAXY_CAUSAL_TWIN_QUERY_CONTRACT
        .impactTraversalOnlyUsesExplicitPropagatingEdges,
    ).toBe(true)
    expect(LOGRES_GALAXY_CAUSAL_TWIN_QUERY_CONTRACT.outputs).toContain(
      'implementation_refs',
    )
    expect(LOGRES_GALAXY_CAUSAL_TWIN_QUERY_CONTRACT.outputs).toContain(
      'test_refs',
    )
  })
})
