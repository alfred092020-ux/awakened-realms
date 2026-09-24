export const LOGRES_GALAXY_CAUSAL_TWIN_PROVENANCE =
  'GALAXY_GLOBAL_3024_CLIENT_CAUSAL_TWIN_WITH_AUTHORITY_BOUNDARIES' as const

export const LOGRES_GALAXY_CAUSAL_TWIN_ARTIFACT = Object.freeze({
  path: '/home/ubuntu/logres/artifacts/global-galaxy-causal-twin-20260924.json',
  sha256: '14262960f59f13070c4dc513bcfff7c7e323e9621ef1c2400bbe18f82ea99814',
} as const)

export const LOGRES_GALAXY_CAUSAL_TWIN_SOURCES = Object.freeze({
  assetBehaviorSha256:
    'a37faddba1c14e7e9fe2c8ca6e08e59dace41f0d9853b830fe2323f76c48d73c',
  behaviorTwinSha256:
    '439d823bca888e313bbb629c53e1e2a79b8ab7d93374c2dece92574d4352bc66',
  closureSha256:
    'dbfda735f3c6820dbd9956b6e2d3fca36bc642f4091a0067187d62cfbdaecda2',
  protocolSchemaSha256:
    '9e9583da01db8aa4a7c808397cbf740114469902862bc5984631bbb6815a1f16',
  resourceGraphSha256:
    'fdd4921dbab864840c1106a5ff2196da2c57b29a5517eca0e4a603a1e1f25ab3',
  semanticLiftSha256:
    'd215de8911416c4dab1185d80b0bc2e163c2f794d7d9f3a1253fc18a11383de5',
  stateMachineSha256:
    '9c0348e02e6ea75986e6a08d5fdbb9c63329958df54ed308cb573eb135e12e7a',
} as const)

export const LOGRES_GALAXY_CAUSAL_TWIN_COUNTS = Object.freeze({
  nodes: 1224,
  edges: 1066,
  causalEdges: 57,
  serverAuthorityBoundaryEdges: 45,
  states: 23,
  stateTransitions: 28,
  boundTransitionFunctions: 6,
  reverseImpactRoots: 105,
  criticalChains: 11,
  exactGlobalResources: 14,
  nodeKinds: Object.freeze({
    authorityBoundary: 2,
    globalFunction: 503,
    globalResource: 14,
    implementation: 11,
    protocolMessage: 124,
    resourcePattern: 501,
    runtimeState: 23,
    stateTransition: 28,
    test: 11,
    verticalSliceRole: 7,
  }),
  edgeRelations: Object.freeze({
    affectsImplementation: 90,
    affectsTest: 53,
    classifiedVerticalRole: 120,
    enablesTransitionContext: 28,
    exactResourceSupportsVerticalRole: 6,
    externalAuthorityInput: 12,
    implementsClientTransitionEffect: 7,
    producesClientState: 28,
    referencesProtocolMessage: 113,
    resourceDependencyOfFunction: 587,
    triggersRecoveredClientReaction: 22,
  }),
} as const)

export const LOGRES_GALAXY_CAUSAL_TWIN_AUTHORITY_POLICY = Object.freeze({
  historicalAuthority: 'GLOBAL_3_0_24_CLIENT_ONLY',
  retiredServerCausalityInferred: false,
  serverMessagesAreExternalInputs: true,
  clientReactionsAfterServerInputsMayBeConfirmed: true,
  serverBoundaryLabel: 'SERVER_AUTHORITY_STUB_BOUNDARY',
  unresolved: Object.freeze([
    'Retired-server decision logic, matchmaking, persistence, economy, dynamic reward rolls and exact production payload selection remain outside client evidence.',
    'Generic Global resource format/path literals do not prove a particular dynamic server-selected resource instance.',
    'The proven Global 002_000_00001 package is not promoted to a historical tutorial-area assignment.',
    'Current-JP changed-byte lineage is excluded from historical Global causality.',
  ]),
} as const)

