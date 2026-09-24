export const LOGRES_GLOBAL_JP_RESOURCE_GENEALOGY_PROVENANCE =
  'GLOBAL_AUTHORITY_WITH_CURRENT_JP_PUBLIC_MANIFEST_LINEAGE' as const

export const LOGRES_GLOBAL_JP_RESOURCE_GENEALOGY_COUNTS =
  Object.freeze({
    jpManifestRecords: 31241,
    globalBootstrapRecords: 27,
    recoveredGlobalCacheRecords: 14,
    combinedGlobalEvidenceRecords: 41,
    exactBytesSamePath: 9,
    exactBytesRenamedOrMoved: 5,
    samePathChangedBytes: 15,
    globalOnlyRecovered: 12,
    exactIdentityEdges: 14,
    jpExactGlobalLineage: 14,
    jpSamePathChangedLineage: 15,
    jpOnlyOrUncorroborated: 31212,
  } as const)

export const LOGRES_GLOBAL_JP_EXACT_BOOTSTRAP_CONTINUITY =
  Object.freeze([
    'graphicSettings/texture.mbn',
    'gui/characreate/slice.mbn',
    'gui.mbn',
    'gui/splash.mbn',
    'gui/system/indicator.mbn',
    'gui/title/patchCharacter.mbn',
    'gui/title/patchCharacter/png.mbn',
    'motion/settings.mbn',
    'sound/se/100_000_00001.wav',
  ] as const)

export const LOGRES_GLOBAL_JP_HIGH_VALUE_MOVED_CONTINUITY =
  Object.freeze({
    battlePresentation: Object.freeze({
      globalPath: 'Battle.mbn',
      jpPath: 'gui/Battle.mbn',
      sha1: 'd736f311f3b557e22c55e4dd58022b1fd6dcf412',
      size: 570181,
    } as const),
    mapInfo: Object.freeze({
      globalPath: 'info.mbn',
      jpPath: 'map/info.mbn',
      sha1: 'e0e791dd462cd82a0bedfa0967e981205ca91540',
      size: 674154,
    } as const),
    millenniumTreeCandidate: Object.freeze({
      globalPath: 'map-002/002_000_00001.mbn',
      jpPath: 'map/002_000_00001.mbn',
      sha1: 'f8f2eb52e5743a516e3329549205e131ba71a1f4',
      size: 435405,
    } as const),
    tutorialUi: Object.freeze({
      globalPath: 'tutorial.mbn',
      jpPath: 'gui/tutorial.mbn',
      sha1: '47345bb5ad21b523f4f04e285710bbdae270a2f9',
      size: 194508,
    } as const),
    bgmRenumbering: Object.freeze({
      globalPath: 'sound/bgm/000_000_00001.ogg',
      jpPath: 'sound/bgm/000_000_00002.ogg',
      sha1: '3eb17ae902c7362ae832e901cf6ac18cf581e2bd',
      size: 935714,
    } as const),
  } as const)

export const LOGRES_GLOBAL_JP_RESOURCE_LINEAGE_POLICY =
  Object.freeze({
    GLOBAL_JP_IDENTICAL:
      'Manifest SHA-1 and size identity proves resource-byte continuity only; it does not prove unchanged surrounding gameplay or server semantics.',
    PATH_CONTINUITY_BYTES_CHANGED:
      'The resource path survives but bytes differ. Timestamp ordering is a lineage hint only.',
    JP_ONLY_OR_UNCORROBORATED:
      'No recovered Global predicate links the JP resource; historical Global presence must not be inferred.',
    EXTERNAL_CEILING:
      'Global remote patch resources absent from recovered bootstrap/cache require independent archival evidence.',
  } as const)

export const LOGRES_GLOBAL_JP_RESOURCE_GENEALOGY_ARTIFACT =
  '/home/ubuntu/logres/artifacts/global-jp-resource-genealogy-20260924.json' as const

export const LOGRES_GLOBAL_JP_RELEASE_MANIFEST =
  Object.freeze({
    generation: '1790230588',
    recordCount: 31241,
    filelistSha256:
      'f502426e907891a5066662131c400cc24b8464ed1b5e45d762afe05913179d2b',
  } as const)
