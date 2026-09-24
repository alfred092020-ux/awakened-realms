export const LOGRES_GLOBAL_JP_RESOURCE_SEMANTIC_GRAPH_PROVENANCE =
  'OMEGA_SEMANTIC_RESOURCE_GRAPH_WITH_EXPLICIT_EDGE_AUTHORITY' as const

export const LOGRES_GLOBAL_JP_RESOURCE_SEMANTIC_GRAPH_COUNTS =
  Object.freeze({
    nodes: 44455,
    edges: 95477,
    systems: 38,
    resources: 31282,
    maps: 1263,
    packageMembers: 2987,
    logicalResourceIds: 7812,
    nativeResourcePatterns: 910,
    nativeResourcePathLiterals: 911,
    originalSourcePaths: 139,
    exactBytesLineageEdges: 14,
    samePathChangedLineageEdges: 15,
    mapChipAtlasEdges: 1263,
    mapObjectAtlasEdges: 1263,
    packageMembershipEdges: 2987,
    systemClassificationEdges: 66506,
  } as const)

export const LOGRES_GLOBAL_JP_RESOURCE_SYSTEM_COUNTS =
  Object.freeze({
    battle: 2026,
    field: 2773,
    onboarding: 350,
    avatar: 3873,
    quest: 726,
    audio: 454,
  } as const)

export const LOGRES_GLOBAL_JP_RESOURCE_GRAPH_CRITICAL_EDGES =
  Object.freeze({
    millenniumTree: Object.freeze({
      source: 'resource:global-cache:map-002/002_000_00001.mbn',
      relation: 'EXACT_BYTES_LINEAGE',
      target: 'resource:jp-current:map/002_000_00001.mbn',
      sha1: 'f8f2eb52e5743a516e3329549205e131ba71a1f4',
      size: 435405,
      provenance: 'GLOBAL_JP_IDENTICAL_MANIFEST_HASH_AND_SIZE',
    } as const),
    bgmRenumbering: Object.freeze({
      source: 'resource:global-bootstrap:sound/bgm/000_000_00001.ogg',
      relation: 'EXACT_BYTES_LINEAGE',
      target: 'resource:jp-current:sound/bgm/000_000_00002.ogg',
      sha1: '3eb17ae902c7362ae832e901cf6ac18cf581e2bd',
      size: 935714,
      provenance: 'GLOBAL_JP_IDENTICAL_MANIFEST_HASH_AND_SIZE',
    } as const),
  } as const)

export const LOGRES_GLOBAL_JP_RESOURCE_GRAPH_POLICY =
  Object.freeze({
    exactBytes:
      'Exact resource identity is a byte-continuity claim only and does not upgrade surrounding gameplay or server semantics.',
    pathChanged:
      'Same-path changed bytes are ancestry evidence, not identity.',
    nativeReference:
      'A Global native resource literal proves that the client references a path or pattern, not ownership by a specific function.',
    systemTaxonomy:
      'Semantic system labels are deterministic query taxonomy and do not upgrade historical behavior confidence.',
    jpOnly:
      'JP-only resources remain current-JP facts unless an independent Global predicate establishes historical presence.',
  } as const)

export const LOGRES_GLOBAL_JP_RESOURCE_SEMANTIC_GRAPH_ARTIFACT =
  Object.freeze({
    path: '/home/ubuntu/logres/artifacts/global-jp-resource-semantic-graph-20260924.json',
    sha256: 'fdd4921dbab864840c1106a5ff2196da2c57b29a5517eca0e4a603a1e1f25ab3',
  } as const)
