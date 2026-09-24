export const LOGRES_MAP_CONTENT_SCHEMA_VERSION =
  'map-content-v1' as const

export type LogresMapContentConfidence =
  | 'CONFIRMED_GLOBAL_3_0_24'
  | 'GLOBAL_JP_IDENTICAL'
  | 'CONFIRMED_CURRENT_JP'
  | 'SUPPORTED_INFERENCE'
  | 'JP_LINEAGE_CANDIDATE_ONLY'
  | 'UNKNOWN'

export const LOGRES_MAP_CONTENT_EVIDENCE =
  Object.freeze({
    mapGenealogy:
      Object.freeze({
        path:
          '/home/ubuntu/logres/artifacts/global-jp-map-genealogy-20260924.json',
        sha256:
          'dbec39a300071ef2f8b30710948fd34de5bb52f010b6d6b05fad13e342dd13a9',
        confidence:
          'CONFIRMED_GLOBAL_3_0_24',
      }),
    worldPlan:
      Object.freeze({
        path:
          '/home/ubuntu/logres/artifacts/logres-galaxy-world-reconstruction-plan-20260924.json',
        sha256:
          '41eb9db5ecf3ec5084d8f75772fbc56ad185686e0a4b69dcb4066dcf6fae0094',
        confidence:
          'CONFIRMED_GLOBAL_3_0_24',
      }),
    globalPackage:
      Object.freeze({
        path:
          '/home/ubuntu/logres/private/global-target/map-002/002_000_00001.mbn',
        sha256:
          'ff0cd4ba4e84af9586c4921147fb463a70bd4f822ea10b456eea8eb5ea3a444c',
        confidence:
          'CONFIRMED_GLOBAL_3_0_24',
      }),
    decodedMapPayload:
      Object.freeze({
        path:
          '/home/ubuntu/logres/private/global-hydrator-validation/002_000_00001/002_000_00001.map.bin',
        sha256:
          'a2ce7b5cc5f45e6063c0e02bee3bd8d7ff8a063a20b8173b05814ad61c89c9f1',
        confidence:
          'CONFIRMED_GLOBAL_3_0_24',
      }),
  } as const)

export const LOGRES_MAP_CONTENT_MANIFEST =
  Object.freeze({
    version:
      LOGRES_MAP_CONTENT_SCHEMA_VERSION,

    entries:
      Object.freeze([
        Object.freeze({
          key:
            'global-terrain-002_000_00001',

          mapFileId:
            '002_000_00001',

          category:
            'terrain' as const,

          provenance:
            'CONFIRMED_GLOBAL_3_0_24' as const,

          historicalHumanReadableRegionName:
            null,

          historicalAreaId:
            null,

          historicalTutorialAssignment:
            'SUPPORTED_INFERENCE' as const,

          resolution:
            Object.freeze({
              kind:
                'RECOVERED_GLOBAL_PACKAGE' as const,

              packagePath:
                'map-002/002_000_00001.mbn',

              packageSha256:
                'ff0cd4ba4e84af9586c4921147fb463a70bd4f822ea10b456eea8eb5ea3a444c',

              packageBytes:
                435405,

              mapMember:
                Object.freeze({
                  name:
                    '002_000_00001.map',
                  compressedSha256:
                    'e4af1d8283c20b709acaa5378c420e3f6548a55c71729ec4f5826205fdcd1db9',
                  compressedBytes:
                    131963,
                  payloadSha256:
                    'a2ce7b5cc5f45e6063c0e02bee3bd8d7ff8a063a20b8173b05814ad61c89c9f1',
                  payloadBytes:
                    476972,
                }),

              chipAtlas:
                Object.freeze({
                  name:
                    '002_000_00001_CHIP.astc',
                  sha256:
                    '3891534e71771537cbf3ad415d389cbaf562bf2bdcd56a1bb62d516653584d8b',
                  bytes:
                    183760,
                }),

              objectAtlas:
                Object.freeze({
                  name:
                    '002_000_00001_OBJ.astc',
                  sha256:
                    'f9551aaf461c2f4c27c83f66f3acb035215fd8bd4ae6904f6335309bda987377',
                  bytes:
                    394432,
                }),

              root:
                Object.freeze({
                  width:
                    120,
                  height:
                    120,
                  fieldQuadUnitCol:
                    8,
                  fieldQuadUnitRow:
                    8,
                  version:
                    1,
                }),

              counts:
                Object.freeze({
                  grids:
                    1380,
                  quadTrees:
                    62,
                  chips:
                    3363,
                  objects:
                    21,
                  animatedObjects:
                    0,
                }),

              collision:
                Object.freeze({
                  traversable:
                    1028,
                  prohibition7:
                    352,
                  pathwayIndex0:
                    352,
                  pathwayIndex1:
                    1028,
                }),

              structureFingerprint:
                '68b153ab61f9c049025e3049191ee7247e82ce5db261113fede2985a698a62cd',

              collisionFingerprint:
                '2430928e75261d6a264f16f186d5a91345ece1d3be23b885e82a36bfe361a679',
            }),

          crossVersion:
            Object.freeze({
              currentJpBasePath:
                'map/002_000_00001.mbn',
              currentJpAnsPath:
                'map/002_000_00001__ans.mbn',
              lineageGrade:
                'GLOBAL_JP_IDENTICAL' as const,
              currentJpBaseByteIdentical:
                true,
              currentJpAnsGeometryIdentical:
                true,
            }),

          runtimeBinding:
            Object.freeze({
              runtimeMapId:
                '002_000_00001',
              provenance:
                'SUPPORTED_INFERENCE' as const,
              reason:
                'The package is proven Global, but its historical Global tutorial-area assignment is not.',
            }),
        }),
      ] as const),

    inventory:
      Object.freeze({
        recoveredGlobalTerrainPackages:
          1,
        directGlobalMapIds:
          1,
        currentJpBaseTerrainMaps:
          738,
        currentJpOnlyBaseTerrainMaps:
          737,
        currentJpMapFamilies:
          111,
      }),

    evidenceCeilings:
      Object.freeze([
        'Historical Global human-readable field-name to static terrain MultiID mappings remain server/runtime evidence unless a Global-era payload or table is recovered.',
        'Current-JP-only maps cannot be promoted to historical Global presence without Global-era package, manifest, payload or equivalent primary evidence.',
        'Static map geometry does not itself prove quest state, NPC population, enemy population or dynamic field instance state.',
      ] as const),
  } as const)

