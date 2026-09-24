export const LOGRES_GLOBAL_JP_SEMANTIC_LIFT_PROVENANCE =
  'OMEGA_GLOBAL_NATIVE_SEMANTIC_LIFT_WITH_EXPLICIT_PREDICATES' as const

export const LOGRES_GLOBAL_JP_SEMANTIC_LIFT_SOURCES =
  Object.freeze({
    functionMatchSha256:
      '9a71e535a3f81a9817512ac911b0d22093c8c55b8dcc9dfbc8fb050106b62372',
    protocolSchemaSha256:
      '9e9583da01db8aa4a7c808397cbf740114469902862bc5984631bbb6815a1f16',
    stateMachineSha256:
      '9c0348e02e6ea75986e6a08d5fdbb9c63329958df54ed308cb573eb135e12e7a',
  } as const)

export const LOGRES_GLOBAL_JP_SEMANTIC_LIFT_COUNTS =
  Object.freeze({
    highConfidenceLiftedFunctions: 16379,
    exactSymbolLifted: 16338,
    structuralHighLifted: 41,
    structuralMediumCandidatesNotLifted: 82,
    unresolvedGlobalFunctions: 3406,

    functionsWithCallers: 127,
    functionsWithCallees: 1939,
    functionsWithLiterals: 2833,
    functionsWithResourceReferenceCandidates: 468,
    functionsWithProtocolReferences: 113,
    protocolMessagesReferenced: 106,

    functionsWithConfirmedStateEffects: 6,
    stateTransitionsBound: 6,
    stateTransitionsTotal: 28,

    missingFunctionInventoryRecords: 0,
  } as const)

export const LOGRES_GLOBAL_JP_SEMANTIC_LIFT_CONFIRMED_STATE_EXAMPLES =
  Object.freeze([
    Object.freeze({
      function: 'lfs::GameInformation::initializeForPreBeginGame()',
      reads: Object.freeze(['CHARACTER_LIST'] as const),
      writes: Object.freeze(['PREBEGIN_INIT'] as const),
      evidence: 'GLOBAL_DIRECT_GHIDRA_0x0205f024',
    }),
    Object.freeze({
      function: 'lfs::ReleaseScene_CharcterMake::create()',
      reads: Object.freeze(['PREBEGIN_INIT'] as const),
      writes: Object.freeze(['GENDER_CREATE'] as const),
      evidence: 'GLOBAL_DIRECT_GHIDRA_0x0205f4a0_PLUS_PLT_0x1478440',
    }),
    Object.freeze({
      function: 'lfs::ReleaseScene_CharacterLogin::create()',
      reads: Object.freeze(['PREBEGIN_INIT', 'GENDER_CREATE'] as const),
      writes: Object.freeze(['CHARACTER_LOGIN'] as const),
      evidence: 'GLOBAL_DIRECT_GHIDRA onboarding state-machine bindings',
    }),
    Object.freeze({
      function: 'lfs::ReleaseScene_AccountLogIn::onAuthRequireAgreement(cocos2d::Ref*)',
      reads: Object.freeze(['ACCOUNT_AUTH'] as const),
      writes: Object.freeze(['TERMS_GATE'] as const),
      evidence: 'GLOBAL_DIRECT_GHIDRA_0x0205ed78',
    }),
  ] as const)

export const LOGRES_GLOBAL_JP_SEMANTIC_LIFT_EVIDENCE_LAYERS =
  Object.freeze([
    Object.freeze({
      layer: 'GLOBAL_CONTROL_FLOW',
      authority: 'GLOBAL_BINARY_DERIVED_DIRECT_CALL_NEIGHBORHOOD',
      contents: 'normalized callers/callees and Global literals',
    }),
    Object.freeze({
      layer: 'GLOBAL_PROTOCOL_STATE',
      authority: 'CONFIRMED_GLOBAL_PROTOCOL_OR_STATE_MACHINE_BINDING',
      contents: 'protocol procedures plus confirmed state reads/writes/effects',
    }),
    Object.freeze({
      layer: 'DESCRIPTIVE_CANDIDATES',
      authority: 'HEURISTIC_NAME_ONLY',
      contents: 'symbol-name semantic tags and candidate state-access roles',
    }),
  ] as const)

export const LOGRES_GLOBAL_JP_SEMANTIC_LIFT_GUARDRAILS =
  Object.freeze([
    'Global 3.0.24 is the semantic authority; current JP supplies lineage predicates only.',
    'No JP-only behavior is copied into a Global semantic claim.',
    'Exact symbol correspondence is not behavioral identity; body divergence remains visible.',
    'Name-derived semantic tags and state-access candidates are search aids only.',
    'Confirmed state reads and writes are emitted only from exact Global protocol-message or state-machine action/trigger bindings.',
    'Unbound critical-loop transitions remain unbound rather than being guessed.',
    'STRUCTURAL_MEDIUM candidates are retained separately and are not semantically lifted as high-confidence functions.',
  ] as const)

export const LOGRES_GLOBAL_JP_SEMANTIC_LIFT_ARTIFACT =
  '/home/ubuntu/logres/artifacts/global-jp-semantic-lift-20260924.json' as const
