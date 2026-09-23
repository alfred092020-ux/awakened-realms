import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  createLogresFieldGridIndex,
} from '../src/game/logres/field/LogresFieldGridIndex'
import {
  createLogresFieldNavigationTile,
  isLogresFieldNeighborDelta,
  LOGRES_FIELD_ADJACENCY_DELTAS,
  logresFieldCanTraverseNeighbor,
  logresFieldHeuristic,
  logresFieldLinkedNeighbors,
  logresFieldLinkCost,
} from '../src/game/logres/field/LogresFieldNavigation'
import type {
  LogresFieldNavigationTile,
} from '../src/game/logres/field/LogresFieldNavigation'
import type {
  LogresMapRoot,
} from '../src/game/logres/field/LogresMapBinary'

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
      0,
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
        (entry) => [
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

describe(
  'Logres original field navigation rules',
  () => {
    it(
      'preserves the confirmed native TileAdjacency enum order',
      () => {
        expect(
          LOGRES_FIELD_ADJACENCY_DELTAS,
        ).toEqual([
          { col: -1, row: -1 },
          { col: 0, row: -1 },
          { col: 1, row: -1 },
          { col: 1, row: 0 },
          { col: 1, row: 1 },
          { col: 0, row: 1 },
          { col: -1, row: 1 },
          { col: -1, row: 0 },
          { col: 0, row: 0 },
        ])
      },
    )

    it(
      'accepts exactly the eight surrounding coordinate deltas',
      () => {
        const accepted =
          [] as string[]

        for (
          let row = -2
          ; row <= 2
          ; row += 1
        ) {
          for (
            let col = -2
            ; col <= 2
            ; col += 1
          ) {
            if (
              isLogresFieldNeighborDelta(
                col,
                row,
              )
            ) {
              accepted.push(
                `${col},${row}`,
              )
            }
          }
        }

        expect(
          accepted,
        ).toHaveLength(
          8,
        )
        expect(
          accepted,
        ).not.toContain(
          '0,0',
        )
      },
    )

    it(
      'maps confirmed protobuf navigation fields without treating depth as movement level',
      () => {
        const root:
          LogresMapRoot =
          {
            QuadTreeRoot: {
              Grids: [
                {
                  Col: 4n,
                  Row: 7n,
                  DepthOrder:
                    99n,
                  Prohibition:
                    2n,
                  PathwayIndex:
                    12n,
                  Attribute:
                    34n,
                  Chips: [],
                  Obj: [],
                  ObjAnimated:
                    [],
                },
                {
                  Col: 5n,
                  Row: 7n,
                  Chips: [],
                  Obj: [],
                  ObjAnimated:
                    [],
                },
              ],
              QuadTrees: [],
            },
          }

        const index =
          createLogresFieldGridIndex(
            root,
          )

        const first =
          index.at(
            4,
            7,
          )[0]

        const second =
          index.at(
            5,
            7,
          )[0]

        expect(
          first,
        ).toBeDefined()
        expect(
          second,
        ).toBeDefined()

        const navigation =
          createLogresFieldNavigationTile(
            first!,
            3,
          )

        expect(
          navigation,
        ).toEqual({
          col: 4,
          row: 7,
          prohibited:
            true,
          level: 3,
          regionId: 12,
          attribute: 34,
        })

        expect(
          createLogresFieldNavigationTile(
            second!,
            0,
          ),
        ).toMatchObject({
          prohibited:
            false,
          regionId: 0,
          attribute: 0,
        })
      },
    )

    it(
      'rejects blocked, missing, and excessive-level destinations',
      () => {
        const from =
          tile(
            0,
            0,
            {
              level: 4,
            },
          )

        expect(
          logresFieldCanTraverseNeighbor(
            from,
            1,
            0,
            lookup([
              tile(
                1,
                0,
                {
                  level: 5,
                },
              ),
            ]),
          ),
        ).toBe(
          true,
        )

        expect(
          logresFieldCanTraverseNeighbor(
            from,
            1,
            0,
            lookup([
              tile(
                1,
                0,
                {
                  prohibited:
                    true,
                  level: 4,
                },
              ),
            ]),
          ),
        ).toBe(
          false,
        )

        expect(
          logresFieldCanTraverseNeighbor(
            from,
            1,
            0,
            lookup([
              tile(
                1,
                0,
                {
                  level: 6,
                },
              ),
            ]),
          ),
        ).toBe(
          false,
        )

        expect(
          logresFieldCanTraverseNeighbor(
            from,
            -1,
            0,
            lookup([]),
          ),
        ).toBe(
          false,
        )
      },
    )

    it(
      'prevents diagonal corner cutting through either orthogonal side',
      () => {
        const from =
          tile(
            10,
            20,
            {
              level: 2,
            },
          )

        const open =
          lookup([
            tile(
              11,
              21,
              {
                level: 3,
              },
            ),
            tile(
              11,
              20,
              {
                level: 2,
              },
            ),
            tile(
              10,
              21,
              {
                level: 1,
              },
            ),
          ])

        expect(
          logresFieldCanTraverseNeighbor(
            from,
            1,
            1,
            open,
          ),
        ).toBe(
          true,
        )

        const blockedSide =
          lookup([
            tile(
              11,
              21,
              {
                level: 2,
              },
            ),
            tile(
              11,
              20,
              {
                prohibited:
                  true,
                level: 2,
              },
            ),
            tile(
              10,
              21,
              {
                level: 2,
              },
            ),
          ])

        expect(
          logresFieldCanTraverseNeighbor(
            from,
            1,
            1,
            blockedSide,
          ),
        ).toBe(
          false,
        )

        const highSide =
          lookup([
            tile(
              11,
              21,
              {
                level: 2,
              },
            ),
            tile(
              11,
              20,
              {
                level: 4,
              },
            ),
            tile(
              10,
              21,
              {
                level: 2,
              },
            ),
          ])

        expect(
          logresFieldCanTraverseNeighbor(
            from,
            1,
            1,
            highSide,
          ),
        ).toBe(
          false,
        )
      },
    )

    it(
      'uses native Manhattan link costs and zero tile heuristic',
      () => {
        expect(
          logresFieldLinkCost(
            {
              col: 3,
              row: 7,
            },
            {
              col: 4,
              row: 7,
            },
          ),
        ).toBe(
          1,
        )

        expect(
          logresFieldLinkCost(
            {
              col: 3,
              row: 7,
            },
            {
              col: 4,
              row: 8,
            },
          ),
        ).toBe(
          2,
        )

        expect(
          logresFieldHeuristic(),
        ).toBe(
          0,
        )
      },
    )

    it(
      'returns only native-valid linked neighbors',
      () => {
        const from =
          tile(
            0,
            0,
          )

        const tileAt =
          lookup([
            tile(
              1,
              0,
            ),
            tile(
              0,
              1,
            ),
            tile(
              1,
              1,
            ),
            tile(
              -1,
              0,
              {
                prohibited:
                  true,
              },
            ),
          ])

        expect(
          logresFieldLinkedNeighbors(
            from,
            tileAt,
          ).map(
            (entry) =>
              `${entry.col},${entry.row}`,
          ),
        ).toEqual([
          '1,0',
          '0,1',
          '1,1',
        ])
      },
    )
  },
)