export const LOGRES_REGION_CONTENT_MANIFEST =
  Object.freeze({
    version:
      LOGRES_MAP_CONTENT_SCHEMA_VERSION,

    entries:
      Object.freeze([
        Object.freeze({
          key:
            'millennium-tree-current-jp-reference',

          displayName:
            'Millennium Tree',

          currentJpAreaId:
            '002_001_00200',

          currentJpMapFileId:
            '002_000_00001',

          currentJpConfidence:
            'CONFIRMED_CURRENT_JP' as const,

          globalPackagePresent:
            true,

          globalJpPackageByteIdentical:
            true,

          historicalGlobalAreaId:
            null,

          historicalGlobalMapFileId:
            null,

          historicalGlobalAssignmentConfidence:
            'SUPPORTED_INFERENCE' as const,

          missingUpgradeEvidence:
            'A Global-era S_GMCL_AREA_ENTER payload, warp/area table, or equivalent primary record pairing Millennium Tree with terrain MultiID 002_000_00001.',
        }),
      ] as const),

    staticGridSemantics:
      Object.freeze({
        confirmedFields:
          Object.freeze([
            'Prohibition',
            'Attribute',
            'PathwayIndex',
            'BorderID',
            'BlendAdjacence',
            'ColorIndex',
          ] as const),

        explicitRegionIdField:
          false,

        guardrail:
          'Attribute, BorderID and PathwayIndex must not be silently renamed to RegionID.',
      }),
  } as const)

export const LOGRES_MAP_CONTENT_REJECTED_TEXTURE_ONLY_CANDIDATES =
  Object.freeze([
    Object.freeze({
      mapFileId:
        '002_000_00008',

      confidence:
        'CONFIRMED_CURRENT_JP' as const,

      disposition:
        'REJECTED_AS_IDENTITY_MATCH' as const,

      reason:
        'Shares base atlases with 002_000_00001 but has a different map payload and collision/structure fingerprint.',

      packageSha256:
        '75ccd816c8aa3d703f8450335db04a65551f017881f33bd4c12bdfed1abec11e',

      mapPayloadSha256:
        '89f6ebd306148a2e386386fa1ed1e054d641d9f9ef3b8852c3283d04091b9878',

      structureFingerprint:
        '5853b5becb1c7fae136d0e6a9a358bbfc05f9545ae5a4e38b169ba1726b24719',
    }),
  ] as const)

export const LOGRES_MAP_CONTENT_POLICY =
  Object.freeze({
    globalAuthority:
      'Global May 25 2017 / client 3.0.24 evidence outranks current-JP lineage.',

    directImplementationRule:
      'Only recovered Global or mechanically identical Global-JP map payloads may be declared historical Global map content.',

    jpOnlyRule:
      'The remaining 737 current-JP base terrain maps are research candidates only.',

    tutorialRule:
      '002_000_00001 is the strongest playable tutorial candidate, but Millennium Tree -> 002_000_00001 remains SUPPORTED_INFERENCE for historical Global.',

    serverStateRule:
      'Map geometry never implies historical NPC, enemy, quest, spawn, schedule or dynamic field state.',
  } as const)
