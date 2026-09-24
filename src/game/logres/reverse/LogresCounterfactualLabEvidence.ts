export const LOGRES_ZENITH_COUNTERFACTUAL_PROVENANCE =
  'ZENITH_OFFLINE_COUNTERFACTUAL_MODEL_FROM_CONFIRMED_GLOBAL_CLIENT_EVIDENCE' as const

export const LOGRES_ZENITH_COUNTERFACTUAL_LAB_ID =
  '8cbf1ddbc33b29bf2ed35d34938a7f3809bddaa01c6a7dfc32820e52ab6eb788' as const

export const LOGRES_ZENITH_COUNTERFACTUAL_COUNTS =
  Object.freeze({
    states: 23,
    reachableStates: 23,
    unreachableStates: 0,
    transitions: 28,
    clientOnlyTransitions: 10,
    serverAuthorityTransitions: 18,
    behavioralCounterfactualCases: 42,
    clientKnownBranches: 22,
    clientImpossible: 8,
    serverUnknown: 8,
    evidenceMismatch: 4,
    longestShortestTraceSteps: 15,
    longestShortestTraceState: 'FIELD_RETURN',
  } as const)

export const LOGRES_ZENITH_COUNTERFACTUAL_CLASSES =
  Object.freeze({
    CLIENT_KNOWN_BRANCH:
      'The recovered Global client has a directly evidenced branch for this input/result.',
    CLIENT_IMPOSSIBLE:
      'The sequence is not an evidenced outgoing transition from that recovered client state.',
    SERVER_UNKNOWN:
      'Client evidence does not establish how the retired server behaves for this value/condition.',
    EVIDENCE_MISMATCH:
      'The alternative contradicts a confirmed recovered client/resource fact.',
  } as const)

export const LOGRES_ZENITH_COUNTERFACTUAL_GUARDRAILS =
  Object.freeze([
    'Counterfactuals are never promoted to historical observations.',
    'A server-authority boundary preserves the recovered client reaction while leaving server validation or payload production unknown.',
    'Current-JP behavior is not used to fill retired-Global server gaps.',
    'Shortest-path reachability proves graph reachability only, not that every route occurred historically.',
    'No live production game server is contacted.',
  ] as const)

export const LOGRES_ZENITH_COUNTERFACTUAL_ARTIFACT =
  '/home/ubuntu/logres/artifacts/global3024-counterfactual-lab-20260924.json' as const
