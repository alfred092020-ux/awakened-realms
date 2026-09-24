export const LOGRES_CONTRADICTION_ARBITER_PROVENANCE =
  'DETERMINISTIC_ARBITRATION_OVER_EXISTING_PROVENANCE_GRAPH' as const

export const LOGRES_CONTRADICTION_ARBITER_COUNTS =
  Object.freeze({
    explicitConflictTasks: 15,
    resolvedByAuthority: 6,
    unresolvedLowAuthority: 8,
    unresolvedSameAuthorityTie: 1,
    unresolvedTasks: 9,
    artifactHashesSnapshotted: 6,
  } as const)

export const LOGRES_CONTRADICTION_AUTHORITY_ORDER =
  Object.freeze([
    'GLOBAL_DIRECT',
    'GLOBAL_BINARY_DERIVED',
    'GLOBAL_JP_IDENTICAL',
    'SAME_ERA_JP_CORROBORATED',
    'JP_LINEAGE_SUPPORTED',
    'IMPLEMENTATION_VERIFIED',
    'SPECULATION_OR_UNRESOLVED',
  ] as const)

export const LOGRES_CONTRADICTION_ARBITER_GUARDRAILS =
  Object.freeze([
    'Arbitration creates no new historical facts.',
    'Only explicit Brain EVIDENCE_CONFLICT tasks are auto-arbitrated.',
    'External evidence ceilings are preserved as constraints rather than factual rivals.',
    'Same-authority disagreement remains unresolved unless the claims are equivalent by artifact hash and normalized summary.',
    'Claims from different tasks are not collapsed merely because their labels look similar; version/time/scope boundaries remain intact.',
    'Speculation or unresolved evidence can never win merely because it is the only claim.',
  ] as const)

export const LOGRES_CONTRADICTION_RESOLVED_EXAMPLES =
  Object.freeze({
    globalStateMachine: Object.freeze({
      taskId: 'GJP-STATE-MACHINE-001',
      result: 'RESOLVED_BY_AUTHORITY',
      winningAuthority: 'GLOBAL_DIRECT',
      winningClaim:
        'Global 3.0.24 critical state machine recovered from original Global code',
    } as const),
  } as const)

export const LOGRES_CONTRADICTION_UNRESOLVED_EXAMPLES =
  Object.freeze({
    millenniumTreeVideoTie: Object.freeze({
      taskId: 'G17-TUT-001',
      result: 'UNRESOLVED_SAME_AUTHORITY_TIE',
      authority: 'GLOBAL_BINARY_DERIVED',
      reason:
        'Two highest-authority Global video claims disagree, so no automatic winner is permitted.',
    } as const),
    androidVisualQa: Object.freeze({
      taskId: 'ANDROID-VISUAL-QA-001',
      result: 'UNRESOLVED_LOW_AUTHORITY',
      reason:
        'No claim rises above speculation/unresolved authority.',
    } as const),
  } as const)

export const LOGRES_CONTRADICTION_ARBITER_ARTIFACT =
  '/home/ubuntu/logres/artifacts/global-contradiction-arbiter-20260924.json' as const
