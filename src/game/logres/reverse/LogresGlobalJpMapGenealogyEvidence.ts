export const LOGRES_GLOBAL_JP_MAP_GENEALOGY_PROVENANCE =
  'GLOBAL_AUTHORITY_WITH_CURRENT_JP_BYTE_AND_STRUCTURE_LINEAGE' as const

export const LOGRES_GLOBAL_JP_MAP_GENEALOGY_SOURCE =
  Object.freeze({
    currentJpPatchGeneration: '1790230588',
    currentJpPatchRecordCount: 31241,
    currentJpMapManifestRecords: 2116,
    currentJpFilelistSha256:
      'f502426e907891a5066662131c400cc24b8464ed1b5e45d762afe05913179d2b',
    genealogyArtifactSha256:
      'dbec39a300071ef2f8b30710948fd34de5bb52f010b6d6b05fad13e342dd13a9',
  } as const)

export const LOGRES_GLOBAL_JP_MAP_INVENTORY =
  Object.freeze({
    jpMapRelatedPackages: 2116,
    categories: Object.freeze({
      terrain: 1263,
      object: 569,
      background: 222,
      clanRoom: 54,
      other: 8,
    } as const),
    terrainVariants: Object.freeze({
      base: 738,
      ans: 525,
    } as const),
    recoveredGlobalTerrainPackages: 1,
  } as const)

export const LOGRES_GLOBAL_JP_MAP_CLUSTER_COUNTS =
  Object.freeze({
    exactMapPayloadReuse: Object.freeze({
      groups: 525,
      members: 1050,
      largestGroup: 2,
    } as const),
    structuralReuse: Object.freeze({
      groups: 509,
      members: 1060,
      largestGroup: 10,
    } as const),
    baseAtlasReuse: Object.freeze({
      groups: 21,
      members: 44,
      largestGroup: 3,
    } as const),
  } as const)

export const LOGRES_GLOBAL_JP_MILLENNIUM_TREE_MAP =
  Object.freeze({
    globalCandidate: '002_000_00001',
    globalPackageSha256:
      'ff0cd4ba4e84af9586c4921147fb463a70bd4f822ea10b456eea8eb5ea3a444c',
    mapPayloadSha256:
      'a2ce7b5cc5f45e6063c0e02bee3bd8d7ff8a063a20b8173b05814ad61c89c9f1',
    structureFingerprint:
      '68b153ab61f9c049025e3049191ee7247e82ce5db261113fede2985a698a62cd',
    lineageGrade: 'GLOBAL_JP_IDENTICAL',
    currentJpBaseByteIdentical: true,
    currentJpAnsGeometryIdentical: true,
    counts: Object.freeze({
      grids: 1380,
      quadTrees: 62,
      chips: 3363,
      objects: 21,
      animatedObjects: 0,
    } as const),
    collision: Object.freeze({
      traversable: 1028,
      prohibition7: 352,
    } as const),
  } as const)

export const LOGRES_GLOBAL_JP_MILLENNIUM_TREE_TEXTURE_AMBIGUITY =
  Object.freeze({
    comparisonCandidate: '002_000_00008',
    comparisonPackageSha256:
      '75ccd816c8aa3d703f8450335db04a65551f017881f33bd4c12bdfed1abec11e',
    comparisonMapPayloadSha256:
      '89f6ebd306148a2e386386fa1ed1e054d641d9f9ef3b8852c3283d04091b9878',
    comparisonStructureFingerprint:
      '5853b5becb1c7fae136d0e6a9a358bbfc05f9545ae5a4e38b169ba1726b24719',
    sameChipAtlasBytes: true,
    sameObjectAtlasBytes: true,
    sameMapPayload: false,
    sameStructureFingerprint: false,
    atlasReuseCluster: Object.freeze([
      '002_000_00001.mbn',
      '002_000_00008.mbn',
      '100_001_00000.mbn',
    ] as const),
    comparisonCounts: Object.freeze({
      grids: 1380,
      quadTrees: 62,
      chips: 3330,
      objects: 21,
      traversable: 987,
      prohibition7: 393,
    } as const),
    conclusion:
      'Texture-only matching cannot uniquely identify the terrain map because 00001, 00008 and 100_001_00000 reuse the same base atlases. 00001 and 00008 have different decompressed map geometry/collision structure.',
  } as const)

export const LOGRES_GLOBAL_JP_MAP_STATIC_GRID_SEMANTICS =
  Object.freeze({
    confirmedFields: Object.freeze([
      'Prohibition',
      'Attribute',
      'PathwayIndex',
      'BorderID',
      'BlendAdjacence',
      'ColorIndex',
    ] as const),
    explicitRegionIdField: false,
    guardrail:
      'The recovered static map schema does not contain a field named RegionID. Attribute, BorderID and PathwayIndex must not be silently renamed to RegionID.',
  } as const)

export const LOGRES_GLOBAL_JP_MAP_CONFIDENCE_POLICY =
  Object.freeze({
    GLOBAL_JP_IDENTICAL:
      'Exact recovered Global and current-JP package bytes match.',
    GLOBAL_GEOMETRY_IDENTICAL:
      'Decompressed .map payload matches while texture encoding or package bytes may differ.',
    JP_LINEAGE_SUPPORTED:
      'Structural fingerprint matches without exact recovered Global byte identity.',
    UNRESOLVED:
      'No identity predicate is sufficient to transfer the current-JP map fact backward.',
  } as const)

export const LOGRES_GLOBAL_JP_MAP_UNRESOLVED =
  Object.freeze([
    'Historical Global human-readable field-name to static terrain MultiID mappings remain server/runtime evidence unless a Global-era payload or table is recovered.',
    'Current-JP-only maps cannot be promoted to historical Global presence without Global-era package, manifest, payload or equivalent primary evidence.',
    'Static map geometry does not itself prove quest state, NPC population, enemy population or dynamic field instance state.',
  ] as const)
