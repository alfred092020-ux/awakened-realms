import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  logresMapInfoHeight,
  logresMultiIdFromComponents,
  parseLogresMapInfoTable,
} from '../src/game/logres/field/LogresMapInfoBinary'

function tableFixture(
  magic: string,
  recordSize: number,
  records:
    readonly {
      components:
        readonly [
          number,
          number,
          number,
        ]
      height:
        number
    }[],
): Uint8Array {
  const data =
    new Uint8Array(
      0x14 +
      recordSize *
        records.length,
    )

  for (
    let index = 0;
    index < magic.length;
    index += 1
  ) {
    data[
      index
    ] =
      magic.charCodeAt(
        index,
      )
  }

  const view =
    new DataView(
      data.buffer,
    )

  view.setUint32(
    0x10,
    (
      records.length <<
        16
    ) |
      10001,
    true,
  )

  records.forEach(
    (
      record,
      recordIndex,
    ) => {
      const offset =
        0x14 +
        recordIndex *
          recordSize

      const [
        component0,
        component1,
        component2,
      ] =
        record.components

      data[
        offset
      ] =
        component0

      data[
        offset +
          1
      ] =
        component1

      view.setUint16(
        offset +
          2,
        component2,
        true,
      )

      data[
        offset +
          0x18
      ] =
        record.height
    },
  )

  return data
}

describe(
  'Logres map-info fixed-record decoder',
  () => {
    it(
      'reconstructs native MultiID packing',
      () => {
        expect(
          logresMultiIdFromComponents(
            2,
            1,
            253,
          ),
        ).toBe(
          0x020100fd,
        )
      },
    )

    it(
      'decodes chip record count, packed id, and native height byte',
      () => {
        const table =
          parseLogresMapInfoTable(
            tableFixture(
              'MAP_CHIP',
              0x28,
              [
                {
                  components:
                    [2, 1, 253],
                  height:
                    2,
                },
                {
                  components:
                    [2, 1, 0],
                  height:
                    1,
                },
              ],
            ),
            'chip',
          )

        expect(
          table.formatWordLow16,
        ).toBe(
          10001,
        )

        expect(
          table.recordCount,
        ).toBe(
          2,
        )

        expect(
          table.records[0],
        ).toEqual({
          packedId:
            0x020100fd,
          component0:
            2,
          component1:
            1,
          component2:
            253,
          height:
            2,
          recordIndex:
            0,
        })

        expect(
          logresMapInfoHeight(
            table,
            0x020100fd,
          ),
        ).toBe(
          2,
        )
      },
    )

    it(
      'uses the distinct original object record size',
      () => {
        const table =
          parseLogresMapInfoTable(
            tableFixture(
              'MAP_OBJECT',
              0x2a,
              [
                {
                  components:
                    [2, 4, 100],
                  height:
                    10,
                },
              ],
            ),
            'object',
          )

        expect(
          table.records,
        ).toEqual([
          {
            packedId:
              0x02040064,
            component0:
              2,
            component1:
              4,
            component2:
              100,
            height:
              10,
            recordIndex:
              0,
          },
        ])
      },
    )

    it.each([
      {
        label:
          'bad magic',
        mutate:
          (
            data:
              Uint8Array,
          ) => {
            data[0] = 0
          },
        message:
          'Unexpected Logres map-info magic',
      },
      {
        label:
          'non-zero magic padding',
        mutate:
          (
            data:
              Uint8Array,
          ) => {
            data[9] = 1
          },
        message:
          'magic padding is non-zero',
      },
      {
        label:
          'truncated record',
        mutate:
          (
            data:
              Uint8Array,
          ) => {
            data[
              data.length -
                1
            ] =
              0
          },
        message:
          null,
      },
    ])(
      'rejects malformed fixed-record envelopes: $label',
      ({
        mutate,
        message,
      }) => {
        const original =
          tableFixture(
            'MAP_CHIP',
            0x28,
            [
              {
                components:
                  [2, 1, 0],
                height:
                  1,
              },
            ],
          )

        if (
          message ===
          null
        ) {
          expect(
            () =>
              parseLogresMapInfoTable(
                original.subarray(
                  0,
                  original.length -
                    1,
                ),
                'chip',
              ),
          ).toThrow(
            'length mismatch',
          )

          return
        }

        mutate(
          original,
        )

        expect(
          () =>
            parseLogresMapInfoTable(
              original,
              'chip',
            ),
        ).toThrow(
          message,
        )
      },
    )
  },
)
