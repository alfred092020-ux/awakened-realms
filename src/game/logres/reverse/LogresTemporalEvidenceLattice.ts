export const LOGRES_HYPERDIMENSION_TEMPORAL_PROVENANCE =
  'HYPERDIMENSION_VERSION_SCOPED_TEMPORAL_EVIDENCE_LATTICE' as const

export const LOGRES_HYPERDIMENSION_TEMPORAL_LATTICE_ID =
  '9b60a149f4e8219fc12ea800147fc30fa0b9a92571cd45c88490277261e37380' as const

export const LOGRES_HYPERDIMENSION_TEMPORAL_COUNTS =
  Object.freeze({
    entities: 673,
    protocolMessages: 631,
    resources: 41,
    mapPackages: 1,
    endpointIdenticalEntities: 377,
    changedOrMissingEndpointEntities: 285,
    comparisonIncompleteEntities: 11,
    unobservedIntermediateHistoryEntities: 673,
    identicalProtocolEndpoints: 367,
    changedProtocolSchemaEndpoints: 92,
    globalProtocolAbsentOrRenamedAtJpEndpoint: 161,
    exactSamePathResources: 9,
    exactMovedResources: 5,
    changedSamePathResources: 15,
    globalResourcesWithoutJpMatch: 12,
    identicalMapEndpoints: 1,
  } as const)

export const LOGRES_HYPERDIMENSION_SNAPSHOTS =
  Object.freeze({
    global: Object.freeze({
      id: 'GLOBAL_3_0_24_2017_05_25',
      version: '3.0.24',
      date: '2017-05-25',
      authority: 'HISTORICAL_TARGET',
    } as const),
    currentJp: Object.freeze({
      id: 'CURRENT_JP_2026_09_24',
      version: 'current-jp-capture',
      date: '2026-09-24',
      authority: 'LINEAGE_REFERENCE_ONLY',
    } as const),
  } as const)

export const LOGRES_HYPERDIMENSION_TEMPORAL_RELATIONS =
  Object.freeze([
    'ENDPOINTS_IDENTICAL_OPCODE_AND_SCHEMA',
    'ENDPOINTS_OPCODE_STABLE_SCHEMA_CHANGED',
    'ENDPOINTS_OPCODE_STABLE_JP_COMPARISON_INCOMPLETE',
    'GLOBAL_PRESENT_CURRENT_JP_ABSENT_OR_RENAMED',
    'ENDPOINTS_BYTES_IDENTICAL_SAME_PATH',
    'ENDPOINTS_BYTES_IDENTICAL_PATH_CHANGED',
    'ENDPOINTS_SAME_PATH_BYTES_CHANGED',
    'GLOBAL_RECOVERED_NO_CURRENT_JP_MATCH',
    'ENDPOINTS_MAP_PACKAGE_AND_STRUCTURE_IDENTICAL',
  ] as const)

export const LOGRES_HYPERDIMENSION_TEMPORAL_POLICY =
  Object.freeze([
    'Equal endpoint bytes, opcodes or schemas prove endpoint identity only; they do not prove continuous unchanged history between 2017 and 2026.',
    'When endpoints differ, the exact change date or version remains unknown unless a dated intermediate snapshot independently narrows it.',
    'Current JP is a lineage reference and never backfills a missing Global fact.',
    'No current-JP name or path match is not automatically interpreted as deletion; rename, move or replacement may remain unresolved.',
  ] as const)

export const LOGRES_HYPERDIMENSION_TEMPORAL_ARTIFACT =
  '/home/ubuntu/logres/artifacts/logres-hyperdimension-temporal-lattice-20260924.json' as const
