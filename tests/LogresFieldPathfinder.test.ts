import {
  describe,
  expect,
  it,
} from 'vitest'

import type {
  LogresFieldNavigationTile,
} from '../src/game/logres/field/LogresFieldNavigation'

import {
  findReconstructedLogresFieldPath,
} from '../src/game/logres/field/LogresFieldPathfinder'

function tile(
  col: number,
  row: number,
  overrides:
    Partial<
      LogresFieldNavigationTile
    > = {},
):
  LogresFieldNavigationTile {
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

function rectangularField(
  width:
    number,
  height:
    number,
):
  LogresFieldNavigationTile[] {
  const result:
    LogresFieldNavigationTile[] =
    []

  for (
    let row = 0
    ; row < height
    ; row += 1
  ) {
    for (
      let col = 0
      ; col < width
      ; col += 1
    ) {
      result.push(
        tile(
          col,
          row,
        ),
      )
    }
  }

  return result
}

describe(
  'reconstructed Logres field pathfinder',
  () => {
    it(
      'finds a minimum-cost route over the confirmed original tile graph',
      () => {
        const tiles =
          rectangularField(
            4,
            3,
          )

        const result =
          findReconstructedLogresFieldPath(
            {
              col: 0,
              row: 1,
            },
            {
              col: 3,
              row: 1,
            },
            lookup(
              tiles,
            ),
          )

        expect(
          result?.provenance,
        ).toBe(
          'RECONSTRUCTED',
        )

        expect(
          result?.totalCost,
        ).toBe(
          3,
        )

        expect(
          result?.coords[0],
        ).toEqual({
          col: 0,
          row: 1,
        })

        expect(
          result?.coords.at(
            -1,
          ),
        ).toEqual({
          col: 3,
          row: 1,
        })
      },
    )

    it(
      'routes around prohibited tiles instead of cutting through them',
      () => {
        const tiles =
          rectangularField(
            5,
            3,
          )

        const blocked =
          tiles.find(
            (entry) =>
              entry.col ===
                2 &&
              entry.row ===
                1,
          )!

        blocked.prohibited =
          true

        const result =
          findReconstructedLogresFieldPath(
            {
              col: 0,
              row: 1,
            },
            {
              col: 4,
              row: 1,
            },
            lookup(
              tiles,
            ),
          )

        expect(
          result,
        ).not.toBeNull()

        expect(
          result?.coords,
        ).not.toContainEqual({
          col: 2,
          row: 1,
        })

        expect(
          result?.totalCost,
        ).toBeGreaterThan(
          4,
        )
      },
    )

    it(
      'does not diagonal-corner-cut through blocked orthogonal neighbors',
      () => {
        const tiles = [
          tile(
            0,
            0,
          ),
          tile(
            1,
            0,
            {
              prohibited:
                true,
            },
          ),
          tile(
            0,
            1,
            {
              prohibited:
                true,
            },
          ),
          tile(
            1,
            1,
          ),
        ]

        expect(
          findReconstructedLogresFieldPath(
            {
              col: 0,
              row: 0,
            },
            {
              col: 1,
              row: 1,
            },
            lookup(
              tiles,
            ),
          ),
        ).toBeNull()
      },
    )

    it(
      'respects the confirmed movement-level difference gate',
      () => {
        const tiles = [
          tile(
            0,
            0,
            {
              level: 0,
            },
          ),
          tile(
            1,
            0,
            {
              level: 2,
            },
          ),
        ]

        expect(
          findReconstructedLogresFieldPath(
            {
              col: 0,
              row: 0,
            },
            {
              col: 1,
              row: 0,
            },
            lookup(
              tiles,
            ),
          ),
        ).toBeNull()
      },
    )

    it(
      'returns a zero-cost one-tile path when start and goal are identical',
      () => {
        const start =
          tile(
            7,
            9,
          )

        expect(
          findReconstructedLogresFieldPath(
            start,
            start,
            lookup([
              start,
            ]),
          ),
        ).toMatchObject({
          provenance:
            'RECONSTRUCTED',
          totalCost:
            0,
          visitedCount:
            1,
          coords: [
            {
              col: 7,
              row: 9,
            },
          ],
        })
      },
    )

    it(
      'rejects blocked endpoints and malformed search safety bounds',
      () => {
        const start =
          tile(
            0,
            0,
          )
        const goal =
          tile(
            1,
            0,
            {
              prohibited:
                true,
            },
          )

        expect(
          findReconstructedLogresFieldPath(
            start,
            goal,
            lookup([
              start,
              goal,
            ]),
          ),
        ).toBeNull()

        expect(
          () =>
            findReconstructedLogresFieldPath(
              start,
              start,
              lookup([
                start,
              ]),
              {
                maxVisited:
                  0,
              },
            ),
        ).toThrow(
          'maxVisited must be a positive safe integer',
        )
      },
    )

    it(
      'does not assert a native route tie-break when equal-cost paths exist',
      () => {
        const tiles =
          rectangularField(
            3,
            3,
          )

        const result =
          findReconstructedLogresFieldPath(
            {
              col: 0,
              row: 0,
            },
            {
              col: 2,
              row: 2,
            },
            lookup(
              tiles,
            ),
          )

        expect(
          result?.totalCost,
        ).toBe(
          4,
        )

        expect(
          result?.coords[0],
        ).toEqual({
          col: 0,
          row: 0,
        })

        expect(
          result?.coords.at(
            -1,
          ),
        ).toEqual({
          col: 2,
          row: 2,
        })
      },
    )
  },
)
