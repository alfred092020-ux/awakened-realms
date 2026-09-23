import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  applyReconstructedLogresInventoryGrant,
  createReconstructedLogresInventory,
  LOGRES_RECONSTRUCTED_INVENTORY_PROVENANCE,
} from '../src/game/logres/server/LogresInventoryAuthority'

describe(
  'reconstructed Logres inventory authority',
  () => {
    it(
      'starts empty without inventing original capacity or item data',
      () => {
        const state =
          createReconstructedLogresInventory()

        expect(
          state,
        ).toEqual({
          provenance:
            'RECONSTRUCTED',
          revision:
            0,
          entries:
            [],
          appliedGrantKeys:
            [],
        })

        expect(
          state.provenance,
        ).toBe(
          LOGRES_RECONSTRUCTED_INVENTORY_PROVENANCE,
        )
      },
    )
    it(
      'applies an authoritative reward grant as an immutable ledger entry',
      () => {
        const sourceEntries = [
          {
            itemKey:
              'reward-line-a',
            originalItemId:
              null,
            quantity:
              2,
          },
        ]

        const result =
          applyReconstructedLogresInventoryGrant(
            createReconstructedLogresInventory(),
            {
              grantKey:
                'victory-grant-1',
              entries:
                sourceEntries,
            },
          )

        sourceEntries[0]!
          .quantity =
            99

        expect(
          result.applied,
        ).toBe(
          true,
        )

        expect(
          result.state,
        ).toEqual({
          provenance:
            'RECONSTRUCTED',
          revision:
            1,
          entries: [
            {
              itemKey:
                'reward-line-a',
              originalItemId:
                null,
              quantity:
                2,
              grantKey:
                'victory-grant-1',
            },
          ],
          appliedGrantKeys: [
            'victory-grant-1',
          ],
        })
        expect(
          Object.isFrozen(
            result.state,
          ),
        ).toBe(
          true,
        )

        expect(
          Object.isFrozen(
            result.state.entries,
          ),
        ).toBe(
          true,
        )

        expect(
          Object.isFrozen(
            result.state.entries[0],
          ),
        ).toBe(
          true,
        )
      },
    )

    it(
      'treats a repeated replacement-server grant key as an idempotent retry',
      () => {
        const first =
          applyReconstructedLogresInventoryGrant(
            createReconstructedLogresInventory(),
            {
              grantKey:
                'same-grant',
              entries: [
                {
                  itemKey:
                    'local-item',
                  originalItemId:
                    null,
                  quantity:
                    1,
                },
              ],
            },
          )

        const retry =
          applyReconstructedLogresInventoryGrant(
            first.state,
            {
              grantKey:
                'same-grant',
              entries: [
                {
                  itemKey:
                    'different-retry-payload',
                  originalItemId:
                    null,
                  quantity:
                    999,
                },
              ],
            },
          )
        expect(
          retry.applied,
        ).toBe(
          false,
        )

        expect(
          retry.state,
        ).toBe(
          first.state,
        )

        expect(
          retry.state.revision,
        ).toBe(
          1,
        )

        expect(
          retry.state.entries,
        ).toHaveLength(
          1,
        )
      },
    )

    it.each([
      {
        input: {
          grantKey:
            '',
          entries:
            [],
        },
        message:
          'grantKey',
      },
      {
        input: {
          grantKey:
            'bad-quantity',
          entries: [
            {
              itemKey:
                'item',
              originalItemId:
                null,
              quantity:
                0,
            },
          ],
        },
        message:
          'positive safe integer',
      },
      {
        input: {
          grantKey:
            'duplicate-lines',
          entries: [
            {
              itemKey:
                'same',
              originalItemId:
                null,
              quantity:
                1,
            },
            {
              itemKey:
                'same',
              originalItemId:
                null,
              quantity:
                2,
            },
          ],
        },
        message:
          'itemKey entries must be unique',
      },
      {
        input: {
          grantKey:
            'bad-original-id',
          entries: [
            {
              itemKey:
                'item',
              originalItemId:
                '   ',
              quantity:
                1,
            },
          ],
        },
        message:
          'originalItemId',
      },
    ])(
      'rejects malformed reconstruction-owned grant data',
      ({
        input,
        message,
      }) => {
        expect(
          () =>
            applyReconstructedLogresInventoryGrant(
              createReconstructedLogresInventory(),
              input,
            ),
        ).toThrow(
          message,
        )
      },
    )
  },
)
