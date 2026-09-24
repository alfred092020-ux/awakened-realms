import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_PLAYABLE_FIELD_MAP_BINDING_PROVENANCE,
  LOGRES_PLAYABLE_FIELD_MAP_ID,
} from '../src/game/logres/field/LogresPlayableFieldRuntime'

import {
  LOGRES_GALAXY_WORLD_PLAN_DIRECT_MAPS,
} from '../src/game/logres/reverse/LogresGalaxyWorldReconstructionPlan'

import {
  LOGRES_GLOBAL_JP_MAP_STATIC_GRID_SEMANTICS,
  LOGRES_GLOBAL_JP_MILLENNIUM_TREE_MAP,
} from '../src/game/logres/reverse/LogresGlobalJpMapGenealogyEvidence'

import {
  LOGRES_GLOBAL_JP_MILLENNIUM_TREE,
} from '../src/game/logres/reverse/LogresGlobalJpLineageEvidence'

import {
  LOGRES_MAP_CONTENT_EVIDENCE,
  LOGRES_MAP_CONTENT_MANIFEST,
  LOGRES_MAP_CONTENT_POLICY,
  LOGRES_MAP_CONTENT_REJECTED_TEXTURE_ONLY_CANDIDATES,
  LOGRES_REGION_CONTENT_MANIFEST,
} from '../src/game/logres/generated/maps/LogresMapContent'