export const LOGRES_GALAXY_CAUSAL_TWIN_CRITICAL_CHAINS = Object.freeze([
  Object.freeze({
    transitionIndex: 1,
    from: 'ACCOUNT_AUTH',
    to: 'TERMS_GATE',
    protocolMessage: 'C_GMCL_ACCOUNT_LOGIN_REQ_Response',
    serverAuthorityBoundary: true,
  }),
  Object.freeze({
    transitionIndex: 7,
    from: 'GENDER_CREATE',
    to: 'CHARACTER_LOGIN',
    protocolMessage: 'C_GMCL_CHAR_CREATE_REQ_Response',
    serverAuthorityBoundary: true,
  }),
  Object.freeze({
    transitionIndex: 13,
    from: 'ZONEIN',
    to: 'AREA_ACTIVE',
    protocolMessage: 'S_GMCL_AREA_ENTER',
    serverAuthorityBoundary: true,
  }),
  Object.freeze({
    transitionIndex: 17,
    from: 'ENCOUNTER_ELIGIBILITY',
    to: 'BATTLE_ENTRY_PENDING',
    protocolMessage: 'C_GMCL_BATTLE_ENTRY_REQ',
    serverAuthorityBoundary: false,
  }),
  Object.freeze({
    transitionIndex: 18,
    from: 'BATTLE_ENTRY_PENDING',
    to: 'BATTLE_ACCEPTED',
    protocolMessage: 'C_GMCL_BATTLE_ENTRY_REQ_Response',
    serverAuthorityBoundary: true,
  }),
  Object.freeze({
    transitionIndex: 19,
    from: 'BATTLE_ENTRY_PENDING',
    to: 'BATTLE_ENTRY_RETRY_WAIT',
    protocolMessage: 'C_GMCL_BATTLE_ENTRY_REQ_Response',
    serverAuthorityBoundary: true,
  }),
  Object.freeze({
    transitionIndex: 21,
    from: 'BATTLE_ACCEPTED',
    to: 'BATTLE_INITIALIZING',
    protocolMessage: 'S_GMCL_BATTLE_INITIALIZE',
    serverAuthorityBoundary: true,
  }),
  Object.freeze({
    transitionIndex: 24,
    from: 'BOUT_ACTIVE',
    to: 'BATTLE_RESULT',
    protocolMessage: 'S_GMCL_BATTLE_RESULT',
    serverAuthorityBoundary: true,
  }),
  Object.freeze({
    transitionIndex: 25,
    from: 'BATTLE_RESULT',
    to: 'REWARD_PROJECTION',
    protocolMessage: 'S_GMCL_QUEST_INFO_STATE_RESULT',
    serverAuthorityBoundary: true,
  }),
  Object.freeze({
    transitionIndex: 26,
    from: 'REWARD_PROJECTION',
    to: 'FIELD_RETURN',
    protocolMessage: 'S_GMCL_QUEST_INFO_STATE_RETURN',
    serverAuthorityBoundary: true,
  }),
  Object.freeze({
    transitionIndex: 27,
    from: 'FIELD_RETURN',
    to: 'AREA_ACTIVE',
    protocolMessage: null,
    serverAuthorityBoundary: false,
  }),
] as const)

