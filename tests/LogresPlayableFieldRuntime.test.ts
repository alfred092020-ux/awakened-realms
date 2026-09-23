import {
  describe,
  expect,
  it,
} from 'vitest'

import type {
  LogresFieldNavigationTile,
} from '../src/game/logres/field/LogresFieldNavigation'

import {
  chooseReconstructedLogresFieldSpawn,
  createLogresPlayableFieldRasterTransform,
  LOGRES_FIELD_TILE_SCREEN_STEP_X,
  LOGRES_FIELD_TILE_SCREEN_STEP_Y,
  LOGRES_PLAYABLE_FIELD_MAP_BINDING_PROVENANCE,
  LOGRES_PLAYABLE_FIELD_MAP_ID,
  logresPlayableFieldInfoUrls,
  nearestLogresPlayableFieldTile,
  projectLogresPlayableFieldTile,
  projectLogresPlayableFieldTileToRaster,
} from '../src/game/logres/field/LogresPlayableFieldRuntime'

import type {
  LogresTerrainMeshData,
} from '../src/game/logres/field/LogresTerrainMeshData'

function tile(
  col: number,
  row: number,
  level = 0,
  prohibited = false,
): LogresFieldNavigationTile {
  return {
    col,
    row,
    level,
    prohibited,
    regionId:
      0,
    attribute:
      0,
  }
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
  'playable Logres field runtime',
  () => {
    it(
      'keeps the tutorial map binding explicitly supported inference',
      () => {
        expect(
          LOGRES_PLAYABLE_FIELD_MAP_ID,
        ).toBe(
          '002_000_00001',
        )

        expect(
          LOGRES_PLAYABLE_FIELD_MAP_BINDING_PROVENANCE,
        ).toBe(
          'SUPPORTED_INFERENCE',
        )
      },
    )

    it(
      'uses the recovered 44 by 22 isometric tile lattice with level height',
      () => {
        expect(
          LOGRES_FIELD_TILE_SCREEN_STEP_X,
        ).toBe(
          44,
        )

        expect(
          LOGRES_FIELD_TILE_SCREEN_STEP_Y,
        ).toBe(
          22,
        )

        expect(
          projectLogresPlayableFieldTile(
            tile(
              24,
              39,
              16,
            ),
          ),
        ).toEqual({
          x:
            -660,
          y:
            -1056,
        })

        expect(
          projectLogresPlayableFieldTile(
            tile(
              25,
              39,
              16,
            ),
          ),
        ).toEqual({
          x:
            -616,
          y:
            -1078,
        })
      },
    )

    it(
      'creates the same centered raster transform used by the terrain proof renderer',
      () => {
        const transform =
          createLogresPlayableFieldRasterTransform(
            mesh(),
            1000,
            800,
          )

        expect(
          transform.centerX,
        ).toBe(
          0,
        )

        expect(
          transform.centerY,
        ).toBe(
          0,
        )

        expect(
          transform.fit,
        ).toBeCloseTo(
          3.68,
        )
      },
    )

    it(
      'projects raw tile anchors into raster coordinates with inverted canvas Y',
      () => {
        const transform =
          createLogresPlayableFieldRasterTransform(
            mesh(),
            1000,
            800,
          )

        const raw =
          projectLogresPlayableFieldTile(
            tile(
              1,
              0,
              0,
            ),
          )

        const raster =
          projectLogresPlayableFieldTileToRaster(
            tile(
              1,
              0,
              0,
            ),
            transform,
          )

        expect(
          raster.x,
        ).toBeCloseTo(
          500 +
            raw.x *
              transform.fit,
        )

        expect(
          raster.y,
        ).toBeCloseTo(
          400 -
            raw.y *
              transform.fit,
        )
      },
    )

    it(
      'chooses a deterministic traversable reconstruction spawn',
      () => {
        const tiles = [
          tile(
            0,
            0,
            0,
            true,
          ),
          tile(
            1,
            0,
          ),
          tile(
            2,
            0,
          ),
          tile(
            1,
            1,
          ),
          tile(
            2,
            1,
          ),
        ]

        const spawn =
          chooseReconstructedLogresFieldSpawn(
            tiles,
          )

        expect(
          spawn.prohibited,
        ).toBe(
          false,
        )

        expect(
          tiles,
        ).toContain(
          spawn,
        )
      },
    )

    it(
      'finds the nearest non-prohibited projected tile',
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
            0,
            true,
          )

        const expected =
          tile(
            1,
            0,
          )

        const point =
          projectLogresPlayableFieldTileToRaster(
            expected,
            transform,
          )

        expect(
          nearestLogresPlayableFieldTile(
            point.x,
            point.y,
            [
              blocked,
              expected,
              tile(
                2,
                0,
              ),
            ],
            transform,
          ),
        ).toBe(
          expected,
        )
      },
    )

    it(
      'resolves runtime map-info URLs beside the hydrated map package',
      () => {
        expect(
          logresPlayableFieldInfoUrls(),
        ).toEqual({
          chip:
            '/__logres_ref/renderer-proof/002_000_00001/chip_d.bin',
          object:
            '/__logres_ref/renderer-proof/002_000_00001/object_d.bin',
        })
      },
    )
  },
)