describe(
  'evidence-backed map content coverage',
  () => {
    it(
      'declares exactly the recovered direct Global map inventory',
      () => {
        expect(
          LOGRES_MAP_CONTENT_MANIFEST
            .version,
        ).toBe(
          'map-content-v1',
        )

        expect(
          LOGRES_MAP_CONTENT_MANIFEST
            .entries
            .map(
              entry =>
                entry.mapFileId,
            ),
        ).toEqual(
          LOGRES_GALAXY_WORLD_PLAN_DIRECT_MAPS,
        )

        expect(
          LOGRES_MAP_CONTENT_MANIFEST
            .inventory
            .recoveredGlobalTerrainPackages,
        ).toBe(
          1,
        )

        expect(
          LOGRES_MAP_CONTENT_MANIFEST
            .inventory
            .directGlobalMapIds,
        ).toBe(
          1,
        )
      },
    )

    it(
      'pins the recovered Global package and decoded geometry hashes',
      () => {
        const entry =
          LOGRES_MAP_CONTENT_MANIFEST
            .entries[
              0
            ]

        expect(
          entry.provenance,
        ).toBe(
          'CONFIRMED_GLOBAL_3_0_24',
        )

        expect(
          entry.resolution.kind,
        ).toBe(
          'RECOVERED_GLOBAL_PACKAGE',
        )

        expect(
          entry.resolution
            .packageSha256,
        ).toBe(
          LOGRES_GLOBAL_JP_MILLENNIUM_TREE_MAP
            .globalPackageSha256,
        )

        expect(
          entry.resolution
            .mapMember
            .payloadSha256,
        ).toBe(
          LOGRES_GLOBAL_JP_MILLENNIUM_TREE_MAP
            .mapPayloadSha256,
        )

        expect(
          entry.resolution
            .structureFingerprint,
        ).toBe(
          LOGRES_GLOBAL_JP_MILLENNIUM_TREE_MAP
            .structureFingerprint,
        )

        expect(
          entry.crossVersion
            .lineageGrade,
        ).toBe(
          'GLOBAL_JP_IDENTICAL',
        )

        expect(
          entry.crossVersion
            .currentJpBaseByteIdentical,
        ).toBe(
          true,
        )
      },
    )

    it(
      'matches the decoded Global geometry and collision counts',
      () => {
        const entry =
          LOGRES_MAP_CONTENT_MANIFEST
            .entries[
              0
            ]

        expect(
          entry.resolution
            .counts,
        ).toEqual({
          grids:
            LOGRES_GLOBAL_JP_MILLENNIUM_TREE_MAP
              .counts
              .grids,
          quadTrees:
            LOGRES_GLOBAL_JP_MILLENNIUM_TREE_MAP
              .counts
              .quadTrees,
          chips:
            LOGRES_GLOBAL_JP_MILLENNIUM_TREE_MAP
              .counts
              .chips,
          objects:
            LOGRES_GLOBAL_JP_MILLENNIUM_TREE_MAP
              .counts
              .objects,
          animatedObjects:
            LOGRES_GLOBAL_JP_MILLENNIUM_TREE_MAP
              .counts
              .animatedObjects,
        })

        expect(
          entry.resolution
            .collision,
        ).toEqual({
          traversable:
            LOGRES_GLOBAL_JP_MILLENNIUM_TREE_MAP
              .collision
              .traversable,
          prohibition7:
            LOGRES_GLOBAL_JP_MILLENNIUM_TREE_MAP
              .collision
              .prohibition7,
          pathwayIndex0:
            352,
          pathwayIndex1:
            1028,
        })
      },
    )

    it(
      'keeps playable map usage separate from historical tutorial assignment',
      () => {
        const entry =
          LOGRES_MAP_CONTENT_MANIFEST
            .entries[
              0
            ]

        expect(
          entry.runtimeBinding
            .runtimeMapId,
        ).toBe(
          LOGRES_PLAYABLE_FIELD_MAP_ID,
        )

        expect(
          entry.runtimeBinding
            .provenance,
        ).toBe(
          LOGRES_PLAYABLE_FIELD_MAP_BINDING_PROVENANCE,
        )

        expect(
          entry.historicalHumanReadableRegionName,
        ).toBeNull()

        expect(
          entry.historicalAreaId,
        ).toBeNull()

        expect(
          entry.historicalTutorialAssignment,
        ).toBe(
          'SUPPORTED_INFERENCE',
        )
      },
    )

    it(
      'models Millennium Tree as a current-JP region reference without back-projecting the area mapping',
      () => {
        const region =
          LOGRES_REGION_CONTENT_MANIFEST
            .entries[
              0
            ]

        expect(
          region.displayName,
        ).toBe(
          'Millennium Tree',
        )

        expect(
          region.currentJpAreaId,
        ).toBe(
          LOGRES_GLOBAL_JP_MILLENNIUM_TREE
            .currentJpAreaId,
        )

        expect(
          region.currentJpMapFileId,
        ).toBe(
          LOGRES_GLOBAL_JP_MILLENNIUM_TREE
            .currentJpMapFileId,
        )

        expect(
          region.currentJpConfidence,
        ).toBe(
          'CONFIRMED_CURRENT_JP',
        )

        expect(
          region.historicalGlobalAreaId,
        ).toBeNull()

        expect(
          region.historicalGlobalMapFileId,
        ).toBeNull()

        expect(
          region.historicalGlobalAssignmentConfidence,
        ).toBe(
          'SUPPORTED_INFERENCE',
        )

        expect(
          region.missingUpgradeEvidence,
        ).toBe(
          LOGRES_GLOBAL_JP_MILLENNIUM_TREE
            .missingUpgradeEvidence,
        )
      },
    )

    it(
      'does not promote the remaining current-JP terrain inventory into Global content',
      () => {
        expect(
          LOGRES_MAP_CONTENT_MANIFEST
            .inventory
            .currentJpBaseTerrainMaps,
        ).toBe(
          738,
        )

        expect(
          LOGRES_MAP_CONTENT_MANIFEST
            .inventory
            .currentJpOnlyBaseTerrainMaps,
        ).toBe(
          737,
        )

        expect(
          LOGRES_MAP_CONTENT_MANIFEST
            .entries,
        ).toHaveLength(
          1,
        )

        expect(
          LOGRES_MAP_CONTENT_POLICY
            .jpOnlyRule,
        ).toContain(
          '737',
        )
      },
    )

    it(
      'rejects texture-only map identity when payload and collision structure differ',
      () => {
        const rejected =
          LOGRES_MAP_CONTENT_REJECTED_TEXTURE_ONLY_CANDIDATES[
            0
          ]

        expect(
          rejected.mapFileId,
        ).toBe(
          '002_000_00008',
        )

        expect(
          rejected.disposition,
        ).toBe(
          'REJECTED_AS_IDENTITY_MATCH',
        )

        expect(
          rejected.mapPayloadSha256,
        ).not.toBe(
          LOGRES_MAP_CONTENT_MANIFEST
            .entries[
              0
            ]
            .resolution
            .mapMember
            .payloadSha256,
        )

        expect(
          rejected.structureFingerprint,
        ).not.toBe(
          LOGRES_MAP_CONTENT_MANIFEST
            .entries[
              0
            ]
            .resolution
            .structureFingerprint,
        )
      },
    )

    it(
      'preserves static grid field names instead of inventing RegionID',
      () => {
        expect(
          LOGRES_REGION_CONTENT_MANIFEST
            .staticGridSemantics
            .confirmedFields,
        ).toEqual(
          LOGRES_GLOBAL_JP_MAP_STATIC_GRID_SEMANTICS
            .confirmedFields,
        )

        expect(
          LOGRES_REGION_CONTENT_MANIFEST
            .staticGridSemantics
            .explicitRegionIdField,
        ).toBe(
          false,
        )

        expect(
          LOGRES_REGION_CONTENT_MANIFEST
            .staticGridSemantics
            .guardrail,
        ).toContain(
          'must not be silently renamed to RegionID',
        )
      },
    )

    it(
      'requires every declared historical Global map to have supported geometry and asset hashes',
      () => {
        for (
          const entry of
          LOGRES_MAP_CONTENT_MANIFEST
            .entries
        ) {
          expect(
            entry.resolution.kind,
          ).toBe(
            'RECOVERED_GLOBAL_PACKAGE',
          )

          expect(
            entry.resolution
              .packageSha256,
          ).toHaveLength(
            64,
          )

          expect(
            entry.resolution
              .mapMember
              .payloadSha256,
          ).toHaveLength(
            64,
          )

          expect(
            entry.resolution
              .chipAtlas
              .sha256,
          ).toHaveLength(
            64,
          )

          expect(
            entry.resolution
              .objectAtlas
              .sha256,
          ).toHaveLength(
            64,
          )
        }
      },
    )

    it(
      'pins the source evidence hashes used to generate the manifest',
      () => {
        expect(
          LOGRES_MAP_CONTENT_EVIDENCE
            .mapGenealogy
            .sha256,
        ).toBe(
          'dbec39a300071ef2f8b30710948fd34de5bb52f010b6d6b05fad13e342dd13a9',
        )

        expect(
          LOGRES_MAP_CONTENT_EVIDENCE
            .globalPackage
            .sha256,
        ).toBe(
          'ff0cd4ba4e84af9586c4921147fb463a70bd4f822ea10b456eea8eb5ea3a444c',
        )

        expect(
          LOGRES_MAP_CONTENT_EVIDENCE
            .decodedMapPayload
            .sha256,
        ).toBe(
          'a2ce7b5cc5f45e6063c0e02bee3bd8d7ff8a063a20b8173b05814ad61c89c9f1',
        )
      },
    )
  },
)