export const LOGRES_GALAXY_CAUSAL_TWIN_REVERSE_IMPACT_EXAMPLES =
  Object.freeze({
    battleEntryResponse: Object.freeze({
      root: 'protocol:C_GMCL_BATTLE_ENTRY_REQ_Response',
      runtimeStates: Object.freeze([
        'BATTLE_ACCEPTED',
        'BATTLE_ENTRY_PENDING',
        'BATTLE_ENTRY_RETRY_WAIT',
        'BATTLE_INITIALIZING',
        'BOUT_ACTIVE',
      ]),
      implementationRefs: Object.freeze([
        'src/game/logres/battle/LogresGlobal3024BattleEvidence.ts',
        'src/game/logres/field/LogresGlobal3024FieldEvidence.ts',
        'src/game/logres/protocol/LogresGlobal3024ProtocolEvidence.ts',
      ]),
      testRefs: Object.freeze([
        'tests/LogresGlobal3024FieldEvidence.test.ts',
        'tests/LogresGlobalJpProtocolSchemaEvidence.test.ts',
      ]),
    }),
    battleResult: Object.freeze({
      root: 'protocol:S_GMCL_BATTLE_RESULT',
      runtimeStates: Object.freeze([
        'BATTLE_RESULT',
        'FIELD_RETURN',
        'REWARD_PROJECTION',
      ]),
      implementationRefs: Object.freeze([
        'src/game/logres/battle/LogresGlobal3024BattleEvidence.ts',
        'src/game/logres/protocol/LogresGlobal3024ProtocolEvidence.ts',
        'src/game/logres/systems/LogresGlobal3024SystemsEvidence.ts',
      ]),
      testRefs: Object.freeze([
        'tests/LogresGlobal3024BattleEvidence.test.ts',
        'tests/LogresGlobal3024SystemsEvidence.test.ts',
      ]),
    }),
    fieldReturnProjection: Object.freeze({
      root: 'protocol:S_GMCL_QUEST_INFO_STATE_RETURN',
      runtimeStates: Object.freeze([
        'AREA_ACTIVE',
        'ENCOUNTER_ELIGIBILITY',
        'FIELD_MOVEMENT',
        'FIELD_RETURN',
        'NPC_INTERACTION',
      ]),
      implementationRefs: Object.freeze([
        'src/game/logres/field/LogresGlobal3024FieldEvidence.ts',
        'src/game/logres/protocol/LogresGlobal3024ProtocolEvidence.ts',
        'src/game/logres/systems/LogresGlobal3024SystemsEvidence.ts',
      ]),
      testRefs: Object.freeze([
        'tests/LogresGlobal3024FieldEvidence.test.ts',
        'tests/LogresGlobalBehaviorTwin.test.ts',
      ]),
    }),
    avatarScale: Object.freeze({
      root: 'resource-pattern:avatar/scale.json',
      runtimeStates: Object.freeze([
        'CHARACTER_LOGIN',
        'FIELD_SELECT',
        'GENDER_CREATE',
        'PREBEGIN_INIT',
        'TITLE',
      ]),
      implementationRefs: Object.freeze([
        'src/game/logres/protocol/LogresGlobal3024ProtocolEvidence.ts',
        'src/game/scenes/LogresCharacterCreateScene.ts',
        'src/game/scenes/LogresTitleScene.ts',
      ]),
      testRefs: Object.freeze([
        'tests/LogresAssetBehaviorBindingEvidence.test.ts',
        'tests/LogresGlobal3024RuntimeEvidence.test.ts',
        'tests/LogresGlobalStateMachineEvidence.test.ts',
      ]),
    }),
    exactFieldPackage: Object.freeze({
      root: 'resource:global-cache:map-002/002_000_00001.mbn',
      runtimeStates: Object.freeze([]),
      implementationRefs: Object.freeze([]),
      testRefs: Object.freeze([
        'tests/LogresAssetBehaviorBindingEvidence.test.ts',
      ]),
      historicalTutorialAreaAssignmentClaimed: false,
    }),
  } as const)

export const LOGRES_GALAXY_CAUSAL_TWIN_QUERY_CONTRACT = Object.freeze({
  rootNodeKinds: Object.freeze([
    'global_function',
    'protocol_message',
    'resource_pattern',
    'global_resource',
    'state_transition',
  ]),
  outputs: Object.freeze([
    'runtime_states',
    'implementation_refs',
    'test_refs',
    'traversed_edge_ids',
  ]),
  impactTraversalOnlyUsesExplicitPropagatingEdges: true,
  maxDepth: 6,
} as const)
