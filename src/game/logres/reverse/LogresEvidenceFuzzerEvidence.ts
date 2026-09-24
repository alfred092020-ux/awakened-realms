export const LOGRES_GLOBAL_3024_EVIDENCE_FUZZER_PROVENANCE =
  'OFFLINE_MUTATION_SUITE_DERIVED_FROM_CONFIRMED_GLOBAL_3_0_24_EVIDENCE' as const

export const LOGRES_GLOBAL_3024_EVIDENCE_FUZZER_COUNTS =
  Object.freeze({
    totalCases: 109,
    criticalSchemaMessages: 30,
    criticalSchemaMessagesMutated: 30,
    wireMutations: 7,
    schemaMutations: 60,
    enumBranches: 29,
    transitionOrderMutations: 8,
    retryTimingMutations: 4,
    resourceIdentityMutations: 1,
    knownGlobalBranches: 22,
    offlineWireRejects: 7,
    offlineSchemaRejects: 60,
    offlineStateModelRejects: 8,
    evidenceMismatchRejects: 4,
    serverBehaviorUnknown: 8,
  } as const)

export const LOGRES_GLOBAL_3024_WIRE_MUTATIONS =
  Object.freeze([
    'bad_packet_marker',
    'declared_packet_payload_too_long',
    'nested_contract_length_mismatch',
    'truncated_packet_header',
    'unknown_compressor_marker',
    'varuint_more_than_five_bytes',
    'wrong_gmcl_contract_id',
  ] as const)

export const LOGRES_GLOBAL_3024_EVIDENCE_FUZZER_POLICIES =
  Object.freeze({
    GLOBAL_KNOWN_BRANCH:
      'Outcome is directly supported by recovered Global client evidence.',
    OFFLINE_WIRE_CONTRACT_REJECT:
      'Recovered offline codec rejects malformed framing; this does not claim historical server behavior.',
    OFFLINE_SCHEMA_REJECT:
      'Fixture violates recovered Global schema and is rejected before server emulation.',
    OFFLINE_STATE_MODEL_REJECT:
      'Sequence contradicts the recovered Global client transition graph; this does not claim retired-server semantics.',
    EVIDENCE_MISMATCH_REJECT:
      'Mutation conflicts with a confirmed recovered fact and must not enter reconstruction.',
    SERVER_BEHAVIOR_UNKNOWN:
      'Client evidence is insufficient; preserve the outcome as an explicit retired-server evidence ceiling.',
  } as const)

export const LOGRES_GLOBAL_3024_KNOWN_RETRY =
  Object.freeze({
    message: 'C_GMCL_BATTLE_ENTRY_REQ_Response',
    retryCode: 2,
    retrySeconds: 1.0,
  } as const)

export const LOGRES_GLOBAL_3024_UNKNOWN_ENUM_BOUNDARIES =
  Object.freeze({
    accountLogin: Object.freeze([0, 8] as const),
    characterCreate: Object.freeze([-1, 4] as const),
    characterLogin: Object.freeze([-1, 8] as const),
    battleEntry: Object.freeze([0, 3] as const),
  } as const)

export const LOGRES_GLOBAL_3024_TRANSITION_MUTATION_GUARDS =
  Object.freeze([
    'TITLE + S_GMCL_BATTLE_RESULT',
    'CHARACTER_LOGIN + S_GMCL_AREA_ENTER',
    'AREA_ACTIVE + S_GMCL_BATTLE_RESULT',
    'BATTLE_ENTRY_PENDING + S_GMCL_BATTLE_RESULT',
    'BATTLE_INITIALIZING + S_GMCL_QUEST_INFO_STATE_RETURN',
    'BOUT_ACTIVE + S_GMCL_AREA_ENTER',
    'BATTLE_RESULT + C_GMCL_CHAR_MOVE_REQ',
    'REWARD_PROJECTION + C_GMCL_BATTLE_ENTRY_REQ',
  ] as const)

export const LOGRES_GLOBAL_3024_RESOURCE_MUTATION_GUARD =
  Object.freeze({
    subject: 'Millennium Tree terrain candidate',
    confirmedCandidate: '002_000_00001',
    rejectedTextureOnlySubstitute: '002_000_00008',
    reason:
      'The candidates share texture atlases but differ in decoded map payload and collision/pathway structure.',
  } as const)

export const LOGRES_GLOBAL_3024_EVIDENCE_FUZZER_ARTIFACT =
  '/home/ubuntu/logres/artifacts/global3024-evidence-fuzzer-20260924.json' as const
