export const LOGRES_GALAXY_EVIDENCE_SEAL_PROVENANCE =
  'GALAXY_CRYPTOGRAPHIC_EVIDENCE_SEAL' as const

export const LOGRES_GALAXY_EVIDENCE_MERKLE_ROOT =
  '919c08eb67a5e5b280ae685429e035cb405704439f9c3b00d7a92f235906c94c' as const

export const LOGRES_GALAXY_EVIDENCE_CANONICAL_SHA =
  'b21c418f754f350fdb3b796e332b547a8497ae05' as const

export const LOGRES_GALAXY_EVIDENCE_SEAL_COUNTS =
  Object.freeze({
    authoritativeArtifacts: 12,
    declaredSources: 17,
    specialLeaves: 1,
    totalLeaves: 30,
    merkleLevels: 6,
    declarationConflicts: 0,
    missingPaths: 0,
    stalePaths: 0,
  } as const)

export const LOGRES_GALAXY_EVIDENCE_SEAL_ALGORITHM =
  Object.freeze({
    hash: 'SHA-256',
    leaf: "SHA256('leaf\\0' || canonical-json)",
    node: "SHA256('node\\0' || left-bytes || right-bytes)",
    ordering: 'kind,path,sha256 ascending',
    oddLevelRule: 'duplicate final hash',
  } as const)

export const LOGRES_GALAXY_EVIDENCE_SEAL_POLICY =
  Object.freeze([
    'Private and local evidence bytes are not copied into the repository; only their path, SHA-256, provenance and owning-artifact metadata are sealed.',
    'Relative resource identities embedded inside genealogy artifacts are not misclassified as filesystem source paths.',
    'Any changed sealed artifact, declared source or canonical repo SHA changes at least one leaf and therefore the Merkle root.',
    'The seal authenticates the evidence universe used by reconstruction; it does not strengthen the historical authority of any leaf.',
  ] as const)

export const LOGRES_GALAXY_EVIDENCE_SEAL_ARTIFACT =
  '/home/ubuntu/logres/artifacts/logres-galaxy-evidence-merkle-20260924.json' as const
