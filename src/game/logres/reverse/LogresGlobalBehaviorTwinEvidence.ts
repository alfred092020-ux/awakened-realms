export const LOGRES_GLOBAL_BEHAVIOR_TWIN_PROVENANCE =
  'OMEGA_OFFLINE_GLOBAL_BEHAVIOR_TWIN_WITH_EXPLICIT_SERVER_STUBS' as const

export const LOGRES_GLOBAL_BEHAVIOR_TWIN_SOURCES =
  Object.freeze({
    offlineProtocolTwinSha256:
      '52a0b140d95e904d57f48e1c936c1efc81c34e0c32a70fbd958b967a4c991a5c',
    semanticLiftSha256:
      'd215de8911416c4dab1185d80b0bc2e163c2f794d7d9f3a1253fc18a11383de5',
    stateMachineSha256:
      '9c0348e02e6ea75986e6a08d5fdbb9c63329958df54ed308cb573eb135e12e7a',
    resourceSemanticGraphSha256:
      'fdd4921dbab864840c1106a5ff2196da2c57b29a5517eca0e4a603a1e1f25ab3',
  } as const)

export const LOGRES_GLOBAL_BEHAVIOR_TWIN_COUNTS =
  Object.freeze({
    states: 23,
    transitions: 28,
    explicitServerAuthorityTransitions: 16,
    clientDirectedOrProjectedTransitions: 12,
    protocolTwinCriticalReplayEvents: 30,
    protocolTwinExactClientFrames: 10,
    protocolTwinServerAuthorityStubs: 20,
    semanticLiftedFunctions: 16379,
    semanticProtocolBoundFunctions: 113,
    semanticConfirmedStateFunctions: 6,
    successfulFirstCharacterCriticalTraceSteps: 20,
  } as const)

export const LOGRES_GLOBAL_BEHAVIOR_TWIN_CRITICAL_TRACE =
  Object.freeze([
    'TITLE',
    'ACCOUNT_AUTH',
    'CHARACTER_LIST',
    'PREBEGIN_INIT',
    'GENDER_CREATE',
    'CHARACTER_LOGIN',
    'PREBEGIN_INIT',
    'FIELD_SELECT',
    'FIELD_INFO',
    'ZONEIN',
    'AREA_ACTIVE',
    'ENCOUNTER_ELIGIBILITY',
    'BATTLE_ENTRY_PENDING',
    'BATTLE_ACCEPTED',
    'BATTLE_INITIALIZING',
    'BOUT_ACTIVE',
    'BOUT_ACTIVE',
    'BATTLE_RESULT',
    'REWARD_PROJECTION',
    'FIELD_RETURN',
    'AREA_ACTIVE',
  ] as const)

export const LOGRES_GLOBAL_BEHAVIOR_TWIN_EXACT_RULES =
  Object.freeze({
    characterCreateSuccessCode: 0,
    acceptedCharacterLoginCodes: Object.freeze([1, 2, 3, 4] as const),
    battleEntryAcceptedCode: 1,
    battleEntryRetryCode: 2,
    battleEntryRetrySeconds: 1.0,
  } as const)

export const LOGRES_GLOBAL_BEHAVIOR_TWIN_GUARDRAILS =
  Object.freeze([
    'The twin performs no socket or production-server access.',
    'Every retired-server-authored transition requires an explicit SERVER_AUTHORITY_STUB.',
    'A server stub preserves the recovered client projection but never claims the retired server would have produced that value.',
    'Implementation traces outside the recovered 28-transition client graph fail evidence validation.',
    'Implementation traces may not label a server-authority transition CONFIRMED_RETIRED_SERVER.',
    'Battle damage, stats, cooldowns, EP, reward rolls, persistence, matchmaking and exact historical dynamic payloads remain external evidence ceilings.',
    'Current-JP behavior is not used to fill changed or missing Global behavior.',
  ] as const)

export const LOGRES_GLOBAL_BEHAVIOR_TWIN_ARTIFACT =
  '/home/ubuntu/logres/artifacts/global3024-behavior-twin-20260924.json' as const
