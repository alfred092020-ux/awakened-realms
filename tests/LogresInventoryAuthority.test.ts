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


import {
  LOGRES_ITEM_EQUIPMENT_EVIDENCE,
  LogresItemEquipmentAuthority,
} from '../src/game/logres/systems/LogresItemEquipmentRuntime'

describe(
  'reconstructed Logres item/equipment gameplay authority',
  () => {
    it('preserves recovered server item projection authority', () => {
      expect(LOGRES_ITEM_EQUIPMENT_EVIDENCE.itemMoveRequest.name)
        .toBe('C_GMCL_ITEM_MOVE_REQ')
      expect(LOGRES_ITEM_EQUIPMENT_EVIDENCE.itemProjection.name)
        .toBe('S_GMCL_ITEM_INFO')
      expect(LOGRES_ITEM_EQUIPMENT_EVIDENCE.slotPolicy)
        .toContain('reconstruction-local')
    })

    it('extends reward inventory with equip and unequip authority', () => {
      const authority = new LogresItemEquipmentAuthority()
      const rewarded = authority.applyReward({
        grantKey: 'battle-1',
        entries: [{
          itemKey: 'weapon-drop',
          originalItemId: null,
          quantity: 1,
        }],
      })
      expect(rewarded.inventory.entries).toHaveLength(1)

      const equipped = authority.equip(
        'main-weapon',
        { grantKey: 'battle-1', itemKey: 'weapon-drop' },
        'equip-1',
      )
      expect(equipped.equippedBySlot['main-weapon']).toEqual({
        grantKey: 'battle-1',
        itemKey: 'weapon-drop',
      })

      const unequipped = authority.unequip('main-weapon', 'unequip-1')
      expect(unequipped.equippedBySlot['main-weapon']).toBeUndefined()
    })

    it('keeps reward and equipment mutations idempotent', () => {
      const authority = new LogresItemEquipmentAuthority()
      const firstReward = authority.applyReward({
        grantKey: 'same-reward',
        entries: [{
          itemKey: 'weapon',
          originalItemId: null,
          quantity: 1,
        }],
      })
      const retryReward = authority.applyReward({
        grantKey: 'same-reward',
        entries: [{
          itemKey: 'different',
          originalItemId: null,
          quantity: 99,
        }],
      })
      expect(retryReward).toEqual(firstReward)

      const firstEquip = authority.equip(
        'main',
        { grantKey: 'same-reward', itemKey: 'weapon' },
        'same-equip',
      )
      const retryEquip = authority.equip(
        'main',
        { grantKey: 'same-reward', itemKey: 'weapon' },
        'same-equip',
      )
      expect(retryEquip).toEqual(firstEquip)
    })

    it('rejects equipment references not present in inventory', () => {
      const authority = new LogresItemEquipmentAuthority()
      expect(() =>
        authority.equip(
          'main',
          { grantKey: 'missing', itemKey: 'missing' },
          'equip-missing',
        ),
      ).toThrow('authoritative inventory')
    })
  },
)
