export const LOGRES_RECONSTRUCTION_CLOSURE_PROVENANCE =
  'OMEGA_EXHAUSTIVE_RECONSTRUCTION_CLOSURE_WITH_TERMINAL_CEILINGS' as const

export const LOGRES_RECONSTRUCTION_CLOSURE_ID =
  'e81e108db86433948da94a1f80e66b43e7f0d696f9ef8051b7d0a2cd66c4b8a9' as const

export const LOGRES_RECONSTRUCTION_CLOSURE_ARTIFACT_SHA256 =
  'dbfda735f3c6820dbd9956b6e2d3fca36bc642f4091a0067187d62cfbdaecda2' as const

export const LOGRES_RECONSTRUCTION_CLOSURE_FACTS_SHA256 =
  'bec04a87dfedd20202653f3d01e0a4ae1e68fa906c287d9e3dd63d95dc93c9bf' as const

export const LOGRES_RECONSTRUCTION_CLOSURE_COUNTS =
  Object.freeze({
    factsTotal: 26584,

    lfsClasses: 2372,
    lfsMethods: 19467,
    protocolMessages: 631,
    protocolConstructorTypes: 533,

    globalResources: 41,
    globalPackageMembers: 461,
    globalNativeResourcePatterns: 910,
    globalMapPackages: 1,

    changedResourceLineageCandidates: 15,
    currentJpMapLineageReferences: 2116,

    criticalStateTransitions: 28,
    externalEvidenceCeilings: 9,

    covered: 1038,
    evidenceKnownNotImplemented: 23406,
    implementationWithWeakerEvidence: 25,
    externallyUnrecoverable: 9,
    unresolved: 2106,

    boundedResearchCandidates: 3,
  } as const)

export const LOGRES_RECONSTRUCTION_CLOSURE_DOMAIN_COVERAGE =
  Object.freeze({
    lfsClass: Object.freeze({
      covered: 216,
      evidenceKnownNotImplemented: 2156,
    }),
    lfsMethod: Object.freeze({
      covered: 543,
      evidenceKnownNotImplemented: 18924,
    }),
    protocolMessage: Object.freeze({
      covered: 116,
      evidenceKnownNotImplemented: 515,
    }),
    protocolConstructorType: Object.freeze({
      covered: 41,
      evidenceKnownNotImplemented: 492,
    }),
    globalResource: Object.freeze({
      covered: 26,
      evidenceKnownNotImplemented: 15,
    }),
    globalPackageMember: Object.freeze({
      covered: 65,
      evidenceKnownNotImplemented: 396,
    }),
    globalNativeResourcePattern: Object.freeze({
      covered: 7,
      evidenceKnownNotImplemented: 903,
    }),
    globalMapPackage: Object.freeze({
      covered: 1,
      evidenceKnownNotImplemented: 0,
    }),
    criticalStateTransition: Object.freeze({
      covered: 23,
      evidenceKnownNotImplemented: 5,
    }),
    changedResourceLineageCandidate: Object.freeze({
      implementationWithWeakerEvidence: 14,
      unresolved: 1,
    }),
    currentJpMapLineageReference: Object.freeze({
      implementationWithWeakerEvidence: 11,
      unresolved: 2105,
    }),
    externalEvidenceCeiling: Object.freeze({
      externallyUnrecoverable: 9,
    }),
  } as const)

export const LOGRES_RECONSTRUCTION_CLOSURE_GAPS =
  Object.freeze([
    Object.freeze({
      key: 'native-semantic-unresolved',
      status: 'RESEARCHABLE_BOUNDED',
      count: 3406,
      suggestedTask: 'GAP-NATIVE-SEMANTICS-001',
    }),
    Object.freeze({
      key: 'critical-transition-function-binding',
      status: 'RESEARCHABLE_BOUNDED',
      count: 22,
      suggestedTask: 'GAP-CRITICAL-TRANSITION-BINDING-001',
    }),
    Object.freeze({
      key: 'native-resource-pattern-binding',
      status: 'RESEARCHABLE_BOUNDED',
      count: 409,
      suggestedTask: 'GAP-NATIVE-RESOURCE-BINDING-001',
    }),
    Object.freeze({
      key: 'historical-runtime-server-and-remote-assets',
      status: 'TERMINAL_EXTERNAL_CEILING',
      count: 9,
      suggestedTask: null,
    }),
  ] as const)

export const LOGRES_RECONSTRUCTION_CLOSURE_POLICY =
  Object.freeze([
    'Only non-reverse src files count as gameplay implementation; evidence modules cannot self-satisfy implementation coverage.',
    'Tests are cross-linked independently from gameplay implementation.',
    'Direct Global static and client facts retain Global authority even when behavior semantics are incomplete.',
    'Current-JP-only maps and changed resources remain weaker lineage references and never backfill Global.',
    'Package-member coverage requires the member entry itself; a package-level reference does not cover every member.',
    'Critical-transition coverage requires the exact Global message or a directly bound Global function; generic action or trigger prose does not count.',
    'Documented external evidence ceilings are terminal facts and generate no research children.',
    'At most one advisory research candidate is emitted per canonical gap; AUTO-RE and UNBLOCK parents are forbidden.',
    'Closure emits no automatic task creation, merge or deployment action.',
  ] as const)

export const LOGRES_RECONSTRUCTION_CLOSURE_ARTIFACT =
  '/home/ubuntu/logres/artifacts/global-reconstruction-closure-20260924.json' as const
