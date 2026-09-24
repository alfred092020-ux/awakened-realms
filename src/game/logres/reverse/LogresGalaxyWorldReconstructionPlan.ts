export const LOGRES_GALAXY_WORLD_PLAN_PROVENANCE =
  'GALAXY_EVIDENCE_RANKED_WORLD_RECONSTRUCTION_PLAN' as const

export const LOGRES_GALAXY_WORLD_PLAN_COUNTS =
  Object.freeze({
    recoveredGlobalMapPackages: 1,
    directGlobalMapIds: 1,
    jpBaseTerrainMaps: 738,
    jpOnlyBaseTerrainMaps: 737,
    jpMapFamilies: 111,
    exactResourceIdentityEdges: 14,
    samePathChangedResourceEdges: 15,
    nativeResourcePatterns: 910,
    nativeExactResourceLinks: 1,
    implementationBatches: 5,
    unsafeBatchIds: 0,
  } as const)

export const LOGRES_GALAXY_WORLD_PLAN_DIRECT_MAPS =
  Object.freeze(['002_000_00001'] as const)

export const LOGRES_GALAXY_WORLD_PLAN_BATCHES =
  Object.freeze([
    Object.freeze({
      id: 'WORLD-BATCH-A-DIRECT-GLOBAL',
      evidenceRank: 4,
      grade: 'GLOBAL_DIRECT_OR_BYTE_IDENTICAL',
      disposition: 'implementation',
    }),
    Object.freeze({
      id: 'WORLD-BATCH-B-EXACT-CONTINUITY',
      evidenceRank: 4,
      grade: 'GLOBAL_JP_IDENTICAL',
      disposition: 'implementation',
    }),
    Object.freeze({
      id: 'WORLD-BATCH-C-CHANGED-CONTINUITY',
      evidenceRank: 3,
      grade: 'GLOBAL_PATH_CONTINUITY_BYTES_CHANGED',
      disposition: 'reconstruct_before_implementation',
    }),
    Object.freeze({
      id: 'WORLD-BATCH-D-NATIVE-PATTERN-BINDINGS',
      evidenceRank: 2,
      grade: 'GLOBAL_NATIVE_PATTERN_ONLY',
      disposition: 'binding_and_evidence',
    }),
    Object.freeze({
      id: 'WORLD-BATCH-E-JP-LINEAGE-RESEARCH',
      evidenceRank: 1,
      grade: 'JP_LINEAGE_CANDIDATE_ONLY',
      disposition: 'research_only',
    }),
  ] as const)

export const LOGRES_GALAXY_WORLD_PLAN_GUARDRAILS =
  Object.freeze([
    'Current-JP-only maps and resources are research candidates, not historical Global facts.',
    'Exact byte identity transfers asset bytes, not server rules or surrounding runtime semantics.',
    'Same-path changed resources require reconstruction or diff evidence before historical implementation.',
    'Native resource patterns prove client content expectations but not every concrete historical resource ID.',
    'External server-side schedules, spawn tables, world-state validation and unrecovered map-name bindings remain evidence ceilings.',
  ] as const)

export const LOGRES_GALAXY_WORLD_PLAN_ARTIFACT =
  '/home/ubuntu/logres/artifacts/logres-galaxy-world-reconstruction-plan-20260924.json' as const
