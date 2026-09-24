export const LOGRES_GALAXY_REPRO_CAPSULE_PROVENANCE =
  'GALAXY_RECONSTRUCTION_REPRODUCIBILITY_CAPSULE' as const

export const LOGRES_GALAXY_REPRO_CAPSULE_ID =
  'afb8592fae539e91f755b081ab4816cc8073b302d831da0dfa7fee14e6f6658e' as const

export const LOGRES_GALAXY_REPRO_CANONICAL_SHA =
  'b21c418f754f350fdb3b796e332b547a8497ae05' as const

export const LOGRES_GALAXY_REPRO_MERKLE_ROOT =
  '919c08eb67a5e5b280ae685429e035cb405704439f9c3b00d7a92f235906c94c' as const

export const LOGRES_GALAXY_REPRO_PACKAGE_LOCK_SHA256 =
  '6b2d72ec6627663656545081d3b116bcbb87b471bcd807a44a6bf21080ad5ec2' as const

export const LOGRES_GALAXY_REPRO_COUNTS =
  Object.freeze({
    toolRecords: 11,
    canonicalTools: 10,
    workerRefTools: 1,
    replayRecipes: 11,
    sealedInputLeavesVerified: 30,
    sealedInputDrift: 0,
  } as const)

export const LOGRES_GALAXY_REPRO_ENVIRONMENT =
  Object.freeze({
    node: 'v24.21.0',
    npm: '11.19.0',
    python: 'Python 3.12.3',
    git: 'git version 2.43.0',
  } as const)

export const LOGRES_GALAXY_REPRO_POLICY =
  Object.freeze([
    'Private APK and asset bytes remain local and are referenced only by Merkle-sealed path and hash metadata.',
    'A generator not yet integrated into canonical is pinned to an exact verified worker commit and content hash.',
    'Capsule identity changes with canonical SHA, Merkle root, package-lock, environment versions, tool hashes or replay recipes.',
    'Reproducibility authenticates computation; it does not elevate the historical confidence of reproduced evidence.',
  ] as const)

export const LOGRES_GALAXY_REPRO_CAPSULE_ARTIFACT =
  '/home/ubuntu/logres/artifacts/logres-galaxy-repro-capsule-20260924.json' as const
