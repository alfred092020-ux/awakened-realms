import {
  describe,
  expect,
  it,
} from 'vitest'

import type {
  LogresFieldNavigationTile,
} from '../src/game/logres/field/LogresFieldNavigation'

import {
  LOGRES_GLOBAL_3024_NATIVE_FIELD_PROVENANCE,
  logresGlobalMoveFallbackCandidates,
  resolveLogresGlobalMoveTarget,
} from '../src/game/logres/field/LogresGlobalNativeFieldEvidence'

import {
  createLogresPlayableFieldRasterTransform,
  nearestLogresPlayableFieldTile,
  projectLogresPlayableFieldTileToRaster,
} from '../src/game/logres/field/LogresPlayableFieldRuntime'

import type {
  LogresTerrainMeshData,
} from '../src/game/logres/field/LogresTerrainMeshData'

function tile(
  col: number,
  row: number,
  overrides:
    Partial<LogresFieldNavigationTile> =
      {},
): LogresFieldNavigationTile {
  return {
    col,
    row,
    prohibited:
      false,
    level:
      0,
    regionId:
      7,
    attribute:
      0,
    ...overrides,
  }
}

function lookup(
  tiles:
    readonly LogresFieldNavigationTile[],
) {
  const index =
    new Map(
      tiles.map(
        (
          entry,
        ) => [
          `${entry.col},${entry.row}`,
          entry,
        ],
      ),
    )

  return (
    col: number,
    row: number,
  ) =>
    index.get(
      `${col},${row}`,
    )
}

function mesh():
  LogresTerrainMeshData {
  return {
    chip: {
      texture:
        'chip',
      vertices: [
        -100,
        -100,
        100,
        -100,
        100,
        100,
      ],
      uvs: [
        0,
        0,
        1,
        0,
        1,
        1,
      ],
      indices: [
        0,
        1,
        2,
      ],
      primitiveCount:
        1,
    },

    obj: {
      texture:
        'obj',
      vertices: [
        -50,
        -50,
        50,
        -50,
        50,
        50,
      ],
      uvs: [
        0,
        0,
        1,
        0,
        1,
        1,
      ],
      indices: [
        0,
        1,
        2,
      ],
      primitiveCount:
        1,
    },
  }
}

describe(
  'Global 3.0.24 native field movement evidence',
  () => {
    it(
      'locks the signed Global provenance label',
      () => {
        expect(
          LOGRES_GLOBAL_3024_NATIVE_FIELD_PROVENANCE,
        ).toBe(
          'CONFIRMED_GLOBAL_3_0_24_NATIVE',
        )
      },
    )

    it(
      'reproduces the destination-to-source shallow Bresenham candidate order',
      () => {
        expect(
          logresGlobalMoveFallbackCandidates(
            {
              col: 0,
              row: 0,
            },
            {
              col: 5,
              row: 2,
            },
          ),
        ).toEqual([
          {
            col: 5,
            row: 2,
          },
          {
            col: 4,
            row: 2,
          },
          {
            col: 3,
            row: 1,
          },
          {
            col: 2,
            row: 1,
          },
          {
            col: 1,
            row: 0,
          },
          {
            col: 0,
            row: 0,
          },
        ])
      },
    )

    it(
      'reproduces the destination-to-source steep Bresenham candidate order',
      () => {
        expect(
          logresGlobalMoveFallbackCandidates(
            {
              col: 1,
              row: 1,
            },
            {
              col: 3,
              row: 6,
            },
          ),
        ).toEqual([
          {
            col: 3,
            row: 6,
          },
          {
            col: 3,
            row: 5,
          },
          {
            col: 2,
            row: 4,
          },
          {
            col: 2,
            row: 3,
          },
          {
            col: 1,
            row: 2,
          },
          {
            col: 1,
            row: 1,
          },
        ])
      },
    )

    it(
      'uses the requested tile directly when it is traversable and in the source region',
      () => {
        const source =
          tile(
            0,
            0,
          )

        const requested =
          tile(
            3,
            1,
          )

        expect(
          resolveLogresGlobalMoveTarget(
            source,
            requested,
            lookup([
              source,
              requested,
            ]),
          ),
        ).toMatchObject({
          provenance:
            LOGRES_GLOBAL_3024_NATIVE_FIELD_PROVENANCE,

          requested: {
            col:
              3,

            row:
              1,
          },

          resolved:
            requested,

          usedFallback:
            false,
        })
      },
    )

    it(
      'backs away from a prohibited or wrong-region request to the first valid source-region tile',
      () => {
        const source =
          tile(
            0,
            0,
          )

        const requested =
          tile(
            5,
            2,
            {
              prohibited:
                true,
            },
          )

        const regionMismatch =
          tile(
            4,
            2,
            {
              regionId:
                9,
            },
          )

        const firstValid =
          tile(
            3,
            1,
          )

        expect(
          resolveLogresGlobalMoveTarget(
            source,
            requested,
            lookup([
              source,
              requested,
              regionMismatch,
              firstValid,
            ]),
          ),
        ).toMatchObject({
          provenance:
            LOGRES_GLOBAL_3024_NATIVE_FIELD_PROVENANCE,

          resolved:
            firstValid,

          usedFallback:
            true,
        })
      },
    )

    it(
      'can fall all the way back to the current source tile',
      () => {
        const source =
          tile(
            0,
            0,
          )

        expect(
          resolveLogresGlobalMoveTarget(
            source,
            tile(
              2,
              0,
              {
                prohibited:
                  true,
              },
            ),
            lookup([
              source,
              tile(
                1,
                0,
                {
                  prohibited:
                    true,
                },
              ),
              tile(
                2,
                0,
                {
                  prohibited:
                    true,
                },
              ),
            ]),
          ),
        ).toMatchObject({
          resolved:
            source,

          usedFallback:
            true,
        })
      },
    )

    it(
      'lets the raster picker expose a blocked raw request only when the Global fallback path opts in',
      () => {
        const transform =
          createLogresPlayableFieldRasterTransform(
            mesh(),
            1000,
            800,
          )

        const blocked =
          tile(
            0,
            0,
            {
              prohibited:
                true,
            },
          )

        const traversable =
          tile(
            1,
            0,
          )

        const blockedPoint =
          projectLogresPlayableFieldTileToRaster(
            blocked,
            transform,
          )

        expect(
          nearestLogresPlayableFieldTile(
            blockedPoint.x,
            blockedPoint.y,
            [
              blocked,
              traversable,
            ],
            transform,
          ),
        ).toBe(
          traversable,
        )

        expect(
          nearestLogresPlayableFieldTile(
            blockedPoint.x,
            blockedPoint.y,
            [
              blocked,
              traversable,
            ],
            transform,
            true,
          ),
        ).toBe(
          blocked,
        )
      },
    )
  },
)
