import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  createLogresFieldGridIndex,
} from '../src/game/logres/field/LogresFieldGridIndex'
import type {
  LogresMapRoot,
} from '../src/game/logres/field/LogresMapBinary'

describe(
  'Logres field grid index',
  () => {
    it(
      'indexes coordinates while preserving raw navigation evidence',
      () => {
        const root: LogresMapRoot = {
          QuadTreeRoot: {
            Grids: [
              {
                Col: 2n,
                Row: 3n,
                Prohibition: 4n,
                Attribute: 5n,
                PathwayIndex: 6n,
                BorderID: 7n,
                BlendAdjacence: 8n,
                ColorIndex: 9n,
                Chips: [],
                Obj: [],
                ObjAnimated: [],
              },
              {
                Col: 2n,
                Row: 3n,
                PathwayIndex: 10n,
                Chips: [],
                Obj: [],
                ObjAnimated: [],
              },
              {
                Chips: [],
                Obj: [],
                ObjAnimated: [],
              },
            ],
            QuadTrees: [],
          },
        }

        const index =
          createLogresFieldGridIndex(
            root,
          )
        const cells =
          index.at(
            2,
            3,
          )

        expect(
          cells,
        ).toHaveLength(
          2,
        )
        expect(
          cells[0]?.navigationEvidence,
        ).toEqual(
          {
            prohibition:
              4n,
            attribute:
              5n,
            pathwayIndex:
              6n,
            borderId:
              7n,
            blendAdjacence:
              8n,
            colorIndex:
              9n,
          },
        )
        expect(
          cells[1]?.navigationEvidence.pathwayIndex,
        ).toBe(
          10n,
        )
        expect(
          index.unaddressedGrids,
        ).toHaveLength(
          1,
        )
      },
    )

    it(
      'rejects non-integer lookup coordinates without inventing coercion',
      () => {
        const index =
          createLogresFieldGridIndex(
            {},
          )

        expect(
          () =>
            index.at(
              1.5,
              2,
            ),
        ).toThrow(
          'Logres field coordinates must be safe integers',
        )
      },
    )
  },
)
