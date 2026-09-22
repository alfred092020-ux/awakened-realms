import {
  describe,
  expect,
  it,
} from 'vitest'

import type {
  LogresMapGrid,
  LogresMapRoot,
} from '../src/game/logres/field/LogresMapBinary'
import type {
  LogresMapInfoRecord,
  LogresMapInfoTable,
} from '../src/game/logres/field/LogresMapInfoBinary'

import {
  createLogresFieldNavigationModel,
  deriveLogresFieldBlockLevel,
  LOGRES_FIELD_LEVEL_FORMULA_EVIDENCE,
  LOGRES_GLOBAL_FIELD_LEVEL_APPLICATION,
} from '../src/game/logres/field/LogresFieldNativeLevels'

function chipTable(
  rows:
    readonly [
      number,
      number,
    ][],
): LogresMapInfoTable {
  const records =
    rows.map(
      (
        [
          packedId,
          height,
        ],
        recordIndex,
      ) => {
        const record:
          LogresMapInfoRecord =
          {
            packedId,
            component0:
              Math.floor(
                packedId /
                  0x1000000,
              ),
            component1:
              Math.floor(
                packedId /
                  0x10000,
              ) &
              0xff,
            component2:
              packedId &
              0xffff,
            height,
            recordIndex,
          }

        return Object.freeze(
          record,
        )
      },
    )

  return {
    kind:
      'chip',
    formatWordLow16:
      10001,
    recordCount:
      records.length,
    records:
      Object.freeze(
        records,
      ),
    byPackedId:
      new Map(
        records.map(
          (record) => [
            record.packedId,
            record,
          ],
        ),
      ),
  }
}

function grid(
  col: number,
  row: number,
  chips:
    LogresMapGrid['Chips'],
  overrides:
    Partial<
      LogresMapGrid
    > = {},
): LogresMapGrid {
  return {
    Col:
      BigInt(
        col,
      ),
    Row:
      BigInt(
        row,
      ),
    DepthOrder:
      999n,
    Prohibition:
      0n,
    Attribute:
      0n,
    PathwayIndex:
      0n,
    BorderID:
      0n,
    BlendAdjacence:
      0n,
    ColorIndex:
      0n,
    Chips:
      chips,
    Obj:
      [],
    ObjAnimated:
      [],
    ...overrides,
  }
}

function root(
  grids:
    LogresMapGrid[],
): LogresMapRoot {
  return {
    Width:
      120n,
    Height:
      120n,
    QuadTreeRoot: {
      Grids:
        grids,
      QuadTrees:
        [],
    },
  }
}

describe(
  'Logres native-derived field levels',
  () => {
    it(
      'uses the last successfully resolved chip block rather than max height or Grid.DepthOrder',
      () => {
        const firstId =
          0x020100fd
        const lastId =
          0x02010000

        const evidence =
          deriveLogresFieldBlockLevel(
            grid(
              1,
              2,
              [
                {
                  Id:
                    BigInt(
                      firstId,
                    ),
                  Height:
                    10n,
                  Vertices:
                    [],
                },
                {
                  Id:
                    0x0201ffffn,
                  Height:
                    50n,
                  Vertices:
                    [],
                },
                {
                  Id:
                    BigInt(
                      lastId,
                    ),
                  Height:
                    2n,
                  Vertices:
                    [],
                },
              ],
              {
                DepthOrder:
                  9000n,
              },
            ),
            chipTable([
              [
                firstId,
                2,
              ],
              [
                lastId,
                1,
              ],
            ]),
          )

        expect(
          evidence,
        ).toEqual({
          level:
            3,
          resolvedBlockCount:
            2,
          unresolvedPackedChipIds: [
            0x0201ffff,
          ],
        })
      },
    )

    it(
      'preserves the previous native level when a later chip metadata lookup fails',
      () => {
        const evidence =
          deriveLogresFieldBlockLevel(
            grid(
              3,
              4,
              [
                {
                  Id:
                    0x020100fdn,
                  Height:
                    10n,
                  Vertices:
                    [],
                },
                {
                  Id:
                    0x0201ffffn,
                  Height:
                    200n,
                  Vertices:
                    [],
                },
              ],
            ),
            chipTable([
              [
                0x020100fd,
                2,
              ],
            ]),
          )

        expect(
          evidence.level,
        ).toBe(
          12,
        )

        expect(
          evidence.resolvedBlockCount,
        ).toBe(
          1,
        )
      },
    )

    it(
      'keeps the constructor level zero when no block resolves',
      () => {
        expect(
          deriveLogresFieldBlockLevel(
            grid(
              0,
              0,
              [],
            ),
            chipTable([]),
          ),
        ).toEqual({
          level:
            0,
          resolvedBlockCount:
            0,
          unresolvedPackedChipIds:
            [],
        })
      },
    )

    it(
      'builds a complete navigation model from addressed unique grids with complete metadata',
      () => {
        const model =
          createLogresFieldNavigationModel(
            root([
              grid(
                10,
                20,
                [
                  {
                    Id:
                      0x020100fdn,
                    Height:
                      10n,
                    Vertices:
                      [],
                  },
                ],
                {
                  Prohibition:
                    7n,
                  PathwayIndex:
                    3n,
                  Attribute:
                    4n,
                },
              ),
              grid(
                11,
                20,
                [
                  {
                    Id:
                      0x02010000n,
                    Height:
                      2n,
                    Vertices:
                      [],
                  },
                ],
              ),
            ]),
            chipTable([
              [
                0x020100fd,
                2,
              ],
              [
                0x02010000,
                1,
              ],
            ]),
          )

        expect(
          model.formulaEvidence,
        ).toBe(
          LOGRES_FIELD_LEVEL_FORMULA_EVIDENCE,
        )

        expect(
          model.globalTargetApplication,
        ).toBe(
          LOGRES_GLOBAL_FIELD_LEVEL_APPLICATION,
        )

        expect(
          model.metadataComplete,
        ).toBe(
          true,
        )

        expect(
          model.tileAt(
            10,
            20,
          ),
        ).toEqual({
          col:
            10,
          row:
            20,
          prohibited:
            true,
          level:
            12,
          regionId:
            3,
          attribute:
            4,
        })

        expect(
          model.tileAt(
            11,
            20,
          )?.level,
        ).toBe(
          3,
        )
      },
    )

    it(
      'reports unresolved metadata and refuses an ambiguous duplicate-coordinate lookup',
      () => {
        const duplicateA =
          grid(
            5,
            6,
            [
              {
                Id:
                  0x0201ffffn,
                Height:
                  1n,
                Vertices:
                  [],
              },
            ],
          )

        const duplicateB =
          grid(
            5,
            6,
            [],
          )

        const model =
          createLogresFieldNavigationModel(
            root([
              duplicateA,
              duplicateB,
            ]),
            chipTable([]),
          )

        expect(
          model.metadataComplete,
        ).toBe(
          false,
        )

        expect(
          model.unresolvedPackedChipIds,
        ).toEqual([
          0x0201ffff,
        ])

        expect(
          model.duplicateCoordinates,
        ).toEqual([
          '5,6',
        ])

        expect(
          model.tileAt(
            5,
            6,
          ),
        ).toBeUndefined()
      },
    )

    it(
      'rejects object metadata where chip metadata is required',
      () => {
        expect(
          () =>
            deriveLogresFieldBlockLevel(
              grid(
                0,
                0,
                [],
              ),
              {
                ...chipTable([]),
                kind:
                  'object',
              },
            ),
        ).toThrow(
          'require MAP_CHIP metadata',
        )
      },
    )
  },
)
