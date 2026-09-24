export const LOGRES_ZENITH_CONSISTENCY_PROVENANCE =
  'ZENITH_DETERMINISTIC_CROSS_ARTIFACT_CONSISTENCY_CERTIFICATE' as const

export const LOGRES_ZENITH_CONSISTENCY_STATUS = 'PASS' as const

export const LOGRES_ZENITH_CONSISTENCY_CERTIFICATE_ID =
  '5d9e3592e3f27fc4469cc123f94a2d4bf2e311988c900b532505b4521e1a1c7b' as const

export const LOGRES_ZENITH_CONSISTENCY_COUNTS =
  Object.freeze({
    invariants: 21,
    passed: 21,
    failed: 0,
    missingSourcePaths: 0,
    protocolMessages: 631,
    criticalProtocolBindings: 30,
    stateMachineStates: 23,
    stateMachineTransitions: 28,
    jpManifestRecords: 31241,
    jpMapRelatedPackages: 2116,
    semanticResourceNodes: 44455,
    semanticResourceEdges: 95477,
    fuzzerCases: 109,
    explicitConflictTasks: 15,
  } as const)

export const LOGRES_ZENITH_CONSISTENCY_GUARANTEES =
  Object.freeze([
    'Every critical state-machine protocol binding resolves to the exact recovered Global opcode catalog.',
    'Offline protocol replay covers the same 30-message boundary as the recovered critical state machine.',
    'Evidence-fuzzer dimensions agree with the recovered state machine and critical protocol corpus.',
    'Millennium Tree 002_000_00001 continuity agrees between map and resource genealogy while 002_000_00008 remains a rejected texture-only structural substitute.',
    'Semantic resource-graph lineage counts agree with resource genealogy and decoded terrain atlas counts.',
    'The contradiction arbiter has no speculation/unresolved winners and preserves same-authority ties.',
    'No available declared source path has drifted from its recorded SHA-256.',
  ] as const)

export const LOGRES_ZENITH_CONSISTENCY_LIMITATIONS =
  Object.freeze([
    'PASS certifies cross-artifact consistency, not completeness of retired-server validation, persistence, formulas or database semantics.',
    'Current-JP-only data remains non-authoritative unless an explicit identity/lineage predicate exists.',
    'Same-authority evidence disagreements remain unresolved.',
    'Function-level semantic lifting remains outside this certificate until GJP-FUNC-MATCH-001 completes.',
  ] as const)

export const LOGRES_ZENITH_CONSISTENCY_ARTIFACT =
  '/home/ubuntu/logres/artifacts/logres-reconstruction-consistency-certificate-20260924.json' as const
