export const LOGRES_OMEGA_PROVENANCE =
  'OMEGA_DETERMINISTIC_GLOBAL_RECONSTRUCTION_KNOWLEDGE_BASE' as const

export const LOGRES_OMEGA_ID =
  'cdc36fbb3660a499ed3fc3e699ad3eba6905d3d0329e8659596dbe57bacfb642' as const

export const LOGRES_OMEGA_DATABASE =
  Object.freeze({
    path:
      '/home/ubuntu/logres/artifacts/global-reconstruction-omega-20260924.sqlite',
    sha256:
      '90f52bd8906aea0043188838b2f742957b00105822115fa0629f3aa8785a85a6',
    bytes: 168542208,
  } as const)

export const LOGRES_OMEGA_MANIFEST =
  Object.freeze({
    path:
      '/home/ubuntu/logres/artifacts/global-reconstruction-omega-20260924.json',
    sha256:
      'ff5d6cc0114e561dab4402536cae82f95e1d50d310f2a3e37efdc1302752838e',
  } as const)

export const LOGRES_OMEGA_SOURCE_IDENTITIES =
  Object.freeze({
    repoSha:
      '4653c15b08626a92f10f2fbfa23115c69e2adbfa',
    closureId:
      'e81e108db86433948da94a1f80e66b43e7f0d696f9ef8051b7d0a2cd66c4b8a9',
    closureFactsSha256:
      'bec04a87dfedd20202653f3d01e0a4ae1e68fa906c287d9e3dd63d95dc93c9bf',
    compilerRunId:
      'c9385e14fb819d308880480e19b71546c7f9e5644b0eed8d2fddd7ad9d1a6b39',
    consistencyCertificateId:
      '5d9e3592e3f27fc4469cc123f94a2d4bf2e311988c900b532505b4521e1a1c7b',
  } as const)

export const LOGRES_OMEGA_PROVENANCE_GRADES =
  Object.freeze([
    'GLOBAL_DIRECT',
    'GLOBAL_BINARY_DERIVED',
    'GLOBAL_JP_IDENTICAL',
    'SAME_ERA_JP_CORROBORATED',
    'JP_LINEAGE_SUPPORTED',
    'IMPLEMENTATION_VERIFIED',
    'EXTERNAL_CEILING',
  ] as const)

export const LOGRES_OMEGA_GRADE_COUNTS =
  Object.freeze({
    GLOBAL_DIRECT: 1162,
    GLOBAL_BINARY_DERIVED: 23282,
    GLOBAL_JP_IDENTICAL: 15,
    SAME_ERA_JP_CORROBORATED: 0,
    JP_LINEAGE_SUPPORTED: 2131,
    IMPLEMENTATION_VERIFIED: 1166,
    EXTERNAL_CEILING: 9,
  } as const)

export const LOGRES_OMEGA_TABLE_COUNTS =
  Object.freeze({
    artifacts: 146,
    claims: 27765,
    claimHeads: 27765,
    claimEvidence: 80635,
    functionSemantics: 16379,
    protocolMessages: 631,
    resourceNodes: 44455,
    resourceEdges: 95477,
    maps: 2118,
    stateTransitions: 28,
    behaviorRules: 11,
    implementationLinks: 2160,
    reconstructionPackets: 12,
    contradictions: 15,
    consistencyInvariants: 21,
    externalCeilings: 9,
  } as const)

export const LOGRES_OMEGA_INTEGRITY =
  Object.freeze({
    missingClaimEvidence: 0,
    sameAuthorityConflictsInClaimHeads: 0,
    failedConsistencyInvariants: 0,
    consistencyStatus: 'PASS',
    consistencyPassed: 21,
    consistencyTotal: 21,
  } as const)

export const LOGRES_OMEGA_CONTRADICTION_STATUS =
  Object.freeze({
    resolvedByAuthority: 6,
    unresolvedLowAuthority: 8,
    unresolvedSameAuthorityTie: 1,
    unresolvedTaskCount: 9,
    quarantinedSameAuthorityTask: 'G17-TUT-001',
    quarantinedSameAuthorityGrade: 'GLOBAL_BINARY_DERIVED',
    automaticWinnerSelected: false,
  } as const)

export const LOGRES_OMEGA_POLICIES =
  Object.freeze([
    'Global 3.0.24 remains historical authority; current JP is lineage/reference unless an explicit identity predicate exists.',
    'Every material claim has at least one exact evidence path and SHA-256.',
    'A second differing payload at the same claim key, provenance grade and version scope aborts the database build instead of coexisting.',
    'IMPLEMENTATION_VERIFIED claims bind to exact current source/test file SHA-256 values and do not promote historical truth.',
    'External evidence ceilings are terminal constraints and are not fabricated into missing historical facts.',
    'Same-authority unresolved arbiter ties are quarantined outside authoritative claim heads.',
  ] as const)

export const LOGRES_OMEGA_CREATES_NEW_HISTORICAL_FACTS = false as const
export const LOGRES_OMEGA_CLAIMS_RETIRED_SERVER_INTERNALS = false as const
