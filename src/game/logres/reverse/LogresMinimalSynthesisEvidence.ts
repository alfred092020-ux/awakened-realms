export const LOGRES_MINIMAL_SYNTHESIS_PROVENANCE =
  'ZENITH_EVIDENCE_SUFFICIENT_MINIMAL_RECONSTRUCTION_SYNTHESIS' as const

export const LOGRES_MINIMAL_SYNTHESIS_ARTIFACT = Object.freeze({
  path: '/home/ubuntu/logres/artifacts/minimal-reconstruction-delta-20260924.json',
  sha256: '8d6099551b1ea9cb89b9c16ad256ab00c90b6de1dd8ecb2a480632152b8aa2c6',
} as const)

export const LOGRES_MINIMAL_SYNTHESIS_RESULT = Object.freeze({
  status: 'ZERO_DELTA_ALREADY_SATISFIED',
  packetId: 'DIFF-FIX-BATTLE-ENTRY-BOUNDARY',
  classification: 'IMPLEMENTATION_BUG',
  deltaFileCount: 0,
  filesToModify: Object.freeze([] as const),
  patchApplied: false,
  commitCreated: false,
  mergePerformed: false,
  deploymentPerformed: false,
} as const)

export const LOGRES_MINIMAL_SYNTHESIS_EVIDENCE = Object.freeze({
  certifiedDifferential: Object.freeze({
    sha256:
      '0036c1187769a5c8935ee61dc1fa5e70dd6f0b6ea84315e70a362e0f8ae0667e',
    implementationBugIds: Object.freeze([
      'battle-entry-retry-gate-enforcement',
      'playable-field-battle-entry-wiring',
    ]),
  }),
  currentDifferential: Object.freeze({
    sha256:
      '90d5760bfb6a3769091c236d5bd36eaad55dc7eb0a93ea56662aaf46104d8f99',
    implementationBugIds: Object.freeze([] as const),
    implementationPacketIds: Object.freeze([] as const),
    classifications: Object.freeze({
      PASS: 7,
      INTENTIONAL_SERVER_STUB: 1,
      UNKNOWN: 1,
    }),
  }),
  truthKernel: Object.freeze({
    sha256:
      'a1fcf7892495bca833db638e10c8e392146d8ebb63c73102d6a37b44461b304c',
    truthKernelId:
      '51fd7b3d64d8fc51b1af04e4020cc7489cdfe2265f35b6657389d0bbd4c4de60',
    status: 'RESOLVED',
    claims: 27765,
  }),
  consistencyCertificate: Object.freeze({
    sha256:
      'd56247dd661f6aca6619bbda703a2f1ae2b71c319c1a48ade99a1c6564eb34a8',
    certificateId:
      '5d9e3592e3f27fc4469cc123f94a2d4bf2e311988c900b532505b4521e1a1c7b',
    status: 'PASS',
    passed: 21,
    failed: 0,
  }),
  traceCertificate: Object.freeze({
    sha256:
      '64219a3efc09dfa6424ed78a1711fea8f7f1c7dfe12122089f025d1aec94260f',
    certificateId:
      '45afc19df46b72790189bad00d0decb0e90d884297bee85446b929c393958731',
    offlineOnly: true,
  }),
} as const)

export const LOGRES_MINIMAL_SYNTHESIS_SCOPE = Object.freeze({
  certifiedPacketScope: Object.freeze([
    'src/game/logres/field/controllers/LogresFieldEncounterController.ts',
    'src/game/logres/encounter/ReconstructedLogresEncounterAuthority.ts',
  ]),
  currentSourceHashes: Object.freeze({
    fieldEncounterController:
      '784b22113632f60d06cf003222d953412407d0ca4b34ed6c8899babd18a61c33',
    encounterAuthority:
      '38187b94f858d6c32ab3e930a485f7fbf7263c9412597390a91d5918417d6068',
  }),
  targetedTests: Object.freeze([
    Object.freeze({
      path: 'tests/ReconstructedLogresEncounterAuthority.test.ts',
      sha256:
        'b45476a678266ab9b5c6ac52c12de625b9b63a9a027558f0eb1afd8247135e9d',
    }),
    Object.freeze({
      path: 'tests/ReconstructedLogresBattleEntryBridge.test.ts',
      sha256:
        'ae1e529d52d9f74497e8be8793aa57e147ba1b7dbe9d0e89da27348f66e1b67b',
    }),
    Object.freeze({
      path: 'tests/LogresGlobalDifferentialEvidence.test.ts',
      sha256:
        'b4d7541bb3e0aa79e43aedef1ac46d782310c1dfdd11e6808af978c080200b5f',
    }),
  ]),
} as const)

export const LOGRES_MINIMAL_SYNTHESIS_PREDICATES = Object.freeze({
  certifiedGapExists: true,
  activeGapExists: false,
  truthKernelResolved: true,
  consistencyCertificatePass: true,
  traceCertificateOfflineOnly: true,
  currentSourcePredicatesPass: true,
  currentImplementationPacketPresent: false,
  currentImplementationBugCount: 0,
  sourcePredicates: Object.freeze([
    'field-controller-requests-entry',
    'field-controller-records-entry-response',
    'field-controller-records-battle-initialized-after-response',
    'field-controller-explicit-server-authority-stub',
    'authority-uses-exact-retry-seconds',
    'authority-rejects-preelapsed-retry',
    'authority-sets-entry-accepted',
    'field-controller-boundary-order',
  ]),
} as const)

export const LOGRES_MINIMAL_SYNTHESIS_ACCEPTANCE = Object.freeze([
  'Playable field must not initialize battle immediately after requestEntry().',
  'Response code 1 must set entryAccepted before battle initialization.',
  'Response code 2 must block another entry request until exactly 1.0 second elapses.',
  'No retired-server payload or response outcome may be invented; use an explicit reconstructed/server stub at the boundary.',
] as const)

export const LOGRES_MINIMAL_SYNTHESIS_ROLLBACK = Object.freeze({
  invalidateIfAny: Object.freeze([
    'current differential contains implementation packet DIFF-FIX-BATTLE-ENTRY-BOUNDARY',
    'current differential contains any IMPLEMENTATION_BUG for the bounded encounter/battle-entry gap',
    'any source predicate in source_predicates becomes false',
    'truth kernel no longer reports read_only=true and status=RESOLVED',
    'consistency certificate no longer reports PASS with zero failed invariants',
    'any targeted verification test hash changes without regenerating this synthesis',
  ]),
  verificationCommand:
    'npx vitest run tests/ReconstructedLogresEncounterAuthority.test.ts tests/ReconstructedLogresBattleEntryBridge.test.ts tests/LogresGlobalDifferentialEvidence.test.ts',
  differentialRegenerationCommand:
    'python3 scripts/logres/run_global_differential_emulator.py --repo . --output <current-differential.json>',
} as const)

export const LOGRES_MINIMAL_SYNTHESIS_AUTHORITY_POLICY = Object.freeze({
  currentJpMayAuthorizeHistoricalGlobalPatch: false,
  retiredServerSemanticsMayBeInvented: false,
  unknownServerSemanticsRemainUnknown: true,
  intentionalServerStubIsNotImplementationBug: true,
} as const)
