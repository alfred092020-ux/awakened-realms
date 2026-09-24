export const LOGRES_TRACE_CERTIFICATE_PROVENANCE =
  'ZENITH_OFFLINE_REPLAYABLE_TRACE_CERTIFICATE' as const

export const LOGRES_TRACE_CERTIFICATE_ID =
  '45afc19df46b72790189bad00d0decb0e90d884297bee85446b929c393958731' as const

export const LOGRES_TRACE_CERTIFICATE_ARTIFACT =
  Object.freeze({
    path:
      '/home/ubuntu/logres/artifacts/global3024-trace-certificate-20260924.json',
    sha256:
      '64219a3efc09dfa6424ed78a1711fea8f7f1c7dfe12122089f025d1aec94260f',
  } as const)

export const LOGRES_TRACE_CERTIFICATE_COUNTS =
  Object.freeze({
    traces: 4,
    totalSteps: 26,
    primaryTraceSteps: 20,
    uniqueTransitionIds: 24,
    stateMachineTransitions: 28,
    serverAuthoritySteps: 15,
    stepsWithProtocolHash: 22,
    stepsWithFunctionHash: 3,
    stepsWithResourceHash: 26,
    consistencyInvariantsPassed: 21,
    differentialChecks: 9,
  } as const)

export const LOGRES_TRACE_CERTIFICATE_CLASSIFICATIONS =
  Object.freeze({
    proven: 11,
    stubbedServerAuthority: 15,
    lineageSupported: 0,
    implementationOnly: 0,
    unresolved: 0,
  } as const)

export const LOGRES_TRACE_CERTIFICATE_PRIMARY_TRANSITIONS =
  Object.freeze([
    0, 2, 3, 4, 7, 8, 10, 11, 12, 13,
    16, 17, 18, 21, 22, 23, 24, 25, 26, 27,
  ] as const)

export const LOGRES_TRACE_CERTIFICATE_PRIMARY_CLASSIFICATIONS =
  Object.freeze([
    'proven',
    'stubbed_server_authority',
    'stubbed_server_authority',
    'proven',
    'stubbed_server_authority',
    'stubbed_server_authority',
    'proven',
    'stubbed_server_authority',
    'proven',
    'stubbed_server_authority',
    'stubbed_server_authority',
    'proven',
    'stubbed_server_authority',
    'stubbed_server_authority',
    'stubbed_server_authority',
    'proven',
    'stubbed_server_authority',
    'stubbed_server_authority',
    'stubbed_server_authority',
    'proven',
  ] as const)

export const LOGRES_TRACE_CERTIFICATE_SOURCES =
  Object.freeze({
    stateMachineSha256:
      '9c0348e02e6ea75986e6a08d5fdbb9c63329958df54ed308cb573eb135e12e7a',
    behaviorTwinSha256:
      '439d823bca888e313bbb629c53e1e2a79b8ab7d93374c2dece92574d4352bc66',
    behaviorRuntimeSha256:
      'e80eaa8ea5644cdbace04a2b7f56776a68a624bf624797b667c445ba4ac06104',
    protocolTwinSha256:
      '52a0b140d95e904d57f48e1c936c1efc81c34e0c32a70fbd958b967a4c991a5c',
    semanticLiftSha256:
      'd215de8911416c4dab1185d80b0bc2e163c2f794d7d9f3a1253fc18a11383de5',
    assetBinderSha256:
      'a37faddba1c14e7e9fe2c8ca6e08e59dace41f0d9853b830fe2323f76c48d73c',
    consistencyCertificateSha256:
      'd56247dd661f6aca6619bbda703a2f1ae2b71c319c1a48ade99a1c6564eb34a8',
    differentialEmulatorSha256:
      '0036c1187769a5c8935ee61dc1fa5e70dd6f0b6ea84315e70a362e0f8ae0667e',
  } as const)

export const LOGRES_TRACE_CERTIFICATE_NEGATIVE_TESTS =
  Object.freeze([
    'illegal_transition_rejected',
    'server_authority_promotion_rejected',
    'altered_evidence_hash_rejected',
  ] as const)

export const LOGRES_TRACE_CERTIFICATE_GUARDRAILS =
  Object.freeze([
    'No socket, production server, or live retired backend is required for build or replay.',
    'SERVER_AUTHORITY_STUB transitions can never be promoted to proven client facts.',
    'Current-JP lineage cannot replace historical Global evidence without an explicit identity predicate.',
    'Missing protocol, function or resource dimensions remain explicit rather than being fabricated.',
    'Illegal transition IDs, state-chain breaks and altered evidence hashes fail verification.',
  ] as const)

export const LOGRES_TRACE_CERTIFICATE_OFFLINE_ONLY = true as const
export const LOGRES_TRACE_CERTIFICATE_PRODUCTION_SERVER_ACCESS = false as const
