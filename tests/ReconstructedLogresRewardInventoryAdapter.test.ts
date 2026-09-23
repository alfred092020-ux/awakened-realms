import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  ReconstructedLogresBattleResolutionFlow,
} from '../src/game/logres/battle/ReconstructedLogresBattleResolutionFlow'

import {
  applyReconstructedLogresBattleRewardGrant,
  LOGRES_RECONSTRUCTED_REWARD_INVENTORY_ADAPTER_PROVENANCE,
} from '../src/game/logres/battle/ReconstructedLogresRewardInventoryAdapter'

import {
  createReconstructedLogresInventory,
} from '../src/game/logres/server/LogresInventoryAuthority'

function rewardReadyFlow(
  rewardKey:
    | string
    | null =
      'tutorial-reward',
) {
  const flow =
    new ReconstructedLogresBattleResolutionFlow(
      'battle-system-1',
    )

  flow.recordResult({
    resultRef:
      null,
    rawOutcomeCode:
      null,
  })

  flow.markResultPresented()

  flow.recordRewardStage({
    rewardKey,
    originalRewardRef:
      null,
    inventoryProjectionRef:
      'projection-1',
  })

  return flow
}

describe(
  'reconstructed battle reward inventory adapter',
  () => {
    it(
      'persists the active reward through inventory authority without advancing presentation state',
      () => {
        const flow =
          rewardReadyFlow()

        const result =
          applyReconstructedLogresBattleRewardGrant(
            flow,
            createReconstructedLogresInventory(),
            {
              rewardKey:
                'tutorial-reward',
              grantKey:
                'victory-grant-1',
              entries: [
                {
                  itemKey:
                    'tutorial-item',
                  originalItemId:
                    null,
                  quantity:
                    1,
                },
              ],
            },
          )

        expect(
          result,
        ).toMatchObject({
          provenance:
            LOGRES_RECONSTRUCTED_REWARD_INVENTORY_ADAPTER_PROVENANCE,
          rewardKey:
            'tutorial-reward',
          originalRewardRef:
            null,
          inventoryProjectionRef:
            'projection-1',
          applied:
            true,
        })

        expect(
          result.state.entries,
        ).toEqual([
          {
            itemKey:
              'tutorial-item',
            originalItemId:
              null,
            quantity:
              1,
            grantKey:
              'victory-grant-1',
          },
        ])

        expect(
          flow.snapshot()
            .phase,
        ).toBe(
          'reward-ready',
        )
      },
    )

    it(
      'keeps duplicate delivery idempotent through the inventory grant key',
      () => {
        const flow =
          rewardReadyFlow()

        const first =
          applyReconstructedLogresBattleRewardGrant(
            flow,
            createReconstructedLogresInventory(),
            {
              rewardKey:
                'tutorial-reward',
              grantKey:
                'same-grant',
              entries: [
                {
                  itemKey:
                    'item-a',
                  originalItemId:
                    null,
                  quantity:
                    2,
                },
              ],
            },
          )

        const retry =
          applyReconstructedLogresBattleRewardGrant(
            flow,
            first.state,
            {
              rewardKey:
                'tutorial-reward',
              grantKey:
                'same-grant',
              entries: [
                {
                  itemKey:
                    'different-retry-data',
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
      },
    )

    it(
      'rejects a reward identity mismatch before inventory mutation',
      () => {
        const flow =
          rewardReadyFlow(
            'reward-a',
          )

        const inventory =
          createReconstructedLogresInventory()

        expect(
          () =>
            applyReconstructedLogresBattleRewardGrant(
              flow,
              inventory,
              {
                rewardKey:
                  'reward-b',
                grantKey:
                  'grant-b',
                entries: [
                  {
                    itemKey:
                      'item-b',
                    originalItemId:
                      null,
                    quantity:
                      1,
                  },
                ],
              },
            ),
        ).toThrow(
          'does not match the active reward stage',
        )

        expect(
          inventory.revision,
        ).toBe(
          0,
        )
      },
    )

    it(
      'supports a genuinely unresolved reward identity without inventing one',
      () => {
        const flow =
          rewardReadyFlow(
            null,
          )

        const result =
          applyReconstructedLogresBattleRewardGrant(
            flow,
            createReconstructedLogresInventory(),
            {
              rewardKey:
                null,
              grantKey:
                'unknown-reward-grant',
              entries:
                [],
            },
          )

        expect(
          result.rewardKey,
        ).toBeNull()

        expect(
          result.applied,
        ).toBe(
          true,
        )
      },
    )

    it(
      'rejects inventory persistence before the battle flow reaches reward-ready',
      () => {
        const flow =
          new ReconstructedLogresBattleResolutionFlow(
            null,
          )

        expect(
          () =>
            applyReconstructedLogresBattleRewardGrant(
              flow,
              createReconstructedLogresInventory(),
              {
                rewardKey:
                  null,
                grantKey:
                  'too-early',
                entries:
                  [],
              },
            ),
        ).toThrow(
          'requires reward-ready phase',
        )
      },
    )

    it(
      'delegates malformed grant rejection to inventory authority without changing battle phase',
      () => {
        const flow =
          rewardReadyFlow()

        expect(
          () =>
            applyReconstructedLogresBattleRewardGrant(
              flow,
              createReconstructedLogresInventory(),
              {
                rewardKey:
                  'tutorial-reward',
                grantKey:
                  'bad-quantity',
                entries: [
                  {
                    itemKey:
                      'bad',
                    originalItemId:
                      null,
                    quantity:
                      0,
                  },
                ],
              },
            ),
        ).toThrow(
          'positive safe integer',
        )

        expect(
          flow.snapshot()
            .phase,
        ).toBe(
          'reward-ready',
        )
      },
    )
  },
)
