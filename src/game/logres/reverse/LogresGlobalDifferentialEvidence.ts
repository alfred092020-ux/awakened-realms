export const LOGRES_GLOBAL_DIFFERENTIAL_PROVENANCE =
  'MUIUE_OFFLINE_GLOBAL_VS_RECONSTRUCTION_DIFFERENTIAL' as const

export const LOGRES_GLOBAL_DIFFERENTIAL_ARTIFACT_SHA256 =
  '0036c1187769a5c8935ee61dc1fa5e70dd6f0b6ea84315e70a362e0f8ae0667e' as const

export const LOGRES_GLOBAL_DIFFERENTIAL_COUNTS =
  Object.freeze({
    checks: 9,
    pass: 5,
    implementationBugs: 2,
    intentionalServerStubs: 1,
    unknown: 1,
    divergences: 4,
    fuzzerCasesAvailable: 109,
  } as const)

export const LOGRES_GLOBAL_DIFFERENTIAL_CONFIRMED_PASSES =
  Object.freeze([
    Object.freeze({
      id: 'movement-global-fallback-and-collision',
      domain: 'movement_collision',
      evidenceScore: 1,
      summary:
        'Recovered destination-to-source fallback and diagonal corner-cut rejection match the reconstruction.',
    }),
    Object.freeze({
      id: 'battle-entry-retry-value',
      domain: 'encounter',
      evidenceScore: 1,
      summary:
        'Response code 2 stores the exact recovered 1.0-second retry delay.',
    }),
    Object.freeze({
      id: 'battle-entry-accepted-code',
      domain: 'encounter',
      evidenceScore: 1,
      summary:
        'Response code 1 sets the distinct local entryAccepted state.',
    }),
    Object.freeze({
      id: 'battle-entry-bridge-order',
      domain: 'battle_sequencing',
      evidenceScore: 1,
      summary:
        'The bridge API keeps entry response separate from authoritative battle initialization.',
    }),
    Object.freeze({
      id: 'critical-resource-binding',
      domain: 'resource_bindings',
      evidenceScore: 1,
      summary:
        'Recovered Global field and battle package identities are bound to the vertical-slice evidence graph.',
    }),
  ] as const)

export const LOGRES_GLOBAL_DIFFERENTIAL_IMPLEMENTATION_BUGS =
  Object.freeze([
    Object.freeze({
      id: 'battle-entry-retry-gate-enforcement',
      domain: 'encounter',
      evidenceScore: 1,
      expected:
        'After response code 2, another battle-entry request is blocked until exactly 1.0 second elapses.',
      actual:
        'ReconstructedLogresEncounterAuthority allows createBattleEntryIntent() immediately while retryDelaySeconds is still 1.',
      repairScope:
        'src/game/logres/encounter/ReconstructedLogresEncounterAuthority.ts',
    }),
    Object.freeze({
      id: 'playable-field-battle-entry-wiring',
      domain: 'battle_sequencing',
      evidenceScore: 1,
      expected:
        'C_GMCL_BATTLE_ENTRY_REQ -> response code 1/2 boundary -> S_GMCL_BATTLE_INITIALIZE',
      actual:
        'LogresFieldEncounterController calls requestEntry() and then recordBattleInitialized() without recordEntryResponse().',
      repairScope:
        'src/game/logres/field/controllers/LogresFieldEncounterController.ts',
    }),
  ] as const)

export const LOGRES_GLOBAL_DIFFERENTIAL_NON_BUG_DIVERGENCES =
  Object.freeze([
    Object.freeze({
      id: 'battle-result-reward-field-return-order',
      classification: 'INTENTIONAL_SERVER_STUB',
      evidenceScore: 0.95,
      summary:
        'Result -> reward -> field-return ordering matches, while reward identifiers/content remain reconstruction-local because retired-server payloads are unrecovered.',
    }),
    Object.freeze({
      id: 'reconstruction-local-reward-idempotency',
      classification: 'UNKNOWN',
      evidenceScore: 0.55,
      summary:
        'Local reconstructed reward grants are idempotent, but exact retired-Global reward idempotency semantics are not established.',
    }),
  ] as const)

export const LOGRES_GLOBAL_DIFFERENTIAL_REPAIR_PACKET =
  Object.freeze({
    id: 'DIFF-FIX-BATTLE-ENTRY-BOUNDARY',
    autoApply: false,
    autoMerge: false,
    acceptance: Object.freeze([
      'Playable field must not initialize battle immediately after requestEntry().',
      'Response code 1 must set entryAccepted before battle initialization.',
      'Response code 2 must block another entry request until exactly 1.0 second elapses.',
      'No retired-server payload or outcome may be invented; the boundary must remain an explicit reconstructed/server stub.',
    ]),
  } as const)

export const LOGRES_GLOBAL_DIFFERENTIAL_GUARDRAILS =
  Object.freeze([
    'Differential findings never auto-fix, auto-merge or auto-deploy.',
    'Server-authored payload differences remain intentional stubs or evidence gaps unless Global evidence directly constrains the client behavior.',
    'Presentation differences are not upgraded to gameplay bugs without a behavior/resource predicate.',
    'Unknown retired-server semantics remain UNKNOWN rather than being filled from current JP.',
  ] as const)

export const LOGRES_GLOBAL_DIFFERENTIAL_ARTIFACT =
  '/home/ubuntu/logres/artifacts/global3024-differential-emulator-20260924.json' as const
